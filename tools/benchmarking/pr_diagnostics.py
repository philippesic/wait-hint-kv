from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from tools.benchmarking.pr_events import reconcile_events, request_sources
from tools.benchmarking.pr_metrics import measure_cell
from tools.benchmarking.pr_statistics import quantile
from tools.benchmarking.probe import digest_file


def distribution(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "mean": statistics.mean(values) if values else None,
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
        "p95": quantile(sorted(values), 0.95) if values else None,
    }


def resource_details(samples: list[dict[str, Any]], cell_start: int) -> dict[str, Any]:
    counters: dict[str, list[dict[str, Any]]] = {}
    gpu: dict[str, list[float]] = {
        key: []
        for key in (
            "memory_used_mib",
            "utilization_percent",
            "temperature_c",
            "power_w",
        )
    }
    for sample in samples:
        for pid, process in sample["processes"].items():
            identity = f"{pid}:{process['start_ticks']}"
            counters.setdefault(identity, []).append(process)
        if "gpu" in sample:
            for row in csv.reader(
                sample["gpu"]["devices"].splitlines(), skipinitialspace=True
            ):
                if len(row) != 8:
                    raise ValueError("unexpected GPU device observation")
                for key, value in zip(gpu, row[4:], strict=True):
                    if value not in {"N/A", "[N/A]", "[Not Supported]"}:
                        gpu[key].append(float(value))
    faults = []
    for identity, rows in sorted(counters.items()):
        faults.append(
            {
                "process_identity": identity,
                "minor_faults_observed_delta": max(r["minor_faults"] for r in rows)
                - min(r["minor_faults"] for r in rows),
                "major_faults_observed_delta": max(r["major_faults"] for r in rows)
                - min(r["major_faults"] for r in rows),
            }
        )
    startup = [s for s in samples if s["monotonic_ns"] < cell_start]
    return {
        "process_faults": faults,
        "minor_faults_observed_delta": sum(
            p["minor_faults_observed_delta"] for p in faults
        ),
        "major_faults_observed_delta": sum(
            p["major_faults_observed_delta"] for p in faults
        ),
        "host_major_faults_delta": samples[-1]["host_major_faults"]
        - samples[0]["host_major_faults"],
        "startup_peak_pss_bytes": max((s["pss_bytes"] for s in startup), default=None),
        "full_job_peak_pss_bytes": max(s["pss_bytes"] for s in samples),
        "startup_peak_summed_rss_bytes": max(
            (sum(p["rss_bytes"] for p in s["processes"].values()) for s in startup),
            default=None,
        ),
        "full_job_peak_summed_rss_bytes": max(
            sum(p["rss_bytes"] for p in s["processes"].values()) for s in samples
        ),
        "gpu_sample_distributions": {
            key: distribution(values) for key, values in gpu.items()
        },
        "scope": "Observed process-counter deltas by PID/start identity; startup includes loading/staging. First samples can miss early faults, vanished processes can be missed, RSS double-counts shared pages, GPU values include graphics and are sample means rather than time integrals. GPU clocks and Windows process activity were not captured.",
    }


def lease_activity(
    events: list[dict[str, Any]], schedule: dict[str, Any]
) -> dict[str, Any]:
    sessions = {s["session_id"]: s for s in schedule["sessions"]}
    leases: dict[tuple[str, int], dict[str, Any]] = {}
    previous: set[tuple[str, int]] = set()
    for event in events:
        current = set()
        for owner, lease in event["leases"].items():
            identity = (owner, lease["generation"])
            current.add(identity)
            session_id = json.loads(owner)[1]
            session = sessions[session_id]
            if identity not in leases:
                leases[identity] = {
                    "owner": owner,
                    "generation": lease["generation"],
                    "session_id": session_id,
                    "first_observed_ns": event["monotonic_ns"],
                    "observed_segments": [],
                    "deadline_ns": lease["deadline_ns"],
                    "maximum_observed_keys": 0,
                    "final_recorded_turn": lease["generation"] == len(session["turns"]),
                    "has_later_recorded_return": lease["generation"]
                    < len(session["turns"]),
                    "ending": session["ending"],
                }
            row = leases[identity]
            if row["deadline_ns"] != lease["deadline_ns"]:
                raise ValueError("lease generation changed its deadline")
            if identity not in previous:
                row["observed_segments"].append(
                    {
                        "first_observed_ns": event["monotonic_ns"],
                        "first_absent_ns": None,
                    }
                )
            row["observed_segments"][-1]["last_observed_ns"] = event["monotonic_ns"]
            row["last_observed_ns"] = event["monotonic_ns"]
            row["maximum_observed_keys"] = max(
                row["maximum_observed_keys"], len(lease["keys"])
            )
        for identity in previous - current:
            leases[identity]["observed_segments"][-1]["first_absent_ns"] = event[
                "monotonic_ns"
            ]
        previous = current
    rows = list(leases.values())
    return {
        "observed_leases": rows,
        "lease_count": len(rows),
        "sessions_with_observed_holds": len({r["session_id"] for r in rows}),
        "final_turn_lease_count": sum(r["final_recorded_turn"] for r in rows),
        "final_turn_leases_by_ending": dict(
            Counter(str(r["ending"]) for r in rows if r["final_recorded_turn"])
        ),
        "peak_physical_held_chunks": max(
            (e["physical_held_chunks"] for e in events), default=0
        ),
        "peak_observed_metadata_bytes": max(
            (e["metadata_bytes"] for e in events), default=0
        ),
        "last_outcome_counters": events[-1]["outcomes"] if events else {},
        "yield_count": events[-1]["yields"] if events else 0,
        "scope": "Observed owner/generation lifetimes; snapshots bound appearance/disappearance and do not establish exact release or expiry times. Final-turn holds have no later recorded return, including truncated ends. return_release is an observation/attempt counter, not a count of held leases released. Metadata-only mutations can be missed by snapshot deduplication.",
    }


def first_turn_reuse(
    observed: dict[str, Any], requests: list[dict[str, Any]]
) -> dict[str, Any]:
    rows = []
    alignment = observed["eligibility_alignment_tokens"]
    for row in requests:
        if row["cohort"] != "first_turn":
            continue
        identity = observed["external_request_ids"].get(row["request_id"])
        source = None
        if identity is not None:
            request = observed["requests"][identity]
            source = request_sources(
                request,
                max(0, request["prompt_tokens"] - 1) // alignment * alignment,
                row["outcome"] == "complete",
                set(observed["completed_jobs"]),
                set(observed["failed_jobs"]),
            )
        rows.append(
            {
                "request_id": row["request_id"],
                "session_id": row["session_id"],
                "task": row["task"],
                "outcome": row["outcome"],
                "sources": source,
            }
        )
    fields = (
        "eligible_tokens",
        "gpu_reused_tokens",
        "cpu_reused_tokens",
        "recomputed_tokens",
        "unobserved_tokens",
    )
    return {
        "requests": rows,
        "totals": {
            field: sum(r["sources"][field] for r in rows if r["sources"] is not None)
            for field in fields
        },
        "missing_native_requests": sum(r["sources"] is None for r in rows),
        "scope": "Full reusable boundary on each session's first turn, which has no previous request in that session: observed reuse is cross-session. This does not exhaust shared reuse on later turns. Primary within-session return eligibility is unchanged.",
    }


def diagnose_cell(directory: Path) -> dict[str, Any]:
    schedule = json.loads((directory / "schedule.json").read_text())
    report = json.loads((directory / "client/report.json").read_text())
    metrics = measure_cell(schedule, directory / "client", directory / "events")
    observed = reconcile_events(directory / "events")
    samples = [
        json.loads(line)
        for line in (directory / "resources.jsonl").read_text().splitlines()
    ]
    captures = {
        path.stem: json.loads(path.read_text())
        for path in (directory / "client/requests").glob("*.json")
    }
    cohorts = {}
    latency_fields = (
        "ttft_scheduled_ns",
        "ttft_submitted_ns",
        "client_mean_token_itl_ns",
        "client_mean_chunk_itl_ns",
        "engine_mean_token_itl_ns",
        "submission_lateness_ns",
    )
    source_fields = (
        "eligible_tokens",
        "gpu_reused_tokens",
        "cpu_reused_tokens",
        "recomputed_tokens",
        "unobserved_tokens",
        "prompt_compute_tokens",
        "repeated_prompt_compute_tokens",
    )
    for cohort in ("first_turn", "hinted_return", "unhinted_return", "one_shot"):
        rows = [r for r in metrics["requests"] if r["cohort"] == cohort]
        complete = [
            captures[r["request_id"]] for r in rows if r["outcome"] == "complete"
        ]
        cohorts[cohort] = {
            "planned_requests": len(rows),
            "complete_requests": len(complete),
            "outcomes": dict(Counter(r["outcome"] for r in rows)),
            "latency_ns": {
                field: distribution(
                    [float(c[field]) for c in complete if c[field] is not None]
                )
                for field in latency_fields
            },
            "output_tokens": sum(len(c["token_ids"]) for c in complete),
            "requested_output_tokens": sum(
                captures[r["request_id"]]["expected_tokens"]
                for r in rows
                if r["request_id"] in captures
            ),
            "coalesced_chunks": sum(c["coalesced_chunks"] for c in complete),
            "sources": {
                field: sum(
                    r["sources"][field] for r in rows if r["sources"] is not None
                )
                for field in source_fields
            },
        }
    sessions = [s for s in report["sessions"] if not s["one_shot"]]
    return {
        "schema": "pr-cell-diagnostics-v1",
        "input_sha256": {
            name: digest_file(directory / name)
            for name in ("admission.json", "terminal.json", "schedule.json")
        },
        "analysis_source_sha256": {
            name: digest_file(Path(__file__).parent / name)
            for name in (
                "pr_diagnostics.py",
                "pr_events.py",
                "pr_metrics.py",
                "pr_statistics.py",
                "resources.py",
                "streaming.py",
            )
        },
        "model": metrics["model"],
        "arm": metrics["arm"],
        "seed": metrics["seed"],
        "cohorts": cohorts,
        "session_completion": {
            "planned": len(sessions),
            "outcomes": dict(Counter(s["outcome"] for s in sessions)),
            "all_termination_seconds": distribution(
                [(s["ended_ns"] - s["scheduled_arrival_ns"]) / 1e9 for s in sessions]
            ),
            "complete_only_seconds": distribution(
                [
                    (s["ended_ns"] - s["scheduled_arrival_ns"]) / 1e9
                    for s in sessions
                    if s["outcome"] == "complete"
                ]
            ),
        },
        "first_turn_cross_session_reuse": first_turn_reuse(
            observed, metrics["requests"]
        ),
        "holds": lease_activity(observed["policy_events"], schedule),
        "hint_messages": report["hints"],
        "trace_endings": dict(Counter(str(s["ending"]) for s in schedule["sessions"])),
        "refusal_capacity": observed["refusal_capacity"],
        "refusal_scope": "Instantaneous native capacity replay ignores holds and excludes in-flight/protected offered keys. No direct obstruction does not rule out indirect cache/scheduling effects; paired refusal counts remain outcomes. Frozen screen has no store-frequency admission threshold.",
        "store_refusals": metrics["store_refusals"],
        "store_failures": metrics["store_failures"],
        "failed_transfer_jobs": metrics["failed_transfer_jobs"],
        "transfer": metrics["transfer"],
        "eviction_count": len(metrics["evictions"]),
        "working_set": metrics["working_set"],
        "resources": metrics["resources"],
        "resource_details": resource_details(samples, report["started_ns"]),
        "scope": "Derived diagnostics, preserving primary metrics and raw records. Latency descriptions are unweighted and complete-response-only, with all failure denominators alongside them; inferential comparisons use the frozen post-stratified estimator.",
    }

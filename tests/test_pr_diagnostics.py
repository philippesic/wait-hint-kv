from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tools.benchmarking.pr_diagnostics import (
    first_turn_reuse,
    lease_activity,
    resource_details,
)
from tools.benchmarking.pr_events import reconcile_events, refusal_capacity
from tools.benchmarking.pr_statistics import first_task_occurrences
from wait_hint_offload.evidence_events import EventJournal


def test_refusal_capacity_distinguishes_pending_load_and_offer_protection() -> None:
    resident = {
        "a": {"ready": True, "loads": 0},
        "b": {"ready": True, "loads": 1},
        "c": {"ready": False, "loads": 0},
    }
    original = copy.deepcopy(resident)
    assert refusal_capacity(["new"], resident, 3)["native_capacity_would_fit"]
    protected = refusal_capacity(["a", "new"], resident, 3)
    assert protected["required_evictions"] == 1
    assert protected["reason"] == "offered keys protect too many idle chunks"
    busy = refusal_capacity(["new", "next"], resident, 3)
    assert busy["reason"] == "insufficient idle chunks"
    assert refusal_capacity(["a", "new"], resident, 4)["native_capacity_would_fit"]
    assert resident == original
    with pytest.raises(ValueError, match="capacity"):
        refusal_capacity([], resident, 2)


def test_refusal_replay_tracks_store_completion_and_load_references(
    tmp_path: Path,
) -> None:
    scheduler = EventJournal(tmp_path, "scheduler")
    worker = EventJournal(tmp_path, "worker")
    a, b, c = [{"key": key, "group": 0} for key in ("aa", "bb", "cc")]
    scheduler.emit("cpu_config", {"num_chunks": 2, "kv_bytes_per_chunk": 32})
    scheduler.emit(
        "group_config",
        {
            "tokens_per_hash": 4,
            "partial_tail": False,
            "groups": [{"tokens_per_chunk": 4}],
        },
    )
    scheduler.emit(
        "prepare_store",
        {
            "request_id": "r",
            "accepted": True,
            "offered": [a, b],
            "stored": [a, b],
            "evicted": [],
            "cpu_block_ids": [0, 1],
        },
    )
    refusal = {
        "request_id": "r",
        "accepted": False,
        "offered": [c],
        "stored": [],
        "evicted": [],
        "cpu_block_ids": [],
    }
    scheduler.emit("prepare_store", refusal)
    scheduler.emit(
        "complete_store",
        {"request_id": "r", "keys": [a], "success": True, "ready": ["aa"]},
    )
    scheduler.emit(
        "prepare_load", {"request_id": "r", "keys": [a], "cpu_block_ids": [0]}
    )
    scheduler.emit("prepare_store", refusal)
    scheduler.emit("complete_load", {"request_id": "r", "keys": [a]})
    scheduler.emit("prepare_store", refusal | {"offered": [a, c]})
    scheduler.emit("prepare_store", refusal)
    scheduler.close()
    worker.close()
    result = reconcile_events(tmp_path)
    assert result["store_refusals"] == 4
    assert [r["native_capacity_would_fit"] for r in result["refusal_capacity"]] == [
        False,
        False,
        False,
        True,
    ]
    assert [r["idle_chunks"] for r in result["refusal_capacity"]] == [0, 0, 1, 1]
    assert all(r["chunks"] == 2 for r in result["occupancy"])


def test_first_task_sensitivity_keeps_failed_first_occurrence_and_one_shots() -> None:
    def row(
        session: str, task: str | None, request_outcome: str = "complete"
    ) -> dict[str, Any]:
        return {
            "request_id": session + "-t0",
            "session_id": session,
            "task": task,
            "stratum": "s",
            "cohort": "one_shot" if task is None else "first_turn",
            "outcome": request_outcome,
        }

    cells: list[dict[str, Any]] = [
        {
            "model": "D8",
            "partition": "pilot",
            "seed": 1,
            "arm": "A2",
            "requests": [row("b", "x"), row("a", "x", "error"), row("shot1", None)],
        },
        {
            "model": "D8",
            "partition": "pilot",
            "seed": 2,
            "arm": "A2",
            "requests": [row("c", "x"), row("d", "y"), row("shot2", None)],
        },
    ]
    treatment: list[dict[str, Any]] = [copy.deepcopy(c) | {"arm": "A4t"} for c in cells]
    original = copy.deepcopy(cells)
    groups, audit = first_task_occurrences([cells, treatment])
    assert [[r["session_id"] for r in c["requests"]] for c in groups[0]] == [
        ["a", "shot1"],
        ["d", "shot2"],
    ]
    assert groups[0][0]["requests"][0]["outcome"] == "error"
    assert audit["retained_unique_tasks"] == 2
    assert len(audit["excluded_sessions"]) == 2
    assert cells == original
    treatment[1]["requests"][0]["task"] = "different"
    with pytest.raises(ValueError, match="identities"):
        first_task_occurrences([cells, treatment])
    with pytest.raises(ValueError, match="ascending"):
        first_task_occurrences([list(reversed(cells))])


def test_lease_report_counts_generations_and_observed_segments_not_release_attempts() -> (
    None
):
    owner = json.dumps(["model", "s", "seed"])

    def event(timestamp: int, generation: int | None) -> dict[str, Any]:
        return {
            "monotonic_ns": timestamp,
            "leases": {}
            if generation is None
            else {
                owner: {
                    "generation": generation,
                    "deadline_ns": generation * 100,
                    "keys": [{"key": "aa"}],
                }
            },
            "physical_held_chunks": int(generation is not None),
            "metadata_bytes": 16,
            "outcomes": {"return_release": 100},
            "yields": 1,
        }

    events = [
        event(10, 1),
        event(20, None),
        event(30, 1),
        event(40, 2),
        event(50, None),
    ]
    result = lease_activity(
        events,
        {"sessions": [{"session_id": "s", "turns": [{}, {}], "ending": "truncated"}]},
    )
    assert result["lease_count"] == 2
    assert result["final_turn_lease_count"] == 1
    assert result["final_turn_leases_by_ending"] == {"truncated": 1}
    assert len(result["observed_leases"][0]["observed_segments"]) == 2
    assert result["observed_leases"][0]["observed_segments"][0]["first_absent_ns"] == 20
    events[2]["leases"][owner]["deadline_ns"] += 1
    with pytest.raises(ValueError, match="deadline"):
        lease_activity(
            events,
            {
                "sessions": [
                    {"session_id": "s", "turns": [{}, {}], "ending": "truncated"}
                ]
            },
        )


def test_first_turn_reuse_uses_full_boundary_without_changing_primary_eligibility() -> (
    None
):
    request = {
        "prompt_tokens": 16,
        "scheduled": [{"start": 8, "tokens": 8}],
        "allocations": [
            {
                "cpu_tokens": 4,
                "supplied_gpu_tokens": 4,
                "load_jobs": [1],
                "load_ranges": [{"start": 4, "end": 8, "group": 0}],
            }
        ],
    }
    observed = {
        "eligibility_alignment_tokens": 4,
        "external_request_ids": {"c": "r"},
        "requests": {"r": request},
        "completed_jobs": ["1"],
        "failed_jobs": [],
    }
    row = {
        "request_id": "c",
        "session_id": "s",
        "task": "t",
        "cohort": "first_turn",
        "outcome": "complete",
        "eligible_tokens": 0,
    }
    result = first_turn_reuse(observed, [row])
    assert result["totals"] == {
        "eligible_tokens": 12,
        "gpu_reused_tokens": 4,
        "cpu_reused_tokens": 4,
        "recomputed_tokens": 4,
        "unobserved_tokens": 0,
    }
    assert row["eligible_tokens"] == 0


def test_resource_report_separates_reused_pids_and_startup_peaks() -> None:
    samples = []
    for timestamp, start, minor, major, pss in (
        (1, 10, 100, 1, 200),
        (2, 10, 120, 3, 300),
        (3, 20, 1, 0, 100),
        (4, 20, 4, 1, 150),
    ):
        samples.append(
            {
                "monotonic_ns": timestamp,
                "host_major_faults": timestamp * 10,
                "pss_bytes": pss,
                "processes": {
                    "7": {
                        "start_ticks": start,
                        "minor_faults": minor,
                        "major_faults": major,
                        "rss_bytes": pss * 2,
                    }
                },
                "gpu": {"devices": "0, uuid, gpu, 11264, 1000, 50, 60, 180\n"},
            }
        )
    result = resource_details(samples, 3)
    assert result["minor_faults_observed_delta"] == 23
    assert result["major_faults_observed_delta"] == 3
    assert result["host_major_faults_delta"] == 30
    assert result["startup_peak_pss_bytes"] == 300
    assert result["startup_peak_summed_rss_bytes"] == 600
    assert result["gpu_sample_distributions"]["power_w"]["mean"] == 180

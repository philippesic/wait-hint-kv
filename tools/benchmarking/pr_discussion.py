from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from tools.benchmarking.pr_jobs import run_gpu_job
from tools.benchmarking.pr_metrics import measure_cell
from tools.runtime_verify import write_record

JOB_FIELDS = {
    "name",
    "model",
    "arm",
    "phase",
    "pool_bytes",
    "gpu_blocks",
    "schedule",
    "runtime_python",
    "model_path",
    "seconds",
}


def _log(campaign: Path, event: dict[str, Any]) -> None:
    with (campaign / "driver.jsonl").open("a") as log:
        log.write(json.dumps({"time": time.time()} | event) + "\n")


def _attempts(campaign: Path, name: str) -> list[dict[str, Any]]:
    attempts = []
    for directory in sorted((campaign / "jobs").glob(name + "-a[0-9]*")):
        terminal = directory / "terminal.json"
        if terminal.is_file():
            attempts.append({"name": directory.name} | json.loads(terminal.read_text()))
    return attempts


def _measure(campaign: Path, job: str) -> None:
    output = campaign / "metrics" / (job + ".json")
    if output.exists():
        return
    output.parent.mkdir(exist_ok=True)
    directory = campaign / "jobs" / job
    try:
        metrics = measure_cell(
            json.loads((directory / "schedule.json").read_text()),
            directory / "client",
            directory / "events",
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        _log(
            campaign, {"job": job, "measure_error": f"{type(error).__name__}: {error}"}
        )
        return
    write_record(output, metrics)


def run_manifest(manifest_path: Path, retries: int = 1) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text())
    root = Path(__file__).resolve().parents[2]
    campaign = root / "artifacts/runs" / manifest["campaign"]
    (campaign / "jobs").mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"complete": [], "failed": [], "stopped": None}
    for job in manifest["jobs"]:
        if set(job) != JOB_FIELDS:
            raise ValueError("closed discussion job required")
        if (campaign / "STOP").exists():
            summary["stopped"] = {"reason": "STOP file present"}
            _log(campaign, {"stopped": "STOP file present"})
            return summary
        attempts = _attempts(campaign, job["name"])
        done = [item for item in attempts if item["status"] == "client_complete"]
        while not done and len(attempts) <= retries:
            base = f"{job['name']}-a{len(attempts) + 1}"
            waits = 0
            while True:
                attempt = base if not waits else f"{base}-w{waits}"
                try:
                    terminal = run_gpu_job(
                        campaign,
                        attempt,
                        Path(job["runtime_python"]),
                        Path(job["model_path"]),
                        job["model"],
                        job["arm"],
                        job["phase"],
                        job["pool_bytes"],
                        job["seconds"],
                        Path(job["schedule"]),
                        job["gpu_blocks"],
                    )
                    break
                except ValueError as error:
                    if "GPU busy" in str(error) and waits < 30:
                        _log(campaign, {"job": attempt, "deferred": str(error)})
                        time.sleep(60)
                        waits += 1
                        continue
                    _log(campaign, {"job": attempt, "refused": str(error)})
                    summary["stopped"] = {"job": attempt, "reason": str(error)}
                    write_record(
                        campaign / f"driver-stop-{int(time.time())}.json", summary
                    )
                    return summary
            _log(campaign, {"job": attempt, "status": terminal["status"]})
            attempts.append({"name": attempt} | terminal)
            if terminal["status"] == "interrupted" or "GPU block override" in str(
                terminal["detail"]
            ):
                summary["stopped"] = {"job": attempt, "reason": terminal["status"]}
                return summary
            done = [item for item in attempts if item["status"] == "client_complete"]
        if done:
            _measure(campaign, done[0]["name"])
            summary["complete"].append(done[0]["name"])
        else:
            summary["failed"].append(job["name"])
    _log(campaign, {"manifest_complete": str(manifest_path), "summary": summary})
    return summary


HARM = (
    ("hinted_return", "client_itl_ns", "relative_harm"),
    ("unhinted_return", "ttft_ns", "relative_harm"),
    ("unhinted_return", "client_itl_ns", "relative_harm"),
    ("one_shot", "ttft_ns", "relative_harm"),
    ("one_shot", "client_itl_ns", "relative_harm"),
    ("unhinted_return", "recompute", "absolute_change"),
)
BENEFIT = (
    ("hinted_return", "recompute", "absolute_change"),
    ("hinted_return", "ttft_ns", "benefit"),
)


def _cell_key(path: Path, cell: dict[str, Any]) -> tuple[str, str, str, int]:
    workload = "regular"
    if cell.get("schedule_schema") == "pr-pressure-schedule-v1":
        pool = re.search(r"-p(\d+)-", path.name)
        if pool is None:
            raise ValueError(f"pressure metric name lacks a pool level: {path.name}")
        level = int(pool[1])
        if "-A1large" in path.name:
            calibration = json.loads(
                (
                    Path(__file__).resolve().parents[2]
                    / "benchmarks/pr-evidence/pressure"
                    / (cell["model"] + ".json")
                ).read_text()
            )
            level = calibration["pools_bytes"][0] // 1024**2
        workload = f"pressure-p{level}"
    arm = cell["arm"]
    if "-A1rep" in path.name:
        arm = "A1rep"
    elif "-A1large" in path.name:
        arm = "A1large"
    return workload, cell["model"], arm, cell["seed"]


def _verdict(result: dict[str, Any], kind: str, metric: str) -> str:
    interval = result.get("interval")
    if result.get("point") is None or interval is None:
        return "unresolved"
    if kind == "relative_harm" or (kind == "absolute_change" and metric == "recompute"):
        margin = 0.05 if kind == "relative_harm" else 0.02
        if interval[1] <= margin:
            return "not worse"
        if result["point"] > margin:
            return "worse"
        return "unresolved"
    raise ValueError("verdict requires a harm contrast")


def campaign_report(metric_dirs: list[Path]) -> dict[str, Any]:
    from tools.benchmarking.pr_statistics import compare, summarize_cohort

    cells: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    for directory in metric_dirs:
        for path in sorted(directory.glob("*.json")):
            cell = json.loads(path.read_text())
            if cell.get("schema") != "pr-cell-metrics-v1" or cell["partition"] not in {
                "pilot",
                "pressure",
            }:
                continue
            key = _cell_key(path, cell)
            if key in cells:
                raise ValueError(f"duplicate cell {key}")
            cells[key] = cell | {"source_file": str(path)}
    groups = sorted({key[:2] for key in cells})
    report: dict[str, Any] = {"schema": "pr-discussion-report-v1", "groups": {}}
    for workload, model in groups:
        arms = {key[2] for key in cells if key[:2] == (workload, model)}
        comparisons = []
        pairs = [(arm, "A1") for arm in ("A7", "A6", "A5", "A1rep", "A1large")]
        pairs.append(("A7", "A6"))
        for treatment_arm, baseline_arm in pairs:
            if treatment_arm not in arms or baseline_arm not in arms:
                continue
            seeds = sorted(
                key[3]
                for key in cells
                if key[:3] == (workload, model, treatment_arm)
                and (workload, model, baseline_arm, key[3]) in cells
            )
            if not seeds:
                continue
            treatment = [cells[(workload, model, treatment_arm, s)] for s in seeds]
            baseline = [cells[(workload, model, baseline_arm, s)] for s in seeds]
            variants: list[tuple[bool, str | None]] = [(False, None)]
            if workload == "regular":
                variants.append((True, None))
            else:
                variants.append((False, "long"))
            for pool_strata, wait_class in variants:
                for cohort, metric, kind in BENEFIT + HARM:
                    if wait_class and cohort != "hinted_return":
                        continue
                    label = f"{workload}-{model}-{treatment_arm}-{baseline_arm}-{cohort}-{metric}-{kind}-{pool_strata}-{wait_class}"
                    try:
                        result = compare(
                            [
                                summarize_cohort(
                                    cell,
                                    cohort,
                                    metric,
                                    pool_strata=pool_strata,
                                    wait_class=wait_class,
                                )
                                for cell in treatment
                            ],
                            [
                                summarize_cohort(
                                    cell,
                                    cohort,
                                    metric,
                                    pool_strata=pool_strata,
                                    wait_class=wait_class,
                                )
                                for cell in baseline
                            ],
                            kind,
                            label,
                        )
                    except ValueError as error:
                        result = {"point": None, "interval": None, "error": str(error)}
                    entry = {
                        "treatment": treatment_arm,
                        "baseline": baseline_arm,
                        "seeds": seeds,
                        "cohort": cohort,
                        "metric": metric,
                        "contrast": kind,
                        "pooled_strata": pool_strata,
                        "wait_class": wait_class,
                        "point": result.get("point"),
                        "bca": result.get("interval"),
                        "delta": result.get("delta_interval"),
                        "reason": result.get("reason") or result.get("error"),
                        "treatment_value": (result.get("treatment") or {}).get("value"),
                        "baseline_value": (result.get("baseline") or {}).get("value"),
                    }
                    if (cohort, metric, kind) in HARM:
                        entry["verdict"] = _verdict(result, kind, metric)
                    comparisons.append(entry)
        mechanism = {}
        for key, cell in cells.items():
            if key[:2] != (workload, model):
                continue
            hinted = [
                row
                for row in cell["requests"]
                if row["cohort"] == "hinted_return" and row["sources"]
            ]
            outcomes: dict[str, int] = {}
            for event in cell.get("policy_events", []):
                outcomes = event.get("outcomes", outcomes)
            mechanism[f"{key[2]}-{key[3]}"] = {
                "hinted_eligible": sum(row["eligible_tokens"] for row in hinted),
                "hinted_cpu_reused": sum(
                    row["sources"].get("cpu_reused_tokens", 0) for row in hinted
                ),
                "hinted_gpu_reused": sum(
                    row["sources"].get("gpu_reused_tokens", 0) for row in hinted
                ),
                "hinted_recomputed": sum(
                    row["sources"]["recomputed_tokens"] for row in hinted
                ),
                "policy_outcomes": outcomes,
                "store_failures": cell.get("store_failures"),
                "store_refusals": cell.get("store_refusals"),
                "session_failures": cell.get("session_failures"),
                "one_shot_failures": cell.get("one_shot_failures"),
                "working_set_bytes": (cell.get("working_set") or {}).get(
                    "mean_unique_reachable_bytes"
                ),
                "pool_chunks": cell.get("cpu_config", {}).get("num_chunks"),
                "chunk_bytes": cell.get("cpu_config", {}).get("kv_bytes_per_chunk"),
                "source_file": cell["source_file"],
            }
        report["groups"][f"{workload}-{model}"] = {
            "arms": sorted(arms),
            "comparisons": comparisons,
            "mechanism": mechanism,
        }
    return report

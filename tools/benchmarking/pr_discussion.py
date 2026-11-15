from __future__ import annotations

import json
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

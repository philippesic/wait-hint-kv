from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

from tools.benchmarking.pr_agent_mix import ARMS

AGE_BINS = (0.0, 1.0, 5.0, 15.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0, 240.0)
GATE_POINTS = 3.0
BASES: dict[str, dict[str, Any]] = {
    "lru": {
        "oracles": ("oracle-lru", "oracle-gpu-lru"),
        "server": ("lru", "auto-lru", "auto300-lru", "auto-st2-lru", "auto300old-lru"),
    },
    "arc": {
        "oracles": ("oracle-arc", "oracle-gpu-arc"),
        "server": ("arc", "auto-arc", "auto300old-arc"),
    },
}
NAME = re.compile(
    r"^(?P<study>.+)-p(?P<pool>\d+)-(?P<arm>"
    + "|".join(sorted(ARMS, key=len, reverse=True))
    + r")-s(?P<seed>\d+)-a\d+(?:-w\d+)?$"
)


def _share(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = sum(row["eligible_tokens"] for row in rows)
    recomputed = sum(row["sources"]["recomputed_tokens"] for row in rows)
    return {
        "requests": len(rows),
        "eligible_tokens": eligible,
        "recomputed_tokens": recomputed,
        "cpu_reused_tokens": sum(
            row["sources"].get("cpu_reused_tokens", 0) for row in rows
        ),
        "recompute_share": recomputed / eligible if eligible else None,
    }


def _quantiles(values: list[int]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "p50": None, "p90": None}
    ordered = sorted(values)
    return {
        "mean": statistics.fmean(ordered) / 1e9,
        "p50": ordered[len(ordered) // 2] / 1e9,
        "p90": ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))] / 1e9,
    }


def returns(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    previous: dict[str, int] = {}
    rows = []
    for row in sorted(
        metrics["requests"], key=lambda item: (item["session_id"], item["request_id"])
    ):
        ended = previous.get(row["session_id"])
        if row["ended_ns"] is not None:
            previous[row["session_id"]] = row["ended_ns"]
        if (
            row["cohort"] not in {"hinted_return", "unhinted_return"}
            or row["outcome"] != "complete"
            or not row["sources"]
            or row["eligible_tokens"] <= 0
            or ended is None
        ):
            continue
        rows.append(row | {"idle_seconds": (row["scheduled_ns"] - ended) / 1e9})
    return rows


def cell_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    rows = returns(metrics)
    hinted = [row for row in rows if row["cohort"] == "hinted_return"]
    complete = [
        row
        for row in metrics["requests"]
        if row["outcome"] == "complete" and row["ttft_ns"] is not None
    ]
    queue = sum(row.get("queue_ns") or 0 for row in complete)
    ttft = sum(row["ttft_ns"] for row in complete)
    outcomes: dict[str, int] = {}
    for event in metrics.get("policy_events", []):
        outcomes = event.get("outcomes", outcomes)
    return {
        "arm": metrics["arm"],
        "seed": metrics["seed"],
        "opt_in": _share(hinted),
        "non_hinting": _share(
            [row for row in rows if row["cohort"] == "unhinted_return"]
        ),
        "by_wait": {
            wait: _share([row for row in hinted if row["wait_class"] == wait])
            for wait in ("instant", "tool", "long")
        },
        "long_halves": {
            half: _share(
                [
                    row
                    for row in hinted
                    if row["wait_class"] == "long"
                    and (row["idle_seconds"] < 135) == (half == "short")
                ]
            )
            for half in ("short", "long")
        },
        "ttft_seconds": {
            cohort: _quantiles(
                [row["ttft_ns"] for row in complete if row["cohort"] == cohort]
            )
            for cohort in ("first_turn", "hinted_return", "unhinted_return", "one_shot")
        },
        "queue_share_of_ttft": queue / ttft if ttft else None,
        "failures": {
            "sessions": metrics["session_failures"],
            "one_shots": metrics["one_shot_failures"],
            "captures": metrics["capture_failures"],
            "store": metrics["store_failures"],
            "store_refusals": metrics["store_refusals"],
            "transfer_jobs": len(metrics["failed_transfer_jobs"]),
        },
        "advice": {
            status: sum(hint["outcome"] == status for hint in metrics["hints"])
            for status in sorted({hint["outcome"] for hint in metrics["hints"]})
        },
        "evictions": len(metrics["evictions"]),
        "policy_outcomes": outcomes,
        "resources": metrics.get("resources"),
    }


def idle_profile(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for cell in metrics for row in returns(cell)]
    profile = []
    for low, high in zip(AGE_BINS, (*AGE_BINS[1:], float("inf")), strict=True):
        selected = [row for row in rows if low <= row["idle_seconds"] < high]
        profile.append({"from_seconds": low, "to_seconds": high} | _share(selected))
    return profile


def retention_horizon(profile: list[dict[str, Any]]) -> float | None:
    for entry in profile:
        share = entry["recompute_share"]
        if share is not None and share >= 0.5:
            return float(entry["from_seconds"])
    return None


def _gate(
    cells: dict[tuple[str, int], dict[str, Any]], base: str, oracle_arm: str
) -> dict[str, Any]:
    shape = BASES[base]
    seeds = sorted(
        seed
        for arm, seed in cells
        if arm == oracle_arm
        and any((server, seed) in cells for server in shape["server"])
    )
    comparators = [
        arm
        for arm in shape["server"]
        if seeds and all((arm, seed) in cells for seed in seeds)
    ]
    rows = []
    for seed in seeds:
        descriptive = {
            arm: cells[(arm, seed)]["opt_in"]["recompute_share"]
            for arm in shape["server"]
            if (arm, seed) in cells
        }
        server = {
            arm: share
            for arm, share in descriptive.items()
            if arm in comparators and share is not None
        }
        oracle = cells[(oracle_arm, seed)]["opt_in"]["recompute_share"]
        if not server or oracle is None:
            continue
        best = min(server, key=server.__getitem__)
        rows.append(
            {
                "seed": seed,
                "oracle": oracle,
                "best_server_arm": best,
                "best_server": server[best],
                "points": 100 * (server[best] - oracle),
                "all_server_arms": descriptive,
            }
        )
    passed = len(rows) >= 3 and all(row["points"] >= GATE_POINTS for row in rows)
    return {
        "base": base,
        "oracle_arm": oracle_arm,
        "seeds": rows,
        "comparators": comparators,
        "passed": passed,
        "rule": f"capped oracle beats the best server-only arm by >= {GATE_POINTS} recompute points in every seed (at least 3)",
    }


def campaign_agent_report(metrics_directory: Path) -> dict[str, Any]:
    levels: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    raw: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(metrics_directory.glob("*.json")):
        match = NAME.match(path.stem)
        if match is None:
            continue
        metrics = json.loads(path.read_text())
        if metrics.get("schema") != "pr-cell-metrics-v1":
            continue
        level = f"{match['study']}-p{match['pool']}"
        key = (match["arm"], int(match["seed"]))
        if key in levels.setdefault(level, {}):
            raise ValueError(f"duplicate cell {level} {key}")
        levels[level][key] = cell_summary(metrics) | {"source": path.name}
        if match["arm"] == "lru":
            raw.setdefault(level, []).append(metrics)
    report: dict[str, Any] = {"schema": "pr-agent-mix-report-v1", "levels": {}}
    for level, cells in sorted(levels.items()):
        profile = idle_profile(raw.get(level, []))
        report["levels"][level] = {
            "cells": {
                f"{arm}-s{seed}": cell for (arm, seed), cell in sorted(cells.items())
            },
            "lru_idle_profile": profile,
            "lru_retention_horizon_seconds": retention_horizon(profile),
            "gates": {
                oracle: _gate(cells, base, oracle)
                for base, shape in BASES.items()
                for oracle in shape["oracles"]
                if any(arm == oracle for arm, _ in cells)
            },
        }
    return report

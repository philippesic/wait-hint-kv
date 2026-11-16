from __future__ import annotations

import json
import math
import statistics
from functools import cache
from pathlib import Path
from typing import Any

from tools.benchmarking.pr_workload import DISCUSSION_ARMS, _rng, seeded_order

SCHEMA = "pr-agent-mix-schedule-v1"
MODELS = ("Q7",)
PARTITIONS = ("stage-a", "decision")
SYSTEM_TOKENS = 2048
TASK_TOKENS = (1000, 2000)
OUTPUT_TOKENS = (48, 160)
TOOL_TOKENS = (700, 2000)
SUMMARY_TOKENS = (2000, 3000)
CONTEXT_CEILING = 16000
TURNS = (7, 10)
COMPACTION_SHARE = 0.10
ABANDON_SHARE = 3 / 8
WAIT_MIXES = {
    "default": (("instant", 0.50), ("tool", 0.35), ("long", 0.15)),
    "long": (("instant", 0.35), ("tool", 0.25), ("long", 0.40)),
}
TOOL_MEDIAN_SECONDS = 4.0
TOOL_SIGMA = 0.8
LONG_WAIT = (30.0, 240.0)
INSTANT_LIMIT_SECONDS = 5.0
SHORT_EXPIRY_MS = 30_000
LONG_EXPIRY_MS = 240_000
ORACLE_SLACK_MS = 5_000
MAX_HOLD_MS = 300_000
ONE_SHOT_TOKENS = (1000, 2500)
ONE_SHOT_OUTPUT = 64
REQUEST_DEADLINE_SECONDS = 120.0
INFORMATION = ("none", "oracle", "candidate")
ARMS: dict[str, dict[str, Any]] = {
    "lru": {"policy": "lru", "information": "none"},
    "arc": {"policy": "arc", "information": "none"},
    "auto-lru": {"policy": "AutoHoldLRU", "information": "none"},
    "auto-arc": {"policy": "AutoHoldARC", "information": "none"},
    "auto300-lru": {"policy": "AutoHold300LRU", "information": "none"},
    "auto-st2-lru": {
        "policy": "AutoHoldLRU",
        "information": "none",
        "store_threshold": 2,
    },
    "oracle-lru": {"policy": "AdvisedHoldLRU", "information": "oracle"},
    "oracle-arc": {"policy": "AdvisedHoldARC", "information": "oracle"},
    "oracle-uncapped-lru": {"policy": "AdvisedUncappedLRU", "information": "oracle"},
    "cand-lru": {"policy": "AdvisedHoldLRU", "information": "candidate"},
    "cand-arc": {"policy": "AdvisedHoldARC", "information": "candidate"},
    "oracle-gpu-lru": {"policy": "AdvisedGpuLRU", "information": "oracle"},
    "oracle-gpu-arc": {"policy": "AdvisedGpuARC", "information": "oracle"},
    "cand-gpu-lru": {"policy": "AdvisedGpuLRU", "information": "candidate"},
    "cand-gpu-arc": {"policy": "AdvisedGpuARC", "information": "candidate"},
    "auto300old-lru": {"policy": "AutoHold300OldLRU", "information": "none"},
    "auto300old-arc": {"policy": "AutoHold300OldARC", "information": "none"},
}
if tuple(ARMS) != DISCUSSION_ARMS:
    raise RuntimeError("discussion arm tables differ")
PARAMETERS = {"sessions", "window_seconds", "one_shot_mean_seconds", "max_running"}


@cache
def instant_pool() -> tuple[float, ...]:
    shapes = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "benchmarks/replay/release-01-shapes.json"
        ).read_text()
    )
    return tuple(
        sorted(
            float(turn[3])
            for sessions in shapes["models"].values()
            for session in sessions
            for turn in session[1:]
            if 0 < float(turn[3]) <= INSTANT_LIMIT_SECONDS
        )
    )


def type_median_ms(wait_class: str) -> int:
    if wait_class == "instant":
        return round(statistics.median(instant_pool()) * 1000)
    if wait_class == "tool":
        return round(TOOL_MEDIAN_SECONDS * 1000)
    if wait_class == "long":
        return round(sum(LONG_WAIT) / 2 * 1000)
    raise ValueError("unknown wait class")


def _tokens(rng: Any, count: int) -> list[int]:
    return [rng.randrange(1000, 30000) for _ in range(count)]


def system_prefix() -> list[int]:
    return _tokens(_rng(0, "agent-mix-system"), SYSTEM_TOKENS)


def _wait(rng: Any, mix: str) -> tuple[str, float]:
    draw = rng.random()
    total = 0.0
    for name, share in WAIT_MIXES[mix]:
        total += share
        if draw < total:
            break
    if name == "instant":
        pool = instant_pool()
        return name, pool[rng.randrange(len(pool))]
    if name == "tool":
        return name, min(
            MAX_HOLD_MS / 1000,
            rng.lognormvariate(math.log(TOOL_MEDIAN_SECONDS), TOOL_SIGMA),
        )
    return name, rng.uniform(*LONG_WAIT)


def _session(
    seed: int,
    index: int,
    system: list[int],
    abandon: bool,
    adopter: bool,
    arrival: float,
    mix: str,
) -> dict[str, Any]:
    content = _rng(seed, f"agent-mix-content-{index}")
    waits = _rng(seed, f"agent-mix-waits-{index}")
    planned = content.randint(*TURNS)
    if abandon:
        planned = content.randint(3, planned - 1)
    prompt = system + _tokens(content, content.randint(*TASK_TOKENS))
    turns: list[dict[str, Any]] = []
    lcp = 0
    while len(turns) < planned:
        output = content.randint(*OUTPUT_TOKENS)
        tool = _tokens(content, content.randint(*TOOL_TOKENS))
        grown = len(prompt) + output + len(tool)
        compacts = grown > CONTEXT_CEILING or content.random() < COMPACTION_SHARE
        wait_class, gap = _wait(waits, mix)
        turns.append(
            {
                "message_index": len(turns),
                "prompt_tokens": prompt,
                "recorded_output_tokens": output,
                "requested_output_tokens": output,
                "output_template_prefix_changed_tokens": 0,
                "previous_request_lcp_tokens": lcp,
                "previous_request_lost_suffix_tokens": 0,
                "post_response_eligible": True,
                "gap_seconds": gap,
                "wait_class": wait_class,
                "expected_return_ms": type_median_ms(wait_class),
                "candidate_expiry_ms": LONG_EXPIRY_MS
                if wait_class == "long"
                else SHORT_EXPIRY_MS,
                "keep_tokens": SYSTEM_TOKENS if compacts else None,
            }
        )
        if compacts:
            lcp = SYSTEM_TOKENS
            prompt = system + _tokens(content, content.randint(*SUMMARY_TOKENS)) + tool
        else:
            lcp = len(prompt)
            prompt = prompt + _tokens(content, output) + tool
    ending = "abandoned" if abandon else "complete"
    if not abandon:
        last = turns[-1]
        last["post_response_eligible"] = False
        last["keep_tokens"] = None
    return {
        "session_id": f"m{seed}-{index:04d}",
        "task": f"m{seed}-{index:04d}",
        "repository": "synthetic",
        "trajectory": "synthetic",
        "source_resolved": False,
        "stratum": "agent-mix",
        "ending": ending,
        "arrival_seconds": arrival,
        "adopter": adopter,
        "task_occurrence": 1,
        "turns": turns,
    }


def agent_mix_schedule(
    model: str,
    partition: str,
    seed: int,
    sessions: int,
    window_seconds: float,
    one_shot_mean_seconds: float,
    max_running: int,
    wait_mix: str = "default",
) -> dict[str, Any]:
    if (
        wait_mix not in WAIT_MIXES
        or model not in MODELS
        or partition not in PARTITIONS
        or not 4 <= sessions <= 48
        or not 60 <= window_seconds <= 1800
        or not 2 <= one_shot_mean_seconds <= 600
        or max_running not in (4, 6, 8)
    ):
        raise ValueError("agent-mix schedule outside admitted settings")
    system = system_prefix()
    order = sorted(
        range(sessions),
        key=lambda index: seeded_order(seed, "agent-mix-hint", str(index)),
    )
    silent = set(order[: max(2, round(sessions / 8))])
    abandoning = set(
        sorted(
            range(sessions),
            key=lambda index: seeded_order(seed, "agent-mix-abandon", str(index)),
        )[: round(sessions * ABANDON_SHARE)]
    )
    stagger = min(120.0, window_seconds / 4) / sessions
    session_list = [
        _session(
            seed,
            index,
            system,
            index in abandoning,
            index not in silent,
            1.0 + index * stagger,
            wait_mix,
        )
        for index in range(sessions)
    ]
    shots = _rng(seed, "agent-mix-one-shots")
    one_shots: list[dict[str, Any]] = []
    arrival = shots.expovariate(1 / one_shot_mean_seconds)
    while arrival < window_seconds:
        one_shots.append(
            {
                "session_id": f"n{seed}-{len(one_shots):06d}",
                "arrival_seconds": arrival,
                "prompt_tokens": system
                + _tokens(shots, shots.randint(*ONE_SHOT_TOKENS)),
                "requested_output_tokens": ONE_SHOT_OUTPUT,
            }
        )
        arrival += shots.expovariate(1 / one_shot_mean_seconds)
    return {
        "schema": SCHEMA,
        "model": model,
        "partition": partition,
        "seed": seed,
        "parameters": {
            "sessions": sessions,
            "window_seconds": window_seconds,
            "one_shot_mean_seconds": one_shot_mean_seconds,
            "max_running": max_running,
        }
        | ({} if wait_mix == "default" else {"wait_mix": wait_mix}),
        "horizon_seconds": 3600,
        "request_deadline_seconds": REQUEST_DEADLINE_SECONDS,
        "session_deadline_seconds": 3600,
        "ttl_ms": SHORT_EXPIRY_MS,
        "sessions": session_list,
        "one_shots": one_shots,
        "arm_order": sorted(ARMS, key=lambda arm: seeded_order(seed, "arm-order", arm)),
        "stratum_weights": {"agent-mix": 1},
    }


def validate_agent_mix_schedule(schedule: dict[str, Any]) -> None:
    if (
        set(schedule)
        != {
            "schema",
            "model",
            "partition",
            "seed",
            "parameters",
            "horizon_seconds",
            "request_deadline_seconds",
            "session_deadline_seconds",
            "ttl_ms",
            "sessions",
            "one_shots",
            "arm_order",
            "stratum_weights",
        }
        or set(schedule["parameters"]) - {"wait_mix"} != PARAMETERS
    ):
        raise ValueError("closed agent-mix schedule required")
    expected = agent_mix_schedule(
        schedule["model"],
        schedule["partition"],
        schedule["seed"],
        **schedule["parameters"],
    )
    order = schedule["arm_order"]
    if (
        schedule | {"arm_order": expected["arm_order"]} != expected
        or not set(order) <= set(ARMS)
        or len(set(order)) != len(order)
        or order
        != sorted(
            order, key=lambda arm: seeded_order(schedule["seed"], "arm-order", arm)
        )
    ):
        raise ValueError("agent-mix schedule differs from its deterministic generator")


def advice_for_turn(
    session: dict[str, Any], index: int, information: str
) -> dict[str, Any] | None:
    if information not in INFORMATION:
        raise ValueError("unknown information mode")
    if information == "none" or not session["adopter"]:
        return None
    turn = session["turns"][index]
    last = index == len(session["turns"]) - 1
    if last and (session["ending"] == "complete" or information == "oracle"):
        return {"event": "done"}
    if information == "oracle":
        gap_ms = round(turn["gap_seconds"] * 1000)
        return {
            "event": "return",
            "expected_return_ms": gap_ms,
            "expiry_ms": min(MAX_HOLD_MS, gap_ms + ORACLE_SLACK_MS),
            "keep_tokens": turn["keep_tokens"],
        }
    return {
        "event": "return",
        "expected_return_ms": turn["expected_return_ms"],
        "expiry_ms": turn["candidate_expiry_ms"],
        "keep_tokens": turn["keep_tokens"],
    }

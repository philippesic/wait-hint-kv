from __future__ import annotations

import math
from typing import Any

from tools.benchmarking.pr_workload import _rng, seeded_order

PRESSURE_MODELS = ("D8", "HM")
SESSIONS = 8
ABANDONING = 3
FAST_TTL_MS = 12000
PROFILES: dict[str, dict[str, Any]] = {
    "mixed": {
        "arms": ("A1", "A6", "A7"),
        "adopters": 5,
        "long_share": 0.05,
        "long_wait": (20.0, 120.0),
        "long_ttl_ms": 60000,
    },
    "adopt": {
        "arms": ("A1", "A6", "A7", "A6s", "A9s"),
        "adopters": 7,
        "long_share": 0.05,
        "long_wait": (20.0, 120.0),
        "long_ttl_ms": 150000,
    },
    "adopt-long": {
        "arms": ("A1", "A6", "A7", "A6s", "A9s"),
        "adopters": 7,
        "long_share": 0.25,
        "long_wait": (30.0, 240.0),
        "long_ttl_ms": 300000,
    },
}
ADOPTERS = PROFILES["mixed"]["adopters"]
LONG_TTL_MS = PROFILES["mixed"]["long_ttl_ms"]
MAX_CONTEXT = 5000
TURN_ALLOWANCE_SECONDS = 20.0
DRAIN_SECONDS = 60.0
STAGGER_SECONDS = 10.0
ONE_SHOT_MEAN_SECONDS = 20.0


def _tokens(rng: Any, count: int) -> list[int]:
    return [rng.randrange(1000, 30000) for _ in range(count)]


def pressure_schedule(
    model: str, partition: str, seed: int, profile: str = "mixed"
) -> dict[str, Any]:
    if (
        model not in PRESSURE_MODELS
        or partition not in {"pressure-pilot", "pressure"}
        or profile not in PROFILES
    ):
        raise ValueError("pressure schedule outside admitted models or partitions")
    shape = PROFILES[profile]
    content, gaps, shots = (
        _rng(seed, f"pressure-{label}") for label in ("content", "gaps", "one-shots")
    )
    order = sorted(
        range(SESSIONS), key=lambda index: seeded_order(seed, "adoption", str(index))
    )
    adopters = set(order[: shape["adopters"]])
    abandoning = set(
        sorted(
            range(SESSIONS),
            key=lambda index: seeded_order(seed, "abandon", str(index)),
        )[:ABANDONING]
    )
    sessions = []
    latest_end = 0.0
    for index in range(SESSIONS):
        arrival = 1.0 + index * STAGGER_SECONDS
        prompt = _tokens(content, content.randint(1500, 3000))
        planned = content.randint(5, 9)
        turns: list[dict[str, Any]] = []
        lcp = 0
        while len(turns) < planned:
            output = content.randint(32, 96)
            if len(prompt) + output > MAX_CONTEXT:
                break
            long_wait = gaps.random() < shape["long_share"]
            gap = (
                gaps.uniform(*shape["long_wait"])
                if long_wait
                else min(300.0, gaps.lognormvariate(math.log(4.0), 0.8))
            )
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
                    "wait_class": "long" if long_wait else "fast",
                    "hint_ttl_ms": shape["long_ttl_ms"] if long_wait else FAST_TTL_MS,
                }
            )
            appended = _tokens(content, output) + _tokens(
                content, content.randint(200, 700)
            )
            if content.random() < 0.1:
                lcp = min(600, len(prompt))
                prompt = prompt[:lcp] + appended
            else:
                lcp = len(prompt)
                prompt = prompt + appended
        if len(turns) < 2:
            raise ValueError("pressure session needs at least two turns")
        ending = "abandoned" if index in abandoning else "complete"
        turns[-1]["post_response_eligible"] = ending == "abandoned"
        sessions.append(
            {
                "session_id": f"p{seed}-{index:04d}",
                "task": f"p{seed}-{index:04d}",
                "repository": "synthetic",
                "trajectory": "synthetic",
                "source_resolved": False,
                "stratum": "pressure",
                "ending": ending,
                "arrival_seconds": arrival,
                "adopter": index in adopters,
                "task_occurrence": 1,
                "turns": turns,
            }
        )
        latest_end = max(
            latest_end,
            arrival
            + sum(float(turn["gap_seconds"]) for turn in turns[:-1])
            + len(turns) * TURN_ALLOWANCE_SECONDS,
        )
    horizon = math.ceil(latest_end + DRAIN_SECONDS)
    one_shots: list[dict[str, Any]] = []
    arrival = shots.expovariate(1 / ONE_SHOT_MEAN_SECONDS)
    while arrival < horizon:
        one_shots.append(
            {
                "session_id": f"q{seed}-{len(one_shots):06d}",
                "arrival_seconds": arrival,
                "prompt_tokens": _tokens(shots, shots.randint(1500, 3500)),
                "requested_output_tokens": 64,
            }
        )
        arrival += shots.expovariate(1 / ONE_SHOT_MEAN_SECONDS)
    schedule = {
        "schema": "pr-pressure-schedule-v1",
        "model": model,
        "partition": partition,
        "seed": seed,
        "horizon_seconds": horizon,
        "request_deadline_seconds": 120.0,
        "session_deadline_seconds": horizon,
        "ttl_ms": FAST_TTL_MS,
        "sessions": sessions,
        "one_shots": one_shots,
        "arm_order": sorted(
            shape["arms"], key=lambda arm: seeded_order(seed, "arm-order", arm)
        ),
        "stratum_weights": {"pressure": 1},
        "end_when_sessions_finish": True,
    }
    if profile != "mixed":
        schedule["profile"] = profile
    return schedule


def validate_pressure_schedule(schedule: dict[str, Any]) -> None:
    if set(schedule) - {"profile"} != {
        "schema",
        "model",
        "partition",
        "seed",
        "horizon_seconds",
        "request_deadline_seconds",
        "session_deadline_seconds",
        "ttl_ms",
        "sessions",
        "one_shots",
        "arm_order",
        "stratum_weights",
        "end_when_sessions_finish",
    }:
        raise ValueError("closed pressure schedule required")
    if schedule != pressure_schedule(
        schedule["model"],
        schedule["partition"],
        schedule["seed"],
        schedule.get("profile", "mixed"),
    ):
        raise ValueError("pressure schedule differs from its deterministic generator")

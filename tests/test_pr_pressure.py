from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.benchmarking.pr_pressure import (
    ADOPTERS,
    LONG_TTL_MS,
    SESSIONS,
    pressure_schedule,
    validate_pressure_schedule,
)
from tools.benchmarking.pr_workload import request_payload, validate_schedule


def test_pressure_schedule_is_deterministic_and_closed() -> None:
    schedule = pressure_schedule("D8", "pressure", 22001)
    validate_schedule(schedule)
    assert schedule == pressure_schedule("D8", "pressure", 22001)
    assert schedule != pressure_schedule("D8", "pressure", 22002)
    assert len(schedule["sessions"]) == SESSIONS
    assert sum(session["adopter"] for session in schedule["sessions"]) == ADOPTERS
    changed = schedule | {"seed": 22002}
    with pytest.raises(ValueError, match="generator"):
        validate_pressure_schedule(changed)
    with pytest.raises(ValueError, match="closed"):
        validate_pressure_schedule(schedule | {"extra": 1})


def test_pressure_turns_share_prefixes_and_carry_class_ttl() -> None:
    longs = 0
    for seed in range(22001, 22013):
        schedule = pressure_schedule("HM", "pressure", seed)
        last = max(
            session["arrival_seconds"]
            + sum(turn["gap_seconds"] for turn in session["turns"][:-1])
            for session in schedule["sessions"]
        )
        assert schedule["horizon_seconds"] > last
        assert all(
            shot["arrival_seconds"] < schedule["horizon_seconds"]
            for shot in schedule["one_shots"]
        )
        for session in schedule["sessions"]:
            turns = session["turns"]
            for previous, turn in zip(turns, turns[1:]):
                lcp = turn["previous_request_lcp_tokens"]
                assert turn["prompt_tokens"][:lcp] == previous["prompt_tokens"][:lcp]
                assert lcp in {len(previous["prompt_tokens"]), 600} or lcp < 600
            assert turns[-1]["post_response_eligible"] == (
                session["ending"] == "abandoned"
            )
            for turn in turns:
                long_wait = turn["wait_class"] == "long"
                longs += long_wait
                assert (turn["hint_ttl_ms"] == LONG_TTL_MS) == long_wait
                assert (20 <= turn["gap_seconds"] <= 120) or not long_wait
    assert longs > 0


def test_variant_arms_send_no_request_ttl() -> None:
    schedule = pressure_schedule("D8", "pressure", 22001)
    adopter = next(session for session in schedule["sessions"] if session["adopter"])
    assert request_payload(schedule, adopter, 0, "A5")["ttl_ms"] == 12000
    for arm in ("A1", "A6", "A7"):
        assert request_payload(schedule, adopter, 0, arm)["ttl_ms"] is None


def _metric_cell(arm: str, seed: int, recompute: float, ttft: float) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for cohort, count in (
        ("hinted_return", 4),
        ("unhinted_return", 3),
        ("one_shot", 2),
    ):
        for index in range(count):
            rows.append(
                {
                    "request_id": f"{cohort}-{index}",
                    "session_id": f"{cohort}-{index}",
                    "task": None,
                    "stratum": "one_shot" if cohort == "one_shot" else "pressure",
                    "cohort": cohort,
                    "outcome": "complete",
                    "wait_class": "fast",
                    "eligible_tokens": 1000,
                    "sources": {
                        "recomputed_tokens": int(1000 * recompute) + index,
                        "unobserved_tokens": 0,
                        "cpu_reused_tokens": 0,
                        "gpu_reused_tokens": 0,
                    },
                    "ttft_ns": ttft * (1 + index / 100) * (1 + seed % 7 / 50),
                    "client_itl_ns": 50.0 + index,
                }
            )
    return {
        "schema": "pr-cell-metrics-v1",
        "schedule_schema": "pr-pressure-schedule-v1",
        "model": "D8",
        "seed": seed,
        "arm": arm,
        "partition": "pressure",
        "stratum_weights": {"pressure": 1},
        "requests": rows,
        "cpu_config": {"num_chunks": 10, "kv_bytes_per_chunk": 1},
    }


def test_campaign_report_separates_pool_levels_and_judges_harm(
    tmp_path: Path,
) -> None:
    import json

    from tools.benchmarking.pr_discussion import campaign_report

    for seed in range(22001, 22005):
        for pool, arm, recompute, ttft in (
            (2048, "A1", 0.7, 100.0),
            (2048, "A7", 0.4, 80.0),
            (1254, "A1", 0.8, 100.0),
            (1254, "A7", 0.6, 120.0),
        ):
            path = tmp_path / f"press-d8-{seed}-p{pool}-{arm}-a1.json"
            path.write_text(json.dumps(_metric_cell(arm, seed, recompute, ttft)))
    report = campaign_report([tmp_path])
    assert set(report["groups"]) == {"pressure-p2048-D8", "pressure-p1254-D8"}
    moderate = {
        (
            entry["cohort"],
            entry["metric"],
            entry["contrast"],
            entry["wait_class"],
        ): entry
        for entry in report["groups"]["pressure-p2048-D8"]["comparisons"]
    }
    benefit = moderate[("hinted_return", "recompute", "absolute_change", None)]
    assert benefit["point"] < -0.25 and "verdict" not in benefit
    harm = moderate[("unhinted_return", "ttft_ns", "relative_harm", None)]
    assert harm["verdict"] == "not worse"
    heavy = {
        (
            entry["cohort"],
            entry["metric"],
            entry["contrast"],
            entry["wait_class"],
        ): entry
        for entry in report["groups"]["pressure-p1254-D8"]["comparisons"]
    }
    assert (
        heavy[("unhinted_return", "ttft_ns", "relative_harm", None)]["verdict"]
        == "worse"
    )


def test_adoption_profiles_keep_mixed_schedules_and_add_combined_arm() -> None:
    mixed = pressure_schedule("D8", "pressure", 22003)
    assert "profile" not in mixed
    assert mixed == pressure_schedule("D8", "pressure", 22003, "mixed")
    for profile, long_ttl in (("adopt", 150000), ("adopt-long", 300000)):
        schedule = pressure_schedule("D8", "pressure", 22003, profile)
        validate_schedule(schedule)
        assert schedule["profile"] == profile
        assert sum(session["adopter"] for session in schedule["sessions"]) == 7
        assert set(schedule["arm_order"]) == {"A1", "A6", "A7", "A8"}
        hints = {
            turn["hint_ttl_ms"]
            for session in schedule["sessions"]
            for turn in session["turns"]
            if turn["wait_class"] == "long"
        }
        assert hints <= {long_ttl}
        adopter = next(s for s in schedule["sessions"] if s["adopter"])
        assert request_payload(schedule, adopter, 0, "A8")["ttl_ms"] is None

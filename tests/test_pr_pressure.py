from __future__ import annotations

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

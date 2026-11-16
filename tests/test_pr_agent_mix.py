from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.benchmarking.pr_agent_mix import (
    ARMS,
    SYSTEM_TOKENS,
    advice_for_turn,
    agent_mix_schedule,
    type_median_ms,
    validate_agent_mix_schedule,
)
from tools.benchmarking.pr_jobs import agent_server_command, run_gpu_job
from tools.benchmarking.pr_workload import validate_schedule
from wait_hint_offload.discussion_protocol import (
    Advice,
    AdviceEnvelope,
    validate_advice_acknowledgement,
)
from wait_hint_offload.policy_protocol import PolicySession

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def schedule() -> dict[str, Any]:
    return agent_mix_schedule("Q7", "stage-a", 31001, 16, 600, 20, 6)


def test_schedule_regenerates_exactly_and_refuses_edits(
    schedule: dict[str, Any],
) -> None:
    validate_schedule(schedule)
    changed = json.loads(json.dumps(schedule))
    changed["sessions"][0]["turns"][1]["gap_seconds"] += 1
    with pytest.raises(ValueError, match="deterministic"):
        validate_agent_mix_schedule(changed)
    with pytest.raises(ValueError, match="closed"):
        validate_agent_mix_schedule(schedule | {"extra": 1})


def test_sessions_share_system_prefix_and_grow_to_ceiling(
    schedule: dict[str, Any],
) -> None:
    first = schedule["sessions"][0]["turns"][0]["prompt_tokens"][:SYSTEM_TOKENS]
    prompts = [
        turn["prompt_tokens"]
        for session in schedule["sessions"]
        for turn in session["turns"]
    ] + [shot["prompt_tokens"] for shot in schedule["one_shots"]]
    assert all(prompt[:SYSTEM_TOKENS] == first for prompt in prompts)
    lengths = [len(prompt) for prompt in prompts]
    assert min(lengths) >= 3000 and max(lengths) <= 16000
    assert max(lengths) > 12000


def test_compaction_keeps_only_system_prefix(schedule: dict[str, Any]) -> None:
    compactions = 0
    for session in schedule["sessions"]:
        turns = session["turns"]
        for turn, following in zip(turns, turns[1:], strict=False):
            if turn["keep_tokens"] is None:
                assert following["previous_request_lcp_tokens"] == len(
                    turn["prompt_tokens"]
                )
                assert (
                    following["prompt_tokens"][: len(turn["prompt_tokens"])]
                    == turn["prompt_tokens"]
                )
            else:
                compactions += 1
                assert turn["keep_tokens"] == SYSTEM_TOKENS
                assert following["previous_request_lcp_tokens"] == SYSTEM_TOKENS
    assert compactions >= 5


def test_cohorts_waits_and_one_shots(schedule: dict[str, Any]) -> None:
    sessions = schedule["sessions"]
    assert sum(not session["adopter"] for session in sessions) >= 2
    assert {session["ending"] for session in sessions} == {"complete", "abandoned"}
    classes = {turn["wait_class"] for session in sessions for turn in session["turns"]}
    assert classes == {"instant", "tool", "long"}
    for session in sessions:
        for turn in session["turns"]:
            assert turn["expected_return_ms"] == type_median_ms(turn["wait_class"])
            assert turn["candidate_expiry_ms"] == (
                240_000 if turn["wait_class"] == "long" else 30_000
            )
            if turn["wait_class"] == "long":
                assert 30 <= turn["gap_seconds"] <= 240
            if turn["wait_class"] == "instant":
                assert turn["gap_seconds"] <= 5
    assert 200 <= type_median_ms("instant") <= 300
    assert schedule["one_shots"] and all(
        shot["arrival_seconds"] < 600 for shot in schedule["one_shots"]
    )


def test_advice_differs_only_in_information(schedule: dict[str, Any]) -> None:
    hinting = [session for session in schedule["sessions"] if session["adopter"]]
    silent = next(session for session in schedule["sessions"] if not session["adopter"])
    assert advice_for_turn(silent, 0, "oracle") is None
    assert advice_for_turn(hinting[0], 0, "none") is None
    for session in hinting:
        last = len(session["turns"]) - 1
        for index, turn in enumerate(session["turns"]):
            oracle = advice_for_turn(session, index, "oracle")
            candidate = advice_for_turn(session, index, "candidate")
            assert oracle is not None and candidate is not None
            if index == last:
                assert oracle == {"event": "done"}
                expected = "done" if session["ending"] == "complete" else "return"
                assert candidate["event"] == expected
                continue
            gap = round(turn["gap_seconds"] * 1000)
            assert oracle["expected_return_ms"] == gap
            assert oracle["expiry_ms"] == min(300_000, gap + 5_000)
            assert candidate["expected_return_ms"] == turn["expected_return_ms"]
            assert oracle["keep_tokens"] == candidate["keep_tokens"]
            assert oracle["keep_tokens"] == turn["keep_tokens"]


def test_advice_protocol_is_closed() -> None:
    session = PolicySession("pr-evidence", "m1", "1", 2)
    advice = Advice("a", session, "return", 236, 30_000, 2048)
    envelope = AdviceEnvelope("m", (advice,))
    assert AdviceEnvelope.parse(envelope.to_dict()) == envelope
    with pytest.raises(ValueError):
        Advice("a", session, "done", 236, None, None)
    with pytest.raises(ValueError):
        Advice("a", session, "return", None, None, None)
    with pytest.raises(ValueError):
        Advice.parse(advice.to_dict() | {"extra": 1})
    with pytest.raises(ValueError, match="repeated"):
        AdviceEnvelope.parse(
            {**envelope.to_dict(), "actions": [advice.to_dict(), advice.to_dict()]}
        )
    acknowledgement = {
        "schema": "pr-discussion-advice-ack-v1",
        "message_id": "m",
        "accepted_ns": 1,
        "actions": [{"action_id": "a", "decision": "planned"}],
    }
    assert validate_advice_acknowledgement(acknowledgement, envelope)
    with pytest.raises(ValueError):
        validate_advice_acknowledgement(
            acknowledgement
            | {"actions": [{"action_id": "a", "decision": "advice_disabled"}]},
            envelope,
        )


def test_agent_commands_match_across_arms_except_policy(tmp_path: Path) -> None:
    commands = {
        arm: agent_server_command(
            Path("python"), tmp_path, arm, 8000, 12 * 1024**3, tmp_path, False, 6
        )
        for arm in ARMS
    }
    base = commands["lru"]
    assert base[base.index("--max-model-len") + 1] == "17408"
    assert base[base.index("--max-num-seqs") + 1] == "6"
    for arm, command in commands.items():
        extra = json.loads(command[-1])["kv_connector_extra_config"]
        assert command[:-1] == base[:-1]
        assert extra["eviction_policy"] == ARMS[arm]["policy"]
        assert extra.get("store_threshold") == (2 if arm == "auto-st2-lru" else None)
        assert ("cache_policy_module_path" in extra) == (arm not in {"lru", "arc"})
    with pytest.raises(ValueError):
        agent_server_command(
            Path("python"), tmp_path, "A1", 8000, 12 * 1024**3, tmp_path, False, 6
        )
    with pytest.raises(ValueError):
        agent_server_command(
            Path("python"), tmp_path, "lru", 8000, 65 * 1024**3, tmp_path, False, 6
        )


def test_native_campaign_keeps_models_and_arms_apart(tmp_path: Path) -> None:
    arguments = (
        tmp_path / "python",
        tmp_path / "b25037543e9394b818fdfca67ab2a00ecc7dd641",
    )
    with pytest.raises(ValueError, match="agent-mix job outside"):
        run_gpu_job(
            ROOT / "artifacts/runs/discussion-native",
            "wrong-arm",
            *arguments,
            "Q7",
            "A1",
            "decision",
            1024**3,
            60,
            tmp_path / "schedule.json",
        )
    with pytest.raises(ValueError, match="belong to the native campaign"):
        run_gpu_job(
            ROOT / "artifacts/runs/discussion-2080ti",
            "wrong-campaign",
            *arguments,
            "Q7",
            "lru",
            "decision",
            1024**3,
            60,
            tmp_path / "schedule.json",
        )

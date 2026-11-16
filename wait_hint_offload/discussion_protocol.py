from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wait_hint_offload.contracts import bounded_name
from wait_hint_offload.policy_protocol import PolicySession

ADVICE_SCHEMA = "pr-discussion-advice-v1"
ENVELOPE_SCHEMA = "pr-discussion-advice-envelope-v1"
ACK_SCHEMA = "pr-discussion-advice-ack-v1"
EVENTS = ("return", "done", "ephemeral")
MAX_WAIT_MS = 300_000
MAX_KEEP_TOKENS = 1 << 20
DECISIONS = {
    "pending",
    "replayed",
    "conflict",
    "stale",
    "disabled",
    "planned",
    "ended",
    "metadata_limit",
}


def _optional_int(raw: object, name: str, minimum: int, maximum: int) -> int | None:
    if raw is None:
        return None
    if type(raw) is not int or not minimum <= raw <= maximum:
        raise ValueError(name)
    return raw


@dataclass(frozen=True)
class Advice:
    action_id: str
    session: PolicySession
    event: str
    expected_return_ms: int | None = None
    expiry_ms: int | None = None
    keep_tokens: int | None = None

    def __post_init__(self) -> None:
        bounded_name(self.action_id, "action_id")
        if self.event not in EVENTS:
            raise ValueError("unsupported advice event")
        _optional_int(self.expected_return_ms, "expected_return_ms", 0, MAX_WAIT_MS)
        _optional_int(self.expiry_ms, "expiry_ms", 1, MAX_WAIT_MS)
        _optional_int(self.keep_tokens, "keep_tokens", 0, MAX_KEEP_TOKENS)
        if self.event == "return" and self.expiry_ms is None:
            raise ValueError("return advice needs an expiry")
        if self.event != "return" and (
            self.expected_return_ms is not None
            or self.expiry_ms is not None
            or self.keep_tokens is not None
        ):
            raise ValueError("end advice carries no wait or extent")

    @classmethod
    def parse(cls, raw: object) -> Advice:
        if not isinstance(raw, dict) or set(raw) != {
            "schema",
            "action_id",
            "session",
            "event",
            "expected_return_ms",
            "expiry_ms",
            "keep_tokens",
        }:
            raise ValueError("closed discussion advice required")
        if raw["schema"] != ADVICE_SCHEMA:
            raise ValueError("unsupported discussion advice schema")
        return cls(
            raw["action_id"],
            PolicySession.parse(raw["session"]),
            raw["event"],
            raw["expected_return_ms"],
            raw["expiry_ms"],
            raw["keep_tokens"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ADVICE_SCHEMA,
            "action_id": self.action_id,
            "session": self.session.to_dict(),
            "event": self.event,
            "expected_return_ms": self.expected_return_ms,
            "expiry_ms": self.expiry_ms,
            "keep_tokens": self.keep_tokens,
        }


@dataclass(frozen=True)
class AdviceEnvelope:
    message_id: str
    actions: tuple[Advice, ...]

    @classmethod
    def parse(cls, raw: object) -> AdviceEnvelope:
        if not isinstance(raw, dict) or set(raw) != {"schema", "message_id", "actions"}:
            raise ValueError("closed discussion advice envelope required")
        if raw["schema"] != ENVELOPE_SCHEMA:
            raise ValueError("unsupported discussion advice envelope")
        actions = raw["actions"]
        if not isinstance(actions, list) or not 1 <= len(actions) <= 16:
            raise ValueError("discussion advice envelope needs 1-16 actions")
        parsed = tuple(Advice.parse(item) for item in actions)
        if len({item.action_id for item in parsed}) != len(parsed):
            raise ValueError("repeated advice identity")
        return cls(bounded_name(raw["message_id"], "message_id"), parsed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ENVELOPE_SCHEMA,
            "message_id": self.message_id,
            "actions": [action.to_dict() for action in self.actions],
        }


def validate_advice_acknowledgement(
    raw: object, envelope: AdviceEnvelope
) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {
        "schema",
        "message_id",
        "accepted_ns",
        "actions",
    }:
        raise ValueError("closed advice acknowledgement required")
    if (
        raw["schema"] != ACK_SCHEMA
        or raw["message_id"] != envelope.message_id
        or type(raw["accepted_ns"]) is not int
        or raw["accepted_ns"] < 0
    ):
        raise ValueError("invalid advice acknowledgement identity or time")
    actions = raw["actions"]
    if not isinstance(actions, list) or len(actions) != len(envelope.actions):
        raise ValueError("advice acknowledgement action count mismatch")
    for action, expected in zip(actions, envelope.actions, strict=True):
        if (
            not isinstance(action, dict)
            or set(action) != {"action_id", "decision"}
            or action["action_id"] != expected.action_id
            or action["decision"] not in DECISIONS
        ):
            raise ValueError("invalid advice action acknowledgement")
    return dict(raw)

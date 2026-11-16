from __future__ import annotations

from typing import Any

from vllm.v1.kv_offload import base

from wait_hint_offload.discussion_protocol import Advice, AdviceEnvelope
from wait_hint_offload.policy_protocol import PolicySession
from wait_hint_offload.vllm_adapter.discussion_endpoint import DiscussionEndpoint
from wait_hint_offload.vllm_adapter.policy_checks import (
    _store_keys,
    policy_fixture,
    request_fixture,
)
from wait_hint_offload.vllm_adapter.policy_discussion import (
    AdvisedHoldARC,
    AdvisedHoldLRU,
    AdvisedUncappedLRU,
    AutoHold300LRU,
    AutoHoldARC,
    AutoHoldLRU,
    DiscussionHold,
)

MODULE = "wait_hint_offload.vllm_adapter.policy_discussion"
SECOND = 1_000_000_000


class Harness:
    def __init__(self, name: str, capacity: int = 16):
        self.native, self.owner = policy_fixture(name, capacity, MODULE)
        policy = self.native._policy
        assert isinstance(policy, DiscussionHold)
        self.policy = policy
        self.now = [1_000 * SECOND]
        policy.clock = lambda: self.now[0]
        self.messages = 0

    def advance(self, seconds: float) -> None:
        self.now[0] += int(seconds * SECOND)

    def keys(self, hashes: list[bytes]) -> set[bytes]:
        return {base.make_offload_key(key, 0) for key in hashes}

    def finish(self, name: str, hashes: list[bytes], generation: int = 1) -> None:
        request = f"{name}-{generation}"
        context, _ = request_fixture(
            self.owner, request, name, generation, hashes, False
        )
        self.native.on_new_request(context)
        _store_keys(self.native, context, hashes)
        self.native.on_request_finished(context)
        self.owner._req_status.pop(request, None)

    def store(self, name: str, hashes: list[bytes]) -> None:
        context, _ = request_fixture(self.owner, f"{name}-run", name, 1, hashes, False)
        self.native.on_new_request(context)
        _store_keys(self.native, context, hashes)

    def arrive(self, name: str, hashes: list[bytes], generation: int) -> Any:
        context, _ = request_fixture(
            self.owner, f"{name}-{generation}", name, generation, hashes, False
        )
        self.native.on_new_request(context)
        self.policy._maintain()
        return context

    def advise(
        self,
        name: str,
        event: str,
        generation: int = 1,
        expected: int | None = None,
        expiry: int | None = None,
        keep: int | None = None,
        action_id: str | None = None,
    ) -> str:
        self.messages += 1
        advice = Advice(
            action_id or f"{name}-{generation}-{event}",
            PolicySession("fixture", name, "i", generation),
            event,
            expected,
            expiry,
            keep,
        )
        envelope = AdviceEnvelope(f"m{self.messages}", (advice,))
        acknowledgement = self.policy.publish_envelope(envelope.to_dict())
        return str(acknowledgement["actions"][0]["decision"])

    def leases(self) -> set[str]:
        return {owner_name(owner) for owner in self.policy.book.leases}

    def count(self, name: str) -> int:
        return self.policy.outcomes.get(name, 0)


def owner_name(owner: str) -> str:
    return owner.split('"')[3]


def hashes(prefix: str, count: int) -> list[bytes]:
    return [f"{prefix}{index}".encode() for index in range(count)]


def _automatic(name: str) -> dict[str, Any]:
    harness = Harness(name)
    policy = harness.policy
    harness.finish("s", hashes("s", 2))
    plan = policy.plans['["fixture","s","i"]']
    assert plan.expiry_ns == plan.finished_ns + 30 * SECOND
    assert harness.leases() == {"s"}
    assert harness.advise("s", "done") == "disabled"
    assert harness.leases() == {"s"}
    held = harness.keys(hashes("s", 2))
    harness.store("f", hashes("f", 14))
    harness.store("g", hashes("g", 4))
    assert all(policy.native.get(key) is not None for key in held)
    assert harness.count("hold_yield") == 0
    harness.store("h", hashes("h", 15))
    assert harness.count("hold_yield") == 1 and not policy.book.leases
    harness.advance(31)
    assert policy.evict(0, set()) == [] and not policy.plans
    assert harness.count("intention_expired") == 1
    harness.native.reset_cache()
    return {
        "automatic_expiry_ms": 30000,
        "advice_ignored": True,
        "held_chunks_survive_store_pressure": True,
        "yield_or_displacement_before_store_failure": True,
        "expiry_releases": True,
    }


def _ranking(name: str) -> dict[str, Any]:
    harness = Harness(name)
    policy = harness.policy
    assert policy.book.limit == 8
    harness.finish("a", hashes("a", 4))
    assert harness.advise("a", "return", expected=100_000, expiry=240_000) == "planned"
    harness.finish("b", hashes("b", 4))
    assert harness.advise("b", "return", expected=10_000, expiry=30_000) == "planned"
    assert harness.leases() == {"a", "b"}
    harness.finish("c", hashes("c", 4))
    harness.advise("c", "return", expected=50_000, expiry=240_000)
    assert harness.leases() == {"b", "c"}
    assert harness.count("hold_displaced") >= 1
    harness.finish("d", hashes("d", 4))
    harness.advise("d", "return", expected=200_000, expiry=240_000)
    assert harness.leases() == {"b", "c"}
    assert not policy.plans['["fixture","d","i"]'].held
    harness.advance(5)
    assert harness.advise("b", "done") == "ended"
    assert harness.leases() == {"a", "c"}
    assert harness.count("readmitted") >= 1
    filler = hashes("f", 12)
    context, _ = request_fixture(harness.owner, "f-1", "f", 1, filler, False)
    harness.native.on_new_request(context)
    yields = harness.count("hold_yield")
    _store_keys(harness.native, context, filler)
    assert harness.count("hold_yield") > yields
    assert harness.leases() == {"c"}
    assert not policy.plans['["fixture","a","i"]'].held
    assert harness.count("lost_protection_evictions") >= 1
    harness.native.reset_cache()
    return {
        "largest_remaining_wait_displaced_first": True,
        "larger_wait_cannot_displace_smaller": True,
        "displaced_kept_as_intention": True,
        "readmitted_smallest_wait_first_at_maintenance": True,
        "yield_takes_largest_wait_first": True,
        "no_readmission_inside_eviction": True,
        "lost_protection_counted": True,
    }


def _arrival_and_partial(name: str) -> dict[str, Any]:
    harness = Harness(name)
    policy = harness.policy
    harness.finish("x", hashes("x", 3))
    harness.advise("x", "return", expected=60_000, expiry=240_000)
    harness.advance(100)
    harness.arrive("x", hashes("x", 3), 2)
    plan = policy.plans['["fixture","x","i"]']
    assert plan.arrived_ns == harness.now[0]
    assert plan.expiry_ns == harness.now[0] + 120 * SECOND
    assert harness.count("arrived_held") == 1
    harness.finish("y", hashes("y", 4))
    harness.advise("y", "return", expected=1_000, expiry=30_000)
    filler = hashes("g", 10)
    context, _ = request_fixture(harness.owner, "g-1", "g", 1, filler, False)
    harness.native.on_new_request(context)
    _store_keys(harness.native, context, filler)
    assert "x" in harness.leases() and "y" not in harness.leases()
    harness.owner._req_status.pop("g-1", None)
    harness.advance(110)
    assert policy.evict(0, set()) == [] and "x" in harness.leases()
    harness.advance(11)
    assert policy.evict(0, set()) == [] and "x" not in harness.leases()
    harness.native.reset_cache()
    harness.finish("h", hashes("h", 4))
    harness.advise("h", "return", expected=1_000, expiry=30_000)
    harness.finish("w", hashes("w", 10))
    harness.advise("w", "return", expected=500, expiry=30_000)
    lease = policy.book.leases['["fixture","w","i"]']
    assert len(lease.keys) == 8 and set(lease.keys) == harness.keys(hashes("w", 8))
    assert harness.count("partial_hold") >= 1
    harness.native.reset_cache()
    return {
        "arrival_extends_to_request_deadline_ms": 120000,
        "arrived_kept_while_waiting_yields": True,
        "arrived_protection_bounded_by_deadline": True,
        "partial_hold_keeps_leading_chunks": True,
    }


def _demotion(name: str) -> dict[str, Any]:
    harness = Harness(name)
    policy = harness.policy
    system = hashes("sys", 2)
    harness.finish("p", system + hashes("p", 2))
    harness.finish("q", system + hashes("q", 2))
    assert harness.keys(system) <= policy.shared
    assert harness.advise("p", "done") == "ended"
    assert policy.demoted == harness.keys(hashes("p", 2))
    assert harness.count("shared_kept_chunks") == 2
    evicted = policy.evict(2, set())
    assert evicted is not None
    assert {key for key, _ in evicted} == harness.keys(hashes("p", 2))
    assert harness.count("demoted_evictions") == 2
    assert harness.advise("o", "ephemeral") == "pending"
    harness.finish("o", system + hashes("o", 1))
    assert '["fixture","o","i"]' not in policy.plans
    assert harness.keys(hashes("o", 1)) <= policy.demoted
    assert not harness.keys(system) & policy.demoted
    harness.finish("k", hashes("k", 4))
    harness.advise("k", "return", expected=4_000, expiry=30_000, keep=512)
    lease = policy.book.leases['["fixture","k","i"]']
    assert set(lease.keys) == harness.keys(hashes("k", 2))
    assert harness.keys(hashes("k", 4)[2:]) <= policy.demoted
    harness.arrive("k", hashes("k", 2) + hashes("n", 2), 2)
    assert '["fixture","k","i"]' in policy.plans
    harness.native.reset_cache()
    return {
        "done_demotes_session_suffix": True,
        "shared_chunks_never_demoted": True,
        "demoted_evicted_first": True,
        "ephemeral_before_submission_applied_at_finish": True,
        "keep_tokens_limits_hold_and_demotes_suffix": True,
    }


def _messages() -> dict[str, Any]:
    harness = Harness("AdvisedHoldARC")
    policy = harness.policy
    assert (
        harness.advise("z", "return", expected=4_000, expiry=30_000, action_id="r1")
        == "pending"
    )
    harness.finish("z", hashes("z", 2))
    plan = policy.plans['["fixture","z","i"]']
    assert plan.expected_ns == plan.finished_ns + 4 * SECOND
    harness.finish("e", hashes("e", 2))
    assert (
        harness.advise("e", "return", expected=4_000, expiry=30_000, action_id="e1")
        == "planned"
    )
    assert (
        harness.advise("e", "return", expected=4_000, expiry=30_000, action_id="e1")
        == "replayed"
    )
    assert (
        harness.advise("e", "return", expected=9_000, expiry=30_000, action_id="e1")
        == "conflict"
    )
    harness.finish("e", hashes("e", 3), 2)
    assert harness.advise("e", "done", generation=1, action_id="old") == "stale"
    uncapped = Harness("AdvisedUncappedLRU")
    assert uncapped.policy.book.limit == 16
    auto300 = Harness("AutoHold300LRU")
    auto300.finish("s", hashes("s", 1))
    plan = auto300.policy.plans['["fixture","s","i"]']
    assert plan.expiry_ns == plan.finished_ns + 300 * SECOND
    for item in (harness, uncapped, auto300):
        item.native.reset_cache()
    return {
        "early_return_advice_applied_at_finish": True,
        "replay_and_conflict": True,
        "stale_generation_refused": True,
        "uncapped_limit_is_capacity": True,
        "automatic_300s": True,
        "arc_base_accepts_advice": True,
    }


def _classes() -> dict[str, Any]:
    return {
        cls.__name__: {
            "native": cls.native_class.__name__,
            "automatic_ms": cls.automatic_ms,
            "accepts_advice": cls.accepts_advice,
            "uncapped": cls.uncapped,
        }
        for cls in (
            AutoHoldLRU,
            AutoHoldARC,
            AutoHold300LRU,
            AdvisedHoldLRU,
            AdvisedHoldARC,
            AdvisedUncappedLRU,
        )
    }


def _endpoint() -> dict[str, Any]:
    from fastapi import FastAPI

    app = FastAPI()
    DiscussionEndpoint().attach_router(app)
    paths = {getattr(route, "path", "") for route in app.routes}
    assert {"/v1/pr-evidence/advice", "/v1/pr-evidence/hints"} <= paths
    return {"advice_route": True, "evidence_routes_kept": True}


def observe_discussion_policy() -> dict[str, Any]:
    return {
        "schema": "pr-discussion-policy-observation-v1",
        "classes": _classes(),
        "endpoint": _endpoint(),
        "AutoHoldLRU": _automatic("AutoHoldLRU"),
        "AutoHoldARC": _automatic("AutoHoldARC"),
        **{
            f"{check.__name__.strip('_')}-{base}": check(f"AdvisedHold{base}")
            for check in (_ranking, _arrival_and_partial, _demotion)
            for base in ("LRU", "ARC")
        },
        "messages": _messages(),
        "scope": "CPU fixtures on frozen main; no serving or GPU qualification",
    }

from __future__ import annotations

from typing import Any

from vllm.v1.kv_offload import base

from wait_hint_offload.policy_protocol import PolicyAction, PolicyEnvelope
from wait_hint_offload.vllm_adapter.policy_checks import (
    _store_keys,
    policy_fixture,
    request_fixture,
)
from wait_hint_offload.vllm_adapter.policy_variants import (
    AutomaticHoldLRU,
    PostResponseLRU,
)

VARIANTS = "wait_hint_offload.vllm_adapter.policy_variants"


def _automatic() -> dict[str, Any]:
    native, owner = policy_fixture("AutomaticHoldLRU", 4, VARIANTS)
    policy = native._policy
    assert isinstance(policy, AutomaticHoldLRU)
    now = [1_000_000_000]
    policy.clock = lambda: now[0]
    context, _ = request_fixture(owner, "first", "s", 1, [b"a", b"b"], False)
    native.on_new_request(context)
    keys = [base.make_offload_key(key, 0) for key in (b"a", b"b")]
    output = native.prepare_store(
        keys, context, trigger=getattr(base, "StoreTrigger").ON_COMPUTE
    )
    assert output is not None
    native.on_request_finished(context)
    assert not policy.book.references
    native.complete_store(
        keys, context, trigger=getattr(base, "StoreTrigger").ON_COMPUTE
    )
    held = dict(policy.book.references)
    assert len(held) == 2
    observation = next(iter(policy.observations.values()))
    assert observation.deadline_ns == now[0] + 12_000_000_000
    assert policy.evict(4, set()) is None and policy.book.references == held
    now[0] += 12_000_000_001
    evicted = policy.evict(1, set())
    assert evicted is not None and len(evicted) == 1 and not policy.book.references
    native.reset_cache()
    context, _ = request_fixture(owner, "again", "t", 1, [b"c", b"d"], False)
    native.on_new_request(context)
    _store_keys(native, context, [b"c", b"d"])
    native.on_request_finished(context)
    assert len(policy.book.references) == 2
    returned, _ = request_fixture(owner, "return", "t", 2, [b"c", b"d"], False)
    native.on_new_request(returned)
    held = dict(policy.book.references)
    assert policy.evict(0, set()) == [] and policy.book.references == held
    now[0] += 30_000_000_000
    assert policy.evict(4, set()) is None and policy.book.references == held
    assert policy.outcomes["return_pending"] == 1
    returned_keys = [base.make_offload_key(key, 0) for key in (b"c", b"d")]
    native.prepare_load(returned_keys, returned)
    assert not policy.book.references
    native.complete_load(returned_keys, returned)
    native.on_request_finished(returned)
    assert len(policy.book.references) == 2
    filler, _ = request_fixture(owner, "filler", "u", 1, [b"e", b"f", b"g"], False)
    native.on_new_request(filler)
    _store_keys(native, filler, [b"e", b"f", b"g"])
    assert policy.outcomes.get("hold_yield", 0) >= 1
    native.reset_cache()
    return {
        "hold_starts_at_finish_without_hint": True,
        "deadline_ms": 12000,
        "expiry_releases": True,
        "arrival_keeps_hold_until_load": True,
        "load_releases_and_finish_reholds": True,
        "yields_before_store_failure": True,
    }


def _post_response() -> dict[str, Any]:
    native, owner = policy_fixture("PostResponseLRU", 4, VARIANTS)
    policy = native._policy
    assert isinstance(policy, PostResponseLRU)
    now = [1_000_000_000]
    policy.clock = lambda: now[0]
    context, action = request_fixture(owner, "first", "s", 1, [b"a", b"b"])
    native.on_new_request(context)
    _store_keys(native, context, [b"a", b"b"])
    native.on_request_finished(context)
    assert not policy.book.references
    long_action = PolicyAction.parse(action | {"ttl_ms": 150000})
    acknowledgement = policy.publish_envelope(
        PolicyEnvelope("first", (long_action,)).to_dict()
    )
    assert acknowledgement["actions"][0]["decision"] == "held"
    observation = next(iter(policy.observations.values()))
    assert observation.deadline_ns == now[0] + 150_000_000_000
    capped = PolicyAction.parse(action | {"action_id": "second", "ttl_ms": 900000})
    policy.publish(capped.to_dict())
    assert observation.deadline_ns == now[0] + 300_000_000_000
    cancel = PolicyAction.parse(action | {"action_id": "done", "kind": "cancel"})
    assert policy.publish(cancel.to_dict())["decision"] == "cancelled"
    assert not policy.book.references
    native.reset_cache()
    return {
        "request_ttl_ignored": True,
        "envelope_held": True,
        "server_clamp_ms": 300000,
        "cancel_releases": True,
    }


def observe_policy_variants() -> dict[str, Any]:
    return {
        "schema": "pr-policy-variant-observation-v1",
        "AutomaticHoldLRU": _automatic(),
        "PostResponseLRU": _post_response(),
        "scope": "CPU fixtures on frozen main; no serving or GPU qualification",
    }

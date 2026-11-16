from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from vllm.v1.kv_offload.cpu.policies import arc, lru
from vllm.v1.kv_offload.cpu.policies.base import CachePolicy

from wait_hint_offload.discussion_protocol import (
    ACK_SCHEMA,
    ENVELOPE_SCHEMA,
    Advice,
    AdviceEnvelope,
)
from wait_hint_offload.policy_holds import HoldDecision
from wait_hint_offload.vllm_adapter.policy import PolicyObservation, WaitHoldPolicy
from wait_hint_offload.vllm_adapter.policy_context import PolicyPrefix

MS = 1_000_000
PENDING_LIMIT = 4096
REPLY_LIMIT = 65536


@dataclass
class Plan:
    finished_ns: int
    expiry_ns: int
    expected_ns: int | None = None
    keep_tokens: int | None = None
    arrived_ns: int | None = None
    held: bool = False
    partial: bool = False


class DiscussionHold(WaitHoldPolicy):
    request_ttl = False
    automatic_ms = 30_000
    request_deadline_ms = 120_000
    accepts_advice = False
    uncapped = False

    def __init__(self, cache_capacity: int):
        super().__init__(cache_capacity)
        if self.uncapped:
            self.book.limit = cache_capacity
        self.plans: dict[str, Plan] = {}
        self.dirty: set[str] = set()
        self.demoted: set[bytes] = set()
        self.lost: set[bytes] = set()
        self.first_owner: dict[bytes, str] = {}
        self.shared: set[bytes] = set()
        self.pending: OrderedDict[str, Advice] = OrderedDict()
        self.replies: OrderedDict[tuple[str, str], tuple[Advice, str]] = OrderedDict()

    def _rank(self, owner: str, now: int) -> float:
        plan = self.plans.get(owner)
        if plan is None:
            return math.inf
        if plan.arrived_ns is not None:
            return -math.inf
        if plan.expected_ns is not None and now < plan.expected_ns:
            return float(plan.expected_ns - now)
        return float(now - plan.finished_ns)

    def _boundary_keys(self, prefix: PolicyPrefix, boundary: int) -> frozenset[bytes]:
        partial = boundary % prefix.alignment_tokens != 0
        return frozenset(
            key
            for group in prefix.groups
            for key in group.required_keys(boundary, partial, prefix.tokens_per_hash)
        )

    def _step(self, prefix: PolicyPrefix) -> int:
        return (
            prefix.tokens_per_hash if prefix.partial_tail else prefix.alignment_tokens
        )

    def _ready(self, key: bytes) -> bool:
        chunk = self.native.get(key)
        return chunk is not None and chunk.is_ready

    def _extent(self, owner: str, plan: Plan) -> tuple[int, frozenset[bytes]]:
        prefix = self.observations[owner].prefix
        step = self._step(prefix)
        boundary = prefix.complete_tokens
        for group in prefix.groups:
            if group.window_chunks is None:
                count = 0
                for key in group.keys:
                    if not self._ready(key):
                        break
                    count += 1
                extra = prefix.alignment_tokens - 1 if prefix.partial_tail else 0
                boundary = min(boundary, count * group.tokens_per_chunk + extra)
        if plan.keep_tokens is not None:
            boundary = min(boundary, plan.keep_tokens)
        boundary = boundary // step * step
        while boundary > 0:
            keys = self._boundary_keys(prefix, boundary)
            if all(self._ready(key) for key in keys):
                return boundary, keys
            boundary -= step
        return 0, frozenset()

    def _fits(self, owner: str, keys: frozenset[bytes]) -> bool:
        references = self.book.references
        old = self.book.leases.get(owner)
        added = sum(key not in references for key in keys)
        removed = (
            sum(key not in keys and references[key] == 1 for key in old.keys)
            if old is not None
            else 0
        )
        return len(references) + added - removed <= self.book.limit

    def _leading(self, owner: str, boundary: int) -> frozenset[bytes]:
        prefix = self.observations[owner].prefix
        step = self._step(prefix)
        low, high = 0, boundary // step
        while low < high:
            middle = (low + high + 1) // 2
            if self._fits(owner, self._boundary_keys(prefix, middle * step)):
                low = middle
            else:
                high = middle - 1
        return self._boundary_keys(prefix, low * step) if low else frozenset()

    def _hold(self, owner: str, plan: Plan, keys: frozenset[bytes]) -> str:
        observation = self.observations[owner]
        return self.book.hold(
            owner,
            observation.session.generation,
            plan.expiry_ns,
            keys,
            self.clock(),
        ).value

    def _release(self, owner: str, reason: str) -> None:
        lease = self.book.leases.get(owner)
        if lease is not None:
            self.lost.update(lease.keys)
        self.book.release(owner)
        plan = self.plans.get(owner)
        if plan is not None:
            plan.held = False
            plan.partial = False
        self._count(reason)

    def _admit(self, owner: str) -> str:
        now = self.clock()
        plan = self.plans.get(owner)
        if (
            not self.advice_enabled
            or plan is None
            or plan.expiry_ns <= now
            or owner not in self.observations
        ):
            return "inactive"
        boundary, keys = self._extent(owner, plan)
        if not keys:
            if plan.held:
                self._release(owner, "hold_emptied")
            return "inactive"
        limit = HoldDecision.PHYSICAL_LIMIT.value
        decision = self._hold(owner, plan, keys)
        rank = self._rank(owner, now)
        while decision == limit:
            lower = [
                other
                for other in self.book.leases
                if other != owner and self._rank(other, now) > rank
            ]
            if not lower:
                break
            victim = max(lower, key=lambda other: self._rank(other, now))
            self._release(victim, "hold_displaced")
            decision = self._hold(owner, plan, keys)
        if decision == HoldDecision.HELD.value:
            plan.held, plan.partial = True, False
            self.lost.difference_update(keys)
            return decision
        if decision == limit:
            leading = self._leading(owner, boundary)
            if leading and self._hold(owner, plan, leading) == HoldDecision.HELD.value:
                plan.held, plan.partial = True, True
                self.lost.difference_update(leading)
                self._count("partial_hold")
                return HoldDecision.HELD.value
        if plan.held:
            self._release(owner, "hold_lost")
        self._count("intention")
        return decision

    def _readmit(self) -> None:
        now = self.clock()
        for owner in tuple(self.dirty):
            plan = self.plans.get(owner)
            if plan is not None and plan.held:
                self._admit(owner)
        self.dirty.clear()
        waiting = sorted(
            (
                owner
                for owner, plan in self.plans.items()
                if not plan.held and plan.expiry_ns > now
            ),
            key=lambda owner: self._rank(owner, now),
        )
        for owner in waiting:
            if self._admit(owner) == HoldDecision.HELD.value:
                self._count("readmitted")

    def _expire(self, now: int) -> None:
        self.book.expire(now)
        for owner, plan in tuple(self.plans.items()):
            if plan.expiry_ns <= now:
                self.book.release(owner)
                del self.plans[owner]
                self._count("plan_expired" if plan.held else "intention_expired")
        for owner, observation in tuple(self.observations.items()):
            if observation.expires_ns <= now:
                self._retire(owner)
        if self.scheduler is not None and self.plans:
            for state in tuple(self.scheduler._req_status.values()):
                self._notice_return(state.req_context)

    def _maintain(self) -> None:
        self._expire(self.clock())
        self._readmit()

    def _retire(self, owner: str) -> None:
        super()._retire(owner)
        self.plans.pop(owner, None)
        self.dirty.discard(owner)

    def _refresh(self, observation: PolicyObservation) -> str:
        self.dirty.add(observation.session.owner)
        return "deferred"

    def _notice_return(self, context: Any) -> None:
        session = self._session(context)
        if session is None:
            return
        plan = self.plans.get(session.owner)
        observation = self.observations.get(session.owner)
        if (
            plan is None
            or plan.arrived_ns is not None
            or observation is None
            or session.generation <= observation.session.generation
        ):
            return
        now = self.clock()
        plan.arrived_ns = now
        plan.expiry_ns = now + self.request_deadline_ms * MS
        observation.expires_ns = max(observation.expires_ns, plan.expiry_ns)
        self._count("arrived_held" if plan.held else "arrived_unheld")
        self._admit(session.owner)

    def _note_owner(self, owner: str, keys: Iterable[bytes]) -> None:
        for key in keys:
            first = self.first_owner.setdefault(key, owner)
            if first != owner:
                self.shared.add(key)
            self.demoted.discard(key)
        if len(self.first_owner) > 4 * max(1, self.cache_capacity):
            self.first_owner = {
                key: value
                for key, value in self.first_owner.items()
                if self.native.get(key) is not None
            }
            self.shared.intersection_update(self.first_owner)

    def _forget(self, key: bytes) -> None:
        self.demoted.discard(key)
        self.lost.discard(key)
        self.first_owner.pop(key, None)
        self.shared.discard(key)

    def _demote(self, owner: str, keep_tokens: int) -> None:
        observation = self.observations.get(owner)
        if observation is None:
            return
        prefix = observation.prefix
        step = self._step(prefix)
        kept = (
            self._boundary_keys(prefix, keep_tokens // step * step)
            if keep_tokens >= step
            else frozenset()
        )
        candidates = {
            key
            for group in prefix.groups
            for key in group.all_keys()
            if key not in kept and self.native.get(key) is not None
        }
        safe = {key for key in candidates if key not in self.shared}
        self.demoted.update(safe)
        self.outcomes["demoted_chunks"] = self.outcomes.get("demoted_chunks", 0) + len(
            safe
        )
        self.outcomes["shared_kept_chunks"] = self.outcomes.get(
            "shared_kept_chunks", 0
        ) + (len(candidates) - len(safe))

    def _end(self, owner: str, event: str) -> None:
        plan = self.plans.pop(owner, None)
        if plan is not None:
            self.book.release(owner)
        self._demote(owner, 0)
        self._count(f"{event}_released")
        self._retire(owner)

    def on_request_access(self, keys: Iterable[bytes], req_context: Any) -> None:
        keys = tuple(keys)
        session = self._session(req_context)
        if session is not None:
            self._note_owner(session.owner, keys)
        super().on_request_access(keys, req_context)

    def on_request_finished(
        self,
        key_groups: Sequence[Sequence[bytes]],
        insertion_only_keys: set[bytes],
        reused_keys: set[bytes],
        req_context: Any,
    ) -> None:
        super().on_request_finished(
            key_groups, insertion_only_keys, reused_keys, req_context
        )
        session = self._session(req_context)
        if session is None:
            return
        owner = session.owner
        self._note_owner(owner, (key for group in key_groups for key in group))
        observation = self.observations.get(owner)
        if observation is None or observation.session != session:
            return
        pending = self.pending.pop(owner, None)
        if pending is not None and pending.session.generation != session.generation:
            pending = None
        if pending is not None and pending.event != "return":
            self._end(owner, pending.event)
            self._readmit()
            return
        plan = Plan(observation.finished_ns, observation.finished_ns)
        plan.expiry_ns = observation.finished_ns + self.automatic_ms * MS
        self.plans[owner] = plan
        if pending is not None:
            self._apply(owner, pending)
        observation.expires_ns = max(observation.expires_ns, plan.expiry_ns)
        self._count("finish_planned")
        self._admit(owner)
        self._readmit()

    def _apply(self, owner: str, advice: Advice) -> None:
        plan = self.plans[owner]
        if plan.arrived_ns is None:
            if advice.expiry_ms is not None:
                plan.expiry_ns = plan.finished_ns + advice.expiry_ms * MS
            plan.expected_ns = (
                None
                if advice.expected_return_ms is None
                else plan.finished_ns + advice.expected_return_ms * MS
            )
        if advice.keep_tokens is not None:
            plan.keep_tokens = advice.keep_tokens
            self._demote(owner, advice.keep_tokens)
            self._count("keep_applied")
        observation = self.observations[owner]
        observation.expires_ns = max(observation.expires_ns, plan.expiry_ns)

    def _advise(self, advice: Advice) -> str:
        if not self.accepts_advice:
            self._count("advice_disabled")
            return "disabled"
        owner = advice.session.owner
        reply_key = (owner, advice.action_id)
        previous = self.replies.get(reply_key)
        if previous is not None:
            return "replayed" if previous[0] == advice else self._count("conflict")
        observation = self.observations.get(owner)
        if (
            observation is None
            or observation.session.generation < advice.session.generation
        ):
            self.pending[owner] = advice
            while len(self.pending) > PENDING_LIMIT:
                self.pending.popitem(last=False)
            decision = self._count("pending")
        elif observation.session != advice.session:
            decision = self._count("stale")
        elif advice.event != "return":
            self._end(owner, advice.event)
            decision = "ended"
        else:
            plan = self.plans.get(owner)
            if plan is None:
                plan = Plan(observation.finished_ns, observation.finished_ns)
                self.plans[owner] = plan
            self._apply(owner, advice)
            self._count(f"advice_{advice.event}")
            self._admit(owner)
            decision = "planned"
        self.replies[reply_key] = (advice, decision)
        while len(self.replies) > REPLY_LIMIT:
            self.replies.popitem(last=False)
        return decision

    def publish_envelope(self, raw: object) -> dict[str, Any]:
        if not isinstance(raw, dict) or raw.get("schema") != ENVELOPE_SCHEMA:
            return super().publish_envelope(raw)
        envelope = AdviceEnvelope.parse(raw)
        self._expire(self.clock())
        actions = [
            {"action_id": advice.action_id, "decision": self._advise(advice)}
            for advice in envelope.actions
        ]
        self._readmit()
        return {
            "schema": ACK_SCHEMA,
            "message_id": envelope.message_id,
            "accepted_ns": self.clock(),
            "actions": actions,
        }

    def mark_evictable(self, key: bytes) -> None:
        self.native.mark_evictable(key)
        self._expire(self.clock())
        self.dirty.update(self.key_owners.get(key, ()))

    def remove(self, key: bytes) -> None:
        super().remove(key)
        self._forget(key)

    def _available(self, n: int, protected: set[bytes]) -> bool:
        tables = (
            (self.native.chunks,)
            if hasattr(self.native, "chunks")
            else (self.native.t1, self.native.t2)
        )
        available = 0
        for table in tables:
            for key, chunk in table.items():
                if chunk.ref_cnt == 0 and key not in protected:
                    available += 1
                    if available >= n:
                        return True
        return False

    def _evict_native(self, n: int, protected: set[bytes]) -> Any:
        now = self.clock()
        while self.book.references:
            result = self.native.evict(n, self.book.protection(protected))
            if result is not None:
                return result
            if not self._available(n, protected) or not self.book.leases:
                return None
            victim = max(self.book.leases, key=lambda owner: self._rank(owner, now))
            self._release(victim, "hold_yield")
            self.book.yields += 1
        return self.native.evict(n, protected)

    def evict(self, n: int, protected: set[bytes]) -> Any:
        self._expire(self.clock())
        if n == 0:
            return []
        demoted = []
        for key in tuple(self.demoted):
            chunk = self.native.get(key)
            if chunk is None:
                self.demoted.discard(key)
                continue
            if (
                chunk.ref_cnt == 0
                and key not in protected
                and key not in self.book.references
            ):
                demoted.append((key, chunk))
                if len(demoted) == n:
                    break
        guard = set(protected) | {key for key, _ in demoted} if demoted else protected
        rest = self._evict_native(n - len(demoted), guard) if n > len(demoted) else []
        if rest is None:
            return None
        for key, _ in demoted:
            self.native.remove(key)
        lost = sum(key in self.lost for key, _ in rest)
        for key, _ in (*demoted, *rest):
            self._forget(key)
        if demoted:
            self.outcomes["demoted_evictions"] = self.outcomes.get(
                "demoted_evictions", 0
            ) + len(demoted)
        if lost:
            self.outcomes["lost_protection_evictions"] = (
                self.outcomes.get("lost_protection_evictions", 0) + lost
            )
        return [*demoted, *rest]

    def clear(self) -> None:
        super().clear()
        self.plans.clear()
        self.dirty.clear()
        self.demoted.clear()
        self.lost.clear()
        self.first_owner.clear()
        self.shared.clear()
        self.pending.clear()
        self.replies.clear()


def _variant(name: str, native: Any, **fields: Any) -> Any:
    return type(name, (DiscussionHold, CachePolicy), {"native_class": native} | fields)


AutoHoldLRU = _variant("AutoHoldLRU", lru.LRUCachePolicy)
AutoHoldARC = _variant("AutoHoldARC", arc.ARCCachePolicy)
AutoHold300LRU = _variant("AutoHold300LRU", lru.LRUCachePolicy, automatic_ms=300_000)
AdvisedHoldLRU = _variant("AdvisedHoldLRU", lru.LRUCachePolicy, accepts_advice=True)
AdvisedHoldARC = _variant("AdvisedHoldARC", arc.ARCCachePolicy, accepts_advice=True)
AdvisedUncappedLRU = _variant(
    "AdvisedUncappedLRU", lru.LRUCachePolicy, accepts_advice=True, uncapped=True
)

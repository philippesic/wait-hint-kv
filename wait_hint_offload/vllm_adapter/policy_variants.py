from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vllm.v1.kv_offload.cpu.policies import lru
from vllm.v1.kv_offload.cpu.policies.base import CachePolicy

from wait_hint_offload.policy_holds import HoldDecision
from wait_hint_offload.policy_protocol import PolicyAction
from wait_hint_offload.vllm_adapter.policy import PolicyObservation, WaitHoldPolicy
from wait_hint_offload.vllm_adapter.policy_context import PolicyPrefix

AUTOMATIC_HOLD_MS = 12000
STRENGTHENED_HOLD_MS = 30000
RETURN_PENDING_MS = 120000
HINT_CLAMP_MS = 300000


class ReturnAwareHold(WaitHoldPolicy):
    def __init__(self, cache_capacity: int):
        super().__init__(cache_capacity)
        self.pending_returns: set[str] = set()

    def _retire(self, owner: str) -> None:
        super()._retire(owner)
        self.pending_returns.discard(owner)

    def publish(
        self, raw: object, deadline_origin_ns: int | None = None
    ) -> dict[str, Any]:
        origin = self.clock() if deadline_origin_ns is None else deadline_origin_ns
        result = super().publish(raw, deadline_origin_ns=origin)
        if result["replayed"] or not self.advice_enabled:
            return result
        try:
            action = PolicyAction.parse(raw)
        except (TypeError, ValueError):
            return result
        observation = self.observations.get(action.session.owner)
        if (
            action.kind != "hold"
            or action.ttl_ms <= 60000
            or observation is None
            or observation.session != action.session
            or observation.deadline_ns <= 0
        ):
            return result
        observation.deadline_ns = origin + min(action.ttl_ms, HINT_CLAMP_MS) * 1_000_000
        observation.expires_ns = max(observation.expires_ns, observation.deadline_ns)
        self._refresh(observation)
        return result

    def _maintain(self) -> None:
        now = self.clock()
        self.book.expire(now)
        for owner, expired in tuple(self.observations.items()):
            if expired.expires_ns <= now:
                self._retire(owner)
        if self.scheduler is None or not self.observations:
            return
        for state in tuple(self.scheduler._req_status.values()):
            session = self._session(state.req_context)
            if session is None or session.owner in self.pending_returns:
                continue
            observation = self.observations.get(session.owner)
            if (
                observation is None
                or session.generation <= observation.session.generation
            ):
                continue
            self._arrive(session.owner, observation, now)

    def _arrive(self, owner: str, observation: PolicyObservation, now: int) -> None:
        self.pending_returns.add(owner)
        self._count("return_pending")
        if observation.deadline_ns > now:
            observation.deadline_ns = now + RETURN_PENDING_MS * 1_000_000
            observation.expires_ns = max(
                observation.expires_ns, observation.deadline_ns
            )
            self._refresh(observation)


class AutomaticHold(ReturnAwareHold):
    request_ttl = False
    automatic_ms = AUTOMATIC_HOLD_MS

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
        observation = self.observations.get(session.owner)
        if observation is None or observation.session != session:
            return
        action = PolicyAction(
            f"automatic-{session.generation}", session, "hold", self.automatic_ms
        )
        self.publish(action.to_dict(), deadline_origin_ns=observation.finished_ns)


class LeaseHold(AutomaticHold):
    automatic_ms = STRENGTHENED_HOLD_MS

    def _notice_return(self, context: Any) -> None:
        session = self._session(context)
        if session is None or session.owner in self.pending_returns:
            return
        observation = self.observations.get(session.owner)
        if (
            observation is not None
            and session.generation > observation.session.generation
        ):
            self._arrive(session.owner, observation, self.clock())

    def _finished(self, owner: str) -> int:
        observation = self.observations.get(owner)
        return 0 if observation is None else observation.finished_ns

    def _drop(self, owner: str, decision: str) -> None:
        self.book.release(owner)
        observation = self.observations.get(owner)
        if observation is not None:
            observation.deadline_ns = 0
        self._count(decision)

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

    def _leading_keys(self, prefix: PolicyPrefix, owner: str) -> frozenset[bytes]:
        alignment = prefix.alignment_tokens
        step = prefix.tokens_per_hash if prefix.partial_tail else alignment
        boundary = prefix.complete_tokens // step * step
        while boundary > 0:
            partial = boundary % alignment != 0
            keys = frozenset(
                key
                for group in prefix.groups
                for key in group.required_keys(
                    boundary, partial, prefix.tokens_per_hash
                )
            )
            if self._fits(owner, keys) and all(
                (chunk := self.native.get(key)) is not None and chunk.is_ready
                for key in keys
            ):
                return keys
            boundary -= step
        return frozenset()

    def _hold(self, observation: PolicyObservation, keys: frozenset[bytes]) -> str:
        return self.book.hold(
            observation.session.owner,
            observation.session.generation,
            observation.deadline_ns,
            keys,
            self.clock(),
        ).value

    def _refresh(self, observation: PolicyObservation) -> str:
        if not self.advice_enabled or observation.deadline_ns <= self.clock():
            return "inactive"
        owner = observation.session.owner
        arrived = owner in self.pending_returns
        limit = HoldDecision.PHYSICAL_LIMIT.value
        decision = self._hold(observation, self._ready_keys(observation.prefix))
        while decision == limit:
            lower = [
                other
                for other in self.book.leases
                if other != owner
                and other not in self.pending_returns
                and (arrived or self._finished(other) < observation.finished_ns)
            ]
            if not lower:
                break
            self._drop(min(lower, key=self._finished), "hold_displaced")
            decision = self._hold(observation, self._ready_keys(observation.prefix))
        if decision != limit:
            return decision
        state = "arrived" if arrived else "waiting"
        keys = self._leading_keys(observation.prefix, owner)
        if keys and self._hold(observation, keys) == HoldDecision.HELD.value:
            self._count(f"{state}_partial_hold")
            return HoldDecision.HELD.value
        self._count(f"{state}_hold_refused")
        return decision

    def _victim(self) -> str | None:
        if not self.book.leases:
            return None
        return min(
            self.book.leases,
            key=lambda owner: (owner in self.pending_returns, self._finished(owner)),
        )

    def evict(self, n: int, protected: set[bytes]) -> Any:
        self._maintain()
        while self.book.references:
            result = self.native.evict(n, self.book.protection(protected))
            if result is not None:
                return result
            available = sum(
                chunk.ref_cnt == 0 and key not in protected
                for key, chunk in self.native.chunks.items()
            )
            if available < n:
                return None
            owner = self._victim()
            if owner is None:
                break
            self._drop(owner, "hold_yield")
            self.book.yields += 1
        return self.native.evict(n, protected)


AutomaticHoldLRU = type(
    "AutomaticHoldLRU",
    (AutomaticHold, CachePolicy),
    {"native_class": lru.LRUCachePolicy},
)
PostResponseLRU = type(
    "PostResponseLRU",
    (ReturnAwareHold, CachePolicy),
    {"native_class": lru.LRUCachePolicy, "request_ttl": False},
)
StrengthenedHoldLRU = type(
    "StrengthenedHoldLRU",
    (LeaseHold, CachePolicy),
    {"native_class": lru.LRUCachePolicy},
)

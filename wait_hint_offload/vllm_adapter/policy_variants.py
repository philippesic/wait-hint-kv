from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vllm.v1.kv_offload.cpu.policies import lru
from vllm.v1.kv_offload.cpu.policies.base import CachePolicy

from wait_hint_offload.policy_protocol import PolicyAction
from wait_hint_offload.vllm_adapter.policy import WaitHoldPolicy

AUTOMATIC_HOLD_MS = 12000
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
        for owner, observation in tuple(self.observations.items()):
            if observation.expires_ns <= now:
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
            self.pending_returns.add(session.owner)
            self._count("return_pending")
            if observation.deadline_ns > now:
                observation.deadline_ns = now + RETURN_PENDING_MS * 1_000_000
                observation.expires_ns = max(
                    observation.expires_ns, observation.deadline_ns
                )
                self._refresh(observation)


class AutomaticHold(ReturnAwareHold):
    request_ttl = False

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
            f"automatic-{session.generation}", session, "hold", AUTOMATIC_HOLD_MS
        )
        self.publish(action.to_dict(), deadline_origin_ns=observation.finished_ns)


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

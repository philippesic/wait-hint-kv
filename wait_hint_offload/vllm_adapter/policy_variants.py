from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vllm.v1.kv_offload.cpu.policies import lru
from vllm.v1.kv_offload.cpu.policies.base import CachePolicy

from wait_hint_offload.policy_protocol import PolicyAction
from wait_hint_offload.vllm_adapter.policy import WaitHoldPolicy

AUTOMATIC_HOLD_MS = 12000


class AutomaticHold(WaitHoldPolicy):
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
    (WaitHoldPolicy, CachePolicy),
    {"native_class": lru.LRUCachePolicy, "request_ttl": False},
)

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request

from wait_hint_offload.discussion_protocol import (
    AdviceEnvelope,
    validate_advice_acknowledgement,
)
from wait_hint_offload.vllm_adapter.evidence_endpoint import EvidenceEndpoint, _client


class DiscussionEndpoint(EvidenceEndpoint):
    name = "pr_discussion"

    def attach_router(self, app: FastAPI) -> None:
        super().attach_router(app)
        app.post("/v1/pr-evidence/advice")(self.advise)

    async def advise(self, request: Request) -> dict[str, Any]:
        engine = _client(request)
        try:
            envelope = AdviceEnvelope.parse(await request.json())
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        result = await engine.engine_core.call_utility_async(
            "publish_kv_cache_hints", envelope.to_dict()
        )
        try:
            return validate_advice_acknowledgement(result, envelope)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

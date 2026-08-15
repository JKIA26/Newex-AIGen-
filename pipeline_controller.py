from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipelines import invoice_processing
from tracing.trace_context import new_trace_id, new_session_id

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

_PIPELINES = {
    "invoice_processing": invoice_processing,
    # add support_triage, lead_followup, ops_handoff, etc. as they're implemented
}


class RunPipelineRequest(BaseModel):
    org_id: str
    input: dict


@router.post("/{pipeline_name}/run")
def run_pipeline(pipeline_name: str, req: RunPipelineRequest):
    module = _PIPELINES.get(pipeline_name)
    if module is None:
        raise HTTPException(status_code=404, detail=f"Unknown pipeline: {pipeline_name}")

    session_id = new_session_id()
    trace_id = new_trace_id()

    result = module.run(
        session_id=session_id,
        trace_id=trace_id,
        org_id=req.org_id,
        file_content_hash=req.input.get("file_content_hash", ""),
        extra_fields=req.input.get("extra_fields"),
    )
    return result.model_dump()

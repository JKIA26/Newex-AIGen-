from __future__ import annotations
from fastapi import APIRouter

from tracing.audit_log import get_trace_events

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("/{trace_id}")
def get_trace(trace_id: str):
    return {"trace_id": trace_id, "events": get_trace_events(trace_id)}

"""
Trace ID generation and propagation (Langfuse/Braintrust-style).
Every session gets one trace_id at creation; every tool call, pipeline
step, and agent decision is logged against it via audit_log.py.
"""
from __future__ import annotations
import uuid
import contextvars
from datetime import datetime, timezone

_current_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_trace_id", default=None
)


def new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:12]}"


def new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:12]}"


def set_current_trace(trace_id: str) -> None:
    _current_trace_id.set(trace_id)


def get_current_trace() -> str | None:
    return _current_trace_id.get()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

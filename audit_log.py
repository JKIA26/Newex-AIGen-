"""
Audit logging — every tool call, pipeline step, and agent decision is
recorded here, tagged with trace_id. Backing store is in-memory for this
scaffold; swap for the real audit log table (per security-architecture.md
provenance requirements) before this goes near production.
"""
from __future__ import annotations
from typing import Any
from tracing.trace_context import utc_now_iso

_audit_log: list[dict[str, Any]] = []


def log_event(trace_id: str, event_type: str, detail: dict[str, Any]) -> None:
    _audit_log.append(
        {
            "trace_id": trace_id,
            "timestamp": utc_now_iso(),
            "event_type": event_type,
            "detail": detail,
        }
    )


def get_trace_events(trace_id: str) -> list[dict[str, Any]]:
    return [e for e in _audit_log if e["trace_id"] == trace_id]

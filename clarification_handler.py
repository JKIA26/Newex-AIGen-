"""
Generates a `form` UI schema block (§F) from a pipeline's missing_fields,
so the frontend can render exactly the inputs needed to resume a paused
session — no hardcoded per-pipeline forms.
"""
from __future__ import annotations
from schemas.ui_schemas import UIUpdate, UIBlockType, FormPayload, FormField


def build_clarification_form(session_id: str, trace_id: str, missing_fields: list[str]) -> UIUpdate:
    fields = [
        FormField(name=f, label=f.replace("_", " ").title(), type="text", required=True)
        for f in missing_fields
    ]
    return UIUpdate(
        type=UIBlockType.FORM,
        session_id=session_id,
        trace_id=trace_id,
        payload=FormPayload(fields=fields, submit_action=f"/sessions/{session_id}/resume"),
    )

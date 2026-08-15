"""
support_triage pipeline (Tier 2) — implements the workflow documented in
support/support-operations.md.

  ticket (subject, body) -> validation.parse_and_validate (required fields)
                          -> classify (category, urgency, confidence)
                          -> rag.retrieve (knowledge base for category)
                          -> draft reply
                          -> gate: auto-send OR route to human
                          -> automation.execute_action (send or route)

The auto-send gate mirrors the restriction-first rail from
entitlement-role-sync-policy.md: when in doubt, route to a human.
"""
from __future__ import annotations
from typing import Any

from tools.registry import registry
from schemas.pipeline_schemas import PipelineStep, StepStatus, PipelineRunResult
from tracing.audit_log import log_event


REQUIRED_FIELDS = ["subject", "body"]

# support-operations.md §2 — category keyword signals (deterministic stub;
# swap for a real classifier tool/model before this handles real traffic).
_CATEGORY_KEYWORDS = {
    "billing": ["charge", "invoice", "refund", "billing", "payment"],
    "technical": ["error", "failing", "broken", "bug", "crash", "step 2"],
    "account": ["password", "login", "reset", "locked out", "account"],
    "feature_request": ["can you add", "feature", "would be nice", "request"],
}

# support-operations.md §3 — urgency escalation signals, independent of category.
_ESCALATION_SIGNALS = ["urgent", "production down", "asap", "critical"]


def _classify(subject: str, body: str) -> tuple[str, str, float]:
    text = f"{subject} {body}".lower()

    category = "general"
    best_hits = 0
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            category = cat

    # Confidence: naive stub proportional to keyword hits, capped at 0.95.
    # Real implementation: swap for router.route_request -> classifier model.
    confidence = min(0.5 + 0.15 * best_hits, 0.95) if best_hits > 0 else 0.4

    escalated = any(sig in text for sig in _ESCALATION_SIGNALS)
    if escalated:
        urgency = "high"
    elif category in ("billing", "technical"):
        urgency = "high"
    elif category == "account":
        urgency = "medium"
    else:
        urgency = "low"

    return category, urgency, confidence


def _should_auto_send(category: str, confidence: float, escalated: bool) -> bool:
    # support-operations.md §3 — all three must hold, or it routes to a human.
    if confidence < 0.85:
        return False
    if category == "billing":
        return False
    if escalated:
        return False
    return True


def run(
    session_id: str,
    trace_id: str,
    org_id: str,
    subject: str = "",
    body: str = "",
    extra_fields: dict[str, Any] | None = None,
) -> PipelineRunResult:
    steps: list[PipelineStep] = []
    extra_fields = extra_fields or {}
    raw_ticket = {"subject": subject, "body": body, **extra_fields}

    # Step 1: validate required ticket fields
    validate_result = registry.invoke(
        "validation.parse_and_validate",
        org_id=org_id,
        raw_input={"raw_input": raw_ticket, "target_schema": "support_ticket_fields"},
    )
    steps.append(PipelineStep(
        name="validate_ticket_fields",
        status=StepStatus.DONE if validate_result.valid else StepStatus.FAILED,
        output=validate_result.model_dump(),
    ))
    log_event(trace_id, "pipeline.step_completed", {"step": "validate_ticket_fields"})

    if not validate_result.valid or validate_result.parsed is None:
        return PipelineRunResult(
            session_id=session_id, trace_id=trace_id, pipeline_name="support_triage",
            steps=steps, final_output=None, status=StepStatus.FAILED,
        )

    parsed = validate_result.parsed
    missing = [f for f in REQUIRED_FIELDS if not parsed.get(f)]
    if missing:
        steps.append(PipelineStep(name="await_missing_fields", status=StepStatus.AWAITING_INPUT))
        return PipelineRunResult(
            session_id=session_id, trace_id=trace_id, pipeline_name="support_triage",
            steps=steps, final_output=None, status=StepStatus.AWAITING_INPUT, missing_fields=missing,
        )

    # Step 2: classify (category, urgency, confidence)
    category, urgency, confidence = _classify(parsed["subject"], parsed["body"])
    escalated = urgency == "high" and any(
        sig in f"{parsed['subject']} {parsed['body']}".lower() for sig in _ESCALATION_SIGNALS
    )
    steps.append(PipelineStep(
        name="classify_ticket",
        status=StepStatus.DONE,
        output={"category": category, "urgency": urgency, "confidence": confidence},
    ))
    log_event(trace_id, "pipeline.step_completed", {"step": "classify_ticket"})

    # Step 3: retrieve knowledge base context for this category
    retrieve_result = registry.invoke(
        "rag.retrieve",
        org_id=org_id,
        raw_input={"query": category, "index_id": f"kb_{org_id}", "top_k": 3, "filters": {}},
    )
    steps.append(PipelineStep(
        name="retrieve_knowledge_base",
        status=StepStatus.DONE,
        output=retrieve_result.model_dump(),
    ))
    log_event(trace_id, "pipeline.step_completed", {"step": "retrieve_knowledge_base"})

    # Step 4: draft reply (stub — real implementation routes through a model)
    draft_reply = (
        f"Thanks for reaching out about '{parsed['subject']}'. "
        f"This looks like a {category} issue — here's what we found: "
        f"{retrieve_result.chunks[0].text if retrieve_result.chunks else 'no matching KB article found'}."
    )
    steps.append(PipelineStep(name="draft_reply", status=StepStatus.DONE, output={"draft_reply": draft_reply}))

    # Step 5: gate — auto-send or route to human (support-operations.md §3)
    auto_send = _should_auto_send(category, confidence, escalated)
    action_id = "send_ticket_reply" if auto_send else "route_ticket_to_human"

    automation_result = registry.invoke(
        "automation.execute_action",
        org_id=org_id,
        raw_input={
            "platform": "n8n",
            "action_id": action_id,
            "params": {"category": category, "urgency": urgency, "draft_reply": draft_reply},
            "org_id": org_id,
        },
    )
    steps.append(PipelineStep(
        name="auto_send" if auto_send else "route_to_human",
        status=StepStatus.DONE if automation_result.status == "success" else StepStatus.FAILED,
        output=automation_result.model_dump(),
    ))
    log_event(trace_id, "pipeline.step_completed", {"step": "gate_decision", "auto_send": auto_send})

    final_output = {
        "category": category,
        "urgency": urgency,
        "confidence": confidence,
        "draft_reply": draft_reply,
        "action_taken": "auto_sent" if auto_send else "routed_to_human",
        "external_ref": automation_result.external_ref,
    }

    return PipelineRunResult(
        session_id=session_id, trace_id=trace_id, pipeline_name="support_triage",
        steps=steps, final_output=final_output,
        status=StepStatus.DONE if automation_result.status == "success" else StepStatus.FAILED,
    )

"""
router.route_request — optional multi-model routing + compliance guardrails
(Portkey-style). Selects a model per task_type and surfaces guardrail flags;
never itself decides to bypass a flag it raises.
"""
from __future__ import annotations
from schemas.tool_schemas import RouteRequestInput, RouteRequestOutput

# TODO: replace with real routing logic / Portkey-style gateway config.
_TASK_MODEL_MAP = {
    "content_generation": "claude-sonnet-5",
    "classification": "claude-haiku-4-5-20251001",
    "code": "claude-sonnet-5",
}


def route_request(input_data: RouteRequestInput) -> RouteRequestOutput:
    model = _TASK_MODEL_MAP.get(input_data.task_type, "claude-sonnet-5")

    guardrail_flags: list[str] = []
    if "medical" in input_data.compliance_tags:
        guardrail_flags.append("requires_clinician_review")
    if "financial" in input_data.compliance_tags:
        guardrail_flags.append("requires_risk_gate")

    return RouteRequestOutput(
        selected_model=model,
        routing_reason=f"task_type={input_data.task_type}",
        guardrail_flags=guardrail_flags,
    )

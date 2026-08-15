"""
invoice_processing pipeline (Tier 2) — matches
agent-orchestration-architecture.md §G exactly:

  uploaded file -> validation.parse_and_validate (extract fields)
                -> [pause for missing field if needed]
                -> automation.execute_action (post to accounting system)
                -> structured confirmation output
"""
from __future__ import annotations
from typing import Any

from tools.registry import registry
from schemas.pipeline_schemas import PipelineStep, StepStatus, PipelineRunResult
from tracing.audit_log import log_event
from services import storage_service


REQUIRED_FIELDS = ["vendor", "amount", "due_date", "po_number"]


def run(
    session_id: str,
    trace_id: str,
    org_id: str,
    file_content_hash: str,
    extra_fields: dict[str, Any] | None = None,
) -> PipelineRunResult:
    steps: list[PipelineStep] = []
    extra_fields = extra_fields or {}

    # Step 1: retrieve uploaded file content by hash, then validate/extract fields
    file_record = storage_service.get_file(file_content_hash)
    raw_extracted = {**(file_record.get("extracted_fields", {}) if file_record else {}), **extra_fields}

    validate_result = registry.invoke(
        "validation.parse_and_validate",
        org_id=org_id,
        raw_input={"raw_input": raw_extracted, "target_schema": "invoice_fields"},
    )
    steps.append(PipelineStep(
        name="extract_and_validate_fields",
        status=StepStatus.DONE if validate_result.valid else StepStatus.FAILED,
        output=validate_result.model_dump(),
    ))
    log_event(trace_id, "pipeline.step_completed", {"step": "extract_and_validate_fields"})

    if not validate_result.valid or validate_result.parsed is None:
        return PipelineRunResult(
            session_id=session_id, trace_id=trace_id, pipeline_name="invoice_processing",
            steps=steps, final_output=None, status=StepStatus.FAILED,
        )

    parsed = validate_result.parsed
    missing = [f for f in REQUIRED_FIELDS if not parsed.get(f)]
    if missing:
        steps.append(PipelineStep(name="await_missing_fields", status=StepStatus.AWAITING_INPUT))
        return PipelineRunResult(
            session_id=session_id, trace_id=trace_id, pipeline_name="invoice_processing",
            steps=steps, final_output=None, status=StepStatus.AWAITING_INPUT, missing_fields=missing,
        )

    # Step 2: post to accounting system via the automation tool (allowlisted action)
    automation_result = registry.invoke(
        "automation.execute_action",
        org_id=org_id,
        raw_input={
            "platform": "n8n",
            "action_id": "post_invoice_to_accounting",
            "params": parsed,
            "org_id": org_id,
        },
    )
    steps.append(PipelineStep(
        name="post_to_accounting",
        status=StepStatus.DONE if automation_result.status == "success" else StepStatus.FAILED,
        output=automation_result.model_dump(),
    ))
    log_event(trace_id, "pipeline.step_completed", {"step": "post_to_accounting"})

    final_output = {
        "vendor": parsed["vendor"],
        "amount": parsed["amount"],
        "status": "Posted" if automation_result.status == "success" else "Failed",
        "external_ref": automation_result.external_ref,
    }

    return PipelineRunResult(
        session_id=session_id, trace_id=trace_id, pipeline_name="invoice_processing",
        steps=steps, final_output=final_output,
        status=StepStatus.DONE if automation_result.status == "success" else StepStatus.FAILED,
    )

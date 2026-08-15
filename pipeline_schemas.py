"""
Pydantic schemas for pipeline (Tier 2) input/output and step tracking.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    AWAITING_INPUT = "awaiting_input"


class PipelineStep(BaseModel):
    name: str
    status: StepStatus
    output: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class PipelineRunRequest(BaseModel):
    pipeline_name: str
    input: dict[str, Any]
    org_id: str
    user_id: str
    session_id: Optional[str] = None


class PipelineRunResult(BaseModel):
    session_id: str
    trace_id: str
    pipeline_name: str
    steps: list[PipelineStep]
    final_output: Optional[dict[str, Any]] = None
    status: StepStatus
    missing_fields: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Invoice processing — concrete pipeline I/O (matches example G)
# ---------------------------------------------------------------------------
class InvoiceProcessingInput(BaseModel):
    file_content_hash: str
    org_id: str


class InvoiceFields(BaseModel):
    vendor: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None
    po_number: Optional[str] = None


class InvoiceProcessingOutput(BaseModel):
    vendor: str
    amount: float
    status: str
    external_ref: Optional[str] = None

"""
Generative UI JSON contracts streamed to the frontend.
Matches agent-orchestration-architecture.md §F exactly — the frontend
renders these blocks directly, no additional interpretation needed.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field


class UIBlockType(str, Enum):
    CHAT_MESSAGE = "chat_message"
    FORM = "form"
    PROGRESS = "progress"
    RESULT_CARD = "result_card"


class ChatMessagePayload(BaseModel):
    role: Literal["agent", "user"]
    text: str


class FormField(BaseModel):
    name: str
    label: str
    type: Literal["text", "number", "select", "file"]
    required: bool = True
    options: list[str] = Field(default_factory=list)


class FormPayload(BaseModel):
    fields: list[FormField]
    submit_action: str


class ProgressStep(BaseModel):
    name: str
    status: Literal["pending", "running", "done", "failed"]


class ProgressPayload(BaseModel):
    pipeline_name: str
    steps: list[ProgressStep]


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ResultCardPayload(BaseModel):
    title: str
    kind: Literal["chart", "text", "table"]
    data: dict[str, Any]
    severity: Severity = Severity.INFO
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class UIUpdate(BaseModel):
    """The single envelope streamed over WebSocket/SSE to the frontend."""
    type: UIBlockType
    session_id: str
    trace_id: str
    payload: Union[ChatMessagePayload, FormPayload, ProgressPayload, ResultCardPayload]


def require_severity_and_confidence(pipeline_name: str, payload: ResultCardPayload) -> None:
    """
    Structural enforcement of the 'findings for review' rule for sensitive
    pipelines (anomaly_detection, diagnostic_flagging). Call this before
    emitting a result_card from those pipelines — it's not optional.
    """
    sensitive_pipelines = {"anomaly_detection", "diagnostic_flagging"}
    if pipeline_name in sensitive_pipelines:
        if payload.severity is None or payload.confidence is None:
            raise ValueError(
                f"{pipeline_name} result_card must include severity and confidence — "
                "this is a hard requirement, not a default."
            )

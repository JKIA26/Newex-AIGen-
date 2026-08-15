"""
Pydantic schemas for every MCP tool's input/output.
Every tool call is validated against these before execution — no tool
accepts unvalidated free-form input. See agent-orchestration-architecture.md §B.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    REJECTED = "rejected"  # not in allowlist


# ---------------------------------------------------------------------------
# automation.execute_action
# ---------------------------------------------------------------------------
class AutomationPlatform(str, Enum):
    ZAPIER = "zapier"
    MAKE = "make"
    N8N = "n8n"


class AutomationActionInput(BaseModel):
    platform: AutomationPlatform
    action_id: str = Field(..., description="Must be a pre-registered, allowlisted action id")
    params: dict[str, Any] = Field(default_factory=dict)
    org_id: str


class AutomationActionOutput(BaseModel):
    status: ToolStatus
    result: dict[str, Any] = Field(default_factory=dict)
    external_ref: Optional[str] = None
    rejection_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# rag.index_document / rag.retrieve
# ---------------------------------------------------------------------------
class IndexDocumentInput(BaseModel):
    content_hash: str
    source_uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IndexDocumentOutput(BaseModel):
    index_id: str
    chunk_count: int
    status: ToolStatus


class RetrieveChunk(BaseModel):
    text: str
    score: float
    source: str


class RetrieveInput(BaseModel):
    query: str
    index_id: str
    top_k: int = 5
    filters: dict[str, Any] = Field(default_factory=dict)


class RetrieveOutput(BaseModel):
    chunks: list[RetrieveChunk]


# ---------------------------------------------------------------------------
# validation.parse_and_validate
# ---------------------------------------------------------------------------
class ParseValidateInput(BaseModel):
    raw_input: Any
    target_schema: str = Field(..., description="Registered schema name to validate against")


class ParseValidateOutput(BaseModel):
    valid: bool
    parsed: Optional[dict[str, Any]] = None
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# sandbox.execute_code
# ---------------------------------------------------------------------------
class SandboxLanguage(str, Enum):
    PYTHON = "python"
    JS = "js"


class SandboxExecInput(BaseModel):
    language: SandboxLanguage
    code: str
    timeout_s: int = Field(default=10, le=60)
    resource_limits: dict[str, Any] = Field(default_factory=dict)


class SandboxExecOutput(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    status: ToolStatus


# ---------------------------------------------------------------------------
# router.route_request
# ---------------------------------------------------------------------------
class RouteRequestInput(BaseModel):
    prompt: str
    task_type: str
    compliance_tags: list[str] = Field(default_factory=list)


class RouteRequestOutput(BaseModel):
    selected_model: str
    routing_reason: str
    guardrail_flags: list[str] = Field(default_factory=list)

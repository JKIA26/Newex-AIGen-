"""
Tool registry — the single choke point every tool call passes through.

Two hard rules enforced here, matching the entitlement allowlist rail
in entitlement-role-sync-policy.md:
  1. Input must validate against the tool's declared Pydantic schema.
  2. The requested action must be in the calling org's allowlist for
     that tool, or the call is REJECTED — never silently allowed.
"""
from __future__ import annotations
from typing import Any, Callable
from pydantic import BaseModel, ValidationError

from tracing.audit_log import log_event
from schemas.tool_schemas import ToolStatus


class ToolNotFoundError(Exception):
    pass


class ToolValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Tool input validation failed: {errors}")


class ToolNotAllowlistedError(Exception):
    pass


class RegisteredTool:
    def __init__(
        self,
        name: str,
        input_schema: type[BaseModel],
        output_schema: type[BaseModel],
        handler: Callable[[BaseModel], BaseModel],
        allowed_actions: set[str] | None = None,
    ):
        self.name = name
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.handler = handler
        # None means "no action-level restriction beyond the tool itself
        # being allowlisted for the org" — set explicitly per tool as needed.
        self.allowed_actions = allowed_actions


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}
        # org_id -> set of tool names that org may call at all
        self._org_tool_allowlist: dict[str, set[str]] = {}
        # (org_id, tool_name) -> set of allowed action_ids, for tools with sub-actions
        self._org_action_allowlist: dict[tuple[str, str], set[str]] = {}

    def register(self, tool: RegisteredTool) -> None:
        self._tools[tool.name] = tool

    def set_org_allowlist(self, org_id: str, tool_names: set[str]) -> None:
        self._org_tool_allowlist[org_id] = tool_names

    def set_org_action_allowlist(self, org_id: str, tool_name: str, action_ids: set[str]) -> None:
        self._org_action_allowlist[(org_id, tool_name)] = action_ids

    def invoke(self, tool_name: str, org_id: str, raw_input: dict[str, Any]) -> BaseModel:
        tool = self._tools.get(tool_name)
        if tool is None:
            raise ToolNotFoundError(f"No tool registered as '{tool_name}'")

        # Rail 1: org must be allowlisted for this tool at all
        org_tools = self._org_tool_allowlist.get(org_id, set())
        if tool_name not in org_tools:
            log_event(
                trace_id="n/a",
                event_type="tool.rejected",
                detail={"tool": tool_name, "org_id": org_id, "reason": "tool not in org allowlist"},
            )
            raise ToolNotAllowlistedError(f"Tool '{tool_name}' is not allowlisted for org '{org_id}'")

        # Rail 2: schema validation — never pass unvalidated input to a handler
        try:
            validated_input = tool.input_schema.model_validate(raw_input)
        except ValidationError as e:
            raise ToolValidationError([str(err) for err in e.errors()])

        # Rail 3: action-level allowlist, if this tool has sub-actions (e.g. automation)
        action_id = raw_input.get("action_id")
        if action_id and tool.allowed_actions is not None:
            org_actions = self._org_action_allowlist.get((org_id, tool_name), set())
            if action_id not in org_actions:
                return tool.output_schema.model_validate(
                    {
                        "status": ToolStatus.REJECTED,
                        "result": {},
                        "rejection_reason": f"Action '{action_id}' not allowlisted for org '{org_id}'",
                    }
                )

        result = tool.handler(validated_input)
        return result


# Module-level singleton — real deployments would inject this per-request
# or per-worker instead of a bare global, but this keeps the scaffold simple.
registry = ToolRegistry()

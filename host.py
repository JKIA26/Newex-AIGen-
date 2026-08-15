"""
MCP Host — lives inside agent-service. Registers every MCP tool server
into the shared ToolRegistry at startup, so tool_controller.py has one
consistent dispatch point regardless of which tool is being called.
"""
from __future__ import annotations

from tools.registry import registry, RegisteredTool
from tools import automation_tool, rag_retrieval_tool, data_validation_tool, model_router_tool
from schemas.tool_schemas import (
    AutomationActionInput,
    AutomationActionOutput,
    IndexDocumentInput,
    IndexDocumentOutput,
    RetrieveInput,
    RetrieveOutput,
    ParseValidateInput,
    ParseValidateOutput,
    RouteRequestInput,
    RouteRequestOutput,
)


def bootstrap_mcp_host() -> None:
    """Call once at app startup."""
    registry.register(
        RegisteredTool(
            name="automation.execute_action",
            input_schema=AutomationActionInput,
            output_schema=AutomationActionOutput,
            handler=lambda i: automation_tool.execute_automation_action(i),
            allowed_actions=set(),  # per-org overrides set via set_org_action_allowlist
        )
    )
    registry.register(
        RegisteredTool(
            name="rag.index_document",
            input_schema=IndexDocumentInput,
            output_schema=IndexDocumentOutput,
            handler=lambda i: rag_retrieval_tool.index_document(i),
        )
    )
    registry.register(
        RegisteredTool(
            name="rag.retrieve",
            input_schema=RetrieveInput,
            output_schema=RetrieveOutput,
            handler=lambda i: rag_retrieval_tool.retrieve(i),
        )
    )
    registry.register(
        RegisteredTool(
            name="validation.parse_and_validate",
            input_schema=ParseValidateInput,
            output_schema=ParseValidateOutput,
            handler=lambda i: data_validation_tool.parse_and_validate(i),
        )
    )
    registry.register(
        RegisteredTool(
            name="router.route_request",
            input_schema=RouteRequestInput,
            output_schema=RouteRequestOutput,
            handler=lambda i: model_router_tool.route_request(i),
        )
    )
    # NOTE: sandbox.execute_code intentionally not registered until a real
    # sandbox backend (sandboxes/code_exec_sandbox.py) is implemented —
    # registering a tool whose handler raises NotImplementedError would let
    # callers reach it and hit an ungraceful failure instead of a clean 404.


def seed_demo_allowlists() -> None:
    """
    Demo-only org allowlist seeding. Replace with real allowlist config
    pulled from the Role Policy Map (entitlement-role-sync-policy.md).
    """
    demo_org = "org_demo"
    registry.set_org_allowlist(
        demo_org,
        {"automation.execute_action", "rag.index_document", "rag.retrieve",
         "validation.parse_and_validate", "router.route_request"},
    )
    registry.set_org_action_allowlist(
        demo_org, "automation.execute_action", {"post_invoice_to_accounting"}
    )

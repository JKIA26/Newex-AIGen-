"""
automation.execute_action — dispatches to Zapier/Make/n8n-style platforms.
Stubbed here; real implementation calls each platform's API behind this
same interface so callers never need to know which platform is in use.
"""
from __future__ import annotations
from schemas.tool_schemas import AutomationActionInput, AutomationActionOutput, ToolStatus


def execute_automation_action(input_data: AutomationActionInput) -> AutomationActionOutput:
    # TODO: replace with real platform dispatch (Zapier/Make/n8n API calls).
    # This stub simulates a successful action for scaffold/testing purposes.
    return AutomationActionOutput(
        status=ToolStatus.SUCCESS,
        result={"platform": input_data.platform, "action_id": input_data.action_id, "echo": input_data.params},
        external_ref=f"ext_{input_data.action_id}_0001",
    )

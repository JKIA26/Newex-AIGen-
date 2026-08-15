"""
sandbox.execute_code — isolated untrusted code execution.
This is a STUB. Real implementation must run inside an actual isolated
runtime (Modal, Daytona, self-hosted gVisor/Firecracker) — see the open
question in agent-orchestration-architecture.md and sandboxes/code_exec_sandbox.py.
Never execute untrusted code directly in the agent-service process.
"""
from __future__ import annotations
from schemas.tool_schemas import SandboxExecInput, SandboxExecOutput, ToolStatus


def execute_code(input_data: SandboxExecInput) -> SandboxExecOutput:
    # TODO: dispatch to sandboxes/code_exec_sandbox.py, which must enforce:
    #   - no network access
    #   - no filesystem persistence beyond an ephemeral scratch dir
    #   - hard wall-clock timeout (input_data.timeout_s)
    #   - resource limits (input_data.resource_limits)
    raise NotImplementedError(
        "Sandbox execution requires a real isolated runtime — not implemented in this scaffold. "
        "See sandboxes/code_exec_sandbox.py."
    )

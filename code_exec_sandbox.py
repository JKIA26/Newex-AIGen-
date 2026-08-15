"""
Isolated code execution backend — the actual sandbox implementation.

NOT IMPLEMENTED in this scaffold. This is where a real integration with
Modal, Daytona, or a self-hosted gVisor/Firecracker runtime belongs.

Contract this module must satisfy (called only from tools/sandbox_exec_tool.py):
  - run(language: str, code: str, timeout_s: int, resource_limits: dict) -> dict
      with keys: stdout, stderr, exit_code
  - MUST NOT allow network access from inside the sandbox
  - MUST NOT persist filesystem state beyond the single execution
  - MUST enforce timeout_s as a hard wall-clock limit, not advisory
"""


def run(language: str, code: str, timeout_s: int, resource_limits: dict) -> dict:
    raise NotImplementedError(
        "Wire this up to a real sandbox backend (Modal / Daytona / gVisor / Firecracker) "
        "before sandbox.execute_code can be used for anything beyond interface testing."
    )

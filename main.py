"""
JIMJAM'EST Agent Service — entrypoint.

Run locally:
    uvicorn main:app --reload --port 8000

This wires together every controller from agent-orchestration-architecture.md §E
and bootstraps the MCP host (§B) at startup.
"""
from __future__ import annotations
from fastapi import FastAPI

from controllers import (
    session_controller,
    tool_controller,
    pipeline_controller,
    agent_controller,
    file_controller,
    trace_controller,
)
from websocket import event_stream
from mcp.host import bootstrap_mcp_host, seed_demo_allowlists

app = FastAPI(title="JIMJAM'EST Agent Service", version="0.1.0")

app.include_router(session_controller.router)
app.include_router(tool_controller.router)
app.include_router(pipeline_controller.router)
app.include_router(agent_controller.router)
app.include_router(file_controller.router)
app.include_router(trace_controller.router)
app.include_router(event_stream.router)


@app.on_event("startup")
def on_startup():
    bootstrap_mcp_host()
    seed_demo_allowlists()  # TODO: replace with real per-org allowlist loading


@app.get("/health")
def health():
    return {"status": "ok"}

from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel

from orchestrators import agent_loop
from controllers.session_controller import _serialize

router = APIRouter(prefix="/agents", tags=["agents"])


class RunAgentRequest(BaseModel):
    org_id: str
    user_id: str
    goal: str
    input: dict = {}


@router.post("/run")
def run_agent(req: RunAgentRequest):
    """Tier 1 entrypoint — run an agent by goal rather than a named pipeline."""
    state = agent_loop.start_session(req.org_id, req.user_id, req.goal, req.input)
    return _serialize(state)

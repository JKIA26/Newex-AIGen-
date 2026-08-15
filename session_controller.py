from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orchestrators import agent_loop

router = APIRouter(prefix="/sessions", tags=["sessions"])


class StartSessionRequest(BaseModel):
    org_id: str
    user_id: str
    goal: str
    input: dict = {}


class ResumeSessionRequest(BaseModel):
    input: dict = {}


def _serialize(state: agent_loop.AgentSessionState) -> dict:
    return {
        "session_id": state.session_id,
        "trace_id": state.trace_id,
        "status": state.status,
        "pipeline_name": state.pipeline_name,
        "step_count": state.step_count,
        "final_output": state.last_result.final_output if state.last_result else None,
        "missing_fields": state.last_result.missing_fields if state.last_result else [],
    }


@router.post("")
def start_session(req: StartSessionRequest):
    state = agent_loop.start_session(req.org_id, req.user_id, req.goal, req.input)
    return _serialize(state)


@router.get("/{session_id}")
def get_session_status(session_id: str):
    state = agent_loop.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _serialize(state)


@router.post("/{session_id}/resume")
def resume_session(session_id: str, req: ResumeSessionRequest):
    try:
        state = agent_loop.resume_session(session_id, req.input)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _serialize(state)

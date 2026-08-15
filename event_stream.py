"""
WebSocket endpoint streaming incremental UI updates (§F) as the agent
progresses through a session. Clients connect with a session_id and
receive UIUpdate-shaped JSON blocks as pipeline/agent events occur.

This scaffold polls session state; a production version should push
directly from agent_loop/pipeline event hooks instead of polling.
"""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from orchestrators import agent_loop
from schemas.ui_schemas import UIUpdate, UIBlockType, ProgressPayload, ProgressStep, ResultCardPayload

router = APIRouter()


@router.websocket("/ws/sessions/{session_id}")
async def session_event_stream(websocket: WebSocket, session_id: str):
    await websocket.accept()
    last_status = None
    try:
        while True:
            state = agent_loop.get_session(session_id)
            if state is None:
                await websocket.send_json({"type": "error", "detail": "session not found"})
                break

            if state.status != last_status:
                last_status = state.status

                if state.status == "done" and state.last_result and state.last_result.final_output:
                    update = UIUpdate(
                        type=UIBlockType.RESULT_CARD,
                        session_id=state.session_id,
                        trace_id=state.trace_id,
                        payload=ResultCardPayload(
                            title=f"{state.pipeline_name} completed",
                            kind="table",
                            data=state.last_result.final_output,
                        ),
                    )
                    await websocket.send_json(update.model_dump())
                    break

                elif state.status == "awaiting_input":
                    # Frontend should follow up with a `form` block via the
                    # clarification handler — see orchestrators/clarification_handler.py
                    await websocket.send_json({
                        "type": "agent_paused",
                        "session_id": state.session_id,
                        "trace_id": state.trace_id,
                        "missing_fields": state.last_result.missing_fields if state.last_result else [],
                    })
                    break

                elif state.status == "failed":
                    await websocket.send_json({
                        "type": "agent_error",
                        "session_id": state.session_id,
                        "trace_id": state.trace_id,
                    })
                    break

                else:
                    progress = UIUpdate(
                        type=UIBlockType.PROGRESS,
                        session_id=state.session_id,
                        trace_id=state.trace_id,
                        payload=ProgressPayload(
                            pipeline_name=state.pipeline_name or "",
                            steps=[ProgressStep(name=f"step_{state.step_count}", status="running")],
                        ),
                    )
                    await websocket.send_json(progress.model_dump())

            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass

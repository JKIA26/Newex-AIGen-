"""
Tier 1 — Agent orchestration loop. Implements the loop described in
agent-orchestration-architecture.md §D:

  route -> check inputs -> execute -> evaluate -> retry/loop -> stop

The agent NEVER expands its own allowlist or bypasses a risk gate —
those changes only ever come from the policy/approval layer.
"""
from __future__ import annotations
from typing import Any, Optional
from dataclasses import dataclass, field

from pipelines import invoice_processing
from schemas.pipeline_schemas import StepStatus, PipelineRunResult
from tracing.trace_context import new_trace_id, new_session_id
from tracing.audit_log import log_event


# Goal -> pipeline routing table. Extend as more Tier 2 pipelines are added
# (support_triage, lead_followup, ops_handoff, market_research, etc.)
_GOAL_PIPELINE_MAP = {
    "process this invoice": "invoice_processing",
    "process invoice": "invoice_processing",
}

MAX_STEPS = 10


@dataclass
class AgentSessionState:
    session_id: str
    trace_id: str
    org_id: str
    user_id: str
    goal: str
    pipeline_name: Optional[str] = None
    status: str = "running"  # running | awaiting_input | done | failed
    step_count: int = 0
    last_result: Optional[PipelineRunResult] = None
    pending_input: dict[str, Any] = field(default_factory=dict)


# In-memory session store — replace with real persistence (Postgres,
# agent-service's own schema per service-architecture.md) before production.
_sessions: dict[str, AgentSessionState] = {}


def start_session(org_id: str, user_id: str, goal: str, initial_input: dict[str, Any]) -> AgentSessionState:
    session_id = new_session_id()
    trace_id = new_trace_id()
    state = AgentSessionState(session_id=session_id, trace_id=trace_id, org_id=org_id, user_id=user_id, goal=goal)
    _sessions[session_id] = state

    log_event(trace_id, "session.started", {"goal": goal, "org_id": org_id})

    pipeline_name = _route_goal(goal)
    if pipeline_name is None:
        state.status = "failed"
        log_event(trace_id, "agent.error", {"reason": "no matching pipeline for goal"})
        return state

    state.pipeline_name = pipeline_name
    _run_step(state, initial_input)
    return state


def resume_session(session_id: str, additional_input: dict[str, Any]) -> AgentSessionState:
    state = _sessions.get(session_id)
    if state is None:
        raise KeyError(f"No such session: {session_id}")
    if state.status != "awaiting_input":
        raise ValueError(f"Session {session_id} is not awaiting input (status={state.status})")

    # Flat merge: the resume payload uses the exact same field names the
    # API returned in `missing_fields` (e.g. "vendor", "amount") — no
    # hidden nesting the caller has to guess at. Previously-collected
    # fields persist because pending_input already holds them.
    merged_input = {**state.pending_input, **additional_input}
    _run_step(state, merged_input)
    return state


def get_session(session_id: str) -> Optional[AgentSessionState]:
    return _sessions.get(session_id)


def _route_goal(goal: str) -> Optional[str]:
    # TODO: replace with real intent classification / model-based routing.
    # Selection must stay constrained to the org's allowlisted pipelines.
    return _GOAL_PIPELINE_MAP.get(goal.strip().lower())


def _run_step(state: AgentSessionState, pipeline_input: dict[str, Any]) -> None:
    if state.step_count >= MAX_STEPS:
        state.status = "failed"
        log_event(state.trace_id, "agent.error", {"reason": "max_steps_exceeded"})
        return

    state.step_count += 1

    if state.pipeline_name == "invoice_processing":
        # "file_content_hash" is the one reserved key for the uploaded file
        # reference; every other key in pipeline_input is treated as a flat
        # invoice field (vendor, amount, due_date, po_number, ...), matching
        # the exact names the API returns in `missing_fields`.
        file_content_hash = pipeline_input.get("file_content_hash", "")
        extra_fields = {k: v for k, v in pipeline_input.items() if k != "file_content_hash"}
        result = invoice_processing.run(
            session_id=state.session_id,
            trace_id=state.trace_id,
            org_id=state.org_id,
            file_content_hash=file_content_hash,
            extra_fields=extra_fields,
        )
    else:
        state.status = "failed"
        log_event(state.trace_id, "agent.error", {"reason": f"unimplemented pipeline: {state.pipeline_name}"})
        return

    state.last_result = result

    if result.status == StepStatus.AWAITING_INPUT:
        state.status = "awaiting_input"
        state.pending_input = pipeline_input
        log_event(state.trace_id, "clarification.requested", {"missing_fields": result.missing_fields})
    elif result.status == StepStatus.DONE:
        state.status = "done"
        log_event(state.trace_id, "agent.completed", {"final_output": result.final_output})
    else:
        state.status = "failed"
        log_event(state.trace_id, "agent.error", {"reason": "pipeline step failed"})

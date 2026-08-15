# Agent Orchestration Architecture — Three-Tier System + MCP Integration

**Status:** Draft technical spec
**Owner:** Engineering
**Related docs:** `architecture.md` (AI Capability Layer, Event-Driven Backbone), `service-architecture.md` (policy-service/workflow-service split), `security-architecture.md` (sandboxing, guardrails), `entitlement-role-sync-policy.md` (approval gates)

**Tier definitions used throughout this doc** (fixing a numbering inconsistency in the source spec — see §0):
- **Tier 1 — Agents**: autonomous orchestrators that select pipelines/tools, loop on results, request clarification
- **Tier 2 — Pipelines**: end-to-end multi-step workflows producing explicit outputs
- **Tier 3 — Tools**: single-purpose, shippable capabilities

---

## 0. Note on tier numbering

The request that generated this doc included a second version where "Tier One" meant single tools (Document Q&A, Email Assistant) and "Tier Two" meant pipelines — the reverse of Tier 1 = Agents used here. **This doc uses Tools = Tier 3, Pipelines = Tier 2, Agents = Tier 1 throughout**, matching the more detailed of the two specs. If the portfolio-style framing (tools as "Tier 1 shippable projects" for a hiring-manager audience) is actually what's wanted, that's a **separate, differently-purposed document** — a portfolio/demo narrative, not a system architecture — and shouldn't reuse the same tier numbers without reconciling them first.

---

## A. Backend Directory / Module Structure

```
agent-service/
├── controllers/
│   ├── session_controller.py       # start/status/resume session endpoints
│   ├── tool_controller.py          # generic tool invocation endpoint
│   ├── pipeline_controller.py      # run pipeline by name
│   ├── agent_controller.py         # run agent by goal
│   └── file_controller.py          # upload/ingest, content-hash storage
│
├── orchestrators/
│   ├── agent_loop.py               # Tier 1 — the core orchestration loop (§D)
│   ├── clarification_handler.py    # generates missing-parameter forms (ties to §F)
│   └── stopping_conditions.py      # max steps, budget, confidence thresholds
│
├── pipelines/                      # Tier 2 — one module per pipeline
│   ├── invoice_processing.py
│   ├── support_triage.py           # existing JIMJAM'EST pipeline
│   ├── lead_followup.py            # existing JIMJAM'EST pipeline
│   ├── ops_handoff.py              # existing JIMJAM'EST pipeline
│   ├── market_research.py
│   ├── content_generation.py
│   └── ... (one file per pipeline in §C)
│
├── tools/                          # Tier 3 — MCP-exposed tools
│   ├── registry.py                 # tool registration + schema validation
│   ├── automation_tool.py
│   ├── rag_retrieval_tool.py
│   ├── data_validation_tool.py
│   ├── sandbox_exec_tool.py
│   ├── model_router_tool.py
│   └── ... (one file per tool in §B)
│
├── mcp/
│   ├── host.py                     # MCP Host — lives inside agent-service
│   ├── tool_server_automation.py
│   ├── tool_server_rag.py
│   ├── tool_server_validation.py
│   ├── tool_server_sandbox.py
│   └── tool_server_router.py       # optional multi-model routing/guardrails
│
├── services/
│   ├── auth_service.py
│   ├── entitlement_service.py      # calls out to entitlement-role-sync-policy.md logic
│   ├── policy_service_client.py    # per service-architecture.md's policy-service
│   └── storage_service.py          # content-hash file storage
│
├── sandboxes/
│   └── code_exec_sandbox.py        # isolated untrusted-code execution (Modal/Daytona-equivalent)
│
├── tracing/
│   ├── trace_context.py            # trace_id generation/propagation
│   └── audit_log.py                # per security-architecture.md provenance requirements
│
├── schemas/                        # Pydantic models — every tool/pipeline I/O is typed
│   ├── tool_schemas.py
│   ├── pipeline_schemas.py
│   └── ui_schemas.py               # generative UI JSON contracts (§F)
│
├── websocket/
│   └── event_stream.py             # incremental UI update streaming
│
└── main.py
```

This slots directly under `native-compute-service` in `service-architecture.md` — `agent-service` is effectively an expanded `api-service` + `policy-service` client, with `sandboxes/` mapping onto the same isolation principle native compute already uses (narrow interface, no direct DB writes from inside the sandbox).

---

## B. MCP Tool Registry

Each tool is registered with a strict, validated schema — no tool accepts unvalidated free-form input.

| Tool name | Input schema (summary) | Output schema (summary) | Allowed actions |
|---|---|---|---|
| `automation.execute_action` | `{platform: enum[zapier,make,n8n], action_id: str, params: dict}` | `{status: enum[success,failed,pending], result: dict, external_ref: str}` | Only actions pre-registered in an org's automation allowlist — never arbitrary API calls |
| `rag.index_document` | `{content_hash: str, source_uri: str, metadata: dict}` | `{index_id: str, chunk_count: int, status: enum}` | Index only; no delete/overwrite without a separate scoped action |
| `rag.retrieve` | `{query: str, index_id: str, top_k: int, filters: dict}` | `{chunks: [{text: str, score: float, source: str}]}` | Read-only |
| `validation.parse_and_validate` | `{raw_input: str\|dict, target_schema: str}` | `{valid: bool, parsed: dict\|null, errors: [str]}` | Pydantic-AI-style type coercion + validation only — no side effects |
| `sandbox.execute_code` | `{language: enum[python,js], code: str, timeout_s: int, resource_limits: dict}` | `{stdout: str, stderr: str, exit_code: int, status: enum}` | No network access, no filesystem persistence, hard timeout enforced |
| `router.route_request` | `{prompt: str, task_type: str, compliance_tags: [str]}` | `{selected_model: str, routing_reason: str, guardrail_flags: [str]}` | Routing + guardrail evaluation only — never bypasses a guardrail flag |

**Allowlist rule (mirrors `entitlement-role-sync-policy.md`'s allowlist rail):** a tool call is only executed if the requested action is in that org's configured allowlist for that tool. An agent proposing an out-of-allowlist action gets a structured rejection, not a silent failure — same "restriction-first" principle as the entitlement policy.

---

## C. Tier 3 Tools → Tier 2 Pipelines

Each capability maps to one or more tools feeding one pipeline. Format: **input → tool calls → output**.

| Capability | Pipeline | Flow |
|---|---|---|
| Automate repetitive tasks | `invoice_processing` | Uploaded invoice (file) → `validation.parse_and_validate` (extract fields) → `automation.execute_action` (post to accounting system) → structured confirmation output |
| Analyze data sets | `trend_analysis` | Dataset reference → `rag.retrieve` (contextual docs) + native-compute stats job → summarized trends + chart-ready data |
| Generate complex content | `content_generation` | Brief (text) → `router.route_request` (pick model for task type) → draft output → `validation.parse_and_validate` (format check) → final draft |
| Manage customer service | `support_triage` *(existing)* | Ticket event → `rag.retrieve` (knowledge base) → classification + drafted reply → routed to agent or auto-sent per policy |
| Optimize supply chains | `inventory_forecast` | Inventory + sales data → native-compute forecast job → `automation.execute_action` (reorder trigger, gated) |
| Conduct market research | `market_research` | Topic/competitor list → `automation.execute_action` (controlled scrape/collect, allowlisted sources only) → `rag.index_document` → summarized findings |
| Monitor system security | `anomaly_detection` | Event stream → native-compute anomaly job → if flagged: `automation.execute_action` (open incident ticket) — **never auto-remediates**, matches fail-closed model in `security-architecture.md` |
| Personalize user experiences | `personalization` | User profile + behavior data → `rag.retrieve` (similar user patterns) → recommendation output |
| Execute financial trades | `trade_signal_review` | Market data → native-compute signal analysis → **risk gate check** → if approved flag present and within limit thresholds: `automation.execute_action` (trade); otherwise → approval queue, no execution |
| Assist medical diagnostics | `diagnostic_flagging` | Clinical data (structured) → native-compute pattern analysis → output is **always** `{findings: [...], severity: enum, confidence: float, disclaimer: "for clinician review, not a diagnosis"}` — pipeline has no path that outputs a final diagnosis |

**Scope flag:** `trade_signal_review` and `diagnostic_flagging` sit well outside JIMJAM'EST's documented launch scope (`business_context.md` — Ops, Support, Sales only). Including them here as designed capabilities, but they'd need their own compliance review (financial regulation, medical device regulation) before being anything more than a spec — this isn't a "just build it" item.

---

## D. Tier 1 — Agent Orchestration Loop

```
1. RECEIVE goal (natural language or structured) + org/user context (verified token)
2. ROUTE: agent selects a candidate pipeline (or tool, for simple single-step goals)
     - selection is constrained to pipelines/tools in the org's allowlist
3. CHECK required inputs against the pipeline's schema
     - if inputs missing → emit a "clarification" UI event (§F: form schema) and PAUSE
     - on user response → resume from step 3
4. EXECUTE pipeline step-by-step (each step is itself a tool call, per §C)
     - emit progress events after each step (§F: progress schema)
5. EVALUATE step result
     - if step failed and retryable → RETRY (bounded — see stopping conditions)
     - if step failed and not retryable → surface structured error, STOP
     - if step succeeded → continue to next step
6. LOOP back to step 4 until pipeline completes, or a stopping condition triggers:
     - max steps exceeded
     - execution budget (cost/time) exceeded
     - confidence below threshold on a critical step (e.g., diagnostic/trading pipelines)
     - explicit approval-required gate hit (per entitlement-role-sync-policy.md's approval rail)
7. RETURN final structured output + trace_id, or a queued-for-approval status
```

**Never auto-escalates its own authority.** Same rule as `entitlement-role-sync-policy.md`: the agent can retry, re-route, or ask for clarification, but it cannot expand its own allowlist or bypass a risk gate — those changes only come from the policy/approval layer, never from the agent loop itself.

---

## E. Backend Endpoints

### REST
| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sessions` | Start an agent session |
| `GET` | `/sessions/{id}` | Get session status |
| `POST` | `/sessions/{id}/resume` | Resume a paused (clarification-pending) session |
| `POST` | `/tools/{tool_name}/invoke` | Generic tool invocation, dispatches via MCP host |
| `POST` | `/pipelines/{pipeline_name}/run` | Run a named pipeline with structured input |
| `POST` | `/agents/run` | Run agent by goal (Tier 1 entrypoint) |
| `POST` | `/files` | Upload a document for ingestion, stored by content-hash |
| `GET` | `/traces/{trace_id}` | Retrieve full audit trail for a run |

### WebSocket events
| Event | Payload |
|---|---|
| `session.started` | `{session_id, trace_id}` |
| `pipeline.step_completed` | `{session_id, step_name, status, partial_output}` |
| `clarification.requested` | `{session_id, ui_schema}` (see §F) |
| `agent.paused` | `{session_id, reason}` |
| `agent.completed` | `{session_id, final_output, trace_id}` |
| `agent.error` | `{session_id, error_code, message}` |

Every request/response carries a `trace_id` (Langfuse/Braintrust-style), generated at session start and propagated through every tool call and pipeline step — this is what `service-architecture.md`'s tracing layer and `security-architecture.md`'s provenance requirement both depend on.

---

## F. Frontend API — Generative UI Schema

One endpoint streams incremental UI updates; each update is a typed JSON block the frontend renders directly.

```json
{
  "type": "chat_message" | "form" | "progress" | "result_card",
  "session_id": "string",
  "trace_id": "string",
  "payload": { }
}
```

**`chat_message` payload:** `{ "role": "agent"|"user", "text": "string" }`

**`form` payload** (generated from missing parameters):
```json
{
  "fields": [
    { "name": "string", "label": "string", "type": "text"|"number"|"select"|"file",
      "required": true, "options": ["..."] }
  ],
  "submit_action": "string"
}
```

**`progress` payload:**
```json
{ "pipeline_name": "string", "steps": [{ "name": "string", "status": "pending"|"running"|"done"|"failed" }] }
```

**`result_card` payload:**
```json
{
  "title": "string",
  "kind": "chart"|"text"|"table",
  "data": { },
  "severity": "info"|"warning"|"critical",
  "confidence": 0.0
}
```

`severity` and `confidence` are mandatory on any `result_card` coming from `anomaly_detection` or `diagnostic_flagging` — this is the structural enforcement of §C's "findings for review" rule, not just a convention.

Streamed over the same WebSocket channel as §E, or via Server-Sent Events if a simpler transport is preferred for the frontend.

---

## G. Example Run — Invoice Processing

**Request:**
```
POST /agents/run
{ "goal": "process this invoice", "file_ref": "content-hash-abc123" }
```

**Flow:**
1. Agent routes to `invoice_processing` pipeline (Tier 2)
2. Pipeline calls `validation.parse_and_validate` (Tier 3) on the uploaded file → extracts vendor, amount, due date
3. Missing field detected (PO number) → WebSocket emits `clarification.requested` with a `form` UI block asking for it
4. User submits PO number via `POST /sessions/{id}/resume`
5. Pipeline calls `automation.execute_action` → posts the invoice to the accounting system (allowlisted action)
6. WebSocket emits `pipeline.step_completed` after each step, then `agent.completed`

**Final UI response (`result_card`):**
```json
{
  "type": "result_card",
  "session_id": "sess_812",
  "trace_id": "trace_9f21",
  "payload": {
    "title": "Invoice #4471 processed",
    "kind": "table",
    "data": { "vendor": "Acme Supplies", "amount": "$1,204.00", "status": "Posted" },
    "severity": "info",
    "confidence": 0.97
  }
}
```

---

## Open Questions

- [ ] Confirm whether `trade_signal_review` and `diagnostic_flagging` are actually in scope, given the compliance weight they carry vs. `business_context.md`'s current Ops/Support/Sales focus
- [ ] Which sandboxing backend specifically (Modal, Daytona, self-hosted gVisor/Firecracker) — affects `sandboxes/code_exec_sandbox.py`'s actual implementation
- [ ] Does the second (portfolio-framed) tier spec need reconciling into this numbering, or is it a genuinely separate document for a different audience?
- [ ] Is the REST/GraphQL/gRPC "same data, different trips" backend algorithm (Login/APIs/Dashboards/Payments/DatabaseConnections) meant to be part of this agent system, or a separate, unrelated backend exercise?

---
*This document should be kept in sync with `architecture.md` (AI Capability Layer this formalizes) and `service-architecture.md` (the service split this builds on).*

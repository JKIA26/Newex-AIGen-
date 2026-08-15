# Business Context — JIMJAM'EST Globalisation

## 1. Company Snapshot

- **Name:** JIMJAM'EST Globalisation
- **Product category:** Developer-first SaaS platform for AI agents
- **Tagline:** AI agents that run real business workflows. Built by developers.
- **One-line positioning:** JIMJAM'EST lets technical teams build, deploy, and monitor AI agents that execute real operational work — not just chat or draft — starting with Ops, Support, and Sales.

## 2. The Problem

Most "AI agent" tools on the market today are either:
1. **No-code toy builders** — easy to demo, but too shallow to run production workflows reliably, or
2. **Raw LLM APIs** — powerful but require every team to build their own orchestration, auth, retries, logging, and monitoring from scratch.

Meanwhile, operational teams (support, sales, ops) are still doing repetitive, rules-based work by hand: triaging tickets, following up on leads, reconciling handoffs between systems. The tools that promise to fix this often produce output that has to be manually checked, corrected, or re-run — because there's no reliable execution layer underneath.

**The gap:** there is no developer-grade platform for building agents that actually *finish* a task end-to-end — with proper identity, retries, observability, and audit trails — the same way you'd trust a backend service in production.

## 3. The Solution

JIMJAM'EST provides infrastructure and tooling for developers to build AI agents that are:

- **Event-driven** — triggered by real business events (a new lead, a support ticket, a scheduled job), not just chat prompts
- **Reliable** — built-in retry logic, replay, and dead-letter handling so failed runs don't silently disappear
- **Secure by default** — token-based identity, RBAC/ABAC access control, encrypted data handling
- **Observable** — every agent run is logged, traceable, and inspectable like a normal API call (`POST /v1/agents/execute` → `status: completed`, `duration: 12.842s`)
- **Composable** — agents can be configured, versioned, and orchestrated rather than hand-coded from scratch each time

In short: JIMJAM'EST treats an AI agent like a production service, not a prompt.

## 4. Who It's For

**Primary users:** developers and technical teams at small-to-mid-size companies who are responsible for operational tooling — not necessarily an "AI team."

**Initial target workflows (launch focus):**
| Function | Example use case |
|---|---|
| **Support** | Auto-triage incoming tickets, route by urgency/topic, draft first-response replies |
| **Sales** | Lead follow-up sequencing, qualification scoring, handoff to reps at the right moment |
| **Ops** | Cross-system handoffs (e.g., "ops handoff" workflows), status reconciliation, scheduled housekeeping tasks |

These three were chosen because they are high-volume, rules-adjacent, and currently manual — meaning automation ROI is fast and measurable (time saved per ticket/lead/handoff).

## 5. Why Now

- LLMs are now reliable enough to handle judgment-based steps (classification, drafting, prioritization) that used to require hardcoded rules.
- Companies are wary of "black box" AI tools after early hype cycles — there's growing demand for agent platforms with real observability, security, and audit trails.
- Developer teams increasingly want to *own* their automation stack rather than depend on opaque SaaS point-solutions per department.

## 6. Product Principles (from brand identity)

- **Architectural** — structure and clarity over flashy demos
- **Systemic** — workflows should be visible and traceable, not a black box
- **Calm, restrained** — enterprise-credible tone; precision over hype
- **Forward with intention** — built for teams that want to scale automation deliberately, not experimentally

## 7. Business Model (assumptions — confirm/refine)

- **Model:** Usage-based or seat + usage hybrid SaaS pricing, typical of dev-tools platforms
- **Entry point:** self-serve for small teams building their first agent; sales-assisted for larger deployments needing SSO/compliance
- **Expansion path:** start with one department (e.g., Support), expand to Sales and Ops once trust is established

## 8. Open Questions to Resolve Next

- [ ] Exact pricing model (usage-based, per-agent, per-seat?)
- [ ] Which LLM providers/models are supported under the hood?
- [ ] Compliance targets (SOC 2, HIPAA, GDPR) — needed given "Support" may touch customer PII
- [ ] Primary competitors and differentiation points to sharpen positioning
- [ ] First 3 reference customers / design partners for case studies

---
*This document is the canonical business context for JIMJAM'EST Globalisation. Update it as positioning, target segments, or business model assumptions are confirmed.*

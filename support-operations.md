# Support Operations

**Status:** First doc for this folder
**Related docs:** `general/business_context.md` (Support is one of the three launch workflows), `engineering/agent-orchestration-architecture.md` §C (support_triage pipeline spec), `agent-service/pipelines/support_triage.py` (implementation)

This is the first canonical doc for the Support folder — it defines the actual workflow the `support_triage` agent pipeline automates, so the code has a documented source of truth instead of just matching a spec table.

---

## 1. What Support Triage Does

When a support ticket comes in, the agent:
1. Classifies it (category + urgency)
2. Retrieves relevant knowledge base content for that category
3. Drafts a reply
4. Either **auto-sends** the reply (low-risk, high-confidence cases) or **routes to a human agent** for review — never silently auto-closes a ticket a human hasn't seen when confidence is low

This mirrors the exact tool chain from `agent-orchestration-architecture.md` §C: ticket event → `rag.retrieve` (knowledge base) → classification + drafted reply → routed to agent or auto-sent per policy.

---

## 2. Ticket Categories & Urgency

| Category | Example | Default urgency |
|---|---|---|
| `billing` | "Why was I charged twice?" | High |
| `technical` | "Agent run keeps failing at step 2" | High |
| `account` | "Can't reset my password" | Medium |
| `feature_request` | "Can you add X integration?" | Low |
| `general` | Anything not matching the above | Low |

Urgency can be escalated by explicit signals in the ticket (e.g., "urgent", "production down") regardless of category.

---

## 3. Auto-Send vs. Human Review — the Actual Gate

This directly reuses the **restriction-first rail** from `entitlement-role-sync-policy.md` — when in doubt, route to a human, don't auto-send.

**Auto-send only when all three hold:**
1. Classification confidence ≥ 0.85
2. Category is not `billing` (billing always goes to a human — money questions don't get auto-resolved)
3. No escalation signal detected in the ticket text

**Otherwise:** draft is prepared but queued for human review before sending. This is the same pattern as the Approvals Queue in the admin console — the agent proposes, a human confirms for anything above the low-risk line.

---

## 4. SLA Targets (draft — needs confirmation)

| Urgency | First response target |
|---|---|
| High | 15 minutes |
| Medium | 2 hours |
| Low | 24 hours |

*These are placeholder targets, not yet confirmed against real support volume or staffing — flagged in Open Questions below.*

---

## 5. Relationship to Other Docs

- **`entitlement-role-sync-policy.md`** — if a ticket relates to a user's access/role, the support agent can *read* entitlement state to inform its reply, but any role change still goes through the entitlement sync policy's own approval rules, not through the support pipeline
- **`agent-orchestration-architecture.md` §C** — this doc is the business-logic source; the pipeline code in `agent-service/pipelines/support_triage.py` implements it
- **Admin console (`jimjamest-admin-dashboards.html`)** — tickets routed to human review should surface in the same Approvals Queue pattern already built, not a separate UI (not yet wired — see Open Questions)

---

## 6. Open Questions

- [ ] SLA targets above are placeholders — need real numbers from actual support volume/staffing
- [ ] Does a routed-to-human ticket show up in the existing Approvals Queue screen, or does Support need its own queue view?
- [ ] What's the actual knowledge base source for `rag.retrieve` — existing help docs, past resolved tickets, both?
- [ ] Escalation signal detection — keyword list, or a classifier? Keyword lists are easy to bypass accidentally with different phrasing

---
*This is the first doc in this folder — update it as real support data (volume, categories, SLA performance) becomes available.*

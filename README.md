# JIMJAM'EST Globalisation — Documentation Index

**Status:** First documentation pass
**Last updated:** working draft, in progress

This is the entry point into JIMJAM'EST's workspace documentation. It exists because the individual docs below were each built to answer one specific question — this index exists to show how they connect, and where the gaps still are.

---

## 1. What JIMJAM'EST Is (start here)

📄 **`general/business_context.md`**
The canonical positioning doc. Answers: what problem does JIMJAM'EST solve, who is it for, why now, and what are the three launch workflows (Support, Sales, Ops).

> One-line summary: *JIMJAM'EST is a developer-first SaaS platform for building and running AI agents that execute real operational work — starting with Ops, Support, and Sales.*

Open items in this doc: pricing model, LLM providers, compliance targets, competitors, first design partners.

---

## 2. How the Platform Is Built

📄 **`engineering/architecture.md`**
The seven-layer technical architecture: Experience & Operations → API Gateway & Identity → Secure Identity/Consent & Containment → Event-Driven Backbone → MML Content/AI Capability → Data & Operations, plus the Security & Compliance Foundation that runs under all of it. Also defines the multimodal "AI Mode" input handling (text/image/voice) inside the AI Capability Layer.

Cross-references:
- Consent & Containment (§1.4) → points to `entitlement-role-sync-policy.md`
- Security & Compliance Foundation (§2) → points to `security-architecture.md`

Open items: event bus/broker choice, retry/backoff specifics, containment isolation mechanism, voice input scope, data residency.

---

## 3. Automation & Safety Rules

📄 **`entitlement-role-sync-policy.md`**
Defines exactly what the AI agent may do automatically versus what always requires admin approval, specifically for role/entitlement management. Core rule: **auto-execute entitlement sync and downgrades; never auto-execute privilege escalation.** Introduces the two mandatory safety rails (entitlement allowlist, restriction-first) and the 24-hour prototype scope (one job: Entitlement Role Sync).

📄 **`security-architecture.md`**
The broader security layer this policy depends on:
- Encryption/crypto standards (TLS 1.3, AES-256, KMS/HSM, CMEK/CMK)
- OPA/Rego policy-as-code for CI/CD — **now fail-closed**, with per-org approved-key allowlists enforced on every check (§3.3–3.6, updated per latest policy change)
- Runtime drift detection design (what's monitored, cadence, alert lifecycle — also fail-closed for sensitive findings)
- The end-to-end flow tying CI/CD gate → runtime loop → admin remediation together
- Universal identity/authorization principles that apply across every connector (calendar, CRM, billing, etc.), not just the core platform

Resolved: soft-block CI mode is retired — every violation fails the pipeline. Drift detection scope for v1 is single-cloud first.
Still open: confidential computing/enclave timing, SIEM routing.

**How these two connect:** `entitlement-role-sync-policy.md` is the policy layer (what's allowed); `security-architecture.md` is the enforcement machinery underneath it (how "allowed" actually gets checked and can't be bypassed).

📄 **`service-architecture.md`**
How the fail-closed governance flow maps onto real services: `api-service`, `policy-service`, `workflow-service`, `remediation-worker`, and an isolated `native-compute-service` for crypto/parsing (C/Assembly). Single shared Postgres cluster, schema-per-service via Alembic. Native compute is stateless, DB-free, and gated entirely behind governance approval — it never makes its own authorization decisions.

---

## 4. What Users See

🖥️ **`design/jimjamest-ui-model.html`**
Early UI/UX exploration — brutalist login screen + single agent status card, with an AI assistant chat panel ("JIM — Console Assistant") as a proof of concept for in-product AI navigation help.

🖥️ **`design/jimjamest-admin-dashboards.html`**
The full six-screen admin console, built directly from the admin panel requirements in `entitlement-role-sync-policy.md` §8:
Role Policy Map, Automation Rules, Approvals Queue, Audit Log, Subscription Health, Security Controls. Same brutalist visual language as the UI model above — this is the **product/console** design direction.

🌐 **`marketing/marketing-site/`** (`index.html`, `styles.css`)
The public-facing landing page — a *different* visual direction (dark background, serif display headline, teal/lavender accents) reusing the brand board's color palette rather than the brutalist console style. Copy is now tied to actual positioning ("Agents that finish real work," Ops/Support/Sales stat callouts) instead of generic placeholders.

✅ **Confirmed design direction:** the brutalist console and the marketing site are intentionally distinct — product UI stays brutalist, public site stays serif/dark. This is settled, not a mismatch to reconcile.

⚠️ **Known gap:** `marketing-site/main.js` (mobile menu + count-up stat animation logic) was referenced by `index.html` but not yet created — needed before this site actually runs.

---

## 5. Document Relationship Map

```
business_context.md  (why JIMJAM'EST exists)
        │
        ▼
architecture.md  (how the platform is structured)
        │
        ├──► entitlement-role-sync-policy.md  (auto vs. approval rules)
        │              │
        │              ▼
        └──► security-architecture.md  (crypto, policy-as-code, drift detection)
                       │
                       ▼
              service-architecture.md  (concrete services + Postgres + native compute isolation)

design + marketing HTML  (what it looks like — product console vs. public site)
```

---

## 6. Immediate Gaps to Close

Pulled from the "Open Questions" sections across all docs, in one place:

- [ ] `marketing-site/main.js` — not yet built, site won't function without it
- [ ] Pricing model, LLM providers, compliance targets, competitors (`business_context.md`)
- [ ] Event bus choice, retry policy, voice input scope, data residency (`architecture.md`)
- [x] ~~High-privilege role list definition, policy map versioning, alert channel~~ (`entitlement-role-sync-policy.md`) — **Resolved:** high-privilege roles are a platform-default list, configurable per org in the Role Policy Map screen; the policy map is versioned, with changes taking effect on the next scheduled sync rather than forcing an immediate retroactive re-sync; alerts go out via email + in-app by default, with webhook as an optional per-org addition. *(Bundled confirmation — flag if any one of these three should be handled differently.)*
- [ ] Confidential computing timing (`security-architecture.md`)
- [x] ~~SIEM routing~~ (`security-architecture.md`) — **Resolved: configurable per org**, not a fixed destination
- [ ] Native-compute statelessness, async job retry policy, Rego bundle versioning, internal networking model (`service-architecture.md`)
- [x] ~~Confirm product console vs. marketing site as intentionally distinct visual directions, or unify them~~ — **Resolved: intentionally distinct.** Brutalist console (product) and serif/dark landing page (public site) are separate, deliberate directions — not a mismatch to fix.

---

## 7. Folder Status (from workspace structure)

| Folder | Status |
|---|---|
| **general** | ✅ `business_context.md` in place |
| **engineering** | ✅ `architecture.md`, `security-architecture.md`, `entitlement-role-sync-policy.md` |
| **design** | ✅ Brand kit + two console UI mockups |
| **marketing** | 🟡 Landing page started, `main.js` missing |
| **sales** | ⛔ Empty |
| **support** | ⛔ Empty |
| **ops** | ⛔ Empty |
| **finance** | ⛔ Empty |
| **legal** | ⛔ Empty |

---
*This index should be updated every time a new canonical doc is added, so it stays the single starting point for anyone (human or agent) picking up this workspace.*

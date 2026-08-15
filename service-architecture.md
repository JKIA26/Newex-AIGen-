# Service Architecture — Microservices, Postgres, and Native Compute Isolation

**Status:** Draft design spec
**Owner:** Engineering
**Related docs:** `architecture.md` (Event-Driven Backbone, Data & Operations Layer), `security-architecture.md` (fail-closed CI/CD gate, remediation flow), `entitlement-role-sync-policy.md` (approval workflow)

This document defines how JIMJAM'EST is decomposed into services, how a single shared Postgres cluster is organized without becoming a shared-mutable-state problem, and how performance-critical native compute (crypto, parsing, C/Assembly) is isolated so it can't quietly become a second, uncontrolled execution path around the governance model already defined in `security-architecture.md`.

**Core principle:** decompose by *responsibility*, not by *technology*. Python owns orchestration and policy logic; Postgres holds all durable state; native compute is a stateless, narrowly-typed appliance that never touches the database or makes its own governance decisions.

---

## 1. Service Layout

| Service | Responsibility |
|---|---|
| **api-service** | Python entrypoints and routing — the front door |
| **policy-service** | Rule evaluation and compliant-fix proposal generation (implements the OPA/Rego logic from `security-architecture.md` §3) |
| **workflow-service** | Approval queue + remediation workflow orchestration (implements the Approvals Queue from `entitlement-role-sync-policy.md` §8) |
| **remediation-worker** | Executes **only** governance-approved remediation steps — never acts on its own initiative |
| **native-compute-service** | Isolated "hot path" for crypto, parsing, and performance-critical compute (C/Assembly) |

The rest of the system does not link against native code directly. Everything reaches native compute through one narrow interface (§4). This keeps native-code bugs contained to one service instead of scattered across the codebase, and keeps every other service's operational profile "just Python."

---

## 2. Database Strategy: One Postgres Cluster, Schema-per-Service

Single shared PostgreSQL cluster, with **separate schemas per microservice**:

- `api_service`
- `policy_service`
- `workflow_service`
- `remediation_worker`
- `native_compute` *(optional — only if compute needs any durable config, which it generally shouldn't; see §4)*

**Rules:**
- Each microservice owns migrations for its own schema, via **Alembic**, and only its own schema
- Each service's ORM models target only its own schema — no cross-schema ORM relationships
- No service writes into another service's schema directly, ever — cross-service data needs go through the owning service's API, not a shared table

This gives isolation of tables and migration history without the operational overhead of running multiple physical databases. When something breaks, the schema + migration set implicated tells you immediately which service owns the fix.

---

## 3. Governance Flow — Fail-Closed, No Soft Overrides

This is the same fail-closed model from `security-architecture.md` §3.5–3.6, expressed as a concrete service interaction:

1. **api-service** receives a request and calls **policy-service** to evaluate resource/org/key constraints
2. If **policy-service** detects a violation → **workflow-service** creates an approval request record in its own schema (not in policy-service's schema — workflow-service owns the approval lifecycle)
3. **No soft-pass path.** The pipeline fails; remediation is routed into the approval lane, never allowed to proceed on a warning
4. **Admin remediation** is the actual governance mechanism — admins approve only compliant outcomes, typically by updating org-scoped allowlists/approved-key registries (per `security-architecture.md` §3.3's `approved_key_ids` model) and ensuring the corrected configuration is in place
5. **CI/CD reruns** the policy checks after approval
6. **Runtime drift detector** confirms compliance by observing the corrected state live — not just the approval record (same rule as `security-architecture.md` §4.6: a finding isn't resolved until the fix is observed, not just approved on paper)

**The policy engine stays strict forever.** Remediation is only ever allowed after admin approval has changed the governed data in the correct direction, confirmed by runtime observation — there is no code path where policy-service's `deny` gets overridden by anything except that sequence.

---

## 4. Native Compute Isolation

### 4.1 The gating rule
**remediation-worker never calls native-compute-service for remediation unless the governance layer says the remediation is authorized and in the compliant lane** (§3, steps 4–6 complete). Policy/approval is the gate — the compute result is never itself a source of authorization. Native compute does not decide *whether* something should happen; it only performs a requested computation once something has already been authorized to happen.

### 4.2 What it handles
- **Crypto tasks** — hashing/signing, encrypt/decrypt, verification
- **Parsing tasks** — log or binary parsing, extraction
- **Performance-critical compute** — deterministic transforms, compression, feature extraction

### 4.3 Statelessness (deliberate)
The native service executes a job and returns structured results (JSON-serializable, with clear status codes) **without touching Postgres at all.** This is a deliberate operational choice:
- Failures stay contained to individual compute requests, not to shared state
- DB migrations stay entirely within the Python services — native compute never needs an Alembic migration of its own in the common case
- A bad deploy of the native service can't corrupt durable state, only fail its own requests

### 4.4 Interface contract
HTTP, either:
- **Synchronous:** `POST /compute` → result returned immediately
- **Async (preferred for large/slow jobs):** `POST /jobs` → accepted job ID; `GET /jobs/:id` → progress/result

Async is generally the better default when parsing or crypto inputs can be large, or when retries/timeouts matter.

**Contract must be narrow and strictly typed:**
- Only a known, fixed set of job types is accepted
- Payload sizes are validated
- **Never accept arbitrary execution instructions** — this is a deterministic compute appliance, not a general execution sandbox

This makes native-compute-service auditable in the same way the rest of the fail-closed system is: it does one of a known set of operations, returns a result or a structured error, and never performs its own network calls or DB writes. It cannot become a side channel around policy-service's decisions, because it has no way to persist or act on anything beyond returning a result to whoever asked.

---

## 5. Deployment & CI/CD Ordering

To avoid the operational pitfall of orchestrators pointing at a native-compute dependency that wasn't built correctly:

1. **Build and test native-compute-service first** — unit tests plus a small integration smoke test hitting the compute endpoint with known inputs
2. **Deploy native-compute-service**
3. **Deploy the Python services**, each running its own Alembic migration step against its own schema, then connecting to native compute over internal networking

Native compute has its own build pipeline for the C/Assembly artifacts, kept separate from the Python services' build/test/migrate sequence.

---

## 6. Frontend / UX Note

Kept deliberately out of the compute-correctness picture:
- JS + Tailwind for static or near-static pages
- PHP only where genuinely needed for legacy templating or auth bridging — not a default choice
- UI complexity should never leak into the compute pipeline: the compute pipeline stays deterministic, DB writes stay inside the Python services, and policy logic stays authoritative regardless of what the frontend looks like

This is compatible with the existing product console (brutalist) vs. marketing site (serif/dark) split already documented in `README.md` — neither UI layer has any bearing on how compute or governance is structured underneath.

---

## 7. Summary — The Four Rules

1. Each microservice owns its own Postgres schema and Alembic migrations
2. Python owns orchestration and fail-closed governance — policy-service's `deny` is never soft-overridden
3. Native compute is isolated: narrow, deterministic interface, no DB writes, no authorization decisions of its own
4. Remediation only executes in the compliant lane — after admin approval **and** runtime observation confirms the fix actually landed

Following these consistently keeps the performance benefits of C/Assembly and dedicated crypto/parsing compute without turning the platform into an operational or governance liability: deployments stay predictable, failures stay localized to the service that caused them, and there is no soft-pass path anywhere in the system.

---

## 8. Open Questions

- [ ] Does `native-compute-service` need any durable config at all (e.g., algorithm parameters), or can everything be passed per-request and kept fully stateless?
- [ ] What's the specific retry/timeout policy for async native-compute jobs — does this reuse the same retry/dead-letter pattern as the Event-Driven Backbone in `architecture.md` §1.5?
- [ ] Where does policy-service's compiled Rego bundle live, and how is it versioned/deployed relative to the services that call it?
- [ ] Internal networking: service mesh (mTLS between services) or simpler private-network-only access for v1?

---
*This document should be kept in sync with `security-architecture.md` (governance flow this implements) and `architecture.md` (how this maps onto the Event-Driven Backbone and Data & Operations Layer).*

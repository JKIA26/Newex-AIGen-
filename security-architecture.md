# Security Architecture — Encryption, Policy-as-Code & Drift Detection

**Status:** Draft design spec
**Owner:** Engineering / Security
**Related docs:** `engineering/architecture.md`, `entitlement-role-sync-policy.md`

This document defines the concrete crypto standards, policy-enforcement mechanics, and continuous compliance model behind the "Security & Compliance Foundation" bar in `architecture.md`. It answers: *what encryption do we use, where, how do we enforce it before deploy, and how do we catch drift after deploy.*

---

## 1. Encryption & Crypto Choices

### 1.1 Transit (end-to-end)
- **TLS 1.3** everywhere, modern ciphers only — priority order: AES-128-GCM, then ChaCha20-Poly1305
- **Certificate key exchange/signing:** RSA-4096 or ECC (ECDSA/ECDH)
  - RSA-4096 is proven but heavier
  - ECC is modern and more efficient — **prefer ECC-based certificates** where the platform supports it
- Legacy ciphers and pre-TLS 1.3 protocols are disabled, full stop.

### 1.2 Data at rest (databases + file storage)
- Prefer **managed, database-native encryption**:
  - TDE for relational databases
  - Server-side encryption for object storage
- **Strength:** AES-256 as the default standard (AES-128-GCM acceptable depending on provider guidance/performance)
- ChaCha20 is a good fit where AES hardware acceleration isn't available, but most cloud defaults are AES-based at rest — don't fight the provider default without a reason.

### 1.3 Key management (the most important piece)
- Use **KMS/HSM**; enable **customer-managed keys (CMEK/CMK)** wherever stronger governance is needed
- Keys never live in application code:
  - No hardcoded keys
  - No keys in logs
  - Rotation handled via KMS policies, not manual process
- Consider **enclaves/confidential computing** for sensitive processing — this specifically helps against a threat model where the host or cloud runtime itself is compromised, not just external attackers.

### 1.4 Hashing & integrity
- **SHA-256** for general hashing/integrity checks
- **Password hashing is a separate concern** — use a proper password hashing scheme (e.g., Argon2/bcrypt), never plain SHA-256
- **HMAC/signatures** for integrity and authentication of critical artifacts (config bundles, signed audit records, etc.)

### 1.5 Best-practice defaults (summary)
| Layer | Default |
|---|---|
| Transit | TLS 1.3, ECC certs where supported |
| At rest | AES-256, provider-managed encryption |
| Keys | KMS/HSM + CMEK/CMK, no keys in code/logs |
| Hashing | SHA-256 for integrity; dedicated scheme for passwords |
| Isolation | Strict org isolation, RBAC/ABAC, audit logs everywhere |
| High-risk actions | Approval gate required for privilege or billing-term changes |

---

## 2. Wiring AI Operational Upgrades to Enforced Controls

Each capability upgrade the platform gains needs a matching enforced control — capability alone is not a security posture.

| Operational upgrade | Security requirement | Enforcement |
|---|---|---|
| **Reactive → Proactive** | AI acts only on allowed signals | Policy gates on allowed actions; least privilege for connectors; full audit trail |
| **Batch → Real-time** | Prevent "fast but wrong" | Real-time entitlement/role checks; rate limiting and debounce to stop cascades from noisy signals |
| **Single tasks → End-to-end execution** | Guardrails for tool use | Tool allowlist; approval workflow for sensitive actions (privilege changes, billing terms); scoped org context (multi-tenant isolation) |
| **Inconsistent → Policy-driven consistency** | Policy enforced centrally, not client-side | RBAC/ABAC enforced server-side — never rely on UI-layer role checks |
| **Static reporting → Intelligent operations** | Recommendations must be explainable | Store provenance (source, rule, reasoning); surface "why," not just outcomes, to admins |

This table is the enforcement counterpart to `entitlement-role-sync-policy.md` — that doc defines *what* the agent may decide; this table defines *how the platform ensures it can't cheat.*

---

## 3. Policy-as-Code: OPA/Rego for Infrastructure Compliance

### 3.1 Goal
Given an IaC "resource intent" (e.g., from a Terraform plan), policy evaluation either:
- **Denies** (hard block), or
- **Allows with warnings** (soft block / routes to approval)

### 3.2 Normalized resource model
Before Rego evaluates anything, normalize each provider's resource into a common shape:

- `resource.type` (e.g., `storage_bucket`, `database`, `volume`)
- `resource.cloud` (`aws` | `azure` | `gcp` | `onprem`)
- `resource.encryption.mode` (`none` | `provider` | `cmek` | `cmk`)
- `resource.encryption.key_arn_or_id` (string or null)
- `resource.logging.audit_enabled` (bool)
- `resource.resource_name`
- `resource.category` (`sensitive_finance`, `general`, etc.)

This normalization is what lets the same policy logic run at CI/CD time *and* at runtime for drift detection (see §4).

### 3.3 Policy: fail-closed, per-org approved keys

**Policy change:** the encryption policy always includes the org-scoped key allowlist, and CI/CD treats every violation the same way — **fail-closed**. There is no soft-block path. Hard and soft violations are no longer distinguished for CI/CD purposes; any `deny` fails the pipeline. An explicit `allow` rule now exists too — a resource passes only when `deny` is empty, not by default.

```rego
package cloud.encryption

default allow = false

deny[msg] {
  # 1) If sensitive finance requires CMK, we must have a configured org allowlist
  input.resource.category == "sensitive_finance"
  input.org.required_kms.enabled

  not input.org.approved_key_ids
  msg := sprintf("Encryption policy violation: %s missing org approved_key_ids allowlist",
                 [input.resource.resource_name])
}

deny[msg] {
  # 2) If CMK is required, encryption mode must be CMK
  input.resource.category == "sensitive_finance"
  input.org.required_kms.enabled

  input.resource.encryption.mode != "cmk"
  msg := sprintf("Encryption policy violation: %s requires CMK (mode=%s)",
                 [input.resource.resource_name, input.resource.encryption.mode])
}

deny[msg] {
  # 3) If CMK is used, the key must be in the org-scoped allowlist (fail-closed)
  input.resource.category == "sensitive_finance"
  input.org.required_kms.enabled

  input.resource.encryption.mode == "cmk"
  not (input.resource.encryption.key_arn_or_id in input.org.approved_key_ids)

  msg := sprintf("Encryption policy violation: %s uses unapproved key=%v",
                 [input.resource.resource_name, input.resource.encryption.key_arn_or_id])
}

deny[msg] {
  # 4) Audit/logging fail-closed example
  input.resource.logging.audit_enabled == false
  msg := sprintf("Audit logging must be enabled for %s", [input.resource.resource_name])
}

allow {
  not deny[_]
}
```

Rule 1 is new and closes a gap in the previous version: if an org somehow has no `approved_key_ids` configured at all, that's a violation in its own right — not just "no matching key found." An org with no allowlist can never satisfy rule 3, but calling it out explicitly (rule 1) gives admins a clearer, more actionable error message than a generic "unapproved key" failure would.

### 3.4 Structured violation report
```rego
package cloud.violation_report

violations[v] {
  v := {
    "resource_name": input.resource.resource_name,
    "rule": input.rule_name,
    "message": input.rule_message
  }
}
```

### 3.5 CI/CD behavior — the contract

This is treated as a fixed contract between the pipeline and the policy engine, not a set of loose guidelines:

1. **Input construction — always includes:**
   - `input.org.required_kms.enabled`
   - `input.org.approved_key_ids` (the org-scoped allowlist)
   - All `resource` fields the rules depend on
   No partial input. If any of these can't be resolved for an org, that itself should surface as a policy violation (see rule 1 in §3.3), not a silently skipped check.
2. **Run policy.** If `deny` returns anything → **fail the pipeline.** Full stop.
3. **No soft exception in CI.** The pipeline does not "allow" with a warning. Exceptions are a governance/admin action taken outside the pipeline — never a CI-time override. A previous version of this policy allowed a "soft block" mode that kept the pipeline green with a medium-severity warning; that mode is retired.

### 3.6 On failure — remediation via approval queue

When CI fails, remediation happens outside the pipeline, never by weakening the gate:

1. **Auto-open an approval request** containing:
   - Affected resource(s)
   - The `deny` messages (or rule IDs, if tracked)
   - A proposed compliant fix — e.g., *"Update CMK reference to one of `org.approved_key_ids`"* — which the AI agent may draft
2. **Admin remediation loop:**
   - Approve by updating `org.approved_key_ids` (add/confirm the CMK) — this is the actual governance decision, not a pipeline flag
   - Re-run CI
   - **Drift detector** then confirms the runtime state is actually compliant — the finding isn't closed until the corrected state is observed live, not just approved on paper

This keeps the platform fail-closed without ever trading security for pipeline convenience.

> **See also:** `service-architecture.md` maps this exact flow onto concrete services — `policy-service`, `workflow-service`, and `remediation-worker` — including how native compute (crypto/parsing) is isolated so it can never become an unaudited path around this governance model.

---

## 4. Runtime Drift Detection (Continuous Enforcement)

### 4.1 Goal
Catch when a **live** resource becomes non-compliant after deployment — console edits, misconfiguration, hotfix drift, or a compromised credential doing something it shouldn't.

### 4.2 What to evaluate

**Encryption compliance**
- Encryption mode changed to non-compliant
- CMK reference changed/removed
- Key disabled/deleted/scheduled for deletion

**Audit/logging compliance**
- Audit logging disabled
- Logs stop flowing to the central sink

**Key lifecycle signals**
- Key policy changed (who can decrypt)
- Sudden change in decrypt/access patterns (possible exfiltration signal)

**Identity/permissions drift** (critical for this platform specifically, given the role-sync agent)
- Admin roles granted or removed outside the normal flow
- Service accounts gaining access to encrypted data improperly
- Changes to access policies around decryption

### 4.3 Architecture
- **Drift Collector** (per cloud + on-prem) — pulls current config, key state, and access policies
- **Policy Evaluator** — reuses the same normalized model and Rego policies from §3
- **Evidence Store** — saves before/after snapshots (or at minimum current state + hash)
- **Alert + Ticket/Approval integration** — findings route to SIEM and into the admin panel's approval queue

### 4.4 Scheduling strategy
| Check type | Cadence |
|---|---|
| Encryption/audit drift | Every 15–60 minutes, risk-dependent |
| Key lifecycle | Event-driven where possible + periodic reconciliation |
| Permission drift | Every 1–4 hours, or on audit events |

### 4.5 Event sources
- **AWS:** CloudTrail management events (KMS key policy changes, encryption config changes), Config change events
- **Azure:** Activity logs + resource change events
- **GCP:** Cloud Audit Logs + resource configuration changes
- **On-prem:** equivalent audit hooks (Vault logs, HSM audit, orchestration logs)

### 4.6 Alert lifecycle — fail-closed for sensitive findings
1. Deduplicate by `(resource_id, rule_id, detected_state_hash)`
2. If drift persists across N checks, escalate severity
3. **For sensitive findings** (non-compliant with org-approved keys or CMK policy): raise a **high-severity incident immediately** and **block remediation execution** unless a matching approved change already exists — no auto-remediation on a fail-closed finding, ever.
4. Mark a finding "resolved" **only** after the corrected state is actually observed live. An approval on paper is not resolution; the drift detector has to confirm the fix landed.

---

## 5. End-to-End Flow: CI/CD Gate → Runtime Loop → Admin Remediation

### 5.1 Unified guardrail path
Both human admins and the AI agent funnel through the **same** enforcement path — there is no separate, looser path for AI-initiated changes.

1. **AI proposes/executes**
   - Auto-execute only for low-risk, entitlement-consistent paths (per `entitlement-role-sync-policy.md`)
   - High-risk encryption/key/privilege changes → AI creates an approval-required ticket instead of acting
2. **Admin requests JIT elevation**
   - Sensitive changes require time-bound, admin-requested privileges in the control plane
   - Any AI execution under that elevation uses the same server-side elevation state — the agent cannot self-elevate
3. **CI/CD policy-as-code gate**
   - Terraform plan → OPA/Rego check (§3)
   - Hard violation → pipeline fails
   - Soft violation → approval request created
4. **Deploy** — infra changes applied
5. **Runtime drift detector confirms compliance**
   - Evaluator confirms the new config is compliant
   - Drift alert (if any existed) closes
   - Audit trail links: approval request → deployment → drift clearance, end to end

### 5.2 Admin panel — drift finding view
For each finding, the admin sees:
- Resource identifier + cloud
- Which rule failed (e.g., `cloud.encryption:cmk_required`)
- Current state vs. compliant state
- Evidence timestamps
- Actions:
  - **Open remediation approval** (if required)
  - **Run remediation** (only if the admin has active JIT elevation and policy allows auto-fix)
  - **Mark exception** (time-limited, auditable)

### 5.3 AI agent role in remediation — the compliant lane

The agent can still automate effectively, but only within a strictly compliant lane. It **never** makes the pipeline pass or bypasses the policy engine — it operates *around* the gate, not *through* it.

The agent **can**:
- Propose and generate compliant IaC patches
- Prepare remediation
- Validate that a proposed change would comply, via a dry-run policy check

The agent **executes** only after **all four** conditions hold:
1. Admin has approved the change, **and**
2. The org's `approved_key_ids` allowlist has been updated (or the correct CMK is already referenced), **and**
3. CI policy passes — cleanly, with no violations, **and**
4. Runtime confirms compliance on the live resource after execution

There is no partial-credit path: the agent cannot execute on "3 of 4" holding.

---

## 6. Universal Identity & Authorization (Works Across Every Integration)

The following principles apply regardless of which external system (calendar, CRM, billing, file storage) the agent is touching.

### 6.1 Identity as the foundation
- **SSO (OIDC/SAML)** for admins/users — access decisions come from a trusted identity provider
- The platform issues and validates **its own short-lived access tokens** for automation/auth, independent of variance in the user's SSO token

### 6.2 Universal authorization policy
- Central RBAC/ABAC policies: role rules, entitlement rules, approval rules
- **Every** AI action — read, recommend, or execute — is checked against the same policy engine, regardless of where the underlying data lives

### 6.3 Multi-tenant isolation, everywhere
- Every request is scoped to an `org_id`
- Tool/connectors run with **least-privilege, org-scoped credentials** — an org or user in one environment cannot affect another

### 6.4 Standardized connector model
Support broad integrations through a consistent connector shape:
- Calendar/Workspace connector (e.g., Google Workspace)
- File storage connector
- Ticketing/CRM connector
- Billing connector

Each connector exposes the same internal capabilities to the agent (read entitlements, fetch billing status, check permissions) — **the platform handles security and policy enforcement centrally**, not the connector itself.

> **See also:** `connector-authorization.md` and the reference implementation in `connector-auth-service/` implement this model concretely for Google, Spotify, and LinkedIn — gated behind a valid platform token (never an unauthenticated request), with tokens stored server-side rather than returned to the client.

### 6.5 Consistent security model across integrations
No matter what system is integrated:
- TLS 1.3 for all transit
- Encryption at rest in whatever storage/database service is used
- KMS/HSM (provider-managed or compatible) for keys
- Audit logs and provenance for every AI-driven decision/action

### 6.6 Cross-system guardrails for proactive AI
Because the agent can act automatically, safety has to hold across every integrated system, not just the core platform:
- Auto-execute only for entitlement-consistent role updates (the low-risk lane)
- Everything else routes to the approval queue
- Entitlements and token validity are validated **server-side** before execution, every time — never trust a cached or client-asserted state

---

## 7. Open Questions

- [x] ~~Which cloud(s) are in scope for v1 drift detection~~ — **Resolved: single-cloud first.** V1 scopes drift detection to one cloud provider; multi-cloud collectors (§4.5) are a later expansion once the single-cloud loop is proven.
- [ ] Confidential computing/enclaves — is this a v1 requirement or a later hardening step, given it adds real infra complexity?
- [x] ~~Soft-block governance~~ — **Resolved:** fail-closed for all violations, no soft-pass path. Remediation happens via the approval queue, never by weakening the CI/CD gate.
- [x] ~~Which SIEM (if any) do drift alerts route to, and is that configurable per org or fixed?~~ — **Resolved: configurable per org.** No single fixed SIEM — each org configures its own destination (e.g., a generic webhook or Splunk HEC-compatible endpoint) in Security Controls, consistent with how alert channels are handled elsewhere (`entitlement-role-sync-policy.md` §10).

---
*This document should be kept in sync with `architecture.md` (Security & Compliance Foundation) and `entitlement-role-sync-policy.md` (role/entitlement automation rules specifically).*

# Entitlement Role Sync — Automation & Approval Policy

**Status:** Draft design spec
**Owner:** Engineering / Security
**Related docs:** `engineering/architecture.md` (Secure Identity & Tokenization, Consent & Containment layers), `general/business_context.md`, `security-architecture.md` (crypto standards, policy-as-code enforcement, and drift detection that this policy's JIT elevation and approval mechanics rely on)

This document defines how JIMJAM'EST agents are permitted to act on user roles and entitlements automatically, versus when they must stop and route to a human. It is the concrete policy layer sitting behind the "RBAC/ABAC Access Control" and "Consent & Containment" boxes in the architecture diagram.

---

## 1. Core Principle

**Auto-execute low-risk actions. Require admin approval for anything that expands privilege, changes billing, or overrides security policy.**

| Behavior | Default |
|---|---|
| Keep roles aligned to subscription entitlements | ✅ Auto-execute |
| Auto-disable features when subscription balance is depleted | ✅ Auto-execute |
| Correct access to match the approved role map | ✅ Auto-execute |
| Grant new high-privilege rights | ⛔ Approval required |
| Change billing terms | ⛔ Approval required |
| Override security policy | ⛔ Approval required |
| Touch sensitive finance/billing records beyond entitlement sync | ⛔ Approval required |

**Rule of thumb:** the agent can *run entitlement sync* automatically. It can never *perform privilege escalation* automatically.

---

## 2. In-Scope Actions (v1)

### 2.1 Role assignment / role correction
Driven by three inputs:
1. A valid platform access token
2. The user's subscription entitlement
3. The org's configured role policy map

### 2.2 Subscription balance monitoring
Interpreted as:
- Time remaining and/or usage remaining on the subscription
- Automated alerts as balance approaches depletion
- Enforced feature gating once balance/entitlement ends

---

## 3. Safe Role-Assignment Design

To prevent the agent from ever granting the wrong role, three components work together:

1. **Policy Map (admin-configured)**
   `If plan = X and user attribute = Y → allowed role set = {…}`

2. **AI Agent Role Sync (auto)**
   - Reads token validity + org plan/balance state
   - Computes the allowed role set
   - Applies only roles within that allowed set

3. **Hard block on forbidden transitions**
   The agent cannot assign a role that violates the org's security rules — even if the token claims validity. Policy always wins over token claims.

---

## 4. Token Validity vs. Entitlement Window

Two distinct concepts, both required:

| Concept | Meaning |
|---|---|
| **Token validity window** | The token authorizing the agent to act right now |
| **Entitlement effective window** | The period during which the subscription balance entitles the user to specific features/roles |

**Behavior rules:**
- Roles may be auto-updated **only when both** are true: the token is valid **and** the entitlement says the user should have those roles.
- If the token becomes invalid → the agent stops acting immediately; authorization falls back to server-side checks.
- If subscription balance is low or expired → the agent **auto-revokes** down to the expired/limited role set. This is treated as low-risk because it *restricts* access rather than granting new power.

---

## 5. Auto-Execute Workflow (Role Assignment)

**Step 1 — Token check (server-verified)**
- Validate token signature and expiry
- Confirm `org_id` and `user_id` from token claims — never trust agent-provided claims

**Step 2 — Entitlement check**
- Determine allowed feature set / allowed roles from:
  - Plan tier
  - Subscription time/balance state
  - Org role policy map (admin-defined)
- Compute `allowed_roles`

**Step 3 — Role transition safety**
- If `current_roles ⊄ allowed_roles`:
  - Auto-**remove** forbidden roles (restriction = low-risk)
  - Auto-**add** only roles present in `allowed_roles` — never add outside policy
- If the change would require granting any role not covered by entitlement/policy → **queue for admin approval**, even under the "auto" default. This is the safety rail that makes automation acceptable.

**Step 4 — Execute + audit**
- Apply the role update
- Record an audit event containing:
  - Token validity info (expiry, `org_id` match)
  - Entitlement rule matched
  - Roles added / removed
  - Timestamp + `job_id`

---

## 6. Modeling "Balance → Time Remaining"

`how long balance in subscriptions` is modeled as:
- `effective_end_time` (or time remaining), plus
- Optional usage/balance counters where a true consumable balance exists

**Trigger cadence:**
- Scheduled (e.g., daily/hourly), **and**
- Event-driven: payment success, plan change, token refresh

**On expiry:**
- Agent auto-switches the user to the lowest entitlement role set (restricted mode)
- Agent **never** auto-grants higher roles after expiry — that always requires a fresh entitlement check that passes, not just the passage of time.

---

## 7. Two Safety Rails (mandatory)

1. **Entitlement allowlist rail** — the agent can only assign roles present in the computed `allowed_roles`. No exceptions.
2. **Restriction-first rail** — when in doubt, or when entitlement is expired/invalid, the default action is to restrict access, never to preserve or expand it.

---

## 8. Admin Panel Requirements

Minimum screens needed for approvals and oversight to remain meaningful even with automation enabled:

| Screen | Purpose |
|---|---|
| **Role Policy Map** | Edit plan/balance → `allowed_roles` mapping |
| **Automation Rules** | Configure what's auto vs. approval-required (entitlement-driven by default) |
| **Approvals Queue** | Only surfaces transitions that would violate policy |
| **Audit Log** | Every agent decision + human approval, with reasoning and timestamps |
| **Subscription Health Dashboard** | Org-level balances, affected users, next scheduled sync runs |
| **Security Controls** | SSO settings, token/automation toggles |

**Audit log must capture, per event:**
- What the agent decided
- Why (policy rule matched, token claims, balance state)
- What action it took, or what it queued for approval

---

## 9. 24-Hour Prototype Scope

Build exactly one agent job first: **Entitlement Role Sync**

- **Trigger:** daily schedule + on token refresh (or a manual `run sync` endpoint for testing)
- **Admin panel (minimum):**
  - Edit the policy map
  - View the audit log
  - See "queued for approval" when a computed transition is disallowed

Everything else in this doc (finance/billing changes, security policy overrides, high-privilege grants) stays manual/approval-gated until the core sync loop is proven reliable in production.

---

## 10. Open Questions

- [x] ~~What counts as a "high-privilege" role for the purposes of the approval threshold~~ — **Resolved:** platform-default list (e.g., `org_admin`, `billing_admin`, `security_admin`), configurable per org via the Role Policy Map screen. Orgs can add to the list; the platform default is the floor, not a ceiling.
- [x] ~~Where does the policy map live — is it versioned, and can changes retroactively trigger a re-sync?~~ — **Resolved:** the policy map is versioned. A change takes effect on the **next scheduled sync**, not as an immediate forced re-sync — this avoids a policy edit causing a sudden mass role change across every active user at once.
- [x] ~~What's the alerting channel for balance-depletion warnings~~ — **Resolved:** email + in-app by default; webhook to org admin available as an optional per-org addition.
- [ ] Should token refresh failures trigger an immediate restrict-to-lowest-tier action, or a grace period first?

---
*This policy governs the automation boundary for role/entitlement actions specifically. It should be read alongside the broader Security & Compliance Foundation in `architecture.md`.*

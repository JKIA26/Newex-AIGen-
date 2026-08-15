# Connector Authorization Layer — Google, Spotify, LinkedIn (+ extensible)

**Status:** Draft design + working prototype
**Owner:** Engineering
**Related docs:** `security-architecture.md` (§6.1 Identity foundation, §6.4 Standardized connector model), `architecture.md`

This document defines a **standalone connector authorization module** that lets an already-authenticated JIMJAM'EST user grant agents access to third-party accounts (Google, Spotify, LinkedIn, and further providers later) — implementing the "Standardized connector model" described in `security-architecture.md` §6.4.

**This module is not an identity provider.** It does not decide who is allowed into JIMJAM'EST — that remains SSO (OIDC/SAML) per §6.1. It only handles: *"this already-logged-in user wants to connect Spotify — get and hold that authorization safely."*

---

## 1. What changed from the original spec, and why

The original "Unified Login Hub" concept had two issues that made it unsafe to build as-is:

### 1.1 One shared OAuth `code` across three providers — broken
Each provider (Google, Spotify, LinkedIn) issues its **own** authorization code on its **own** redirect back to your app. A single `/callback` route that takes one `code` and tries to redeem it against all three providers will fail for at least two of them — the code is provider-specific and single-use.

**Fix:** one `/connect/{provider}/login` + `/connect/{provider}/callback` pair per provider, each redeeming its own code against its own token endpoint.

### 1.2 Hardcoded, shared TOTP secret — not real MFA, and redundant
The original spec generated MFA off a single hardcoded secret (`"JBSWY3DPEHPK3PXP"`) used for every request — meaning every user's authenticator app would produce a code that verifies *any* user's login. That's not functioning MFA.

**Fix:** removed entirely. MFA is already handled at the SSO/identity-provider layer (`security-architecture.md` §6.1, and the "MFA enforced" toggle in the admin console's Security Controls screen). A connector-authorization module doesn't need — and shouldn't duplicate — its own MFA system; it operates *after* the user is already authenticated and MFA-verified by SSO.

---

## 2. Where this sits in the architecture

```
User → SSO (OIDC/SAML) → JIMJAM'EST short-lived platform token
                                   │
                                   ▼
                    Connector Authorization Layer (this module)
                                   │
                 ┌─────────────────┼─────────────────┐
                 ▼                 ▼                 ▼
             Google OAuth     Spotify OAuth     LinkedIn OAuth
```

Every request into this module requires a **valid JIMJAM'EST platform token** (per `entitlement-role-sync-policy.md`'s token validity rules) — it never accepts an anonymous or unauthenticated connection request. This mirrors the "server-verified token, never trust client claims" rule from that doc.

---

## 3. Scopes & data handling

- Each provider connection is stored **per user, per org**, scoped exactly like any other connector in §6.4 — least-privilege, org-scoped credentials
- OAuth tokens for connected services are **never returned to the frontend**. The original spec's `/callback` returning raw tokens in the JSON response is fixed here — tokens are stored server-side (encrypted at rest, per `security-architecture.md` §1.3) and referenced only by an internal connection ID
- Each connector requests the minimum scopes needed for its intended use — not broad "everything" scopes by default

---

## 4. Open questions

- [ ] Which specific agent workflows will actually use each connector (e.g., does Spotify data feed into any current Ops/Support/Sales workflow, or is it a placeholder for a future use case)?
- [ ] Token storage: dedicated secrets table with KMS-encrypted columns, or delegate entirely to the KMS/HSM layer directly?
- [ ] Revocation flow — does disconnecting a provider in the UI also revoke the token at the provider (not just delete it locally)?
- [ ] Rate limiting per provider — LinkedIn and Spotify both have strict per-app rate limits that will need backoff handling under load

---
*See `connector-auth-service/main.py` for the corrected reference implementation.*

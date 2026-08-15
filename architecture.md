# JIMJAM'EST — Pro Version Integrated Architecture

**Status:** Draft, based on architecture diagram + AI Mode input spec
**Tagline:** Secure, Scalable, Event-Driven, and AI-Enhanced Platform

This document describes the technical architecture underpinning JIMJAM'EST's agent platform, translating the architecture diagram into a reference doc for engineering.

---

## 1. Layer Overview

The platform is organized into seven cooperating layers, connected left-to-right by a central event-driven backbone.

### 1.1 Experience & Operations (entry layer)
- **Public Website & Authenticated Application** — public site, authenticated app, scientific dashboards, admin
- **Cloud Infrastructure & Observability** — cloud infra, monitoring, alerting, CI/CD
- Traffic flows into the platform through this layer before hitting the API Gateway.

### 1.2 API Gateway & Identity Layer
- Single entry point for all requests
- Handles **API Gateway, Identity & Access Management (IAM)**
- Routes authenticated traffic into the Event-Driven Backbone

### 1.3 Secure Identity & Tokenization
- OAuth2 / OIDC
- Short-lived signed tokens
- MFA, RBAC, encryption, audit logs
- Publishes/consumes events to and from the Event-Driven Backbone (identity-related events)

### 1.4 Consent & Containment
- Explicit consent capture
- Isolated containment nodes (sandboxing for agent actions)
- Scoped contributions, validation, quarantine, approval, and revocation flows
- Also connects bidirectionally to the Event-Driven Backbone — consent/containment decisions are themselves events

> **See also:** `entitlement-role-sync-policy.md` defines the concrete auto-execute vs. admin-approval rules that govern this layer for role/entitlement actions specifically — the entitlement allowlist rail and restriction-first rail described there are the operational implementation of "Consent & Containment" for RBAC/ABAC changes.

### 1.5 Event-Driven Backbone (core)
The central nervous system of the platform:

`Event Bus → Webhooks → Real-Time Triggers → Replay → Retries → Dead-Letter Queue`

- Asynchronous event bus
- Real-time triggers
- Webhooks for external system integration
- Replay capability (re-run past events)
- Automatic retries on failure
- Dead-letter queue for events that exhaust retries (visibility instead of silent failure)

This is what makes agent runs behave like production services rather than one-off script executions — every action is an event that can be traced, retried, or replayed.

### 1.6 MML Content Layer
- Structured media/markup
- Reusable components
- Cross-platform rendering
- Validation, versioning, and rollback
- Bidirectionally connected to the backbone (content changes emit/consume events)

### 1.7 AI Capability Layer
- Drafting
- Classification
- Anomaly detection
- Personalization
- Evidence-aware assistance, with governance
- Bidirectionally connected to the backbone (AI actions are triggered by, and emit, events)

### 1.8 Data & Operations Layer (sink)
- Transactional database
- Object & media storage
- Scientific datasets & search
- Immutable audit log & analytics
- Monitoring & alerting

All layers ultimately read/write here; the immutable audit log is the system of record for compliance and traceability.

---

## 2. Security & Compliance Foundation

Applies horizontally across every layer:
- TLS encryption
- AES-256 data protection
- RBAC/ABAC access control *(governed by `entitlement-role-sync-policy.md` — see auto-execute vs. approval rules, token validity vs. entitlement window)*
- MFA enabled
- Secure tokenization
- Provenance & traceability
- Comprehensive observability

> **See also:** `security-architecture.md` defines the concrete crypto standards (TLS 1.3, AES-256, KMS/HSM key management), the OPA/Rego policy-as-code gates enforced in CI/CD, and the runtime drift-detection loop that keeps this foundation continuously enforced — not just enforced at deploy time.

---

## 3. Input Handling (AI Capability Layer — Interaction Modes)

The AI Capability Layer supports flexible multimodal input, referred to internally as **AI Mode**:

| Input type | Description |
|---|---|
| **Text** | Standard typed queries |
| **Image** | Users can upload images for additional context |
| **Voice** | Voice queries supported |

### 3.1 Advanced Reasoning
AI Mode is designed to parse and answer **multi-part questions**, decomposing complex queries into sub-tasks and returning organized, detailed responses rather than a single flat answer.

### 3.2 Key Benefits

| Feature | Description |
|---|---|
| Comprehensive Responses | Detailed answers to complex, multi-part queries |
| Follow-Up Questions | Users can drill deeper into a topic conversationally |
| Multimodal Support | Accepts text, image, and voice — flexible across use cases |

### 3.3 Usage Scenarios
- **Exploring new topics** — organized information on unfamiliar subjects
- **Product/feature comparisons** — structured side-by-side answers
- **Real-time conversations** — back-and-forth clarification, not just single-shot Q&A

> Note: AI Mode is described as continually evolving via user feedback — treat this as a live capability, not a fixed spec. Revisit this section as the AI Capability Layer matures.

---

## 4. How This Maps to Agent Execution

Tying this back to the platform's core value prop (`POST /v1/agents/execute` → `status: completed`):

1. A trigger event (support ticket created, lead form submitted, scheduled job) enters via the **API Gateway**.
2. **Identity & Consent** layers authenticate the request and confirm scope/permissions.
3. The event is placed on the **Event-Driven Backbone**, where it can be routed, retried, replayed, or dead-lettered.
4. The **AI Capability Layer** performs the actual task (draft, classify, detect anomaly, personalize) — optionally using multimodal input (text/image/voice) per the AI Mode spec above.
5. Results are persisted to the **Data & Operations Layer**, with every step captured in the **immutable audit log**.

This is the technical backbone behind the three launch workflows in `business_context.md`: Support Triage, Lead Follow-up, and Ops Handoff.

---

## 5. Open Questions for Engineering

- [ ] Which message broker/event bus technology (Kafka, SQS, NATS, etc.)?
- [ ] Retry/backoff policy specifics (max attempts, backoff curve)
- [ ] Containment node isolation mechanism (containers? VMs? language-level sandboxing?)
- [ ] Voice input — which STT provider, and is it in scope for v1 or a later release?
- [ ] Data residency requirements for Scientific Datasets & Search (relevant if serving regulated industries)

---
*This document should be kept in sync with `general/business_context.md`. Update as architecture decisions are finalized.*

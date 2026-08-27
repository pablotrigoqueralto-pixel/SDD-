# Quermed CRM — Project Constitution

These principles are inviolable. Every OpenSpec change (proposal, specs, design, tasks) must comply with them, and any design that conflicts with them must be rejected or explicitly escalated to the product owner.

## 1. Product context

Quermed S.A. (Madrid, 1978) distributes medical technology to healthcare professionals in Spain across seven divisions (assisted reproduction, consumables, gynaecology, vascular, neurology, equipment, carts & support arms). The CRM serves a small sales team working by territory and speciality, plus sales management, back office and, later, technical service.

Two sales rhythms coexist and must both be first-class: recurring consumables (protect recurrence, detect consumption drops) and long-cycle equipment (demo → quote → negotiation/tender → installation → training).

## 2. Product design principles (inviolable)

1. **30-second rule** — registering a visit, creating a contact or moving an opportunity must take ≤ 30 seconds on a phone.
2. **Zero useless fields** — every field must justify itself with a real use in a report, alert or flow. Mandatory fields are the minimum. No configurable custom fields.
3. **Smart defaults** — owner, territory, division and date are pre-filled whenever derivable.
4. **One screen, one purpose** — no nested tabs; the account 360º view is a single scrollable page with collapsible sections.
5. **Mobile-first for real** — design for the phone first, then desktop. Large buttons, primary actions always visible, usable with poor connectivity.
6. **Business vocabulary** — UI uses "Centro", "Comercial", "Visita", "Presupuesto", "Demo", "Licitación". Never CRM jargon (lead scoring, MQL, workflow rule).
7. **Language** — UI in Spanish (Spain). Architecture i18n-ready; no other languages implemented now. Code, docs, commits and tests in English.
8. **Accessibility and consistency** — one design system, reusable components, adequate contrast, keyboard navigable.

Golden rule: **simplicity always wins.** When a powerful feature and a simple interface conflict, the simple interface is chosen. A new sales rep must be productive without training in under 15 minutes.

## 3. Non-functional requirements (production grade, inviolable)

- **Architecture** — clear layer separation, well-modelled domain, OpenAPI-documented API, extensible without rewrites.
- **Security** — robust authentication (SSO-ready via OIDC / Microsoft Entra ID), RBAC + territory ownership, encryption in transit and at rest, OWASP Top 10 mitigations, rate limiting, secrets outside the code.
- **GDPR / LOPDGDD** — contact consent, right to erasure (anonymisation), personal-data access logging, data minimisation.
- **Audit** — immutable change log on accounts, contacts, opportunities and quotes (who, what, when).
- **Concurrency** — multi-user editing without data loss (optimistic locking with version + `If-Match`, conflict dialog).
- **Performance** — lists and search < 500 ms with tens of thousands of records; pagination and indexes designed up front.
- **Quality** — unit, integration and E2E tests for critical flows; CI blocks merge on failure; automatic lint and format.
- **Operations** — dev/staging/prod environments, versioned migrations, automated backups with tested restore, structured logging, error metrics and alerts, reproducible container deployment.
- **Observability** — error traceability (trace id per request) so the sales team can be supported.
- **Documentation** — startup README, deployment guide, short user guide per role.

## 4. Process rules

- Spec-Driven Development only. No code before an approved change with proposal, specs, design and tasks.
- One change = one closed, tested business capability. Small, verifiable steps.
- Every architecture decision is recorded in the change's design with discarded alternatives and reasons.
- Ambiguity is resolved by asking, not assuming.
- Standards in `ai-specs/specs/backend-standards.mdc` and `frontend-standards.mdc` are binding; `api-spec.yml`, `data-model.md` and `development_guide.md` must reflect the current system at all times.

## 5. Explicitly out of scope

Complex marketing automation, chatbots, e-commerce, full accounting, full warehouse management, per-user UI customisation.

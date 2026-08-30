## ADDED Requirements

### Requirement: Quote list screen
`/presupuestos` SHALL list current versions visible to the user — desktop table (número, centro, oportunidad, estado, total, validez, propietario) and mobile cards — with filters for estado, propietario (managers), and "por caducar", plus text search. Estado SHALL render as a badge: Borrador, Enviado, Aceptado, Rechazado, with a distinct "Caducado" visual on expired sent quotes. Rows navigate to the quote sheet. All labels SHALL come from the `quotes` i18n namespace in Spanish business vocabulary (Presupuesto, Validez, IVA, Base imponible).

#### Scenario: Expired badge
- **WHEN** the list shows a sent quote whose `is_expired` is true
- **THEN** the row shows the Caducado visual instead of the plain Enviado badge

### Requirement: Quote sheet
`/presupuestos/:quoteId` SHALL show the display number and status, the opportunity and account links, lines with per-line discount and VAT, totals with VAT breakdown, conditions, validity, the version chain (navigable), and the latest email status (including a visible error and a "Reintentar envío" action on failure). Actions SHALL follow status and role: drafts show Editar, Enviar, Eliminar and PDF preview; sent quotes show Aceptar, Rechazar, Nueva versión and PDF download; superseded versions are read-only with a link to the current one. Cost and margin SHALL render only for managers/admins. PDF download SHALL use an authenticated fetch and object URL.

#### Scenario: Failed email surfaced
- **WHEN** the latest outbox row is `failed`
- **THEN** the sheet shows the error state and the retry action; after a successful retry the state shows Enviado

#### Scenario: Back office actions
- **WHEN** a back-office user opens a draft
- **THEN** they see Editar and Eliminar but no Enviar/Aceptar/Rechazar

### Requirement: Quote form
Creating (from an opportunity's Presupuestos section) and editing a draft SHALL use one form: contact selector (account's contacts), a lines editor (product picker or free-text description, quantity, unit price, discount %, VAT select 21/10/4/0, per-line base) with add/remove, live totals (base, IVA, total) computed with the backend's exact rounding rules, and the conditions fields pre-filled. Validation errors SHALL use i18n keys; saving uses `If-Match` with the standard conflict dialog.

#### Scenario: Live totals match backend
- **WHEN** the user enters quantity 3, price 33,33 €, discount 10 and VAT 21
- **THEN** the line shows base 89,99 € and the totals update without saving, matching the values the backend later persists

### Requirement: Send dialog
The Enviar action SHALL open a dialog with: recipients (multi-select pre-filled with the account's contacts that have email, free-entry allowed), subject and body pre-filled from the admin template with `{numero}`, `{centro}`, `{comercial}` interpolated, editable validity date, a "Enviar sin email" checkbox (manual mode), and a PDF preview link. Confirming SHALL call send and show the resulting email status; when Graph is off the UI SHALL indicate the manual path (download and send yourself).

#### Scenario: Template interpolation
- **WHEN** the dialog opens for `P-2026-0002` of Clínica Tambre owned by Ana García
- **THEN** subject and body show those values substituted and remain editable

#### Scenario: No recipients with email active
- **WHEN** the user removes all recipients and the checkbox is unchecked
- **THEN** the form blocks submission with the recipients-required message

### Requirement: Accept and reject dialogs
Aceptar SHALL confirm with the quote total and the consequence ("gana la oportunidad por {total}; se rechazarán los demás presupuestos") and allow a date; Rechazar SHALL take an optional note. Both SHALL refresh the opportunity data after success.

#### Scenario: Accept consequence visible
- **WHEN** the user opens Aceptar on a quote whose opportunity has another sent quote
- **THEN** the dialog states the opportunity will be won with the quote's total and sibling quotes rejected before the user confirms

### Requirement: Quote settings screen
The admin area SHALL gain a Presupuestos settings screen editing the condition defaults (validez, plazo de entrega, forma de pago, garantía) and the email template (subject, body with placeholder help). Admin-only via the existing role-gated admin routes.

#### Scenario: Defaults saved
- **WHEN** the admin changes validez to 15 and saves
- **THEN** the PUT is sent and new quotes created afterwards show 15 in their conditions

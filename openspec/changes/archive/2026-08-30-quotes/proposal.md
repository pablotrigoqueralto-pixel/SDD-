## Why

Today Quermed's quotes are Word documents assembled by hand: prices are copied from old files, numbering lives in a shared spreadsheet, and nobody can tell which version the customer actually received. Change 06 left opportunities with product lines and a `win` command waiting for a real total; change 05 left exact catalogue prices. This change closes the loop: a **quote** (Presupuesto) built from the opportunity in a minute, numbered automatically, rendered as a branded PDF and emailed from the rep's own Microsoft 365 mailbox — and, when the customer says yes, one tap wins the opportunity with the accepted total.

Constitution principles served: 30-second interactions (lines pre-filled from the opportunity, one screen to adjust discounts and send), smart defaults (validity +30 days, VAT 21%, conditions from admin defaults, recipients from the account contacts), business vocabulary (Presupuesto, Descuento, IVA, Base imponible, Validez — never "quote" in the UI), exact money (`numeric`, two-decimal strings), immutable evidence (sent versions are frozen; revisions create v2), audit of every step, role-gated cost/margin.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Quote aggregate**: `quotes` always belonging to an opportunity (and through it to the account), with yearly company-wide numbering `P-2026-0001` assigned at creation and never reused, `version` chain (`P-2026-0001-v2` supersedes v1 under the same number), status `draft → sent → accepted | rejected`, validity date (sent + 30 days, editable), editable conditions block (validez, plazo de entrega, forma de pago, garantía) seeded from admin-configurable defaults, and totals (base, VAT by rate, total) computed from the lines.
- **Quote lines**: copied from the opportunity's lines at creation (or empty if none), then edited freely on drafts: product (or free-text line), quantity, unit price (list price default), **discount % per line**, **VAT rate per line** (21% default; 10/4/0 selectable). Managers/admins see cost and margin per line and total.
- **Lifecycle**: `send` freezes the content, generates the PDF, emails it via Microsoft Graph from the acting rep's mailbox (recipients pre-filled with the account's contacts with email; editable subject/body from a template) and stamps `sent_at`/`valid_until`; `accept` (records the date, **wins the opportunity** with the quote total and rejects sibling open quotes) and `reject` (optional reason) are manual; `revise` creates the next version as a new draft copying the last sent content. Expired quotes (past `valid_until`) are flagged visually — no automatic status change.
- **PDF**: server-rendered from a fixed template — Quermed logo and fiscal data, account and contact, numbered lines with discount and VAT, totals by VAT rate, conditions block, rep signature footer. Stored so the exact sent document can be re-downloaded.
- **Microsoft 365 email**: OAuth client-credentials Graph integration (`sendMail` as the signed-in rep's mailbox) with settings for tenant/client; a `mail_outbox` record per send with status (`sent` / `failed`) so failures are visible and retryable; when Graph is not configured, `send` still freezes the version and offers the PDF for manual sending (explicit "sin email" mode for local/dev).
- **Opportunity integration**: the opportunity sheet gains a "Presupuestos" section (list + create); `accept` calls the existing `win` with `won_amount = total`; the account 360º "Presupuestos" placeholder becomes real; the timeline gains `quote_sent` / `quote_accepted` / `quote_rejected` entries; "Hoy" gains "Presupuestos por caducar" (≤ 7 days).
- **Screens**: quote form (lines editor with discount/VAT, conditions, totals live), send dialog (recipients, subject, body, PDF preview link), quote sheet (status, versions, PDF download, accept/reject), list `/presupuestos` with filters (status, owner, expiring), admin screen for condition defaults and email template.

## Non-goals

- Customer-facing acceptance links or portals; electronic signature.
- Orders, invoicing or Sage synchronisation (the accepted quote is the hand-off).
- Discount approval workflows (management sees margin; a threshold flow can come later).
- Inbound email tracking (opens/clicks) or scheduled reminders beyond the "Hoy" expiring block.
- Multi-currency; prices stay EUR.
- Editing sent versions: any change after sending is a new version.

## Roles and territory visibility

| Role | Quotes |
|---|---|
| `sales_rep` | Sees quotes of visible accounts; creates, edits drafts, sends, accepts/rejects on opportunities they own. |
| `sales_manager` | Everything on every quote, including cost and margin. |
| `back_office` | Creates and edits **drafts** on any opportunity (prepares paperwork); never sends, accepts or rejects; no cost/margin. |
| `admin` | Everything, plus condition defaults, email template and Graph settings. |

Visibility is the account's visibility, like opportunities.

## Capabilities

### New Capabilities
- `quote-model`: quote aggregate with numbering, versions, lines with discount/VAT, totals, conditions, statuses, freezing on send, margin computation, migration and indexes.
- `quote-api`: scoped list and detail, create-from-opportunity, draft editing, send (PDF + Graph mail + outbox), accept/reject/revise, PDF download, condition-defaults and email-template administration.
- `quote-screens`: quote form with live totals, send dialog, quote sheet with versions and PDF, list with filters, opportunity and account sections, admin defaults screen.

### Modified Capabilities
- `opportunity-api`: `accept` wins the opportunity (reusing `win`); the opportunity read gains a quotes summary; timeline gains `quote_*` entries; `/me/today` gains expiring quotes.
- `opportunity-screens`: opportunity sheet gains the "Presupuestos" section.
- `account-screens`: the "Presupuestos" placeholder becomes a real section.
- `activity-screens`: "Hoy" gains the "Presupuestos por caducar" block.
- `audit-log`: events `quote.*` (created, updated, sent, accepted, rejected, revised, email_failed).

## Impact

- New tables: `quotes`, `quote_lines`, `quote_counters` (year → last number), `mail_outbox`; conditions/email defaults in a small `app_settings` table; migration `0007_quotes`.
- New API: `/api/v1/quotes` (+ `/{id}`, `/{id}/send`, `/{id}/accept`, `/{id}/reject`, `/{id}/revise`, `/{id}/pdf`), `/opportunities/{id}/quotes`, admin `/quote-settings`; extended today/timeline.
- New backend dependencies: a PDF renderer (WeasyPrint or ReportLab — decided in design) and `msgraph`-less plain HTTPS calls via `httpx` for Graph.
- Frontend: `features/quotes` (form, sheet, list, send dialog, admin defaults), sections in opportunity/account pages, i18n namespace `quotes`.
- New settings: `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SENDER_MODE` (off in dev/E2E).
- Documentation: `api-spec.yml`, `data-model.md`, `development_guide.md` (numbering, PDF, Graph setup, outbox).

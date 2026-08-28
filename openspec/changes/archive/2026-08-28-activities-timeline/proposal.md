## Why

A CRM earns its place when the rep records what happened at a centre in the car park, in under thirty seconds, and sees tomorrow's plan on the phone before leaving home. Change 03 delivered the accounts and contacts those interactions attach to; this change adds the interactions themselves — visits, calls, emails, demos, training sessions and notes — the account timeline that shows them, and the first useful "Hoy" screen. Later changes (opportunities, quotes, dashboards) hang their own events on the same timeline.

Constitution principles served: 30-second rule (type + centre + date, everything else optional; defaults to "now, done"), zero useless fields, smart defaults (centre pre-selected from the 360º page, primary contact suggested), one screen one purpose ("Hoy" shows the plan, the timeline shows the history), mobile-first, business vocabulary (Visita, Llamada, Demo, Formación, Nota — never "task" or "lead"), audit.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Activities**: one record per interaction with `activity_type` (seeded master from change 02), `account` (mandatory), participating `contacts` (optional, many), `status` (`planned` | `done` | `cancelled`), `scheduled_at` (date-time), `done_at`, optional `duration_minutes`, `outcome` (`positive` | `neutral` | `negative` | `no_contact`), `subject` (short line), `notes`, `owner` (the rep who did or will do it), `next_action` shortcut (creates a planned activity in the same request). Activity types whose `counts_as_contact` is false (Nota) never become planned.
- **Lifecycle**: planning creates `status = planned`; "Hecha" sets `done` with `done_at` (defaults now) and optional outcome; "Cancelar" sets `cancelled` with a mandatory short reason; rescheduling moves `scheduled_at` and is audited. Done activities stay editable for 7 days by their owner (typo window); managers always.
- **Account timeline**: `GET /accounts/{id}/timeline` returns the activities of the account (newest first, paginated, filter by type and status) and feeds the "Actividades" section of the 360º page, replacing the placeholder from change 03. Future changes append other event kinds (opportunity stage changes, quotes sent) to the same endpoint through a small `TimelineEntry` shape.
- **Last contact on the account**: `accounts.last_contact_at` and `next_activity_at` are maintained from activities whose type `counts_as_contact` (denormalised for the list and future "centros sin visitar" alerts) and shown on the account list and header.
- **"Hoy" screen**: for the signed-in rep, planned activities for today (ordered by time), overdue planned activities (before today, not closed), and weekly counters (done this week by type, planned for the rest of the week). Managers see the same screen for themselves plus a rep selector. One tap "Hecha" / "Reprogramar" from the list.
- **Activity form**: opened from the 360º page (centre pre-filled), from "Hoy" ("Nueva actividad" asks for the centre with a search box) and from the timeline. Above the fold: tipo (segmented icons), centro, fecha/hora (default now) and "Hecha/Planificada" toggle; collapsed: contactos (checkbox list of the account's contacts, primary pre-checked), duración, resultado, asunto, notas, próxima acción.
- **Visibility**: activities inherit the account's scope (a rep sees the activities of accounts they can see); owners and managers edit; back office reads.
- Navigation: "Hoy" becomes the real home; the 360º "Actividades" section shows the last five entries with "Ver todas".

## Non-goals

- Calendar synchronisation with Microsoft 365 or reminders/push notifications (later, after M365 SSO).
- Recurring activities, route planning, geolocation or check-in.
- Email sending or logging from the CRM (the M365 integration change).
- Linking activities to opportunities or quotes (the fields arrive with changes 06/07; the timeline shape already allows it).
- Dashboard KPIs beyond the weekly counters of "Hoy" (change 09).
- Attachments on activities.

## Roles and territory visibility

| Role | Activities and timeline |
|---|---|
| `sales_rep` | Create, plan, close, reschedule and edit (7-day window) activities of visible accounts; owner defaults to self; "Hoy" shows own plan. |
| `sales_manager` | Everything on every account; can create activities for another rep (owner selector) and view any rep's "Hoy". |
| `back_office` | Read timelines and "Hoy" of any rep; no writes. |
| `admin` | Everything. |

Contacts referenced by an activity must belong to the same account; reading a timeline that names contacts follows the personal-data access rule of change 03 (only names are shown, so no access log entry is written).

## Capabilities

### New Capabilities
- `activity-model`: activity aggregate (status lifecycle, outcome, participants, next action, edit window), account `last_contact_at`/`next_activity_at` maintenance, migration and indexes.
- `activity-api`: scoped endpoints for activities, the account timeline and the "Hoy" query, audit events.
- `activity-screens`: activity form (fast path and full path), account timeline section, "Hoy" screen with one-tap actions, rep selector for managers.

### Modified Capabilities
- `account-model`: `accounts` gains `last_contact_at` and `next_activity_at` (denormalised, maintained by the activity service).
- `account-contact-api`: `AccountSummaryRead` / `AccountRead` expose the two new timestamps; list sort by `last_contact_at`.
- `account-screens`: the "Actividades" placeholder becomes the timeline section; header shows "Último contacto".
- `audit-log`: events `activity.*`.
- `app-shell`: "Hoy" renders the plan instead of the placeholder.

## Impact

- New tables: `activities`, `activity_contacts`; columns on `accounts`. Migration `0004_activities`.
- New API: `/api/v1/activities` (list, create), `/activities/{id}` (read, patch), `/activities/{id}/complete`, `/activities/{id}/cancel`, `/activities/{id}/reschedule`, `/accounts/{id}/timeline`, `/me/today` (+ `?user_id=` for managers).
- Frontend: `features/activities` (form, timeline, today), changes in `features/accounts` (section, header, list column) and `app/pages/TodayPage`.
- Documentation: `api-spec.yml`, `data-model.md`, `development_guide.md`.
- No new dependencies.

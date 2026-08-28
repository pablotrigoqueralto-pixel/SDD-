## MODIFIED Requirements

### Requirement: Activity record
The system SHALL persist activities in an `activities` table with `id`, `account_id` (required — every interaction belongs to a centre and feeds its timeline and `last_contact_at`), `activity_type_id` (required — Visita/Llamada/Email/Demo/Formación/Nota drive icons, weekly counters and `counts_as_contact`), `owner_id` (required — the rep whose "Hoy" shows it), `status` (`planned` | `done` | `cancelled`), `scheduled_at` (required — when it happens or happened; orders "Hoy" and the timeline), optional `opportunity_id` (an opportunity of the same account; feeds the opportunity's activity list and clears an automatic at-risk flag when done), optional `done_at`, `duration_minutes` (1–1440), `outcome` (`positive` | `neutral` | `negative` | `no_contact`), `subject` (≤ 120 chars), `notes`, `cancel_reason`, `created_by`, `version`, `created_at`, `updated_at`, plus participating contacts in `activity_contacts`. Database checks SHALL enforce `done → done_at not null`, `cancelled → cancel_reason not null` and `outcome only when done`.

#### Scenario: Minimum activity recorded as done
- **WHEN** an activity is created with only `activity_type_id = visit`, `account_id` and no other field
- **THEN** it is persisted with `status = done`, `scheduled_at = done_at = now`, `owner_id = created_by = the actor`, no contacts, `opportunity_id = null` and `version = 1`

#### Scenario: Planned activity
- **WHEN** an activity is created with `status = planned` and `scheduled_at` tomorrow 09:30
- **THEN** it is persisted with `done_at = null`, `outcome = null`

#### Scenario: Notes cannot be planned
- **WHEN** an activity of type `note` is created with `status = planned`
- **THEN** a validation error `note_cannot_be_planned` is raised

#### Scenario: Contacts must belong to the account
- **WHEN** `contact_ids` includes a contact of another account
- **THEN** a validation error `contact_not_in_account` is raised

#### Scenario: Opportunity must belong to the account
- **WHEN** `opportunity_id` references an opportunity of another account
- **THEN** a validation error `opportunity_not_in_account` is raised

# activity-model

## Purpose
Persistence and lifecycle of activities (visits, calls, emails, demos, training, notes): planned/done/cancelled, edit window, next action, and the denormalised account activity summary.

## Requirements

### Requirement: Activity record
The system SHALL persist activities in an `activities` table with `id`, `account_id` (required — every interaction belongs to a centre and feeds its timeline and `last_contact_at`), `activity_type_id` (required — Visita/Llamada/Email/Demo/Formación/Nota drive icons, weekly counters and `counts_as_contact`), `owner_id` (required — the rep whose "Hoy" shows it), `status` (`planned` | `done` | `cancelled`), `scheduled_at` (required — when it happens or happened; orders "Hoy" and the timeline), optional `opportunity_id` (an opportunity of the same account; feeds the opportunity's activity list and clears an automatic at-risk flag when done), optional `done_at`, `duration_minutes` (1–1440), `outcome` (`positive` | `neutral` | `negative` | `no_contact`), `subject` (≤ 120 chars), `notes`, `cancel_reason`, `created_by`, `version`, `created_at`, `updated_at`, plus participating contacts in `activity_contacts` **and attending Quermed colleagues in `activity_attendees`**. Database checks SHALL enforce `done → done_at not null`, `cancelled → cancel_reason not null` and `outcome only when done`.

#### Scenario: Minimum activity recorded as done
- **WHEN** an activity is created with only `activity_type_id = visit`, `account_id` and no other field
- **THEN** it is persisted with `status = done`, `scheduled_at = done_at = now`, `owner_id = created_by = the actor`, no contacts, no attendees, `opportunity_id = null` and `version = 1`

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

### Requirement: Lifecycle transitions
The aggregate SHALL allow `planned → done` (`complete`), `planned → cancelled` (`cancel`, reason required), `planned → planned` with a new `scheduled_at` (`reschedule`); `done` and `cancelled` SHALL be terminal. Any other transition SHALL raise `invalid_activity_transition` (409). Completing SHALL set `done_at` (default now) and optionally `outcome`, `notes` and `duration_minutes`.

#### Scenario: Complete a planned visit
- **WHEN** `complete` is called on a planned visit with `outcome = positive`
- **THEN** `status = done`, `done_at = now`, `outcome = positive`

#### Scenario: Cancel without reason
- **WHEN** `cancel` is called with an empty reason
- **THEN** a validation error `cancel_reason_required` is raised

#### Scenario: Reschedule a done activity
- **WHEN** `reschedule` is called on a done activity
- **THEN** `invalid_activity_transition` is raised

### Requirement: Edit window
Descriptive fields (`subject`, `notes`, `contact_ids`, `duration_minutes`, `outcome`, `activity_type_id`) of a `done` activity SHALL be editable by its owner for 7 days after `done_at` and by `sales_manager`/`admin` without limit; planned activities SHALL be editable by owner and managers at any time. Editing outside the window SHALL raise `activity_locked` (409).

#### Scenario: Owner edits within the window
- **WHEN** the owner edits the notes of a visit done 3 days ago
- **THEN** the edit is saved and `activity.updated` is recorded

#### Scenario: Owner edits after the window
- **WHEN** the owner edits a visit done 10 days ago
- **THEN** `activity_locked` is raised

#### Scenario: Manager edits after the window
- **WHEN** a `sales_manager` edits the same visit
- **THEN** the edit is saved

### Requirement: Next action shortcut
`create` and `complete` SHALL accept an optional `next_action { activity_type_id, scheduled_at, subject? }` that creates a `planned` activity in the same transaction with the same account, contacts and owner. `scheduled_at` SHALL be in the future (`next_action_in_past` otherwise) and the type SHALL not be `note`.

#### Scenario: Close and plan the next visit
- **WHEN** a rep completes a visit with `next_action = { call, next Monday 10:00 }`
- **THEN** a planned call for next Monday exists for the same account and owner and the response carries its id as `next_activity_id`

#### Scenario: Next action in the past
- **WHEN** `next_action.scheduled_at` is yesterday
- **THEN** a validation error `next_action_in_past` is raised

### Requirement: Account activity summary
After every activity command the system SHALL recompute on the account `last_contact_at = MAX(scheduled_at)` over `done` activities whose type `counts_as_contact`, and `next_activity_at = MIN(scheduled_at)` over `planned` activities. Both columns SHALL be read-only through the API.

#### Scenario: Note does not count as contact
- **WHEN** the only done activity of an account is a `note`
- **THEN** `last_contact_at` is null

#### Scenario: Summary follows commands
- **WHEN** a planned visit for Friday is completed today and a call is planned for next week
- **THEN** `last_contact_at = today` and `next_activity_at = next week`

#### Scenario: Cancelling the only planned activity
- **WHEN** the only planned activity of an account is cancelled
- **THEN** `next_activity_at` is null

### Requirement: Migration and indexes
Alembic migration `0004_activities` SHALL create `activities`, `activity_contacts`, the enums `activities_status_enum` and `activities_outcome_enum`, the indexes `(account_id, scheduled_at DESC)`, `(owner_id, status, scheduled_at)`, `activity_type_id`, `status`, the columns `accounts.last_contact_at` / `accounts.next_activity_at` with index `(territory_id, last_contact_at)`, and the `crm_app` grants. Downgrade SHALL revert them.

#### Scenario: Round trip
- **WHEN** `alembic upgrade head`, `downgrade 0003_accounts_contacts`, `upgrade head` and `alembic check` run
- **THEN** every step succeeds and no drift is reported

### Requirement: Internal attendees
An activity MAY carry several Quermed users as attendees in `activity_attendees` (composite primary key `(activity_id, user_id)`, cascading from the activity). An attendee SHALL be an **active** user (else `attendee_not_active`) and SHALL NOT be the activity's **owner** (else `owner_cannot_attend`) — the owner is already on the activity, and a row saying otherwise would show it twice in their day and skew every count. Attendees SHALL be replaced wholesale when the activity is saved, like the account's child collections.

Attendees are colleagues, never the centre's people: the hospital's participants stay in `activity_contacts`, so no query has to guess which half of a mixed table it wants.

#### Scenario: Two colleagues on one visit
- **WHEN** a visit owned by one rep is saved with a colleague as attendee
- **THEN** both are recorded, the owner as `owner_id` and the colleague as one `activity_attendees` row

#### Scenario: Owner cannot attend their own activity
- **WHEN** the owner's id is included in the attendees
- **THEN** a validation error `owner_cannot_attend` is raised

#### Scenario: Inactive colleague
- **WHEN** an attendee references a deactivated user
- **THEN** a validation error `attendee_not_active` is raised

#### Scenario: Attendees replaced on save
- **WHEN** an activity with two attendees is saved with one
- **THEN** only that one remains

#### Scenario: Attendees do not own anything
- **WHEN** an attendee attempts to complete, reschedule or cancel the activity
- **THEN** it is refused exactly as for any other non-owner: attending changes what you see, never what you may do

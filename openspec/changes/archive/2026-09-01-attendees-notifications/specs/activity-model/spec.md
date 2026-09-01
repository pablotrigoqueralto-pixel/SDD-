# activity-model (delta)

Activities gain internal attendees, with the invariants that keep an attendee from becoming a second owner.

## MODIFIED Requirements

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

## ADDED Requirements

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

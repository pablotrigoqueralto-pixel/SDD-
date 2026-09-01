# notification-model

## Purpose
The per-user notification inbox: what a notice stores, the snapshot payload, the rule that an actor never notifies themselves, the write that shares the transaction with the change that caused it, and read state that leaves the block without deleting the row.

## Requirements

### Requirement: Notification record
The system SHALL persist notifications in a `notifications` table with `id`, `user_id` (the recipient, FK User `ON DELETE CASCADE` — a deleted user's notices go with them), `kind` (`activity_assigned` | `activity_attending` | `account_assigned` | `opportunity_assigned`), `entity_type` and `entity_id` (what to open when the notice is tapped), `actor_id` (who caused it, FK User `ON DELETE SET NULL`), `payload` (JSONB snapshot of what the line renders: subject, centre name, date), `read_at` (null while unread) and `created_at`. It SHALL be indexed on `(user_id, read_at, created_at DESC)`, which is the shape of "my unread, newest first".

The payload SHALL be a **snapshot taken when the event happened**, not a live join: a notice describes what was done to you then, and must still read correctly when the activity is later renamed or the account reassigned.

#### Scenario: Notice stored for the recipient
- **WHEN** a manager adds a rep as attendee of a visit
- **THEN** a notification exists with that rep as `user_id`, the manager as `actor_id`, `kind = activity_attending`, the activity as entity and a payload carrying the centre and the date

#### Scenario: Payload survives a later edit
- **WHEN** the activity's subject is changed after the notice was created
- **THEN** the notice still shows the subject it was created with

### Requirement: An actor never notifies themselves
Creating a notification whose `user_id` equals its `actor_id` SHALL be a no-op. A user planning their own week, assigning themselves an account or adding themselves to their own activity SHALL produce nothing, so the block only ever holds what somebody else put on them.

#### Scenario: Own activity produces nothing
- **WHEN** a rep creates an activity for themselves
- **THEN** no notification row is created

#### Scenario: Manager assigns to themselves
- **WHEN** a manager assigns an account to themselves
- **THEN** no notification row is created

### Requirement: Notifications are written with the change that causes them
A notification SHALL be collected through the unit of work and committed **in the same transaction** as the write that caused it, the way audit events already are. A rolled-back operation SHALL leave no notice behind.

#### Scenario: Failed write leaves no notice
- **WHEN** an activity creation fails validation after the notification was collected
- **THEN** neither the activity nor the notification is persisted

### Requirement: Read state belongs to the recipient
`read_at` SHALL be set only by the recipient. A notification SHALL never be deleted on read: it leaves the unread block and stays in the table, so the record of what was announced is not lost.

#### Scenario: Marking read
- **WHEN** the recipient marks a notice read
- **THEN** `read_at` is set, the row remains and it no longer counts as unread

### Requirement: Migration and grants
Migration `0011` SHALL create `notifications` with its index and the guarded `crm_app` grants, alongside `activity_attendees`. No backfill SHALL be performed: notifications describe events, and no event happened before the table existed.

#### Scenario: Fresh database
- **WHEN** the migrations run on an empty database
- **THEN** `notifications` and `activity_attendees` exist with their indexes and no rows

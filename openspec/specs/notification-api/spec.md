# notification-api

## Purpose
Reading your own unread notices with their count, marking one or all read, and the four events that create a notification when somebody else assigns you an activity, a centre or an opportunity.

## Requirements

### Requirement: Read own notifications
`GET /api/v1/notifications` SHALL return `NotificationsRead { items: NotificationRead[], unread_count }` for the signed-in user and nobody else — there SHALL be no parameter to read another user's notices, in any role. `items` SHALL carry the **unread** notices, newest first, capped at 20, each with `id`, `kind`, `entity_type`, `entity_id`, `actor_id`, `actor_name`, `payload`, `created_at`. `unread_count` SHALL be the uncapped total, so the bell and the block are fed by one request and cannot disagree.

#### Scenario: Rep reads their notices
- **WHEN** a rep with three unread notices requests the endpoint
- **THEN** the three are returned newest first with `unread_count = 3`

#### Scenario: Nobody reads another's inbox
- **WHEN** any role, including `admin`, adds a `user_id` parameter
- **THEN** it is ignored and their own notifications are returned

#### Scenario: Read ones are absent
- **WHEN** a notice has been marked read
- **THEN** it is absent from `items` and not counted in `unread_count`

#### Scenario: Cap with a truthful count
- **WHEN** a user holds 25 unread notices
- **THEN** `items` has 20 and `unread_count` is 25

### Requirement: Mark notifications read
`POST /api/v1/notifications/{id}/read` SHALL mark one notice read, and `POST /api/v1/notifications/read-all` SHALL mark every unread notice of the caller. Both SHALL return the refreshed `NotificationsRead`. Marking a notice that is already read SHALL succeed without changing `read_at`. A notice belonging to another user SHALL answer 404 `not_found`, never 403 — the caller has no business learning it exists.

#### Scenario: Mark one
- **WHEN** the recipient marks one of three notices read
- **THEN** the response carries the remaining two and `unread_count = 2`

#### Scenario: Mark all
- **WHEN** the recipient posts `read-all`
- **THEN** the response has an empty `items` and `unread_count = 0`

#### Scenario: Someone else's notice
- **WHEN** a user marks a notice belonging to a colleague
- **THEN** the response is 404 `not_found` and nothing changes

#### Scenario: Already read
- **WHEN** the same notice is marked read twice
- **THEN** the second call succeeds and `read_at` keeps its first value

### Requirement: Events that create a notification
The system SHALL create exactly one notification, for the affected user, when **another** person: adds them as an attendee of an activity (`activity_attending`), creates or reassigns an activity with them as owner (`activity_assigned`), assigns them a centre (`account_assigned`), or reassigns them an opportunity (`opportunity_assigned`). No other write SHALL notify.

#### Scenario: Attendee added
- **WHEN** a manager saves an activity adding a rep as attendee
- **THEN** that rep gets an `activity_attending` notice naming the manager, the centre and the date

#### Scenario: Activity created for someone else
- **WHEN** a manager creates an activity with `owner_id` of a rep
- **THEN** that rep gets an `activity_assigned` notice

#### Scenario: Centre assigned
- **WHEN** a manager assigns a centre to a rep through the assignment endpoint
- **THEN** that rep gets an `account_assigned` notice naming the centre

#### Scenario: Opportunity reassigned
- **WHEN** a manager reassigns an opportunity to a rep
- **THEN** that rep gets an `opportunity_assigned` notice; the previous owner gets nothing, because nothing was put on their plate

#### Scenario: Attendee removed
- **WHEN** an attendee is removed from an activity
- **THEN** no notification is created, and any unread notice about that activity remains as the record of what was announced

### Requirement: Notifications OpenAPI and conventions
The three endpoints SHALL appear in the exported `api-spec.yml`, return problem+json errors and require authentication. They SHALL NOT require `If-Match`: marking a notice read is idempotent and cannot conflict with anybody, since only its recipient can do it.

#### Scenario: Documented
- **WHEN** `api-spec.yml` is regenerated
- **THEN** it contains `/notifications`, `/notifications/{id}/read` and `/notifications/read-all`

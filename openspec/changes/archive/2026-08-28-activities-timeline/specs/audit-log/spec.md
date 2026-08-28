## ADDED Requirements

### Requirement: Activity audit events
The following events SHALL be recorded in the same transaction as the mutation: `activity.created` (field snapshot), `activity.updated` (field diffs), `activity.completed` (`done_at`, `outcome`), `activity.cancelled` (`cancel_reason`), `activity.rescheduled` (`scheduled_at` before/after). A next action created by `complete` SHALL produce its own `activity.created` event.

#### Scenario: Reschedule audited
- **WHEN** a planned call is moved from Monday to Wednesday
- **THEN** one `activity.rescheduled` row exists with `changes.scheduled_at = { before: Monday, after: Wednesday }`

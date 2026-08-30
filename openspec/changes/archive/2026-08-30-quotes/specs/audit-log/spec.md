## ADDED Requirements

### Requirement: Quote audit events
The following events SHALL be recorded in the same transaction as the mutation: `quote.created` (field snapshot, opportunity and number), `quote.updated` (field and line diffs on drafts), `quote.deleted` (draft snapshot), `quote.sent` (recipients, `valid_until`, skip flag), `quote.accepted` (total, `occurred_on`), `quote.rejected` (`rejection_note`), `quote.auto_rejected` (the accepted sibling's display number), `quote.revised` (new version number), `quote.email_failed` (error text; also on failed retries), `quote_settings.updated` (value diffs). Accepting a quote SHALL additionally produce the existing `opportunity.won` and `opportunity.stage_changed` events.

#### Scenario: Accept produces the full trail
- **WHEN** a quote is accepted while a sibling was sent
- **THEN** the audit log gains `quote.accepted`, one `quote.auto_rejected`, `opportunity.won` and `opportunity.stage_changed` rows sharing the actor

#### Scenario: Email failure audited
- **WHEN** the Graph call fails after sending
- **THEN** a `quote.email_failed` row exists with the error while `quote.sent` remains recorded

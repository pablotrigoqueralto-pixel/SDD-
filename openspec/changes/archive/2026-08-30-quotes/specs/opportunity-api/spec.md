## ADDED Requirements

### Requirement: Quotes summary on opportunity reads
`OpportunityRead` SHALL include `quotes_count` (current versions) and the timeline SHALL include quote events. `GET /me/today` SHALL gain `expiring_quotes`: current versions with `status = sent` and `valid_until` within 7 days, owned (via the opportunity) by the user, each with display number, account name, total and `valid_until`, ordered by `valid_until`.

#### Scenario: Expiring block scoped to the owner
- **WHEN** a rep calls `/me/today` and a colleague's quote expires tomorrow
- **THEN** only the rep's own expiring quotes appear in `expiring_quotes`

### Requirement: Timeline quote events
The account timeline SHALL include entries of kind `quote_sent`, `quote_accepted` and `quote_rejected`, derived from the status timestamps of every quote version reached through the account's opportunities, each carrying the display number, total and opportunity name, with server-side Spanish titles, merged chronologically with the existing kinds.

#### Scenario: Sent and accepted both appear
- **WHEN** a quote was sent on Monday and accepted on Wednesday
- **THEN** the account timeline shows a `quote_sent` entry and a `quote_accepted` entry at their respective times

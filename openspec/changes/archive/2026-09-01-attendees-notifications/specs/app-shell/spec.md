# app-shell (delta)

The header gains the notifications bell.

## ADDED Requirements

### Requirement: Notifications bell
The page header SHALL show a bell button for every authenticated role, carrying the caller's unread notification count as a badge and an accessible name that states the number (never a bare dot: a count only conveyed by colour tells a screen reader nothing). Activating it SHALL take the user to `/hoy`, where the notifications block holds the detail — the bell announces, the block explains, so the same information never lives in two places that can disagree. With nothing unread the bell SHALL render without a badge. The count SHALL come from the same request that feeds the block, and SHALL refresh when the window regains focus rather than on a timer.

#### Scenario: Unread count
- **WHEN** the user has three unread notices
- **THEN** the bell shows "3" and its accessible name says three unread notifications

#### Scenario: Nothing unread
- **WHEN** the user has none
- **THEN** the bell renders with no badge and an accessible name saying there is nothing new

#### Scenario: Bell leads to the block
- **WHEN** the user activates the bell from any screen
- **THEN** the app navigates to `/hoy` with the notifications block visible

#### Scenario: Refresh on return
- **WHEN** the user leaves the tab and comes back
- **THEN** the count is refetched once, without polling while the tab is hidden

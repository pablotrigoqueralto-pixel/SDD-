# account-contact-api (delta)

Assigning a centre to somebody else tells them.

## MODIFIED Requirements

### Requirement: Assignment
`PUT /api/v1/accounts/{id}/assignment` with `If-Match` SHALL accept `{ owner_id?, territory_id? }` from `sales_manager` and `admin` only. `owner_id` SHALL reference an active `sales_rep` (else 422 `owner_not_sales_rep`); `territory_id` an active territory. The event `account.assigned` SHALL record before/after of both fields. When `owner_id` changes to a user other than the caller, the new owner SHALL receive an `account_assigned` notification in the same transaction; assigning a centre to oneself SHALL notify nobody.

#### Scenario: Manager reassigns
- **WHEN** a manager assigns an account to another active rep
- **THEN** the response is 200 with the new `owner_id`, `version` incremented, `account.assigned` audited and the rep notified

#### Scenario: Manager takes it themselves
- **WHEN** a manager assigns the account to themselves
- **THEN** the assignment succeeds and no notification is created

#### Scenario: Rep attempts assignment
- **WHEN** a rep calls the assignment endpoint
- **THEN** the response is 403 `permission_denied`

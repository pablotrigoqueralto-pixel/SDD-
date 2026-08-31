# operations

Backups with a rehearsed restore, uptime alerting, the Graph go-live tenant procedure, the first-admin bootstrap and the go-live checklist.

## ADDED Requirements

### Requirement: Nightly backups with external copy
`deploy/backup.sh` SHALL produce a nightly `pg_dump` custom-format dump of the production database (cron at 03:30 Europe/Madrid), store it under `/var/backups/quermed-crm/` named by date, prune local dumps older than 30 days, and copy the fresh dump to external storage in the Microsoft tenant via a preconfigured rclone remote. Any failing step SHALL make the script exit non-zero so cron reports the failure by mail.

#### Scenario: Nightly dump lands in both places
- **WHEN** the cron entry fires
- **THEN** a dated `.dump` file exists locally and the same file exists in the external storage container

#### Scenario: Retention pruning
- **WHEN** the script runs with dumps older than 30 days present
- **THEN** those files are deleted locally while newer ones remain

#### Scenario: Copy failure is loud
- **WHEN** the rclone copy step fails (bad credentials, network down)
- **THEN** the script exits non-zero and no silent success is reported

### Requirement: Restore procedure documented and rehearsed
The development guide SHALL contain the restore runbook — `pg_restore --clean --if-exists` of a chosen dump into the db container, followed by health verification and spot checks — and the procedure SHALL be executed at least once for real during this change (against a stack restored from an actual dump), recording that the rehearsal happened.

#### Scenario: Dump proves restorable
- **WHEN** the rehearsal restores a production-shaped dump into a clean stack
- **THEN** the application starts healthy and the restored records are visible through the API

### Requirement: Uptime monitoring with email alert
An external uptime monitor SHALL poll `https://crm.quermed.com/health` at an interval of five minutes or less and alert by email when the check fails, so a dead VM or broken release is noticed without user reports. The enrolment steps SHALL be part of the go-live checklist.

#### Scenario: Outage triggers an email
- **WHEN** the health endpoint stops answering
- **THEN** the monitor sends an alert email to the configured operations address

### Requirement: Graph mail activation procedure
The development guide SHALL document taking Graph mail live: Azure app registration, application permission `Mail.Send` with tenant-admin consent, an application access policy restricting the app to the sales mailboxes' security group, and the production env values (`GRAPH_SENDER_MODE=graph` plus tenant/client credentials). The checklist SHALL end with a real test quote sent from a rep mailbox and its `sent` outbox row verified.

#### Scenario: Test quote proves the tenant setup
- **WHEN** the go-live operator sends the test quote after configuring the tenant
- **THEN** the recipient receives the email from the rep's mailbox and the quote's outbox entry reads `sent`

### Requirement: First admin bootstrap command
The backend SHALL provide `python -m app.tooling.bootstrap_admin`, reading `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`, that idempotently creates (or resets the password of) the initial admin with a validated password and an Argon2 hash. The E2E seed tool SHALL reuse the same underlying function. Running it twice SHALL leave exactly one admin with the latest password.

#### Scenario: Bootstrap then log in
- **WHEN** the operator runs the command on the production stack and opens the login page
- **THEN** the bootstrap credentials sign in as an `admin`

#### Scenario: Idempotent re-run
- **WHEN** the command runs again with a new password for the same email
- **THEN** no duplicate user is created and the new password is the one that works

### Requirement: Go-live checklist
The development guide SHALL contain an ordered go-live checklist covering: provisioning done, DNS resolving, env file in place, first deploy approved and healthy, admin bootstrapped, territories/users/settings created, Graph credentials live with the test quote sent, uptime monitor enrolled, backup cron verified with a first external copy, initial catalogue and accounts/contacts loads executed by back office through the change-08 import screens, and reps onboarded.

#### Scenario: Checklist is complete and ordered
- **WHEN** the operator executes the checklist top to bottom on a fresh environment
- **THEN** each item is actionable as written and finishing the list yields a production CRM with real data and working email

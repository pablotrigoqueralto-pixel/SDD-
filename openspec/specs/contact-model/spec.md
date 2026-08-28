# contact-model

## Purpose
Persistence and invariants of contacts: job title, speciality, channels, GDPR consent evidence, primary contact rule, anonymisation and the personal data access log.

## Requirements

### Requirement: Contact record
The system SHALL persist contacts in a `contacts` table belonging to exactly one account, with `first_name` and `last_name` (required — identify the person in activities, quotes and emails), optional `job_title_id` (drives the "who decides" view in opportunities), `division_id` (speciality, filters contacts per division rep), `email`, `mobile`, `landline`, `preferred_channel` (`email` | `mobile` | `landline`, requires the corresponding field to be present), `notes`, `is_primary` (at most one per account), `is_active`, consent fields, `anonymised_at`, `version`, `created_at`, `updated_at`. Phone fields SHALL be normalised as account phones.

#### Scenario: Minimum contact
- **WHEN** a contact is created with only `first_name` and `last_name` for a visible account
- **THEN** it is persisted with `consent_status = unknown`, `is_primary = false`, `is_active = true`

#### Scenario: Preferred channel without value
- **WHEN** `preferred_channel = mobile` is set and `mobile` is empty
- **THEN** a validation error `preferred_channel_missing_value` is raised

#### Scenario: Unknown job title or division
- **WHEN** `job_title_id` or `division_id` does not exist
- **THEN** a validation error `unknown_reference` naming the field is raised

### Requirement: Primary contact
Setting `is_primary = true` on a contact SHALL demote the current primary contact of the same account in the same transaction; the database SHALL enforce at most one primary per account.

#### Scenario: Promote another contact
- **WHEN** contact B is marked primary while contact A is primary in the same account
- **THEN** after the operation only B is primary and an audit event `contact.primary_changed` records A → B

### Requirement: Commercial communications consent
Each contact SHALL carry `consent_status` (`unknown` | `granted` | `denied`, default `unknown`), `consent_at`, `consent_source` (`verbal` | `email` | `form` | `imported`) and `consent_recorded_by` (user). When `consent_status` is not `unknown`, `consent_at` and `consent_source` SHALL be required and `consent_recorded_by` SHALL be set to the acting user. Every change SHALL emit `contact.consent_changed` with before/after values.

#### Scenario: Grant consent
- **WHEN** a rep records `{ status: granted, at: 2026-08-28, source: verbal }`
- **THEN** the contact stores the record with `consent_recorded_by` = the rep and one `contact.consent_changed` audit event exists

#### Scenario: Incomplete consent
- **WHEN** `consent_status = granted` is sent without `consent_source`
- **THEN** a validation error `consent_incomplete` is raised

### Requirement: Anonymisation
`Contact.anonymise()` SHALL replace `first_name`/`last_name` with `Contacto`/`anonimizado`, null `email`, `mobile`, `landline`, `notes`, set `consent_status = denied`, `is_active = false`, `is_primary = false` and `anonymised_at = now`. The audit event `contact.anonymised` SHALL list only the names of the cleared fields, never their previous values. Anonymised contacts SHALL reject any further modification with `contact_anonymised`.

#### Scenario: Anonymise
- **WHEN** a manager anonymises a contact with email and mobile
- **THEN** personal fields are cleared, the row and its id remain, and the audit row `changes` is `{"fields": {"cleared": ["first_name", "last_name", "email", "mobile", "landline", "notes"]}}` without values

#### Scenario: Edit after anonymisation
- **WHEN** a PATCH is attempted on an anonymised contact
- **THEN** the error `contact_anonymised` (409) is raised

### Requirement: Personal data access log
The system SHALL append one row to `personal_data_access_log` (`user_id`, `contact_id`, `occurred_at`, `trace_id`) for each contact whose personal data is returned to a user who is neither the account owner nor `sales_manager`/`admin`. The table SHALL be append-only for the application role.

#### Scenario: Back office reads a contact
- **WHEN** a `back_office` user reads `GET /contacts/{id}`
- **THEN** one access log row exists for that user and contact with the request trace id

#### Scenario: Owner reads their contact
- **WHEN** the account owner reads the same contact
- **THEN** no access log row is added

#### Scenario: Update rejected
- **WHEN** the application role executes UPDATE or DELETE on `personal_data_access_log`
- **THEN** the database rejects the statement

# contact-model (delta)

Contacts get their own labelled phone list, an independent head-of-department flag, and an anonymisation path that deletes phone rows.

## MODIFIED Requirements

### Requirement: Contact record
The system SHALL persist contacts in a `contacts` table belonging to exactly one account, with `first_name` and `last_name` (required — identify the person in activities, quotes and emails), optional `job_title_id` (drives the "who decides" view in opportunities), `division_id` (speciality, filters contacts per division rep), `is_head_of_department` (boolean, default false — independent of the job title: a vascular surgeon may also head the department), `email`, `preferred_channel` (`email` | `phone`, requiring an email or at least one phone respectively), `notes`, `is_primary` (at most one per account), `is_active`, consent fields, `anonymised_at`, `version`, `created_at`, `updated_at`. Telephone numbers SHALL live in the `contact_phones` child collection, not in columns.

#### Scenario: Minimum contact
- **WHEN** a contact is created with only `first_name` and `last_name` for a visible account
- **THEN** it is persisted with `consent_status = unknown`, `is_primary = false`, `is_head_of_department = false`, `is_active = true` and no phone rows

#### Scenario: Preferred channel without value
- **WHEN** `preferred_channel = phone` is set and the contact has no phone in its list
- **THEN** a validation error `preferred_channel_missing_value` is raised

#### Scenario: Unknown job title or division
- **WHEN** `job_title_id` or `division_id` does not exist
- **THEN** a validation error `unknown_reference` naming the field is raised

### Requirement: Anonymisation
`Contact.anonymise()` SHALL replace `first_name`/`last_name` with `Contacto`/`anonimizado`, null `email` and `notes`, **delete every row of its phone list**, set `consent_status = denied`, `is_active = false`, `is_primary = false` and `anonymised_at = now`. The audit event `contact.anonymised` SHALL list only the names of the cleared fields (with `phones` naming the deleted list), never their previous values. Anonymised contacts SHALL reject any further modification with `contact_anonymised`.

#### Scenario: Anonymise
- **WHEN** a manager anonymises a contact with email and two phones
- **THEN** personal fields are cleared, zero phone rows remain for that contact, the row and its id remain, and the audit row `changes` is `{"fields": {"cleared": ["first_name", "last_name", "email", "phones", "notes"]}}` without values

#### Scenario: Edit after anonymisation
- **WHEN** a PATCH is attempted on an anonymised contact
- **THEN** the error `contact_anonymised` (409) is raised

## ADDED Requirements

### Requirement: Contact phone list
The system SHALL persist contact telephone numbers in a `contact_phones` table with the same shape and rules as `account_phones` (`label`, `number` normalised to E.164, optional `extension`, optional `note`, `sort_order`, cascade delete, no duplicate label+number, lowest `sort_order` is the primary one, whole-list replacement on save). Contact phones are personal data and SHALL be removed by anonymisation; account phones are business data and SHALL NOT be affected by it.

#### Scenario: Doctor with several numbers
- **WHEN** a contact is saved with "Móvil +34612345678", "Despacho +34915550003 ext. 210" and "Secretaría +34915550004"
- **THEN** the three rows persist in order and the mobile is the primary number shown on the contact card

#### Scenario: Account phones survive contact anonymisation
- **WHEN** a contact of a centre is anonymised
- **THEN** the centre's own phone list is unchanged

### Requirement: Head of department flag
`is_head_of_department` SHALL be settable independently of `job_title_id`, both on creation and update, and SHALL be exposed in contact payloads. It SHALL NOT be inferred from the job title.

#### Scenario: Both facts at once
- **WHEN** a contact is saved as "Cirujano/a vascular" with the head-of-department flag set
- **THEN** both are persisted and both are returned in the contact payload

#### Scenario: Flag without job title
- **WHEN** a contact is saved with the flag and no job title
- **THEN** it persists with `job_title_id = null` and `is_head_of_department = true`

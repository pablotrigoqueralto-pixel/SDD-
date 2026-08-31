# contact-model (delta)

The contact's `division_id` becomes `specialty_id`.

## MODIFIED Requirements

### Requirement: Contact record
The system SHALL persist contacts in a `contacts` table belonging to exactly one account, with `first_name` and `last_name` (required — identify the person in activities, quotes and emails), optional `job_title_id` (the person's role: drives the "who decides" view in opportunities), `specialty_id` (the medical specialty they practise: powers the contacts list filter and the centre's derived specialties), `is_head_of_department` (boolean, default false — independent of the job title: a vascular surgeon may also head the department), `email`, `preferred_channel` (`email` | `phone`, requiring an email or at least one phone respectively), `notes`, `is_primary` (at most one per account), `is_active`, consent fields, `anonymised_at`, `version`, `created_at`, `updated_at`. Telephone numbers SHALL live in the `contact_phones` child collection, not in columns. Contacts SHALL NOT carry a commercial division.

#### Scenario: Minimum contact
- **WHEN** a contact is created with only `first_name` and `last_name` for a visible account
- **THEN** it is persisted with `consent_status = unknown`, `is_primary = false`, `is_head_of_department = false`, `is_active = true`, no specialty and no phone rows

#### Scenario: Preferred channel without value
- **WHEN** `preferred_channel = phone` is set and the contact has no phone in its list
- **THEN** a validation error `preferred_channel_missing_value` is raised

#### Scenario: Unknown job title or specialty
- **WHEN** `job_title_id` or `specialty_id` does not exist
- **THEN** a validation error `unknown_reference` naming the field is raised

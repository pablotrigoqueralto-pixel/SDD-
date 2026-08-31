# reference-data-model (delta)

Specialties join the reference masters.

## ADDED Requirements

### Requirement: Specialties master
The specialties catalogue SHALL be a reference master alongside job titles: global, seeded insert-only by `code`, editable in name, order and activation without losing its identity, and included in the reference bundle so every screen resolves specialty names from one place.

#### Scenario: Part of the masters
- **WHEN** the reference masters are enumerated
- **THEN** specialties appear with account types, activity types, divisions, brands, loss reasons, pipelines, job titles and product families

#### Scenario: Seed respects edits
- **WHEN** an administrator renames a specialty and the seed runs again
- **THEN** the rename survives and no duplicate is created

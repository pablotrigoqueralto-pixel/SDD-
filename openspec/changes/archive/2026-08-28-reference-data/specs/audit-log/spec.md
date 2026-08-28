## ADDED Requirements

### Requirement: Reference data audit events
The following events SHALL be recorded with field diffs: `brand.created`, `brand.updated`, `brand.activated`, `brand.deactivated`, `loss_reason.created`, `loss_reason.updated`, `pipeline.updated`, `pipeline_stage.updated`, `pipeline_stages.reordered` (changes `{ "order": { "before": [stage ids], "after": [stage ids] } }`).

#### Scenario: Reorder is audited
- **WHEN** an admin reorders the stages of a pipeline
- **THEN** one `pipeline_stages.reordered` row exists with `entity_type = "pipeline"`, the pipeline id and the before/after id lists

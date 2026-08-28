"""Reference data domain errors."""

from app.domain.shared.errors import DomainError, ValidationFailedError


class BrandNameAlreadyExistsError(DomainError):
    code = "brand_name_already_exists"
    status = 409
    title = "Brand name already exists"

    def __init__(self) -> None:
        super().__init__("A brand with this name already exists")


class LossReasonNameAlreadyExistsError(DomainError):
    code = "loss_reason_name_already_exists"
    status = 409
    title = "Loss reason name already exists"

    def __init__(self) -> None:
        super().__init__("A loss reason with this name already exists")


class JobTitleNameAlreadyExistsError(DomainError):
    code = "job_title_name_already_exists"
    status = 409
    title = "Job title name already exists"

    def __init__(self) -> None:
        super().__init__("A job title with this name already exists")


class PipelineNameAlreadyExistsError(DomainError):
    code = "pipeline_name_already_exists"
    status = 409
    title = "Pipeline name already exists"

    def __init__(self) -> None:
        super().__init__("A pipeline with this name already exists")


class StageOrderInvalidError(ValidationFailedError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            [{"field": "stage_ids", "message": detail, "code": "stage_order_invalid"}],
            detail,
        )
        self.code = "stage_order_invalid"


class StageProbabilityInvalidError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "probability",
                    "message": "Probability must be between 0 and 100",
                    "code": "stage_probability_invalid",
                }
            ]
        )
        self.code = "stage_probability_invalid"


class StageFlagImmutableError(DomainError):
    code = "stage_flag_immutable"
    status = 400
    title = "Stage flags are immutable"

    def __init__(self) -> None:
        super().__init__("The won/lost/at-risk flags of a stage cannot be changed")


class LastActiveStageError(DomainError):
    code = "last_active_stage"
    status = 400
    title = "Last active stage"

    def __init__(self) -> None:
        super().__init__("A pipeline must keep at least one active open stage")

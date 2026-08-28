"""Opportunity domain errors."""

from app.domain.shared.errors import DomainError, PermissionDeniedError, ValidationFailedError


class PipelineRequiredError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "pipeline_id",
                    "message": "The division has no default pipeline; choose one",
                    "code": "pipeline_required",
                }
            ]
        )
        self.code = "pipeline_required"


class StageNotInPipelineError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "stage_id",
                    "message": "The stage does not belong to the opportunity's pipeline",
                    "code": "stage_not_in_pipeline",
                }
            ]
        )
        self.code = "stage_not_in_pipeline"


class InvalidOpportunityTransitionError(DomainError):
    code = "invalid_opportunity_transition"
    status = 409
    title = "Invalid opportunity transition"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


class OpportunityClosedError(DomainError):
    code = "opportunity_closed"
    status = 409
    title = "Opportunity is closed"

    def __init__(self) -> None:
        super().__init__("A closed opportunity only accepts reopening")


class LossReasonRequiresBrandError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "competitor_brand_id",
                    "message": "This loss reason requires the competitor brand",
                    "code": "loss_reason_requires_brand",
                }
            ]
        )
        self.code = "loss_reason_requires_brand"


class LossReasonRequiresNoteError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "note",
                    "message": "This loss reason requires a note",
                    "code": "loss_reason_requires_note",
                }
            ]
        )
        self.code = "loss_reason_requires_note"


class OpportunityHasLinesError(DomainError):
    code = "opportunity_has_lines"
    status = 409
    title = "Amount is computed from the lines"

    def __init__(self) -> None:
        super().__init__("The estimated amount is read-only while product lines exist")


class TenderFieldsRequireTenderError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "is_tender",
                    "message": "Tender fields are only accepted on tender opportunities",
                    "code": "tender_fields_require_tender",
                }
            ]
        )
        self.code = "tender_fields_require_tender"


class AtRiskNotSupportedError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "flag",
                    "message": "Only won opportunities of a pipeline with an at-risk stage",
                    "code": "at_risk_not_supported",
                }
            ]
        )
        self.code = "at_risk_not_supported"


class LineProductInactiveError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "product_id",
                    "message": "Retired products cannot be added",
                    "code": "line_product_inactive",
                }
            ]
        )
        self.code = "line_product_inactive"


class LineDuplicatedError(DomainError):
    code = "line_duplicated"
    status = 409
    title = "Product already on the opportunity"

    def __init__(self) -> None:
        super().__init__("The product already has a line; edit its quantity instead")


class ReopenForbiddenError(PermissionDeniedError):
    def __init__(self) -> None:
        super().__init__("Only sales managers and admins can reopen a closed opportunity")
        self.code = "reopen_forbidden"


class OpportunityNotInAccountError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "opportunity_id",
                    "message": "The opportunity belongs to another account",
                    "code": "opportunity_not_in_account",
                }
            ]
        )
        self.code = "opportunity_not_in_account"

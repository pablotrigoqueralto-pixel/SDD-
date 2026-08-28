"""Account domain errors."""

from uuid import UUID

from app.domain.shared.errors import DomainError, ValidationFailedError


class InvalidTaxIdError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [{"field": "tax_id", "message": "Invalid Spanish tax id", "code": "tax_id_invalid"}]
        )
        self.code = "tax_id_invalid"


class InvalidPhoneError(ValidationFailedError):
    def __init__(self, field: str = "phone") -> None:
        super().__init__(
            [{"field": field, "message": "Invalid phone number", "code": "phone_invalid"}]
        )
        self.code = "phone_invalid"


class InvalidPostalCodeError(ValidationFailedError):
    def __init__(self, field: str = "postal_code") -> None:
        super().__init__(
            [
                {
                    "field": field,
                    "message": "Postal code must have five digits",
                    "code": "postal_code_invalid",
                }
            ]
        )
        self.code = "postal_code_invalid"


class TaxIdAlreadyExistsError(DomainError):
    code = "tax_id_already_exists"
    status = 409
    title = "Tax id already exists"

    def __init__(self, existing_account_id: UUID | None = None) -> None:
        super().__init__("An account with this tax id already exists")
        self.existing_account_id = existing_account_id
        if existing_account_id is not None:
            self.extensions = {"existing_account_id": str(existing_account_id)}


class AddressLabelDuplicatedError(ValidationFailedError):
    def __init__(self, label: str) -> None:
        super().__init__(
            [
                {
                    "field": "addresses",
                    "message": f"Address label '{label}' is used more than once",
                    "code": "address_label_duplicated",
                }
            ]
        )
        self.code = "address_label_duplicated"


class TooManyAddressesError(ValidationFailedError):
    def __init__(self, maximum: int) -> None:
        super().__init__(
            [
                {
                    "field": "addresses",
                    "message": f"An account can have at most {maximum} additional addresses",
                    "code": "too_many_addresses",
                }
            ]
        )
        self.code = "too_many_addresses"


class AssignmentForbiddenError(DomainError):
    code = "assignment_forbidden"
    status = 403
    title = "Assignment forbidden"

    def __init__(self) -> None:
        super().__init__("Only sales managers and administrators can change owner or territory")


class OwnerNotSalesRepError(ValidationFailedError):
    def __init__(self) -> None:
        super().__init__(
            [
                {
                    "field": "owner_id",
                    "message": "The owner must be an active sales rep",
                    "code": "owner_not_sales_rep",
                }
            ]
        )
        self.code = "owner_not_sales_rep"

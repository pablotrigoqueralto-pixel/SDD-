"""Territory domain errors."""

from app.domain.shared.errors import DomainError, ValidationFailedError


class InvalidProvinceError(ValidationFailedError):
    def __init__(self, invalid_codes: list[str]) -> None:
        super().__init__(
            [
                {
                    "field": "provinces",
                    "message": f"Invalid province codes: {', '.join(invalid_codes)}",
                    "code": "invalid_province",
                }
            ]
        )


class ProvinceAlreadyAssignedError(DomainError):
    code = "province_already_assigned"
    status = 409
    title = "Province already assigned"

    def __init__(self, province_code: str, territory_name: str) -> None:
        self.province_code = province_code
        self.territory_name = territory_name
        super().__init__(
            f"Province {province_code} is already assigned to territory '{territory_name}'"
        )


class TerritoryInUseError(DomainError):
    code = "territory_in_use"
    status = 400
    title = "Territory in use"

    def __init__(self, active_user_count: int) -> None:
        self.active_user_count = active_user_count
        super().__init__(f"The territory still has {active_user_count} active user(s) assigned")


class TerritoryNameAlreadyExistsError(DomainError):
    code = "territory_name_already_exists"
    status = 409
    title = "Territory name already exists"

    def __init__(self) -> None:
        super().__init__("A territory with this name already exists")

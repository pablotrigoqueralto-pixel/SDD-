"""Catalogue domain errors."""

from uuid import UUID

from app.domain.shared.errors import DomainError, ValidationFailedError


class PriceInvalidError(ValidationFailedError):
    def __init__(self, field: str = "list_price") -> None:
        super().__init__(
            [{"field": field, "message": "Price must be zero or positive", "code": "price_invalid"}]
        )
        self.code = "price_invalid"


class ProductFieldInvalidError(ValidationFailedError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__([{"field": field, "message": message, "code": "product_field_invalid"}])


class SkuAlreadyExistsError(DomainError):
    code = "product_sku_exists"
    status = 409
    title = "Product code already exists"

    def __init__(self, existing_product_id: UUID | None = None) -> None:
        super().__init__("A product with this Sage code already exists")
        self.existing_product_id = existing_product_id
        if existing_product_id is not None:
            self.extensions = {"existing_product_id": str(existing_product_id)}


class SkuLockedError(DomainError):
    code = "product_sku_locked"
    status = 409
    title = "Product code locked"

    def __init__(self) -> None:
        super().__init__("The Sage code cannot change once the product is referenced")


class BrandNotFoundError(ValidationFailedError):
    def __init__(self, reference: str) -> None:
        super().__init__(
            [
                {
                    "field": "brand",
                    "message": f"Unknown brand: {reference}",
                    "code": "brand_not_found",
                }
            ]
        )
        self.code = "brand_not_found"


class FamilyNotFoundError(ValidationFailedError):
    def __init__(self, reference: str) -> None:
        super().__init__(
            [
                {
                    "field": "family",
                    "message": f"Unknown product family: {reference}",
                    "code": "family_not_found",
                }
            ]
        )
        self.code = "family_not_found"

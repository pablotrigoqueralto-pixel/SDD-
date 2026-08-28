"""Catalogue API schemas. Prices travel as two-decimal strings; cost is role-gated."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer

from app.application.catalogue.commands import ImportProduct
from app.application.catalogue.queries import ProductSummary
from app.domain.catalogue.entities import ProductKind

Price = Annotated[Decimal, PlainSerializer(lambda value: f"{value:.2f}", return_type=str)]
PriceInput = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class BrandRefRead(BaseModel):
    id: UUID
    name: str
    is_own: bool


class FamilyRefRead(BaseModel):
    id: UUID
    name: str
    division_id: UUID


class ProductSummaryPublicRead(BaseModel):
    """Catalogue row for roles that never see the cost (sales reps, back office)."""

    id: UUID
    sku: str
    name: str
    brand: BrandRefRead
    family: FamilyRefRead
    kind: ProductKind
    list_price: Price
    unit: str
    is_active: bool
    version: int

    @classmethod
    def from_summary(cls, summary: ProductSummary) -> "ProductSummaryPublicRead":
        return cls.model_validate(_summary_fields(summary))


class ProductSummaryRead(ProductSummaryPublicRead):
    cost_price: Price | None

    @classmethod
    def from_summary(cls, summary: ProductSummary) -> "ProductSummaryRead":
        return cls.model_validate({**_summary_fields(summary), "cost_price": summary.cost_price})


class ProductPublicRead(ProductSummaryPublicRead):
    description: str | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_summary(cls, summary: ProductSummary) -> "ProductPublicRead":
        return cls.model_validate(_detail_fields(summary))


class ProductRead(ProductPublicRead):
    cost_price: Price | None

    @classmethod
    def from_summary(cls, summary: ProductSummary) -> "ProductRead":
        return cls.model_validate({**_detail_fields(summary), "cost_price": summary.cost_price})


def _summary_fields(summary: ProductSummary) -> dict[str, object]:
    return {
        "id": summary.id,
        "sku": summary.sku,
        "name": summary.name,
        "brand": BrandRefRead(
            id=summary.brand.id, name=summary.brand.name, is_own=summary.brand.is_own
        ),
        "family": FamilyRefRead(
            id=summary.family.id, name=summary.family.name, division_id=summary.family.division_id
        ),
        "kind": summary.kind,
        "list_price": summary.list_price,
        "unit": summary.unit,
        "is_active": summary.is_active,
        "version": summary.version,
    }


def _detail_fields(summary: ProductSummary) -> dict[str, object]:
    return {
        **_summary_fields(summary),
        "description": summary.description,
        "created_at": summary.created_at,
        "updated_at": summary.updated_at,
    }


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    brand_id: UUID
    family_id: UUID
    kind: ProductKind
    list_price: PriceInput
    cost_price: PriceInput | None = None
    unit: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)


class ProductUpdate(BaseModel):
    """PATCH: only provided fields change; `cost_price`/`description` accept null to clear."""

    sku: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    brand_id: UUID | None = None
    family_id: UUID | None = None
    kind: ProductKind | None = None
    list_price: PriceInput | None = None
    cost_price: PriceInput | None = None
    unit: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)

    def changes(self) -> dict[str, object]:
        provided = self.model_fields_set
        values = self.model_dump()
        return {key: values[key] for key in provided}


class ProductImportRow(BaseModel):
    """One row of the Sage export (change 08 parses the CSV into this shape)."""

    sku: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    brand_code: str | None = Field(default=None, max_length=100)
    brand_name: str | None = Field(default=None, max_length=100)
    family_code: str = Field(min_length=1, max_length=100)
    kind: ProductKind
    list_price: PriceInput
    cost_price: PriceInput | None = None
    unit: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    def to_command(self) -> ImportProduct:
        return ImportProduct(
            sku=self.sku,
            name=self.name,
            family_code=self.family_code,
            kind=self.kind,
            list_price=self.list_price,
            brand_code=self.brand_code,
            brand_name=self.brand_name,
            cost_price=self.cost_price,
            unit=self.unit,
            description=self.description,
            is_active=self.is_active,
        )

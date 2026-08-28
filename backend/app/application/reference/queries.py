"""Read side: the reference data bundle every screen loads once."""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from app.application.shared.unit_of_work import UnitOfWork
from app.domain.reference.entities import (
    AccountType,
    ActivityType,
    Brand,
    JobTitle,
    LossReason,
    Pipeline,
    ProductFamily,
)
from app.domain.territories.entities import Division


@dataclass(frozen=True)
class ReferenceBundle:
    account_types: list[AccountType]
    activity_types: list[ActivityType]
    divisions: list[Division]
    brands: list[Brand]
    loss_reasons: list[LossReason]
    pipelines: list[Pipeline]
    job_titles: list[JobTitle]
    product_families: list[ProductFamily]
    etag: str


def compute_etag(timestamps: list[datetime | None], counts: list[int]) -> str:
    """Weak-validator style tag: newest change plus row counts (deactivation-safe)."""
    newest = max((ts for ts in timestamps if ts is not None), default=None)
    material = f"{newest.isoformat() if newest else ''}|{'/'.join(map(str, counts))}"
    return hashlib.sha256(material.encode()).hexdigest()[:32]


class ReferenceQueries:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def bundle(self) -> ReferenceBundle:
        uow = self._uow
        account_types = await uow.reference.account_types()
        activity_types = await uow.reference.activity_types()
        divisions = await uow.divisions.list_all()
        brands = await uow.brands.list_all()
        loss_reasons = await uow.loss_reasons.list_all()
        pipelines = await uow.pipelines.list_all()
        job_titles = await uow.job_titles.list_all()
        product_families = await uow.product_families.list_all()
        timestamps: list[datetime | None] = [
            *(t.updated_at for t in account_types),
            *(t.updated_at for t in activity_types),
            *(b.updated_at for b in brands),
            *(r.updated_at for r in loss_reasons),
            *(p.updated_at for p in pipelines),
            *(s.updated_at for p in pipelines for s in p.stages),
            *(j.updated_at for j in job_titles),
            *(f.updated_at for f in product_families),
        ]
        counts = [
            len(account_types),
            len(activity_types),
            len(divisions),
            len(brands),
            len(loss_reasons),
            sum(len(p.stages) for p in pipelines),
            len(job_titles),
            len(product_families),
        ]
        return ReferenceBundle(
            account_types=account_types,
            activity_types=activity_types,
            divisions=divisions,
            brands=brands,
            loss_reasons=loss_reasons,
            pipelines=[
                Pipeline(
                    id=p.id,
                    code=p.code,
                    name_es=p.name_es,
                    sort_order=p.sort_order,
                    division_ids=p.division_ids,
                    stages=p.ordered_stages(),
                    version=p.version,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
                for p in pipelines
            ],
            job_titles=job_titles,
            product_families=product_families,
            etag=compute_etag(timestamps, counts),
        )

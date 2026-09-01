"""Reference data use cases (administrators only)."""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import UUID

from app.application.reference.catalogue_entry import (
    ActivatableEntry,
    CatalogueOutcome,
    reuse_or_reactivate,
)
from app.application.reference.commands import (
    CreateAccountType,
    CreateBrand,
    CreateJobTitle,
    CreateLossReason,
    CreateProductFamily,
    CreateSpecialty,
    ReorderStages,
    UpdateBrand,
    UpdateJobTitle,
    UpdateLossReason,
    UpdateProductFamily,
    UpdateStage,
)
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.reference.codes import slugify_code
from app.domain.reference.entities import (
    AccountType,
    Brand,
    JobTitle,
    LossReason,
    Pipeline,
    PipelineStage,
    ProductFamily,
    Specialty,
)
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import NotFoundError
from app.domain.users.errors import UnknownReferenceError


def _brand_snapshot(brand: Brand) -> dict[str, object]:
    return {
        "name": brand.name,
        "is_own": brand.is_own,
        "is_active": brand.is_active,
        "division_ids": brand.division_ids,
    }


async def _ensure_divisions(uow: UnitOfWork, division_ids: frozenset[UUID]) -> None:
    if not division_ids:
        return
    missing = division_ids - await uow.divisions.existing_ids(division_ids)
    if missing:
        raise UnknownReferenceError("division_ids", sorted(str(m) for m in missing))


class BrandService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(self, command: CreateBrand, *, acting_user_id: UUID) -> Brand:
        async with self._uow as uow:
            await _ensure_divisions(uow, command.division_ids)
            brand = Brand.create(
                name=command.name, is_own=command.is_own, division_ids=command.division_ids
            )
            await uow.brands.add(brand)
            uow.audit.record(
                entity_type="brand",
                entity_id=brand.id,
                action="brand.created",
                changes=diff_fields({}, _brand_snapshot(brand)),
                actor_id=acting_user_id,
            )
            await uow.commit()
            return brand

    async def update(self, brand_id: UUID, command: UpdateBrand, *, acting_user_id: UUID) -> Brand:
        async with self._uow as uow:
            brand = await uow.brands.get(brand_id)
            if brand is None:
                raise NotFoundError("Brand not found")
            before = _brand_snapshot(brand)
            if isinstance(command.name, str):
                brand.rename(command.name)
            if isinstance(command.is_own, bool):
                brand.set_own(command.is_own)
            if isinstance(command.division_ids, frozenset):
                await _ensure_divisions(uow, command.division_ids)
                brand.set_divisions(command.division_ids)
            if isinstance(command.is_active, bool):
                if command.is_active:
                    brand.activate()
                else:
                    brand.deactivate()
            await uow.brands.save(brand, expected_version=command.expected_version)
            after = _brand_snapshot(brand)
            general = diff_fields(
                {k: v for k, v in before.items() if k != "is_active"},
                {k: v for k, v in after.items() if k != "is_active"},
            )
            if general:
                uow.audit.record(
                    entity_type="brand",
                    entity_id=brand.id,
                    action="brand.updated",
                    changes=general,
                    actor_id=acting_user_id,
                )
            if before["is_active"] != after["is_active"]:
                uow.audit.record(
                    entity_type="brand",
                    entity_id=brand.id,
                    action="brand.activated" if brand.is_active else "brand.deactivated",
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return brand


def _reactivator[T: ActivatableEntry](
    uow: UnitOfWork,
    entity_type: str,
    save: Callable[..., Awaitable[None]],
    acting_user_id: UUID,
) -> Callable[[T], Awaitable[None]]:
    """Save a revived catalogue entry and record why it came back.

    Reactivation is the one outcome that changes data, so it is the one that is audited;
    a plain reuse records nothing because nothing changed.
    """

    async def reactivate(entry: T) -> None:
        await save(entry, expected_version=entry.version)  # type: ignore[attr-defined]
        uow.audit.record(
            entity_type=entity_type,
            entity_id=entry.id,  # type: ignore[attr-defined]
            action=f"{entity_type}.reactivated",
            changes=diff_fields({"is_active": False}, {"is_active": True}),
            actor_id=acting_user_id,
        )

    return reactivate


class LossReasonService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(
        self, command: CreateLossReason, *, acting_user_id: UUID
    ) -> tuple[LossReason, CatalogueOutcome]:
        """Adding a reason that already exists reuses it — see catalogue_entry."""
        async with self._uow as uow:
            resolved = await reuse_or_reactivate(
                await uow.loss_reasons.matching(code=slugify_code(command.name), name=command.name),
                reactivate=_reactivator(uow, "loss_reason", uow.loss_reasons.save, acting_user_id),
            )
            if resolved is not None:
                await uow.commit()
                return resolved
            reason = LossReason.create(
                name=command.name, sort_order=await uow.loss_reasons.next_sort_order()
            )
            await uow.loss_reasons.add(reason)
            uow.audit.record(
                entity_type="loss_reason",
                entity_id=reason.id,
                action="loss_reason.created",
                changes=diff_fields(
                    {}, {"name_es": reason.name_es, "sort_order": reason.sort_order}
                ),
                actor_id=acting_user_id,
            )
            await uow.commit()
            return reason, CatalogueOutcome.CREATED

    async def update(
        self, reason_id: UUID, command: UpdateLossReason, *, acting_user_id: UUID
    ) -> LossReason:
        async with self._uow as uow:
            reason = await uow.loss_reasons.get(reason_id)
            if reason is None:
                raise NotFoundError("Loss reason not found")
            before = {"name_es": reason.name_es, "is_active": reason.is_active}
            if isinstance(command.name, str):
                reason.rename(command.name)
            if isinstance(command.is_active, bool):
                if command.is_active:
                    reason.activate()
                else:
                    reason.deactivate()
            await uow.loss_reasons.save(reason, expected_version=command.expected_version)
            changes = diff_fields(
                before, {"name_es": reason.name_es, "is_active": reason.is_active}
            )
            if changes:
                uow.audit.record(
                    entity_type="loss_reason",
                    entity_id=reason.id,
                    action="loss_reason.updated",
                    changes=changes,
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return reason


class AccountTypeService:
    """Creation only, and always with an explicit `buys_via_tender`."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(
        self, command: CreateAccountType, *, acting_user_id: UUID
    ) -> tuple[AccountType, CatalogueOutcome]:
        async with self._uow as uow:
            existing = await uow.reference.account_type_matching(
                code=slugify_code(command.name), name=command.name
            )
            if existing is not None:
                if existing.is_active:
                    return existing, CatalogueOutcome.REUSED
                # AccountType is frozen and has no version: reactivation is a direct
                # update, and the stored `buys_via_tender` is never overwritten.
                await uow.reference.activate_account_type(existing.id)
                uow.audit.record(
                    entity_type="account_type",
                    entity_id=existing.id,
                    action="account_type.reactivated",
                    changes=diff_fields({"is_active": False}, {"is_active": True}),
                    actor_id=acting_user_id,
                )
                await uow.commit()
                return replace(existing, is_active=True), CatalogueOutcome.REACTIVATED
            account_type = AccountType.create(
                name=command.name,
                sort_order=await uow.reference.next_account_type_sort_order(),
                buys_via_tender=command.buys_via_tender,
            )
            await uow.reference.add_account_type(account_type)
            uow.audit.record(
                entity_type="account_type",
                entity_id=account_type.id,
                action="account_type.created",
                changes=diff_fields(
                    {},
                    {
                        "name_es": account_type.name_es,
                        "sort_order": account_type.sort_order,
                        "buys_via_tender": account_type.buys_via_tender,
                    },
                ),
                actor_id=acting_user_id,
            )
            await uow.commit()
            return account_type, CatalogueOutcome.CREATED


class SpecialtyService:
    """Creation only: renaming and deactivating stay in the administration screens."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(
        self, command: CreateSpecialty, *, acting_user_id: UUID
    ) -> tuple[Specialty, CatalogueOutcome]:
        async with self._uow as uow:
            resolved = await reuse_or_reactivate(
                await uow.specialties.matching(code=slugify_code(command.name), name=command.name),
                reactivate=_reactivator(uow, "specialty", uow.specialties.save, acting_user_id),
            )
            if resolved is not None:
                await uow.commit()
                return resolved
            specialty = Specialty.create(
                name=command.name, sort_order=await uow.specialties.next_sort_order()
            )
            await uow.specialties.add(specialty)
            uow.audit.record(
                entity_type="specialty",
                entity_id=specialty.id,
                action="specialty.created",
                changes=diff_fields(
                    {}, {"name_es": specialty.name_es, "sort_order": specialty.sort_order}
                ),
                actor_id=acting_user_id,
            )
            await uow.commit()
            return specialty, CatalogueOutcome.CREATED


class JobTitleService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(
        self, command: CreateJobTitle, *, acting_user_id: UUID
    ) -> tuple[JobTitle, CatalogueOutcome]:
        """Adding a title that already exists reuses it — see catalogue_entry."""
        async with self._uow as uow:
            resolved = await reuse_or_reactivate(
                await uow.job_titles.matching(code=slugify_code(command.name), name=command.name),
                reactivate=_reactivator(uow, "job_title", uow.job_titles.save, acting_user_id),
            )
            if resolved is not None:
                await uow.commit()
                return resolved
            job_title = JobTitle.create(
                name=command.name, sort_order=await uow.job_titles.next_sort_order()
            )
            await uow.job_titles.add(job_title)
            uow.audit.record(
                entity_type="job_title",
                entity_id=job_title.id,
                action="job_title.created",
                changes=diff_fields(
                    {}, {"name_es": job_title.name_es, "sort_order": job_title.sort_order}
                ),
                actor_id=acting_user_id,
            )
            await uow.commit()
            return job_title, CatalogueOutcome.CREATED

    async def update(
        self, job_title_id: UUID, command: UpdateJobTitle, *, acting_user_id: UUID
    ) -> JobTitle:
        async with self._uow as uow:
            job_title = await uow.job_titles.get(job_title_id)
            if job_title is None:
                raise NotFoundError("Job title not found")
            before = {"name_es": job_title.name_es, "is_active": job_title.is_active}
            if isinstance(command.name, str):
                job_title.rename(command.name)
            if isinstance(command.is_active, bool):
                if command.is_active:
                    job_title.activate()
                else:
                    job_title.deactivate()
            await uow.job_titles.save(job_title, expected_version=command.expected_version)
            changes = diff_fields(
                before, {"name_es": job_title.name_es, "is_active": job_title.is_active}
            )
            if changes:
                uow.audit.record(
                    entity_type="job_title",
                    entity_id=job_title.id,
                    action="job_title.updated",
                    changes=changes,
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return job_title


class ProductFamilyService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(
        self, command: CreateProductFamily, *, acting_user_id: UUID
    ) -> tuple[ProductFamily, CatalogueOutcome]:
        """A family is identified by its name WITHIN a division: the same name under
        another division is a different family, so the lookup is division-scoped."""
        async with self._uow as uow:
            await _ensure_divisions(uow, frozenset({command.division_id}))
            resolved = await reuse_or_reactivate(
                await uow.product_families.matching(
                    division_id=command.division_id,
                    code=slugify_code(command.name),
                    name=command.name,
                ),
                reactivate=_reactivator(
                    uow, "product_family", uow.product_families.save, acting_user_id
                ),
            )
            if resolved is not None:
                await uow.commit()
                return resolved
            family = ProductFamily.create(
                name=command.name,
                division_id=command.division_id,
                sort_order=await uow.product_families.next_sort_order(command.division_id),
            )
            await uow.product_families.add(family)
            uow.audit.record(
                entity_type="product_family",
                entity_id=family.id,
                action="product_family.created",
                changes=diff_fields({}, _family_snapshot(family)),
                actor_id=acting_user_id,
            )
            await uow.commit()
            return family, CatalogueOutcome.CREATED

    async def update(
        self, family_id: UUID, command: UpdateProductFamily, *, acting_user_id: UUID
    ) -> ProductFamily:
        async with self._uow as uow:
            family = await uow.product_families.get(family_id)
            if family is None:
                raise NotFoundError("Product family not found")
            before = _family_snapshot(family)
            if isinstance(command.name, str):
                family.rename(command.name)
            if isinstance(command.sort_order, int):
                family.set_sort_order(command.sort_order)
            if isinstance(command.is_active, bool):
                if command.is_active:
                    family.activate()
                else:
                    family.deactivate()
            await uow.product_families.save(family, expected_version=command.expected_version)
            changes = diff_fields(before, _family_snapshot(family))
            if changes:
                uow.audit.record(
                    entity_type="product_family",
                    entity_id=family.id,
                    action="product_family.updated",
                    changes=changes,
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return family


def _family_snapshot(family: ProductFamily) -> dict[str, object]:
    return {
        "name_es": family.name_es,
        "division_id": family.division_id,
        "sort_order": family.sort_order,
        "is_active": family.is_active,
    }


class PipelineService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def rename(
        self, pipeline_id: UUID, name: str, *, expected_version: int, acting_user_id: UUID
    ) -> Pipeline:
        async with self._uow as uow:
            pipeline = await self._load(uow, pipeline_id)
            before = {"name_es": pipeline.name_es}
            pipeline.rename(name)
            await uow.pipelines.save(pipeline, expected_version=expected_version)
            changes = diff_fields(before, {"name_es": pipeline.name_es})
            if changes:
                uow.audit.record(
                    entity_type="pipeline",
                    entity_id=pipeline.id,
                    action="pipeline.updated",
                    changes=changes,
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return pipeline

    async def update_stage(
        self,
        pipeline_id: UUID,
        stage_id: UUID,
        command: UpdateStage,
        *,
        acting_user_id: UUID,
    ) -> tuple[Pipeline, PipelineStage]:
        async with self._uow as uow:
            pipeline = await self._load(uow, pipeline_id)
            stage = pipeline.stage(stage_id)
            before = _stage_snapshot(stage)
            pipeline.update_stage(
                stage_id,
                name=command.name if isinstance(command.name, str) else None,
                probability=command.probability if isinstance(command.probability, int) else None,
                is_active=command.is_active if isinstance(command.is_active, bool) else None,
            )
            await uow.pipelines.save_stage(
                pipeline, stage_id, expected_version=command.expected_version
            )
            changes = diff_fields(before, _stage_snapshot(stage))
            if changes:
                uow.audit.record(
                    entity_type="pipeline_stage",
                    entity_id=stage.id,
                    action="pipeline_stage.updated",
                    changes=changes,
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return pipeline, stage

    async def reorder(
        self, pipeline_id: UUID, command: ReorderStages, *, acting_user_id: UUID
    ) -> Pipeline:
        async with self._uow as uow:
            pipeline = await self._load(uow, pipeline_id)
            before = [stage.id for stage in pipeline.ordered_stages()]
            pipeline.reorder(command.stage_ids)
            await uow.pipelines.save(pipeline, expected_version=command.expected_version)
            after = [stage.id for stage in pipeline.ordered_stages()]
            if before != after:
                uow.audit.record(
                    entity_type="pipeline",
                    entity_id=pipeline.id,
                    action="pipeline_stages.reordered",
                    changes=diff_fields({"order": before}, {"order": after}),
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return pipeline

    @staticmethod
    async def _load(uow: UnitOfWork, pipeline_id: UUID) -> Pipeline:
        pipeline = await uow.pipelines.get(pipeline_id)
        if pipeline is None:
            raise NotFoundError("Pipeline not found")
        return pipeline


def _stage_snapshot(stage: PipelineStage) -> dict[str, object]:
    return {
        "name_es": stage.name_es,
        "probability": stage.probability,
        "is_active": stage.is_active,
    }

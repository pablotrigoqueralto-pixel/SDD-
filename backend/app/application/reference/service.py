"""Reference data use cases (administrators only)."""

from uuid import UUID

from app.application.reference.commands import (
    CreateBrand,
    CreateLossReason,
    ReorderStages,
    UpdateBrand,
    UpdateLossReason,
    UpdateStage,
)
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.reference.entities import Brand, LossReason, Pipeline, PipelineStage
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


class LossReasonService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(self, command: CreateLossReason, *, acting_user_id: UUID) -> LossReason:
        async with self._uow as uow:
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
            return reason

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

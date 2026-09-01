"""Notifications: the signed-in user's own inbox, and nobody else's."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, UowDep
from app.domain.shared.errors import NotFoundError
from app.schemas.notifications import NotificationRead, NotificationsRead

router = APIRouter(prefix="/notifications", tags=["notifications"])

# What the block shows; `unread_count` stays uncapped so the bell tells the truth.
UNREAD_LIMIT = 20


async def _inbox(uow: UowDep, user_id: UUID) -> NotificationsRead:
    items = await uow.notification_inbox.unread_for(user_id, limit=UNREAD_LIMIT)
    return NotificationsRead(
        items=[NotificationRead.from_entity(n) for n in items],
        unread_count=await uow.notification_inbox.unread_count(user_id),
    )


@router.get(
    "",
    response_model=NotificationsRead,
    summary="Your unread notifications and their count (never another user's)",
)
async def list_notifications(user: CurrentUser, uow: UowDep) -> NotificationsRead:
    # Deliberately no `user_id` parameter, in any role: an inbox is personal.
    return await _inbox(uow, user.id)


@router.post("/read-all", response_model=NotificationsRead, summary="Mark every notification read")
async def mark_all_read(user: CurrentUser, uow: UowDep) -> NotificationsRead:
    await uow.notification_inbox.mark_all_read(user.id)
    await uow.commit()
    return await _inbox(uow, user.id)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationsRead,
    summary="Mark one notification read",
)
async def mark_read(notification_id: UUID, user: CurrentUser, uow: UowDep) -> NotificationsRead:
    # 404 rather than 403: nobody should learn that somebody else's notice exists.
    if not await uow.notification_inbox.mark_read(notification_id, user_id=user.id):
        raise NotFoundError("Notification not found")
    await uow.commit()
    return await _inbox(uow, user.id)

"""Aggregates every v1 router under /api/v1."""

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    activities,
    audit_log,
    auth,
    contacts,
    me,
    opportunities,
    products,
    reference,
    territories,
    users,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(me.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(territories.router)
api_v1_router.include_router(reference.router)
api_v1_router.include_router(accounts.router)
api_v1_router.include_router(products.router)
api_v1_router.include_router(opportunities.router)
api_v1_router.include_router(contacts.router)
api_v1_router.include_router(activities.router)
api_v1_router.include_router(audit_log.router)

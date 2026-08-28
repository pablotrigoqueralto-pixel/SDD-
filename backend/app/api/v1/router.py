"""Aggregates every v1 router under /api/v1."""

from fastapi import APIRouter

from app.api.v1 import audit_log, auth, me, reference, territories, users

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(me.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(territories.router)
api_v1_router.include_router(reference.router)
api_v1_router.include_router(audit_log.router)

"""Dashboard: one read-only reporting request, scoped by the actor's role."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.application.dashboard.periods import DashboardPeriod, resolve_period
from app.application.dashboard.queries import DashboardQueries
from app.schemas.dashboard import DashboardRead

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "",
    response_model=DashboardRead,
    summary="KPI panel: won, conversion, forecast, pipeline, activity (scoped)",
)
async def read_dashboard(
    user: CurrentUser,
    session: SessionDep,
    period: DashboardPeriod = DashboardPeriod.MONTH,
) -> DashboardRead:
    resolved = resolve_period(period)
    data = await DashboardQueries(session).load(resolved, user)
    return DashboardRead.build(resolved, data)

"""Admin dashboard — superuser only. Surfaces analytics + user data so the app
can be exercised end-to-end (auth → tracking → aggregation)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.models import User
from app.users import current_superuser

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(current_superuser)])


@router.get("/overview")
async def overview(session: AsyncSession = Depends(get_async_session)):
    counts = (await session.execute(text("""
        SELECT (SELECT count(*) FROM "user") AS users,
               (SELECT count(*) FROM analytics_events) AS events,
               (SELECT count(DISTINCT session_id) FROM analytics_events) AS sessions,
               (SELECT count(*) FROM saved_searches) AS saved_searches,
               (SELECT count(*) FROM favorites) AS favorites,
               (SELECT value FROM meta WHERE key = 'data_version') AS data_version
    """))).mappings().one()

    by_type = (await session.execute(text("""
        SELECT event_type, count(*) AS n FROM analytics_events
        GROUP BY event_type ORDER BY n DESC
    """))).mappings().all()

    by_day = (await session.execute(text("""
        SELECT date_trunc('day', created_at)::date AS day, count(*) AS n
        FROM analytics_events
        WHERE created_at > now() - interval '14 days'
        GROUP BY day ORDER BY day
    """))).mappings().all()

    return {
        "counts": dict(counts),
        "events_by_type": [dict(r) for r in by_type],
        "events_by_day": [dict(r) for r in by_day],
    }


@router.get("/events")
async def recent_events(
    session: AsyncSession = Depends(get_async_session),
    event_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    where = "WHERE event_type = :event_type" if event_type else ""
    params = {"limit": limit, "offset": offset}
    if event_type:
        params["event_type"] = event_type
    rows = (await session.execute(text(f"""
        SELECT ae.id, ae.event_type, ae.payload, ae.created_at,
               ae.session_id, u.email AS user_email
        FROM analytics_events ae LEFT JOIN "user" u ON u.id = ae.user_id
        {where}
        ORDER BY ae.created_at DESC LIMIT :limit OFFSET :offset
    """), params)).mappings().all()
    return {"events": [dict(r) for r in rows]}


@router.get("/users")
async def list_users(
    session: AsyncSession = Depends(get_async_session),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    rows = (await session.execute(text("""
        SELECT id, email, display_name, institution, is_active, is_superuser,
               is_verified, created_at
        FROM "user" ORDER BY created_at DESC LIMIT :limit OFFSET :offset
    """), {"limit": limit, "offset": offset})).mappings().all()
    return {"users": [dict(r) for r in rows]}


@router.post("/users/{user_id}/superuser")
async def set_superuser(
    user_id: str,
    value: bool = True,
    session: AsyncSession = Depends(get_async_session),
    _: User = Depends(current_superuser),
):
    await session.execute(
        text('UPDATE "user" SET is_superuser = :v WHERE id = :id'),
        {"v": value, "id": user_id},
    )
    await session.commit()
    return {"ok": True}

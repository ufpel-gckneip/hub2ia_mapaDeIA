"""Overview KPIs + distributions (streamlit_app.py:556-574)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.db import get_async_session

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def stats(session: AsyncSession = Depends(get_async_session)):
    async def produce():
        totals = (
            (
                await session.execute(
                    text("""
            SELECT (SELECT count(*) FROM researchers) AS researchers,
                   (SELECT count(*) FROM articles) AS articles,
                   (SELECT count(*) FROM events) AS events,
                   (SELECT count(*) FROM topics WHERE NOT is_noise) AS topics
        """)
                )
            )
            .mappings()
            .one()
        )
        by_year = (
            (
                await session.execute(
                    text("SELECT year, count(*) AS n FROM articles GROUP BY year ORDER BY year")
                )
            )
            .mappings()
            .all()
        )
        by_event = (
            (
                await session.execute(
                    text("""
            SELECT ev.acronym AS event, count(*) AS n
            FROM articles a JOIN events ev ON ev.event_id = a.event_id
            GROUP BY ev.acronym ORDER BY n DESC
        """)
                )
            )
            .mappings()
            .all()
        )
        return {
            "totals": dict(totals),
            "by_year": [dict(r) for r in by_year],
            "by_event": [dict(r) for r in by_event],
        }

    return await cache.cached("stats", session, produce)

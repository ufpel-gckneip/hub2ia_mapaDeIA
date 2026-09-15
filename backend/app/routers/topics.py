"""Topic distribution (streamlit_app.py:537-547)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.db import get_async_session

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("")
async def list_topics(session: AsyncSession = Depends(get_async_session)):
    async def produce():
        rows = (await session.execute(text("""
            SELECT t.topic_id, t.topic_name, t.topic_keywords, t.is_noise,
                   count(r.researcher_id) AS researchers,
                   coalesce(sum(r.n_articles), 0) AS articles
            FROM topics t LEFT JOIN researchers r ON r.topic_id = t.topic_id
            GROUP BY t.topic_id, t.topic_name, t.topic_keywords, t.is_noise
            ORDER BY researchers DESC
        """))).mappings().all()
        return {"topics": [dict(r) for r in rows]}

    return await cache.cached("topics", session, produce)

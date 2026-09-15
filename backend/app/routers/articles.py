"""Article search + detail. Full-text over articles.search_vector
(streamlit_app.py:597-658)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("")
async def list_articles(
    session: AsyncSession = Depends(get_async_session),
    q: str | None = Query(None, description="full-text query"),
    event: str | None = None,
    year: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    where = ["1=1"]
    params: dict = {"limit": limit, "offset": offset}
    rank = "a.year"
    if q:
        where.append("a.search_vector @@ plainto_tsquery('portuguese', :q)")
        params["q"] = q
        rank = "ts_rank(a.search_vector, plainto_tsquery('portuguese', :q)) DESC, a.year"
    if event:
        where.append("ev.acronym = :event")
        params["event"] = event
    if year is not None:
        where.append("a.year = :year")
        params["year"] = year
    where_sql = " AND ".join(where)

    total = (
        await session.execute(
            text(
                f"SELECT count(*) FROM articles a "
                f"JOIN events ev ON ev.event_id=a.event_id WHERE {where_sql}"
            ),
            params,
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                text(f"""
        SELECT a.article_id, a.title, ev.acronym AS event, a.year, a.track
        FROM articles a JOIN events ev ON ev.event_id = a.event_id
        WHERE {where_sql} ORDER BY {rank} DESC LIMIT :limit OFFSET :offset
    """),
                params,
            )
        )
        .mappings()
        .all()
    )
    return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/{article_id}")
async def article_detail(article_id: int, session: AsyncSession = Depends(get_async_session)):
    a = (
        (
            await session.execute(
                text("""
        SELECT a.article_id, a.title, a.abstract, ev.acronym AS event, ev.name AS event_name,
               a.year, a.track, a.pages, a.pdf_url, a.article_url
        FROM articles a JOIN events ev ON ev.event_id = a.event_id
        WHERE a.article_id = :id
    """),
                {"id": article_id},
            )
        )
        .mappings()
        .first()
    )
    if not a:
        raise HTTPException(404, "article not found")
    authors = (
        (
            await session.execute(
                text("""
        SELECT r.researcher_id, r.display_name, au.raw_affiliation, au.author_order
        FROM authorships au JOIN researchers r ON r.researcher_id = au.researcher_id
        WHERE au.article_id = :id ORDER BY au.author_order
    """),
                {"id": article_id},
            )
        )
        .mappings()
        .all()
    )
    return {**dict(a), "authors": [dict(x) for x in authors]}

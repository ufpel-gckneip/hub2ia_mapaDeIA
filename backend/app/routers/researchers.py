"""Researcher list, detail, and ego-network endpoints.

Ports the pandas masking in app/streamlit_app.py:118-124 to server-side SQL.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session

router = APIRouter(prefix="/api/researchers", tags=["researchers"])


@router.get("")
async def list_researchers(
    session: AsyncSession = Depends(get_async_session),
    topic_id: list[int] | None = Query(None),
    min_articles: int = 1,
    state: str | None = None,
    event: str | None = Query(None, description="event acronym"),
    q: str | None = Query(None, description="name substring"),
    year_from: int | None = None,
    year_to: int | None = None,
    sort: str = Query("n_articles", pattern="^(n_articles|display_name|last_year)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    where = ["r.n_articles >= :min_articles"]
    params: dict = {"min_articles": min_articles, "limit": limit, "offset": offset}
    joins = ""

    if topic_id:
        where.append("r.topic_id = ANY(:topic_id)")
        params["topic_id"] = topic_id
    if state:
        where.append("r.state = :state")
        params["state"] = state
    if q:
        where.append("r.display_name ILIKE :q")
        params["q"] = f"%{q}%"
    if year_from is not None:
        where.append("r.last_year >= :year_from")
        params["year_from"] = year_from
    if year_to is not None:
        where.append("r.first_year <= :year_to")
        params["year_to"] = year_to
    if event:
        joins += " JOIN researcher_events re ON re.researcher_id = r.researcher_id JOIN events e ON e.event_id = re.event_id"
        where.append("e.acronym = :event")
        params["event"] = event

    where_sql = " AND ".join(where)
    order_sql = {"n_articles": "r.n_articles DESC", "display_name": "r.display_name ASC",
                 "last_year": "r.last_year DESC"}[sort]

    total = (await session.execute(
        text(f"SELECT count(DISTINCT r.researcher_id) FROM researchers r{joins} WHERE {where_sql}"),
        params,
    )).scalar_one()

    rows = (await session.execute(text(f"""
        SELECT DISTINCT r.researcher_id, r.display_name, r.n_articles, r.first_year,
               r.last_year, r.topic_id, t.topic_name, r.state, r.city, r.primary_affiliation
        FROM researchers r{joins}
        JOIN topics t ON t.topic_id = r.topic_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT :limit OFFSET :offset
    """), params)).mappings().all()

    return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/{researcher_id}")
async def researcher_detail(researcher_id: int, session: AsyncSession = Depends(get_async_session)):
    r = (await session.execute(text("""
        SELECT r.researcher_id, r.normalized_name, r.display_name, r.n_articles,
               r.first_year, r.last_year, r.topic_id, t.topic_name, t.topic_keywords,
               r.primary_affiliation, r.city, r.state, r.events
        FROM researchers r JOIN topics t ON t.topic_id = r.topic_id
        WHERE r.researcher_id = :id
    """), {"id": researcher_id})).mappings().first()
    if not r:
        raise HTTPException(404, "researcher not found")

    institutions = (await session.execute(text("""
        SELECT i.institution_id, i.full_name, i.city, i.state, ri.is_primary
        FROM researcher_institutions ri JOIN institutions i ON i.institution_id = ri.institution_id
        WHERE ri.researcher_id = :id ORDER BY ri.is_primary DESC
    """), {"id": researcher_id})).mappings().all()

    articles = (await session.execute(text("""
        SELECT a.article_id, a.title, a.year, a.track, ev.acronym AS event, a.article_url
        FROM authorships au JOIN articles a ON a.article_id = au.article_id
        JOIN events ev ON ev.event_id = a.event_id
        WHERE au.researcher_id = :id ORDER BY a.year DESC
    """), {"id": researcher_id})).mappings().all()

    return {**dict(r), "institutions": [dict(x) for x in institutions],
            "articles": [dict(x) for x in articles]}


@router.get("/{researcher_id}/coauthors")
async def coauthors(researcher_id: int, session: AsyncSession = Depends(get_async_session)):
    rows = (await session.execute(text("""
        SELECT r.researcher_id, r.display_name, r.n_articles, e.weight
        FROM coauthorship_edges e
        JOIN researchers r ON r.researcher_id =
            CASE WHEN e.src_id = :id THEN e.dst_id ELSE e.src_id END
        WHERE e.src_id = :id OR e.dst_id = :id
        ORDER BY e.weight DESC
    """), {"id": researcher_id})).mappings().all()
    return {"coauthors": [dict(r) for r in rows]}

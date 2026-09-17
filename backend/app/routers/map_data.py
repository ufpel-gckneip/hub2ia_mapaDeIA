"""Map endpoints: geo points (deck.gl ScatterplotLayer) and state aggregates
(choropleth + inter-state ArcLayer). Ports streamlit_app.py:167-183, 306-320.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.db import get_async_session

router = APIRouter(prefix="/api/map", tags=["map"])

# Co-authorship arcs aggregated at three granularities. Each returns a uniform
# shape: {x1,y1,x2,y2,label1,label2,weight}. Endpoints are lng/lat.
_ARC_SQL = {
    # Between states: sum weights per (different) UF pair; endpoints = data-driven
    # state centroids (avg of researcher coords in that state).
    "state": """
        WITH sc AS (
            SELECT state, avg(ST_X(geom)) AS x, avg(ST_Y(geom)) AS y
            FROM researchers WHERE state IS NOT NULL AND geom IS NOT NULL
            GROUP BY state
        ), pairs AS (
            SELECT least(rs.state, rd.state) AS a, greatest(rs.state, rd.state) AS b,
                   sum(e.weight) AS weight
            FROM coauthorship_edges e
            JOIN researchers rs ON rs.researcher_id = e.src_id
            JOIN researchers rd ON rd.researcher_id = e.dst_id
            WHERE rs.state IS NOT NULL AND rd.state IS NOT NULL AND rs.state <> rd.state
            GROUP BY 1, 2
        )
        SELECT p.weight, sa.x AS x1, sa.y AS y1, p.a AS label1,
               sb.x AS x2, sb.y AS y2, p.b AS label2
        FROM pairs p JOIN sc sa ON sa.state = p.a JOIN sc sb ON sb.state = p.b
        WHERE p.weight >= :min_weight ORDER BY p.weight DESC LIMIT :limit
    """,
    # Between universities/institutions: aggregate by each researcher's PRIMARY
    # institution pair; endpoints = institution coordinates.
    "institution": """
        WITH pairs AS (
            SELECT least(ra.institution_id, rb.institution_id) AS a,
                   greatest(ra.institution_id, rb.institution_id) AS b,
                   sum(e.weight) AS weight
            FROM coauthorship_edges e
            JOIN researcher_institutions ra ON ra.researcher_id = e.src_id AND ra.is_primary
            JOIN researcher_institutions rb ON rb.researcher_id = e.dst_id AND rb.is_primary
            WHERE ra.institution_id <> rb.institution_id
            GROUP BY 1, 2
        )
        SELECT p.weight, ST_X(i1.geom) AS x1, ST_Y(i1.geom) AS y1, i1.full_name AS label1,
               ST_X(i2.geom) AS x2, ST_Y(i2.geom) AS y2, i2.full_name AS label2
        FROM pairs p
        JOIN institutions i1 ON i1.institution_id = p.a
        JOIN institutions i2 ON i2.institution_id = p.b
        WHERE p.weight >= :min_weight ORDER BY p.weight DESC LIMIT :limit
    """,
    # Between authors: the raw person-to-person edges, both geocoded, endpoints
    # at distinct coordinates (skip same-location pairs → invisible zero-length arcs).
    "author": """
        SELECT e.weight, ST_X(rs.geom) AS x1, ST_Y(rs.geom) AS y1, rs.display_name AS label1,
               ST_X(rd.geom) AS x2, ST_Y(rd.geom) AS y2, rd.display_name AS label2
        FROM coauthorship_edges e
        JOIN researchers rs ON rs.researcher_id = e.src_id
        JOIN researchers rd ON rd.researcher_id = e.dst_id
        WHERE rs.geom IS NOT NULL AND rd.geom IS NOT NULL
          AND NOT ST_Equals(rs.geom, rd.geom) AND e.weight >= :min_weight
        ORDER BY e.weight DESC LIMIT :limit
    """,
}


@router.get("/arcs")
async def arcs(
    session: AsyncSession = Depends(get_async_session),
    level: str = Query("state", pattern="^(state|institution|author)$"),
    min_weight: int = Query(1, ge=1),
    limit: int = Query(150, ge=1, le=2000),
):
    sql = _ARC_SQL.get(level)
    if sql is None:
        raise HTTPException(400, "invalid level")

    async def produce():
        rows = (
            (await session.execute(text(sql), {"min_weight": min_weight, "limit": limit}))
            .mappings()
            .all()
        )
        return {"level": level, "arcs": [dict(r) for r in rows]}

    return await cache.cached(f"arcs:{level}:{min_weight}:{limit}", session, produce)


# Individual researcher points are meant to be narrowed (a viewport bbox or a
# sidebar filter). Without any narrowing filter the effective limit is clamped to
# this, so an unfiltered request can't dump the whole ~8.3k-row geolocated set.
UNFILTERED_POINT_CAP = 500


@router.get("/researchers")
async def map_researchers(
    session: AsyncSession = Depends(get_async_session),
    topic_id: list[int] | None = Query(None),
    min_articles: int = 1,
    q: str | None = None,
    bbox: str | None = Query(None, description="minLng,minLat,maxLng,maxLat"),
    limit: int = Query(2000, ge=1, le=2000),
):
    where = ["r.geom IS NOT NULL", "r.n_articles >= :min_articles"]
    params: dict = {"min_articles": min_articles}
    bbox_applied = False
    if topic_id:
        where.append("r.topic_id = ANY(:topic_id)")
        params["topic_id"] = topic_id
    if q:
        where.append("r.display_name ILIKE :q")
        params["q"] = f"%{q}%"
    if bbox:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise HTTPException(
                422, "bbox must be 'minLng,minLat,maxLng,maxLat' (4 comma-separated numbers)"
            )
        try:
            mnx, mny, mxx, mxy = (float(x) for x in parts)
        except ValueError:
            raise HTTPException(422, "bbox coordinates must be numbers") from None
        where.append("r.geom && ST_MakeEnvelope(:mnx,:mny,:mxx,:mxy,4326)")
        params.update(mnx=mnx, mny=mny, mxx=mxx, mxy=mxy)
        bbox_applied = True
    # Clamp unfiltered pulls; a bbox or any sidebar filter unlocks the full limit.
    narrowed = bool(topic_id or q or min_articles > 1 or bbox_applied)
    params["limit"] = limit if narrowed else min(limit, UNFILTERED_POINT_CAP)
    rows = (
        (
            await session.execute(
                text(f"""
        SELECT r.researcher_id, r.display_name, r.n_articles, r.topic_id,
               ST_X(r.geom) AS lng, ST_Y(r.geom) AS lat
        FROM researchers r WHERE {" AND ".join(where)}
        ORDER BY r.n_articles DESC LIMIT :limit
    """),
                params,
            )
        )
        .mappings()
        .all()
    )
    return {"points": [dict(r) for r in rows]}


def _researcher_filter(topic_id, min_articles, q):
    """Shared WHERE fragment + params for filtering by the sidebar controls."""
    where = ["ri.is_primary", "r.n_articles >= :min_articles"]
    params: dict = {"min_articles": min_articles}
    if topic_id:
        where.append("r.topic_id = ANY(:topic_id)")
        params["topic_id"] = topic_id
    if q:
        where.append("r.display_name ILIKE :q")
        params["q"] = f"%{q}%"
    return where, params


@router.get("/institutions")
async def map_institutions(
    session: AsyncSession = Depends(get_async_session),
    topic_id: list[int] | None = Query(None),
    min_articles: int = 1,
    q: str | None = None,
):
    """One marker per university (canonical full_name merges affiliation-string
    variants), sized by researcher count. This is the default map layer — avoids
    stacking every author on the same campus point."""
    where, params = _researcher_filter(topic_id, min_articles, q)
    rows = (
        (
            await session.execute(
                text(f"""
        SELECT coalesce(i.full_name, i.affiliation_key) AS name,
               max(i.city) AS city, max(i.state) AS state,
               avg(ST_X(i.geom)) AS lng, avg(ST_Y(i.geom)) AS lat,
               count(DISTINCT r.researcher_id) AS n_researchers,
               sum(r.n_articles) AS n_articles
        FROM researcher_institutions ri
        JOIN institutions i ON i.institution_id = ri.institution_id
        JOIN researchers r ON r.researcher_id = ri.researcher_id
        WHERE {" AND ".join(where)}
        GROUP BY coalesce(i.full_name, i.affiliation_key)
        ORDER BY n_researchers DESC
    """),
                params,
            )
        )
        .mappings()
        .all()
    )
    return {"institutions": [dict(r) for r in rows]}


@router.get("/institution-authors")
async def map_institution_authors(
    session: AsyncSession = Depends(get_async_session),
    name: str = Query(..., description="canonical institution name"),
    topic_id: list[int] | None = Query(None),
    min_articles: int = 1,
    q: str | None = None,
):
    """Individual researchers whose primary institution is `name`. They share the
    campus coordinate; the frontend fans them out (spiderfies) on drill-down."""
    where, params = _researcher_filter(topic_id, min_articles, q)
    where.append("coalesce(i.full_name, i.affiliation_key) = :name")
    params["name"] = name
    rows = (
        (
            await session.execute(
                text(f"""
        SELECT r.researcher_id, r.display_name, r.n_articles, r.topic_id
        FROM researcher_institutions ri
        JOIN institutions i ON i.institution_id = ri.institution_id
        JOIN researchers r ON r.researcher_id = ri.researcher_id
        WHERE {" AND ".join(where)}
        ORDER BY r.n_articles DESC
    """),
                params,
            )
        )
        .mappings()
        .all()
    )
    return {"name": name, "authors": [dict(r) for r in rows]}


@router.get("/state-aggregates")
async def state_aggregates(session: AsyncSession = Depends(get_async_session)):
    async def produce():
        states = (
            (
                await session.execute(
                    text("""
            SELECT r.state,
                   count(*) AS researchers,
                   sum(r.n_articles) AS articles
            FROM researchers r WHERE r.state IS NOT NULL
            GROUP BY r.state
        """)
                )
            )
            .mappings()
            .all()
        )

        top_topics = (
            (
                await session.execute(
                    text("""
            SELECT state, topic_name, n FROM (
              SELECT r.state, t.topic_name, count(*) AS n,
                     row_number() OVER (PARTITION BY r.state ORDER BY count(*) DESC) AS rk
              FROM researchers r JOIN topics t ON t.topic_id = r.topic_id
              WHERE r.state IS NOT NULL AND NOT t.is_noise
              GROUP BY r.state, t.topic_name
            ) s WHERE rk <= 5
        """)
                )
            )
            .mappings()
            .all()
        )

        edges = (
            (
                await session.execute(
                    text("""
            SELECT least(rs.state, rd.state) AS s1, greatest(rs.state, rd.state) AS s2,
                   sum(e.weight) AS weight
            FROM coauthorship_edges e
            JOIN researchers rs ON rs.researcher_id = e.src_id
            JOIN researchers rd ON rd.researcher_id = e.dst_id
            WHERE rs.state IS NOT NULL AND rd.state IS NOT NULL AND rs.state <> rd.state
            GROUP BY 1, 2 ORDER BY weight DESC LIMIT 100
        """)
                )
            )
            .mappings()
            .all()
        )

        topics_by_state: dict[str, list] = {}
        for t in top_topics:
            topics_by_state.setdefault(t["state"], []).append(
                {"topic": t["topic_name"], "count": t["n"]}
            )

        return {
            "states": [
                {**dict(s), "top_topics": topics_by_state.get(s["state"], [])} for s in states
            ],
            "edges": [dict(e) for e in edges],
        }

    return await cache.cached("state_aggregates", session, produce)

"""Co-authorship graph for Sigma.js. Served whole (Sigma needs the full graph
for layout); precomputed layout comes from the pipeline. Cached; supports
min_degree thinning for weaker clients. Replaces the pyvis tab."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import cache
from app.db import get_async_session

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("")
async def full_graph(
    session: AsyncSession = Depends(get_async_session),
    min_degree: int = Query(0, ge=0),
):
    async def produce():
        nodes = (
            (
                await session.execute(
                    text("""
            SELECT n.researcher_id AS id, coalesce(n.display_name, r.display_name) AS label,
                   n.degree, n.x, n.y, r.topic_id, r.n_articles
            FROM coauthorship_nodes n
            JOIN researchers r ON r.researcher_id = n.researcher_id
            WHERE n.degree >= :min_degree
        """),
                    {"min_degree": min_degree},
                )
            )
            .mappings()
            .all()
        )
        # Filter edges in SQL against the same degree-filtered node set
        # (both endpoints must survive), so min_degree reduces DB->app transfer
        # instead of shipping every edge and dropping most in Python.
        edges = (
            (
                await session.execute(
                    text("""
            WITH kept AS (
                SELECT n.researcher_id AS id
                FROM coauthorship_nodes n
                JOIN researchers r ON r.researcher_id = n.researcher_id
                WHERE n.degree >= :min_degree
            )
            SELECT e.src_id AS source, e.dst_id AS target, e.weight
            FROM coauthorship_edges e
            JOIN kept ks ON ks.id = e.src_id
            JOIN kept kd ON kd.id = e.dst_id
            WHERE e.weight >= 1
        """),
                    {"min_degree": min_degree},
                )
            )
            .mappings()
            .all()
        )
        return {"nodes": [dict(n) for n in nodes], "edges": [dict(e) for e in edges]}

    return await cache.cached(f"graph:{min_degree}", session, produce)

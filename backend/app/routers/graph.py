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
        ids = {n["id"] for n in nodes}
        edges = (
            (
                await session.execute(
                    text("""
            SELECT src_id AS source, dst_id AS target, weight
            FROM coauthorship_edges
            WHERE weight >= 1
        """)
                )
            )
            .mappings()
            .all()
        )
        edges = [dict(e) for e in edges if e["source"] in ids and e["target"] in ids]
        return {"nodes": [dict(n) for n in nodes], "edges": edges}

    return await cache.cached(f"graph:{min_degree}", session, produce)

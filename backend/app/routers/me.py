"""Per-user data: saved searches and favorites (JWT required)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.models import Favorite, SavedSearch, User
from app.schemas import FavoriteCreate, SavedSearchCreate, SavedSearchRead
from app.users import current_active_user

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/saved-searches", response_model=list[SavedSearchRead])
async def list_saved(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_async_session)
):
    rows = (
        (
            await session.execute(
                select(SavedSearch)
                .where(SavedSearch.user_id == user.id)
                .order_by(SavedSearch.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return rows


@router.post("/saved-searches", response_model=SavedSearchRead, status_code=201)
async def create_saved(
    body: SavedSearchCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    row = (
        await session.execute(
            insert(SavedSearch)
            .values(user_id=user.id, name=body.name, params=body.params)
            .returning(SavedSearch)
        )
    ).scalar_one()
    await session.commit()
    return row


@router.delete("/saved-searches/{search_id}", status_code=204)
async def delete_saved(
    search_id: int,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    res = await session.execute(
        delete(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.user_id == user.id)
    )
    await session.commit()
    if res.rowcount == 0:
        raise HTTPException(404, "not found")


@router.get("/favorites")
async def list_favorites(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_async_session)
):
    rows = (
        (await session.execute(select(Favorite).where(Favorite.user_id == user.id))).scalars().all()
    )
    return [{"entity_type": f.entity_type, "entity_id": f.entity_id} for f in rows]


@router.post("/favorites", status_code=201)
async def add_favorite(
    body: FavoriteCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    # Idempotent: ignore if the favorite already exists.
    await session.execute(
        pg_insert(Favorite)
        .values(user_id=user.id, entity_type=body.entity_type, entity_id=body.entity_id)
        .on_conflict_do_nothing()
    )
    await session.commit()
    return {"ok": True}


@router.delete("/favorites", status_code=204)
async def remove_favorite(
    body: FavoriteCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    await session.execute(
        delete(Favorite).where(
            Favorite.user_id == user.id,
            Favorite.entity_type == body.entity_type,
            Favorite.entity_id == body.entity_id,
        )
    )
    await session.commit()

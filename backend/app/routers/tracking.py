"""Analytics ingest. Accepts optional JWT (fills user_id) or anonymous
session_id. Fire-and-forget → 202. LGPD: no IP/UA stored."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.models import AnalyticsEvent, User
from app.schemas import TrackEvent
from app.users import optional_current_user

router = APIRouter(prefix="/api/events", tags=["tracking"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def track(
    body: TrackEvent,
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    await session.execute(
        insert(AnalyticsEvent).values(
            user_id=user.id if user else None,
            session_id=body.session_id,
            event_type=body.event_type,
            payload=body.payload,
        )
    )
    await session.commit()
    return {"accepted": True}

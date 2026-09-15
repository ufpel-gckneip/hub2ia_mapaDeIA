"""FastAPI application assembly for Mapa de IA."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    admin,
    articles,
    graph,
    map_data,
    me,
    researchers,
    stats,
    topics,
    tracking,
)
from app.schemas import UserCreate, UserRead, UserUpdate
from app.users import auth_backend, fastapi_users

# Refuse to start the API with an unset/weak signing key (fails the boot and the
# container healthcheck). The loader path never imports this module, so data
# loading is unaffected.
settings.assert_secure_secret_key()

app = FastAPI(title="Mapa de IA API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}


# ── Auth routes (fastapi-users) ──
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"]
)
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)

# ── Application routes ──
app.include_router(researchers.router)
app.include_router(map_data.router)
app.include_router(topics.router)
app.include_router(graph.router)
app.include_router(articles.router)
app.include_router(stats.router)
app.include_router(me.router)
app.include_router(tracking.router)
app.include_router(admin.router)

"""SQLAlchemy ORM models — the full Mapa de IA schema.

Research tables mirror the shapes produced by the pipeline (files/02, 04, 05).
Auth + tracking tables support accounts and analytics.

The DDL is owned by Alembic migrations; these models are the source of truth
that `alembic revision --autogenerate` compares against, and that the API and
loader import.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# ─────────────────────────────────────────────────────────────────────────────
# Reference / research data
# ─────────────────────────────────────────────────────────────────────────────


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    acronym: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    issn: Mapped[str | None] = mapped_column(Text)


class Topic(Base):
    __tablename__ = "topics"

    # PK is the raw HDBSCAN cluster id (incl. -1 for noise), so researchers.cluster
    # maps 1:1. -1 is stored as a real row with is_noise = TRUE ("Outros").
    topic_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    topic_name: Mapped[str] = mapped_column(Text, nullable=False)
    topic_keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    is_noise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Institution(Base):
    __tablename__ = "institutions"

    institution_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    affiliation_key: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    # Brazilian UF (2-letter) for domestic institutions, or a country/region
    # string ("Portugal", "CA, USA") for international ones — hence wider than 2.
    state: Mapped[str | None] = mapped_column(String(32))
    geom: Mapped[object] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=False
    )

    __table_args__ = (Index("ix_institutions_geom", "geom", postgresql_using="gist"),)


class Article(Base):
    __tablename__ = "articles"

    article_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    event_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("events.event_id"), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    track: Mapped[str | None] = mapped_column(Text)
    pages: Mapped[str | None] = mapped_column(Text)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    article_url: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # Best-effort dedup guard (§4.7): the same paper crawled twice would collide.
        UniqueConstraint("title", "event_id", "year", name="uq_articles_title_event_year"),
        Index("ix_articles_event_id", "event_id"),
        Index("ix_articles_year", "year"),
        # Full-text search over title + abstract. The generated tsvector column and
        # its GIN index are created in the Alembic migration via raw SQL (SQLAlchemy
        # cannot express GENERATED tsvector cleanly across versions).
    )


class Researcher(Base):
    __tablename__ = "researchers"

    researcher_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    normalized_name: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    n_articles: Mapped[int] = mapped_column(Integer, nullable=False)
    first_year: Mapped[int | None] = mapped_column(SmallInteger)
    last_year: Mapped[int | None] = mapped_column(SmallInteger)
    topic_id: Mapped[int] = mapped_column(Integer, ForeignKey("topics.topic_id"), nullable=False)

    # Denormalized geo (present for ~8,293 / 8,898 → nullable).
    primary_affiliation: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    # Brazilian UF (2-letter) for domestic institutions, or a country/region
    # string ("Portugal", "CA, USA") for international ones — hence wider than 2.
    state: Mapped[str | None] = mapped_column(String(32))
    geom: Mapped[object | None] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))

    # Denormalized event acronyms for cheap display; also normalized in researcher_events.
    events: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    __table_args__ = (
        Index("ix_researchers_topic_id", "topic_id"),
        Index("ix_researchers_n_articles", "n_articles"),
        Index("ix_researchers_state", "state"),
        Index("ix_researchers_geom", "geom", postgresql_using="gist"),
        # Infix name search (matches current str.contains UX) via trigram index.
        Index(
            "ix_researchers_display_name_trgm",
            "display_name",
            postgresql_using="gin",
            postgresql_ops={"display_name": "gin_trgm_ops"},
        ),
    )


class Authorship(Base):
    __tablename__ = "authorships"

    article_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("articles.article_id"), primary_key=True)
    researcher_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("researchers.researcher_id"), primary_key=True)
    author_order: Mapped[int | None] = mapped_column(SmallInteger)
    raw_affiliation: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_authorships_researcher_id", "researcher_id"),)


class ResearcherInstitution(Base):
    __tablename__ = "researcher_institutions"

    researcher_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("researchers.researcher_id"), primary_key=True)
    institution_id: Mapped[int] = mapped_column(Integer, ForeignKey("institutions.institution_id"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("ix_researcher_institutions_institution_id", "institution_id"),)


class ResearcherEvent(Base):
    __tablename__ = "researcher_events"

    researcher_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("researchers.researcher_id"), primary_key=True)
    event_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("events.event_id"), primary_key=True)


class CoauthorshipEdge(Base):
    __tablename__ = "coauthorship_edges"

    # Canonical undirected edge: src_id < dst_id, no self-loops.
    src_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("researchers.researcher_id"), primary_key=True)
    dst_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("researchers.researcher_id"), primary_key=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("src_id < dst_id", name="ck_coauthorship_edges_canonical"),
        Index("ix_coauthorship_edges_dst_id", "dst_id"),
    )


class CoauthorshipNode(Base):
    """Precomputed graph nodes with spring-layout coordinates.

    The graph node universe (9,056) is a superset of the researchers table
    (8,898); ~158 nodes will not resolve. researcher_id is therefore NULLABLE
    so the mismatch is explicit/queryable rather than a silent join failure.
    """

    __tablename__ = "coauthorship_nodes"

    node_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    normalized_name: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    researcher_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("researchers.researcher_id", ondelete="SET NULL")
    )
    display_name: Mapped[str | None] = mapped_column(Text)
    degree: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    x: Mapped[float | None] = mapped_column()
    y: Mapped[float | None] = mapped_column()

    __table_args__ = (Index("ix_coauthorship_nodes_degree", "degree"),)


class Meta(Base):
    """Key/value store; holds data_version bumped on each pipeline reload."""

    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


# ─────────────────────────────────────────────────────────────────────────────
# Auth + tracking
# ─────────────────────────────────────────────────────────────────────────────


class User(SQLAlchemyBaseUserTableUUID, Base):
    """fastapi-users base gives: id (UUID), email, hashed_password,
    is_active, is_superuser, is_verified. We extend with profile fields."""

    __tablename__ = "user"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(Text)
    institution: Mapped[str | None] = mapped_column(Text)


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_saved_searches_user_id", "user_id"),)


class Favorite(Base):
    __tablename__ = "favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    entity_type: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('researcher','article','topic')",
            name="ck_favorites_entity_type",
        ),
    )


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Nullable: anonymous visitors allowed. SET NULL on account deletion keeps
    # aggregate stats intact (LGPD-friendly).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_analytics_events_type_created", "event_type", "created_at"),
        Index("ix_analytics_events_session_id", "session_id"),
    )

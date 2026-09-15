"""initial schema — research data + auth + tracking

Creates all tables from app.models plus the extensions, the generated
full-text search column on articles, and its GIN index.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op

from app.db import Base
from app import models  # noqa: F401  (registers tables on Base.metadata)

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Extensions must exist before CITEXT columns / gin_trgm_ops / PostGIS types.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create every table declared on the models' metadata, in dependency order.
    Base.metadata.create_all(bind=bind)

    # Full-text search on articles: a STORED generated tsvector + GIN index.
    # ('portuguese' config is the pragmatic default for a mostly-PT corpus.)
    op.execute(
        """
        ALTER TABLE articles
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('portuguese', coalesce(title, '') || ' ' || coalesce(abstract, ''))
        ) STORED
        """
    )
    op.execute("CREATE INDEX ix_articles_search_vector ON articles USING gin (search_vector)")


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_articles_search_vector")
    op.execute("ALTER TABLE articles DROP COLUMN IF EXISTS search_vector")
    Base.metadata.drop_all(bind=bind)

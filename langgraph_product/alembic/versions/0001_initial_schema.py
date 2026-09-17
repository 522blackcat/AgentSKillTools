"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-16
"""

from __future__ import annotations

from alembic import op

from app.database.base import Base
from app.database import models  # noqa: F401


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

from __future__ import annotations

from pathlib import Path

from app.database.base import Base
from app.database import models  # noqa: F401


def test_alembic_migration_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "alembic.ini").exists()
    assert (root / "alembic" / "env.py").exists()
    assert (root / "alembic" / "script.py.mako").exists()
    assert (root / "alembic" / "versions" / "0001_initial_schema.py").exists()


def test_initial_migration_covers_model_tables() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "alembic" / "versions" / "0001_initial_schema.py").read_text(
        encoding="utf-8"
    )
    assert 'revision = "0001_initial_schema"' in migration
    assert "down_revision = None" in migration
    assert "Base.metadata.create_all" in migration
    assert "Base.metadata.drop_all" in migration
    assert len(Base.metadata.tables) >= 20
    assert {"tenants", "users", "agent_runs", "domain_templates"}.issubset(
        Base.metadata.tables
    )

"""initial pgvector schema

Revision ID: 0001_initial_pgvector_schema
Revises:
Create Date: 2026-09-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_pgvector_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists vector")
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("domain", sa.String(length=120), nullable=False, server_default="general"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False, server_default=""),
        sa.Column("doc_type", sa.String(length=80), nullable=False, server_default="text"),
        sa.Column("checksum", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="indexed"),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("document_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("chunk_id", sa.String(length=160), nullable=False),
        sa.Column("parent_chunk_id", sa.String(length=160), nullable=True),
        sa.Column("chunk_type", sa.String(length=80), nullable=False, server_default="leaf"),
        sa.Column("section_title", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("location", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "chunk_id"),
    )
    op.execute("alter table document_chunks add column if not exists embedding_vector vector(8)")
    op.execute(
        "create index if not exists ix_document_chunks_embedding_vector "
        "on document_chunks using ivfflat (embedding_vector vector_cosine_ops)"
    )
    op.execute(
        "create index if not exists ix_document_chunks_search_text "
        "on document_chunks using gin (to_tsvector('simple', search_text))"
    )
    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("retrieval_logs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")

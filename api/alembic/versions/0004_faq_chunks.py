"""add FAQ chunks with pgvector embeddings

Revision ID: 0004_faq_chunks
Revises: 0003_staff_invitations
Create Date: 2026-10-21

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0004_faq_chunks"
down_revision: str | Sequence[str] | None = "0003_staff_invitations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "faq_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clinic_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clinic_id",
            "question",
            "chunk_index",
            name="uq_faq_chunks_clinic_question_chunk",
        ),
    )
    op.create_index("ix_faq_chunks_clinic_id", "faq_chunks", ["clinic_id"])
    op.create_index(
        "ix_faq_chunks_clinic_active",
        "faq_chunks",
        ["clinic_id"],
        postgresql_where=sa.text("is_active"),
    )
    op.execute(
        "CREATE INDEX ix_faq_chunks_embedding ON faq_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("faq_chunks")

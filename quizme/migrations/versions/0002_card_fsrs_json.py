"""card: add fsrs_json, relax stability/difficulty nullability

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06

The raw ``fsrs.Card`` dict is the scheduler's source of truth; the flat columns
are denormalised for selection queries and may be null before the first review.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("card", sa.Column("fsrs_json", sa.JSON, nullable=False, server_default="{}"))
    op.alter_column("card", "stability", nullable=True)
    op.alter_column("card", "difficulty", nullable=True)
    op.alter_column("card", "step", nullable=True)
    op.alter_column("card", "reps", nullable=True, server_default="0")
    op.alter_column("card", "lapses", nullable=True, server_default="0")


def downgrade() -> None:
    op.drop_column("card", "fsrs_json")
    op.alter_column("card", "stability", nullable=False)
    op.alter_column("card", "difficulty", nullable=False)
    op.alter_column("card", "step", nullable=False)
    op.alter_column("card", "reps", nullable=False)
    op.alter_column("card", "lapses", nullable=False)

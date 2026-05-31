"""add ML model run persistence

Revision ID: 0002_ml_model_runs
Revises: 0001_initial
Create Date: 2026-05-31
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0002_ml_model_runs"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def id_col() -> sa.Column[Any]:
    return sa.Column("id", sa.String(length=36), nullable=False)


def upgrade() -> None:
    op.create_table(
        "ml_model_runs",
        id_col(),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("feature_names", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ml_model_runs_run_type"), "ml_model_runs", ["run_type"])
    op.create_index(op.f("ix_ml_model_runs_status"), "ml_model_runs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ml_model_runs_status"), table_name="ml_model_runs")
    op.drop_index(op.f("ix_ml_model_runs_run_type"), table_name="ml_model_runs")
    op.drop_table("ml_model_runs")

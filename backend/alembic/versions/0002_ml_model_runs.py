"""legacy compatibility shim for ML model runs

Revision ID: 0002_ml_model_runs
Revises: 0001_initial
Create Date: 2026-05-31
"""

from collections.abc import Sequence


revision: str = "0002_ml_model_runs"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep legacy databases on 0002 resolvable after folding schema into 0001."""


def downgrade() -> None:
    """No-op: schema is owned by 0001_initial."""

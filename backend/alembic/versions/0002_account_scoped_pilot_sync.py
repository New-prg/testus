"""account scoped pilot sync

Revision ID: 0002_account_scoped_pilot_sync
Revises: 0001_initial
Create Date: 2026-06-01
"""

from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.core.security import encrypt_secret, hash_password

revision: str = "0002_account_scoped_pilot_sync"
down_revision: str | None = "0002_ml_model_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("pilot_password_encrypted", sa.String(length=1024), nullable=True))
    op.add_column("users", sa.Column("pilot_server_address", sa.String(length=512), nullable=True))
    op.add_column("users", sa.Column("pilot_node", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("sync_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_sync_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_sync_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_sync_error", sa.String(length=1000), nullable=True))
    op.execute("UPDATE users SET login = email WHERE login IS NULL")
    op.create_index(op.f("ix_users_login"), "users", ["login"], unique=True)
    op.create_index(op.f("ix_users_next_sync_at"), "users", ["next_sync_at"], unique=False)

    bind = op.get_bind()
    admin_id = bind.execute(sa.text("SELECT id FROM users WHERE login = :login LIMIT 1"), {"login": "admin@example.com"}).scalar_one_or_none()
    if admin_id is None:
        admin_id = str(uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO users (
                    id, email, login, password_hash, pilot_password_encrypted, full_name, role,
                    pilot_server_address, pilot_node, is_demo, created_at
                ) VALUES (
                    :id, :email, :login, :password_hash, :pilot_password_encrypted, :full_name, :role,
                    :pilot_server_address, :pilot_node, :is_demo, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": admin_id,
                "email": "admin@example.com",
                "login": "admin@example.com",
                "password_hash": hash_password("admin123"),
                "pilot_password_encrypted": encrypt_secret("admin123"),
                "full_name": "Demo Admin",
                "role": "admin",
                "pilot_server_address": None,
                "pilot_node": None,
                "is_demo": True,
            },
        )
    else:
        bind.execute(
            sa.text(
                """
                UPDATE users
                SET is_demo = CASE WHEN login = 'admin@example.com' THEN TRUE ELSE is_demo END,
                    pilot_password_encrypted = COALESCE(pilot_password_encrypted, :pilot_password_encrypted)
                WHERE id = :id
                """
            ),
            {"id": admin_id, "pilot_password_encrypted": encrypt_secret("admin123")},
        )

    op.add_column("vehicles", sa.Column("user_id", sa.String(length=36), nullable=True))
    bind.execute(sa.text("UPDATE vehicles SET user_id = :user_id WHERE user_id IS NULL"), {"user_id": admin_id})
    op.create_index(op.f("ix_vehicles_user_id"), "vehicles", ["user_id"], unique=False)
    if bind.dialect.name != "sqlite":
        op.create_foreign_key("fk_vehicles_user_id_users", "vehicles", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.drop_index(op.f("ix_vehicles_pilot_agent_id"), table_name="vehicles")
    op.create_index(op.f("ix_vehicles_pilot_agent_id"), "vehicles", ["pilot_agent_id"], unique=False)
    if bind.dialect.name != "sqlite":
        op.create_unique_constraint("uq_vehicle_owner_agent", "vehicles", ["user_id", "pilot_agent_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("uq_vehicle_owner_agent", "vehicles", type_="unique")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_vehicles_user_id_users", "vehicles", type_="foreignkey")
    op.drop_index(op.f("ix_vehicles_user_id"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_pilot_agent_id"), table_name="vehicles")
    op.create_index(op.f("ix_vehicles_pilot_agent_id"), "vehicles", ["pilot_agent_id"], unique=True)
    op.drop_column("vehicles", "user_id")

    op.drop_index(op.f("ix_users_next_sync_at"), table_name="users")
    op.drop_index(op.f("ix_users_login"), table_name="users")
    op.drop_column("users", "last_sync_error")
    op.drop_column("users", "next_sync_at")
    op.drop_column("users", "last_sync_completed_at")
    op.drop_column("users", "last_sync_started_at")
    op.drop_column("users", "sync_started_at")
    op.drop_column("users", "is_demo")
    op.drop_column("users", "pilot_node")
    op.drop_column("users", "pilot_server_address")
    op.drop_column("users", "pilot_password_encrypted")
    op.drop_column("users", "login")

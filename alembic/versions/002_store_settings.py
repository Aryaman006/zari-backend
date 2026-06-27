"""Add store_settings table for persistent runtime configuration.

Replaces the local uploads/store_settings.json file approach.
This table allows admin settings (store name, tax rates, API keys) to
persist across server restarts and deployments on Render.

Revision ID: 002_store_settings
Revises: 001_initial_schema
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = "002_store_settings"
down_revision = "16b8eb569a4d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("store_settings")

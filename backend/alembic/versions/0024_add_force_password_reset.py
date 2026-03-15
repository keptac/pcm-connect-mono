"""add force password reset flag

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("force_password_reset", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("users", "force_password_reset", server_default=None)


def downgrade():
    op.drop_column("users", "force_password_reset")

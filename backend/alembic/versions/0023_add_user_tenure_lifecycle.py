"""add user tenure lifecycle fields

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_system_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("subject_to_tenure", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("tenure_starts_on", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("tenure_ends_on", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("disabled_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    op.execute(sa.text("UPDATE users SET subject_to_tenure = true WHERE member_id IS NULL"))

    op.alter_column("users", "is_system_admin", server_default=None)
    op.alter_column("users", "subject_to_tenure", server_default=None)


def downgrade():
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "disabled_at")
    op.drop_column("users", "tenure_ends_on")
    op.drop_column("users", "tenure_starts_on")
    op.drop_column("users", "subject_to_tenure")
    op.drop_column("users", "is_system_admin")

"""add conference scope to users

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("conference_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_conference_id_conferences",
        "users",
        "conferences",
        ["conference_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_users_conference_id_conferences", "users", type_="foreignkey")
    op.drop_column("users", "conference_id")

"""add union scope to users

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("union_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_union_id_unions",
        "users",
        "unions",
        ["union_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_users_union_id_unions", "users", type_="foreignkey")
    op.drop_column("users", "union_id")

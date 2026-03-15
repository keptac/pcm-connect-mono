"""add conferences and assign campuses

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("union_name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    with op.batch_alter_table("universities") as batch_op:
        batch_op.add_column(sa.Column("conference_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_universities_conference_id_conferences",
            "conferences",
            ["conference_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("universities") as batch_op:
        batch_op.drop_constraint("fk_universities_conference_id_conferences", type_="foreignkey")
        batch_op.drop_column("conference_id")

    op.drop_table("conferences")

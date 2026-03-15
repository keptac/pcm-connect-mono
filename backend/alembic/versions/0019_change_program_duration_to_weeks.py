"""change program duration storage to weeks

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("programs") as batch_op:
        batch_op.add_column(sa.Column("duration_weeks", sa.Float(), nullable=True))

    op.execute("UPDATE programs SET duration_weeks = duration_months * 4 WHERE duration_months IS NOT NULL")

    with op.batch_alter_table("programs") as batch_op:
        batch_op.drop_column("duration_months")


def downgrade():
    with op.batch_alter_table("programs") as batch_op:
        batch_op.add_column(sa.Column("duration_months", sa.Integer(), nullable=True))

    op.execute("UPDATE programs SET duration_months = ROUND(duration_weeks / 4.0) WHERE duration_weeks IS NOT NULL")

    with op.batch_alter_table("programs") as batch_op:
        batch_op.drop_column("duration_weeks")

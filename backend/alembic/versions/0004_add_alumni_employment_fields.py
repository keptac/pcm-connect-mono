"""add alumni employment fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("members", sa.Column("employment_status", sa.String(), nullable=True))
    op.add_column("members", sa.Column("employer_name", sa.String(), nullable=True))
    op.add_column("members", sa.Column("current_city", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("members") as batch_op:
        batch_op.drop_column("current_city")
        batch_op.drop_column("employer_name")
        batch_op.drop_column("employment_status")

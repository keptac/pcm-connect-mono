"""add reporting date to program updates

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("program_updates", sa.Column("reporting_date", sa.Date(), nullable=True))
    op.execute(sa.text("UPDATE program_updates SET reporting_date = DATE(created_at) WHERE reporting_date IS NULL"))
    with op.batch_alter_table("program_updates") as batch_op:
        batch_op.alter_column("reporting_date", existing_type=sa.Date(), nullable=False)


def downgrade():
    op.drop_column("program_updates", "reporting_date")

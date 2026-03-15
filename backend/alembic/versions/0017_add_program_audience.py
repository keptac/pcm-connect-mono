"""add program audience

Revision ID: 0017_add_program_audience
Revises: 0016
Create Date: 2026-03-13 15:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0017_add_program_audience"
down_revision = "0016_add_reporting_periods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("programs", sa.Column("audience", sa.String(), nullable=True))
    op.execute("UPDATE programs SET audience = 'Students' WHERE audience IS NULL OR audience = ''")


def downgrade() -> None:
    op.drop_column("programs", "audience")

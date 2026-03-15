"""remove beneficiary member type

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-13
"""

from alembic import op


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE members SET status = 'Student' WHERE status = 'Beneficiary'")


def downgrade():
    op.execute("UPDATE members SET status = 'Beneficiary' WHERE status = 'Student' AND member_id LIKE '%-002'")

"""allow hq funding records

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("funding_records") as batch_op:
        batch_op.alter_column("university_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table("funding_records") as batch_op:
        batch_op.alter_column("university_id", existing_type=sa.Integer(), nullable=False)

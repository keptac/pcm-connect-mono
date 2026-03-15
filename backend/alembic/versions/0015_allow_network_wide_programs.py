"""allow network wide programs

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("programs") as batch_op:
        batch_op.alter_column("university_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.execute(
        "DELETE FROM programs WHERE university_id IS NULL"
    )
    with op.batch_alter_table("programs") as batch_op:
        batch_op.alter_column("university_id", existing_type=sa.Integer(), nullable=False)

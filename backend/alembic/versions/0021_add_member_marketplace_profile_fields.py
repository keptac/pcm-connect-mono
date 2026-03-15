"""add member marketplace profile fields

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("members") as batch_op:
        batch_op.add_column(sa.Column("services_offered", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("products_supplied", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("members") as batch_op:
        batch_op.drop_column("products_supplied")
        batch_op.drop_column("services_offered")

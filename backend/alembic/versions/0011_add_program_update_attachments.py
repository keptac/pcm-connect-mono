"""add attachments to program updates

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("program_updates") as batch_op:
        batch_op.add_column(sa.Column("attachments_json", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("program_updates") as batch_op:
        batch_op.drop_column("attachments_json")

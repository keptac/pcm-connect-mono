"""add mandatory events and update event fields

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("program_updates", sa.Column("event_name", sa.String(), nullable=True))
    op.add_column("program_updates", sa.Column("event_detail", sa.String(), nullable=True))

    program_updates = sa.table(
        "program_updates",
        sa.column("title", sa.String()),
        sa.column("event_name", sa.String()),
    )
    conn = op.get_bind()
    conn.execute(
        program_updates.update()
        .where(program_updates.c.event_name.is_(None))
        .values(event_name=program_updates.c.title)
    )

    op.create_table(
        "mandatory_programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("program_type", sa.String(), nullable=True),
        sa.Column("allow_other_detail", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("mandatory_programs")
    with op.batch_alter_table("program_updates") as batch_op:
        batch_op.drop_column("event_detail")
        batch_op.drop_column("event_name")

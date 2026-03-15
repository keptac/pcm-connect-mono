"""add campus events

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campus_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey("programs.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=True),
        sa.Column("audience", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("venue", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("organizer_name", sa.String(), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_campus_events_university_id", "campus_events", ["university_id"])
    op.create_index("ix_campus_events_starts_at", "campus_events", ["starts_at"])


def downgrade():
    op.drop_index("ix_campus_events_starts_at", table_name="campus_events")
    op.drop_index("ix_campus_events_university_id", table_name="campus_events")
    op.drop_table("campus_events")

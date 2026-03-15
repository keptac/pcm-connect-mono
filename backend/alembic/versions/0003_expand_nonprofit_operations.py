"""expand nonprofit operations

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("universities", sa.Column("short_code", sa.String(), nullable=True))
    op.add_column("universities", sa.Column("region", sa.String(), nullable=True))
    op.add_column("universities", sa.Column("mission_focus", sa.String(), nullable=True))
    op.add_column("universities", sa.Column("contact_name", sa.String(), nullable=True))
    op.add_column("universities", sa.Column("contact_email", sa.String(), nullable=True))
    op.add_column("universities", sa.Column("contact_phone", sa.String(), nullable=True))

    op.add_column("programs", sa.Column("category", sa.String(), nullable=True))
    op.add_column("programs", sa.Column("status", sa.String(), nullable=True))
    op.add_column("programs", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("programs", sa.Column("manager_name", sa.String(), nullable=True))
    op.add_column("programs", sa.Column("target_beneficiaries", sa.Integer(), nullable=True))
    op.add_column("programs", sa.Column("beneficiaries_served", sa.Integer(), nullable=True))
    op.add_column("programs", sa.Column("annual_budget", sa.Float(), nullable=True))
    op.add_column("programs", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("programs", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("programs", sa.Column("last_update_at", sa.DateTime(), nullable=True))

    op.create_table(
        "funding_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey("programs.id"), nullable=True),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("entry_type", sa.String(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("designation", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "program_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey("programs.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("reporting_period", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("outcomes", sa.Text(), nullable=True),
        sa.Column("challenges", sa.Text(), nullable=True),
        sa.Column("next_steps", sa.Text(), nullable=True),
        sa.Column("beneficiaries_reached", sa.Integer(), nullable=True),
        sa.Column("volunteers_involved", sa.Integer(), nullable=True),
        sa.Column("funds_used", sa.Float(), nullable=True),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("program_updates")
    op.drop_table("funding_records")

    with op.batch_alter_table("programs") as batch_op:
        batch_op.drop_column("last_update_at")
        batch_op.drop_column("end_date")
        batch_op.drop_column("start_date")
        batch_op.drop_column("annual_budget")
        batch_op.drop_column("beneficiaries_served")
        batch_op.drop_column("target_beneficiaries")
        batch_op.drop_column("manager_name")
        batch_op.drop_column("description")
        batch_op.drop_column("status")
        batch_op.drop_column("category")

    with op.batch_alter_table("universities") as batch_op:
        batch_op.drop_column("contact_phone")
        batch_op.drop_column("contact_email")
        batch_op.drop_column("contact_name")
        batch_op.drop_column("mission_focus")
        batch_op.drop_column("region")
        batch_op.drop_column("short_code")

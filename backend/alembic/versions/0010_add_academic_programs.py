"""add academic programs and decouple member study from ministry programs

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "academic_programs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("faculty", sa.String(), nullable=True),
        sa.Column("study_area", sa.String(), nullable=True),
        sa.Column("qualification_level", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_academic_programs_university_name",
        "academic_programs",
        ["university_id", "name"],
        unique=True,
    )

    with op.batch_alter_table("members") as batch_op:
        batch_op.add_column(sa.Column("program_of_study_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_members_program_of_study_id_academic_programs",
            "academic_programs",
            ["program_of_study_id"],
            ["id"],
        )

    with op.batch_alter_table("program_updates") as batch_op:
        batch_op.alter_column("program_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table("program_updates") as batch_op:
        batch_op.alter_column("program_id", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("members") as batch_op:
        batch_op.drop_constraint("fk_members_program_of_study_id_academic_programs", type_="foreignkey")
        batch_op.drop_column("program_of_study_id")

    op.drop_index("ix_academic_programs_university_name", table_name="academic_programs")
    op.drop_table("academic_programs")

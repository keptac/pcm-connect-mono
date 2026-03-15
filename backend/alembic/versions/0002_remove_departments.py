"""remove departments

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect_name = bind.dialect.name

    existing_tables = set(inspector.get_table_names())

    if "programs" in existing_tables and any(
        column["name"] == "department_id" for column in inspector.get_columns("programs")
    ):
        if dialect_name == "sqlite":
            with op.batch_alter_table("programs") as batch_op:
                batch_op.drop_column("department_id")
        else:
            for foreign_key in inspector.get_foreign_keys("programs"):
                if foreign_key.get("name") and "department_id" in foreign_key.get("constrained_columns", []):
                    op.drop_constraint(foreign_key["name"], "programs", type_="foreignkey")
            op.drop_column("programs", "department_id")

    if "members" in existing_tables and any(
        column["name"] == "department_id" for column in inspector.get_columns("members")
    ):
        if dialect_name == "sqlite":
            with op.batch_alter_table("members") as batch_op:
                batch_op.drop_column("department_id")
        else:
            for foreign_key in inspector.get_foreign_keys("members"):
                if foreign_key.get("name") and "department_id" in foreign_key.get("constrained_columns", []):
                    op.drop_constraint(foreign_key["name"], "members", type_="foreignkey")
            op.drop_column("members", "department_id")

    if "departments" in existing_tables:
        op.drop_table("departments")


def downgrade():
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
    )
    op.add_column("programs", sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False))
    op.add_column("members", sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=True))

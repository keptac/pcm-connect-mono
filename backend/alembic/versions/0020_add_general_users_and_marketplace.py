"""add general users and marketplace support

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column("donor_interest", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_unique_constraint("uq_users_member_id", ["member_id"])
        batch_op.create_foreign_key("fk_users_member_id_members", "members", ["member_id"], ["id"])

    op.create_table(
        "marketplace_listings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=True),
        sa.Column("listing_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("price_text", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        INSERT INTO roles (name)
        SELECT 'general_user'
        WHERE NOT EXISTS (
            SELECT 1 FROM roles WHERE name = 'general_user'
        )
        """
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("donor_interest", server_default=None)


def downgrade():
    op.drop_table("marketplace_listings")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_member_id_members", type_="foreignkey")
        batch_op.drop_constraint("uq_users_member_id", type_="unique")
        batch_op.drop_column("donor_interest")
        batch_op.drop_column("member_id")

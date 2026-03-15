"""add treasury receipting fields

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("funding_records", sa.Column("flow_direction", sa.String(), nullable=True))
    op.add_column("funding_records", sa.Column("receipt_category", sa.String(), nullable=True))
    op.add_column("funding_records", sa.Column("category_detail", sa.String(), nullable=True))
    op.add_column("funding_records", sa.Column("reporting_window", sa.String(), nullable=True))

    funding_records = sa.table(
        "funding_records",
        sa.column("entry_type", sa.String()),
        sa.column("designation", sa.String()),
        sa.column("flow_direction", sa.String()),
        sa.column("receipt_category", sa.String()),
        sa.column("category_detail", sa.String()),
        sa.column("reporting_window", sa.String()),
    )
    conn = op.get_bind()

    conn.execute(
        funding_records.update()
        .where(funding_records.c.entry_type == "expense")
        .values(
            flow_direction="outflow",
            receipt_category="Other",
            category_detail=sa.func.coalesce(funding_records.c.designation, "Expense"),
            reporting_window="monthly",
        )
    )
    conn.execute(
        funding_records.update()
        .where(funding_records.c.entry_type == "donation")
        .values(
            flow_direction="inflow",
            receipt_category="Donation",
            reporting_window="monthly",
        )
    )
    conn.execute(
        funding_records.update()
        .where(funding_records.c.entry_type == "grant")
        .values(
            flow_direction="inflow",
            receipt_category="Other",
            category_detail="Grant",
            reporting_window="monthly",
        )
    )
    conn.execute(
        funding_records.update()
        .where(funding_records.c.entry_type == "sponsorship")
        .values(
            flow_direction="inflow",
            receipt_category="Other",
            category_detail="Sponsorship",
            reporting_window="monthly",
        )
    )
    conn.execute(
        funding_records.update()
        .where(funding_records.c.flow_direction.is_(None))
        .values(
            flow_direction="inflow",
            receipt_category="Other",
            category_detail="Legacy receipt",
            reporting_window="monthly",
        )
    )


def downgrade():
    with op.batch_alter_table("funding_records") as batch_op:
        batch_op.drop_column("reporting_window")
        batch_op.drop_column("category_detail")
        batch_op.drop_column("receipt_category")
        batch_op.drop_column("flow_direction")

"""add unions and conference scope

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-17
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


DEFAULT_UNION_NAMES = [
    "Zimbabwe Central Union Conference",
    "Zimbabwe East Union Conference",
    "Zimbabwe West Union Conference",
]

SEEDED_CONFERENCE_UNION_MAP = {
    "North Zimbabwe Conference": "Zimbabwe Central Union Conference",
    "East Zimbabwe Conference": "Zimbabwe East Union Conference",
    "South Zimbabwe Conference": "Zimbabwe West Union Conference",
    "Central Zimbabwe Conference": "Zimbabwe Central Union Conference",
}


def _slug_safe_name(value: str) -> str:
    return value.strip()


def upgrade():
    op.create_table(
        "unions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.add_column("conferences", sa.Column("union_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_conferences_union_id_unions",
        "conferences",
        "unions",
        ["union_id"],
        ["id"],
    )

    connection = op.get_bind()
    now = datetime.utcnow()

    union_table = sa.table(
        "unions",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
    )

    existing_union_names = {
        row[0]
        for row in connection.execute(
            sa.text("SELECT DISTINCT union_name FROM conferences WHERE union_name IS NOT NULL AND union_name <> ''")
        )
    }
    for union_name in [*DEFAULT_UNION_NAMES, *sorted(existing_union_names)]:
        normalized_name = _slug_safe_name(union_name)
        if not normalized_name:
            continue
        exists = connection.execute(
            sa.text("SELECT id FROM unions WHERE name = :name"),
            {"name": normalized_name},
        ).first()
        if not exists:
            connection.execute(
                sa.insert(union_table).values(
                    name=normalized_name,
                    is_active=True,
                    created_at=now,
                )
            )

    for conference_name, union_name in SEEDED_CONFERENCE_UNION_MAP.items():
        connection.execute(
            sa.text(
                """
                UPDATE conferences
                SET union_name = :union_name
                WHERE name = :conference_name
                """
            ),
            {
                "conference_name": conference_name,
                "union_name": union_name,
            },
        )

    conference_rows = connection.execute(
        sa.text("SELECT id, union_name FROM conferences")
    ).fetchall()
    union_id_by_name = {
        row[1]: row[0]
        for row in connection.execute(sa.text("SELECT id, name FROM unions"))
    }
    for conference_id, union_name in conference_rows:
        if not union_name:
            continue
        union_id = union_id_by_name.get(union_name)
        if union_id:
            connection.execute(
                sa.text("UPDATE conferences SET union_id = :union_id WHERE id = :conference_id"),
                {"union_id": union_id, "conference_id": conference_id},
            )


def downgrade():
    op.drop_constraint("fk_conferences_union_id_unions", "conferences", type_="foreignkey")
    op.drop_column("conferences", "union_id")
    op.drop_table("unions")

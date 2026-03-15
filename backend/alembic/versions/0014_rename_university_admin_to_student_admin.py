"""rename university admin role to student admin

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


roles = sa.table(
    "roles",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
)

user_roles = sa.table(
    "user_roles",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("role_id", sa.Integer),
)


def _rename_role(old_name: str, new_name: str) -> None:
    bind = op.get_bind()
    old_role_id = bind.execute(
        sa.select(roles.c.id).where(roles.c.name == old_name)
    ).scalar_one_or_none()
    new_role_id = bind.execute(
        sa.select(roles.c.id).where(roles.c.name == new_name)
    ).scalar_one_or_none()

    if old_role_id is None:
        if new_role_id is None:
            bind.execute(sa.insert(roles).values(name=new_name))
        return

    if new_role_id is None:
        bind.execute(
            sa.update(roles)
            .where(roles.c.id == old_role_id)
            .values(name=new_name)
        )
        return

    existing_user_ids = set(
        bind.execute(
            sa.select(user_roles.c.user_id).where(user_roles.c.role_id == new_role_id)
        ).scalars()
    )
    old_user_ids = list(
        bind.execute(
            sa.select(user_roles.c.user_id).where(user_roles.c.role_id == old_role_id)
        ).scalars()
    )

    for user_id in old_user_ids:
        if user_id in existing_user_ids:
            continue
        bind.execute(
            sa.insert(user_roles).values(user_id=user_id, role_id=new_role_id)
        )

    bind.execute(sa.delete(user_roles).where(user_roles.c.role_id == old_role_id))
    bind.execute(sa.delete(roles).where(roles.c.id == old_role_id))


def upgrade():
    _rename_role("university_admin", "student_admin")


def downgrade():
    _rename_role("student_admin", "university_admin")

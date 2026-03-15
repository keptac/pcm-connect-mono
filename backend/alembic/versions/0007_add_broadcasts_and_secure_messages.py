"""add broadcasts and secure messages

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("chat_public_key", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("chat_private_key_encrypted", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("chat_key_salt", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("chat_key_iv", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("chat_key_algorithm", sa.String(), nullable=True))

    op.create_table(
        "program_broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("program_id", sa.Integer(), sa.ForeignKey("programs.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("venue", sa.String(), nullable=True),
        sa.Column("contact_name", sa.String(), nullable=True),
        sa.Column("contact_email", sa.String(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "broadcast_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("broadcast_id", sa.Integer(), sa.ForeignKey("program_broadcasts.id"), nullable=False),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("broadcast_id", "university_id", name="uq_broadcast_invite"),
    )

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "chat_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("thread_id", "user_id", name="uq_chat_participant"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id"), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("ciphertext", sa.Text(), nullable=True),
        sa.Column("iv", sa.String(), nullable=True),
        sa.Column("algorithm", sa.String(), nullable=True),
        sa.Column("key_envelopes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("chat_messages")
    op.drop_table("chat_participants")
    op.drop_table("chat_threads")
    op.drop_table("broadcast_invites")
    op.drop_table("program_broadcasts")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("chat_key_algorithm")
        batch_op.drop_column("chat_key_iv")
        batch_op.drop_column("chat_key_salt")
        batch_op.drop_column("chat_private_key_encrypted")
        batch_op.drop_column("chat_public_key")

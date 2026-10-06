"""Add Paperless

Revision ID: a7c3e9d15b42
Revises: d6a2f8b1c493
Create Date: 2026-10-06 12:00:00.000000

A user may connect their own Paperless-ngx (F-04, ADR-0010): one connection per
user, with the API token kept encrypted. An attachment kept there carries the
document's id. The outbox PDFs wait in on their way to Paperless is a sibling
of the webhook outbox. Like it, it keeps its state in plain strings with check
constraints rather than in database enums, so the downgrade has no types of its
own to drop.
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c3e9d15b42"
down_revision = "d6a2f8b1c493"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attachment",
        sa.Column("paperless_document_id", sa.BigInteger(), nullable=True),
    )
    op.create_table(
        "paperlessconnection",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("token_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "paperlesshandover",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("paperless_task_id", sa.String(length=100), nullable=True),
        sa.Column("paperless_document_id", sa.BigInteger(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "state IN ('pending', 'failed')", name="paperlesshandover_state"
        ),
        sa.CheckConstraint(
            "stage IN ('send', 'poll', 'finish')", name="paperlesshandover_stage"
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"], ["attachment.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attachment_id"),
    )
    op.create_index(
        "ix_paperlesshandover_state_next_attempt_at",
        "paperlesshandover",
        ["state", "next_attempt_at"],
    )


def downgrade() -> None:
    # Nothing here created a database enum or any type of its own.
    op.drop_index(
        "ix_paperlesshandover_state_next_attempt_at", table_name="paperlesshandover"
    )
    op.drop_table("paperlesshandover")
    op.drop_table("paperlessconnection")
    op.drop_column("attachment", "paperless_document_id")

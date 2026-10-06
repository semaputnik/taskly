"""Add webhooks

Revision ID: d6a2f8b1c493
Revises: b5e8a1d4c926
Create Date: 2026-10-06 00:00:00.000000

A bot user gets two optional webhook URLs and one secret (F-11, ADR-0009), and
the outbox their events wait in gets a table. The secret is kept encrypted, not
as a digest: signing needs it back. The outbox keeps its state in plain
strings, with check constraints, rather than in database enums, so the
downgrade has no types of its own to drop.
"""

import sqlalchemy as sa
from alembic import op

revision = "d6a2f8b1c493"
down_revision = "b5e8a1d4c926"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "botuser",
        sa.Column("task_webhook_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "botuser",
        sa.Column("comment_webhook_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "botuser",
        sa.Column("webhook_secret_encrypted", sa.String(length=512), nullable=True),
    )
    op.create_table(
        "webhookdelivery",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bot_user_id", sa.Uuid(), nullable=False),
        sa.Column("webhook", sa.String(length=20), nullable=False),
        sa.Column("event", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("task_title", sa.String(length=255), nullable=True),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("last_duration_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "state IN ('pending', 'delivered', 'failed')",
            name="webhookdelivery_state",
        ),
        sa.CheckConstraint(
            "webhook IN ('task', 'comment')", name="webhookdelivery_webhook"
        ),
        sa.ForeignKeyConstraint(["bot_user_id"], ["botuser.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_webhookdelivery_state_next_attempt_at",
        "webhookdelivery",
        ["state", "next_attempt_at"],
    )
    op.create_index(
        "ix_webhookdelivery_bot_user_id_webhook",
        "webhookdelivery",
        ["bot_user_id", "webhook"],
    )


def downgrade() -> None:
    # Nothing here created a database enum or any type of its own: the table
    # and its indexes go, and the columns with them.
    op.drop_index("ix_webhookdelivery_bot_user_id_webhook", table_name="webhookdelivery")
    op.drop_index(
        "ix_webhookdelivery_state_next_attempt_at", table_name="webhookdelivery"
    )
    op.drop_table("webhookdelivery")
    op.drop_column("botuser", "webhook_secret_encrypted")
    op.drop_column("botuser", "comment_webhook_url")
    op.drop_column("botuser", "task_webhook_url")

"""Track bot token lifecycle

Revision ID: a4d8e2c6b135
Revises: f3c9a7b1d824
Create Date: 2026-09-16 01:20:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a4d8e2c6b135'
down_revision = 'f3c9a7b1d824'
branch_labels = None
depends_on = None


def upgrade():
    # Tokens issued so far never expire and have no recorded use yet.
    for column in ('token_expires_at', 'token_last_used_at', 'token_revoked_at'):
        op.add_column(
            'botuser', sa.Column(column, sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    # Without an expiry to enforce, an expired token would start working again.
    op.execute(
        'UPDATE botuser SET token_hash = NULL '
        'WHERE token_expires_at IS NOT NULL AND token_expires_at <= now()'
    )
    for column in ('token_revoked_at', 'token_last_used_at', 'token_expires_at'):
        op.drop_column('botuser', column)

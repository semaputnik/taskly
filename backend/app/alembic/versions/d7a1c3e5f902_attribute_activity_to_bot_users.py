"""Attribute activity to bot users

Revision ID: d7a1c3e5f902
Revises: c5d2e8f41a97
Create Date: 2026-09-15 22:30:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd7a1c3e5f902'
down_revision = 'c5d2e8f41a97'
branch_labels = None
depends_on = None


def upgrade():
    # Every existing entry names a user as its actor and keeps doing so; the
    # constraint below holds for all of them as they are.
    op.add_column(
        'activityentry',
        sa.Column('actor_bot_user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'activityentry_actor_bot_user_id_fkey',
        'activityentry',
        'botuser',
        ['actor_bot_user_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.alter_column('activityentry', 'actor_id', nullable=True)
    op.create_check_constraint(
        'activityentry_one_actor',
        'activityentry',
        '(actor_id IS NULL) <> (actor_bot_user_id IS NULL)',
    )


def downgrade():
    # Entries made by bot users have no user to fall back on without claiming
    # the owner made them, so they go rather than being misattributed.
    op.execute('DELETE FROM activityentry WHERE actor_bot_user_id IS NOT NULL')
    op.drop_constraint('activityentry_one_actor', 'activityentry', type_='check')
    op.alter_column('activityentry', 'actor_id', nullable=False)
    op.drop_constraint(
        'activityentry_actor_bot_user_id_fkey', 'activityentry', type_='foreignkey'
    )
    op.drop_column('activityentry', 'actor_bot_user_id')

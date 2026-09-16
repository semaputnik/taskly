"""Index a bot user's own feed

Revision ID: c4f1b8d90a62
Revises: b7e4c9a2f051
Create Date: 2026-09-16 12:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c4f1b8d90a62'
down_revision = 'b7e4c9a2f051'
branch_labels = None
depends_on = None


def upgrade():
    # Reading one bot user's activity walks the owner's log newest-first until
    # it finds that actor's entries. The log is kept for ever (FR-10.5), so on
    # a quiet integration that is the whole history, on every panel open.
    op.create_index(
        'ix_activityentry_owner_id_actor_bot_user_id_position',
        'activityentry',
        ['owner_id', 'actor_bot_user_id', 'position'],
    )


def downgrade():
    op.drop_index(
        'ix_activityentry_owner_id_actor_bot_user_id_position',
        table_name='activityentry',
    )

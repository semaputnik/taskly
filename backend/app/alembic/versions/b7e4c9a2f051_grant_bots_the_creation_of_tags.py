"""Grant bots the creation of tags

Revision ID: b7e4c9a2f051
Revises: a4d8e2c6b135
Create Date: 2026-09-16 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b7e4c9a2f051'
down_revision = 'a4d8e2c6b135'
branch_labels = None
depends_on = None


def upgrade():
    # Off for every bot user that exists already: a scope keeps granting
    # exactly what the user last saw, and creating tags was never part of it.
    op.add_column(
        'botuser',
        sa.Column(
            'create_tags', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column('botuser', 'create_tags', server_default=None)


def downgrade():
    op.drop_column('botuser', 'create_tags')

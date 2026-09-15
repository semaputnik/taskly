"""Record bot authors of comments

Revision ID: f3c9a7b1d824
Revises: e8b4d2f6a013
Create Date: 2026-09-16 00:30:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f3c9a7b1d824'
down_revision = 'e8b4d2f6a013'
branch_labels = None
depends_on = None


def upgrade():
    # Every existing comment was written by the user it belongs to.
    op.add_column(
        'comment',
        sa.Column('author_bot_user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'comment_author_bot_user_id_fkey',
        'comment',
        'botuser',
        ['author_bot_user_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade():
    # A bot user's comment would otherwise read as its owner's own words.
    op.execute('DELETE FROM comment WHERE author_bot_user_id IS NOT NULL')
    op.drop_constraint('comment_author_bot_user_id_fkey', 'comment', type_='foreignkey')
    op.drop_column('comment', 'author_bot_user_id')

"""Add bot users

Revision ID: c5d2e8f41a97
Revises: b36cf65b82d1
Create Date: 2026-09-15 20:10:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c5d2e8f41a97'
down_revision = 'b36cf65b82d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'botuser',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('create_tasks', sa.Boolean(), nullable=False),
        sa.Column('read_tasks', sa.Boolean(), nullable=False),
        sa.Column('update_tasks', sa.Boolean(), nullable=False),
        sa.Column('delete_tasks', sa.Boolean(), nullable=False),
        sa.Column('add_comments', sa.Boolean(), nullable=False),
        sa.Column('token_hash', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('token_issued_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='botuser_owner_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='botuser_pkey'),
        sa.UniqueConstraint('token_hash', name='botuser_token_hash_key'),
    )
    op.create_index('ix_botuser_owner_id', 'botuser', ['owner_id'])
    op.create_table(
        'botuserproject',
        sa.Column('bot_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['bot_user_id'], ['botuser.id'], name='botuserproject_bot_user_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], name='botuserproject_project_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('bot_user_id', 'project_id', name='botuserproject_pkey'),
    )


def downgrade():
    op.drop_table('botuserproject')
    op.drop_index('ix_botuser_owner_id', table_name='botuser')
    op.drop_table('botuser')

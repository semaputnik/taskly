"""Add attachments

Revision ID: 90f55891a218
Revises: d1f6d21ccfb0
Create Date: 2026-09-13 00:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '90f55891a218'
down_revision = 'd1f6d21ccfb0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'attachment',
        sa.Column('filename', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('content_type', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('size', sa.BigInteger(), nullable=False),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], name='attachment_task_id_fkey', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name='attachment_owner_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='attachment_pkey'),
    )
    op.create_index(op.f('ix_attachment_task_id'), 'attachment', ['task_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_attachment_task_id'), table_name='attachment')
    op.drop_table('attachment')

"""Sign in with passkeys

Passkeys replace passwords (ADR-0007): the password column goes, and the
tables for passkeys, ceremony challenges and recovery codes come in, with a
session version on each user so every session can be ended at once.

Revision ID: a9d3f7c2e815
Revises: f4b2a9e17c30
Create Date: 2026-10-05 12:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a9d3f7c2e815'
down_revision = 'f4b2a9e17c30'
branch_labels = None
depends_on = None

challenge_kind = postgresql.ENUM(
    'registration',
    'sign_in',
    'confirmation',
    'new_passkey',
    'recovery',
    name='challengekind',
)


def upgrade():
    op.add_column(
        'user',
        sa.Column('session_version', sa.Integer(), nullable=False, server_default='0'),
    )
    op.alter_column('user', 'session_version', server_default=None)
    op.drop_column('user', 'hashed_password')

    op.create_table(
        'passkey',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('credential_id', sa.LargeBinary(), nullable=False),
        sa.Column('public_key', sa.LargeBinary(), nullable=False),
        sa.Column('sign_count', sa.Integer(), nullable=False),
        sa.Column('transports', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='passkey_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='passkey_pkey'),
    )
    op.create_index('ix_passkey_user_id', 'passkey', ['user_id'])
    op.create_index('ix_passkey_credential_id', 'passkey', ['credential_id'], unique=True)

    op.create_table(
        'webauthn_challenge',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kind', challenge_kind, nullable=False),
        sa.Column('challenge', sa.LargeBinary(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('user_handle', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='webauthn_challenge_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='webauthn_challenge_pkey'),
    )
    op.create_index(
        'ix_webauthn_challenge_challenge', 'webauthn_challenge', ['challenge'], unique=True
    )

    op.create_table(
        'recovery_code',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('digest', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='recovery_code_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', name='recovery_code_pkey'),
    )


def downgrade():
    op.drop_table('recovery_code')
    op.drop_index('ix_webauthn_challenge_challenge', table_name='webauthn_challenge')
    op.drop_table('webauthn_challenge')
    challenge_kind.drop(op.get_bind(), checkfirst=True)
    op.drop_index('ix_passkey_credential_id', table_name='passkey')
    op.drop_index('ix_passkey_user_id', table_name='passkey')
    op.drop_table('passkey')

    # Passwords cannot be brought back: every account comes back without one
    # and can no longer sign in until it is given one by hand.
    op.add_column(
        'user',
        sa.Column(
            'hashed_password',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default='',
        ),
    )
    op.alter_column('user', 'hashed_password', server_default=None)
    op.drop_column('user', 'session_version')

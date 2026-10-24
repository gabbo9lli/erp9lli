"""add_legacy_migration_sync_model

Revision ID: 7fdd120eb524
Revises: 838cf2eb5a1d
Create Date: 2026-10-25 00:15:32.086564

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7fdd120eb524'
down_revision = '838cf2eb5a1d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'legacy_migration_sync',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_file', sa.String(length=255), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('legacy_id', sa.String(length=100), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('anno', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_file', 'entity_type', 'legacy_id', name='uq_legacy_sync_source_entity_id')
    )
    op.create_index(op.f('ix_legacy_migration_sync_source_file'), 'legacy_migration_sync', ['source_file'], unique=False)
    op.create_index(op.f('ix_legacy_migration_sync_entity_type'), 'legacy_migration_sync', ['entity_type'], unique=False)
    op.create_index(op.f('ix_legacy_migration_sync_legacy_id'), 'legacy_migration_sync', ['legacy_id'], unique=False)
    op.create_index(op.f('ix_legacy_migration_sync_target_id'), 'legacy_migration_sync', ['target_id'], unique=False)
    op.create_index(op.f('ix_legacy_migration_sync_anno'), 'legacy_migration_sync', ['anno'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_legacy_migration_sync_anno'), table_name='legacy_migration_sync')
    op.drop_index(op.f('ix_legacy_migration_sync_target_id'), table_name='legacy_migration_sync')
    op.drop_index(op.f('ix_legacy_migration_sync_legacy_id'), table_name='legacy_migration_sync')
    op.drop_index(op.f('ix_legacy_migration_sync_entity_type'), table_name='legacy_migration_sync')
    op.drop_index(op.f('ix_legacy_migration_sync_source_file'), table_name='legacy_migration_sync')
    op.drop_table('legacy_migration_sync')

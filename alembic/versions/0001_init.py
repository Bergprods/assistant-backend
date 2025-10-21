from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(length=128), nullable=False),
        sa.Column('user_id', sa.String(length=128)),
        sa.Column('tenant_id', sa.String(length=128)),
        sa.Column('language', sa.String(length=32)),
        sa.Column('terminated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_utc', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('session_id'),
    )
    op.create_index('ix_sessions_session_id', 'sessions', ['session_id'])

    op.create_table(
        'router_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id_fk', sa.Integer(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_message_id', sa.String(length=128)),
        sa.Column('schema_version', sa.String(length=32)),
        sa.Column('original_message', sa.Text()),
        sa.Column('language', sa.String(length=32)),
        sa.Column('raw', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Index('ix_router_messages_session', 'session_id_fk'),
        sa.Index('ix_router_messages_created', 'created_at'),
    )

    op.create_table(
        'intents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id_fk', sa.Integer(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('intent_key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=64)),
        sa.Column('sequence', sa.Integer()),
        sa.Column('agent_schema_version', sa.String(length=64)),
        sa.Column('confidence', sa.Float()),
        sa.Column('slots', sa.JSON()),
        sa.Column('candidates', sa.JSON()),
        sa.Column('agent_capabilities', sa.JSON()),
        sa.Index('ix_intents_session', 'session_id_fk'),
        sa.Index('ix_intents_intent_key', 'intent_key'),
    )

    op.create_table(
        'items',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('intent_id_fk', sa.Integer(), sa.ForeignKey('intents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_correlation_id', sa.String(length=128)),
        sa.Column('dependency_ids', sa.JSON()),
        sa.Column('description', sa.Text()),
        sa.Column('type', sa.String(length=64)),
        sa.Column('subject', sa.String(length=64)),
        sa.Column('key', sa.String(length=256)),
        sa.Column('deterministic_key', sa.String(length=256)),
        sa.Column('confidence', sa.Float()),
        sa.Column('agent', sa.String(length=64)),
        sa.Column('attributes', sa.JSON()),
        sa.Column('payload', sa.JSON()),
        sa.Column('tags', sa.JSON()),
        sa.Column('language', sa.String(length=32)),
        sa.Column('pii_flags', sa.JSON()),
        sa.Column('redaction', sa.String(length=32)),
        sa.Column('is_actionable', sa.Boolean()),
        sa.Column('execution_status', sa.String(length=32)),
        sa.Index('ix_items_intent', 'intent_id_fk'),
        sa.Index('ix_items_key', 'key'),
        sa.Index('ix_items_deterministic_key', 'deterministic_key'),
    )

    op.create_table(
        'entities',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('item_id_fk', sa.Integer(), sa.ForeignKey('items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(length=64)),
        sa.Column('text', sa.Text()),
        sa.Column('value', sa.Text()),
        sa.Column('aliases', sa.JSON()),
        sa.Index('ix_entities_item', 'item_id_fk'),
    )

    op.create_table(
        'consents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id_fk', sa.Integer(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scope', sa.String(length=128), nullable=False),
        sa.Column('granted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Index('ix_consents_session', 'session_id_fk'),
    )

    op.create_table(
        'telemetry',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id_fk', sa.Integer(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('generator', sa.String(length=128)),
        sa.Column('model', sa.JSON()),
        sa.Column('prompt_version', sa.String(length=128)),
        sa.Column('latency_ms', sa.Integer()),
        sa.Column('confidence_policy', sa.JSON()),
        sa.Column('key_strategy', sa.JSON()),
        sa.Index('ix_telemetry_session', 'session_id_fk'),
    )

    op.create_table(
        'errors',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id_fk', sa.Integer(), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('message', sa.Text()),
        sa.Column('payload', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Index('ix_errors_session', 'session_id_fk'),
        sa.Index('ix_errors_created', 'created_at'),
    )


def downgrade() -> None:
    op.drop_table('errors')
    op.drop_table('telemetry')
    op.drop_table('consents')
    op.drop_table('entities')
    op.drop_table('items')
    op.drop_table('intents')
    op.drop_table('router_messages')
    op.drop_table('sessions')

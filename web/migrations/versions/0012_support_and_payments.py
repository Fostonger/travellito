"""Add support system and payment tracking tables

Revision ID: 0012
Revises: 0011
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    # Create support_messages table
    op.create_table('support_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('message_type', sa.String(length=20), nullable=False, comment='Type: issue, question, payment_request'),
        sa.Column('message', sa.String(length=2000), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False, comment='Status: pending, in_progress, resolved'),
        sa.Column('assigned_admin_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_admin_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_support_messages_user_id'), 'support_messages', ['user_id'], unique=False)
    
    # Create support_responses table
    op.create_table('support_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('support_message_id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('response', sa.String(length=2000), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['support_message_id'], ['support_messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create landlord_payment_requests table
    op.create_table('landlord_payment_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('landlord_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('phone_number', sa.String(length=32), nullable=False),
        sa.Column('bank_name', sa.String(length=120), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False, comment='Status: pending, processing, completed, rejected'),
        sa.Column('requested_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processed_by_id', sa.Integer(), nullable=True),
        sa.Column('unique_users_count', sa.Integer(), nullable=False, comment='Number of unique users at time of request'),
        sa.ForeignKeyConstraint(['landlord_id'], ['landlords.id'], ),
        sa.ForeignKeyConstraint(['processed_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_landlord_payment_requests_landlord_id'), 'landlord_payment_requests', ['landlord_id'], unique=False)
    
    # Create landlord_payment_history table
    op.create_table('landlord_payment_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('landlord_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('paid_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('paid_by_id', sa.Integer(), nullable=False),
        sa.Column('payment_request_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['landlord_id'], ['landlords.id'], ),
        sa.ForeignKeyConstraint(['paid_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['payment_request_id'], ['landlord_payment_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_landlord_payment_history_landlord_id'), 'landlord_payment_history', ['landlord_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_landlord_payment_history_landlord_id'), table_name='landlord_payment_history')
    op.drop_table('landlord_payment_history')
    op.drop_index(op.f('ix_landlord_payment_requests_landlord_id'), table_name='landlord_payment_requests')
    op.drop_table('landlord_payment_requests')
    op.drop_table('support_responses')
    op.drop_index(op.f('ix_support_messages_user_id'), table_name='support_messages')
    op.drop_table('support_messages') 
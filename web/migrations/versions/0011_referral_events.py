"""Add referral_events table for tracking referral changes

Revision ID: 0011_referral_events
Revises: 0010_remove_category_id
Create Date: 2023-08-01 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011_referral_events'
down_revision = '0010_remove_category_id'
branch_labels = None
depends_on = None


def upgrade():
    # Create referral_events table
    op.create_table(
        'referral_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('old_referral', sa.Integer(), nullable=True),
        sa.Column('new_referral', sa.Integer(), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['old_referral'], ['apartments.id'], ),
        sa.ForeignKeyConstraint(['new_referral'], ['apartments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for faster lookups by user_id
    op.create_index('ix_referral_events_user_id', 'referral_events', ['user_id'], unique=False)


def downgrade():
    # Drop referral_events table
    op.drop_index('ix_referral_events_user_id', table_name='referral_events')
    op.drop_table('referral_events') 
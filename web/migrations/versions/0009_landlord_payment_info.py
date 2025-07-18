"""Add payment info to landlord model

Revision ID: 0009_landlord_payment_info
Revises: 0008_tour_multiple_categories
Create Date: 2023-06-20 13:15:31.837373

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009_landlord_payment_info'
down_revision = '0008_tour_multiple_categories'
branch_labels = None
depends_on = None


def upgrade():
    # Add payment info columns to landlords table
    op.add_column('landlords', sa.Column('phone_number', sa.String(32), nullable=True))
    op.add_column('landlords', sa.Column('bank_name', sa.String(120), nullable=True))


def downgrade():
    # Remove payment info columns from landlords table
    op.drop_column('landlords', 'phone_number')
    op.drop_column('landlords', 'bank_name') 
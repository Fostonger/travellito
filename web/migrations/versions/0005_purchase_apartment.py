"""Add apartment_id to purchases table

Revision ID: 0005_purchase_apartment
Revises: 0004_remove_tour_price
Create Date: 2023-09-15 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_purchase_apartment'
down_revision = '0004_remove_tour_price'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add apartment_id column to purchases table with foreign key to apartments
    op.add_column('purchases', sa.Column('apartment_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_purchase_apartment', 
        'purchases', 'apartments', 
        ['apartment_id'], ['id']
    )


def downgrade() -> None:
    # Drop foreign key constraint first
    op.drop_constraint('fk_purchase_apartment', 'purchases', type_='foreignkey')
    # Then drop the column
    op.drop_column('purchases', 'apartment_id') 
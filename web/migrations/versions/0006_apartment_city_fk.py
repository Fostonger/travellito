"""Apartment city foreign key

Revision ID: 0006_apartment_city_fk
Revises: 0005_purchase_apartment
Create Date: 2023-11-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_apartment_city_fk'
down_revision = '0005_purchase_apartment'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create temporary column to store city_id
    op.add_column('apartments', sa.Column('city_id', sa.Integer(), nullable=True))
    
    # Create cities from existing apartment city names
    op.execute("""
    INSERT INTO cities (name)
    SELECT DISTINCT city FROM apartments WHERE city IS NOT NULL AND city != ''
    ON CONFLICT (name) DO NOTHING
    """)
    
    # Update city_id in apartments table
    op.execute("""
    UPDATE apartments
    SET city_id = (SELECT id FROM cities WHERE cities.name = apartments.city)
    WHERE city IS NOT NULL AND city != ''
    """)
    
    # Make city_id not nullable
    op.alter_column('apartments', 'city_id', nullable=False)
    
    # Drop old city column
    op.drop_column('apartments', 'city')


def downgrade() -> None:
    # Add city column back
    op.add_column('apartments', sa.Column('city', sa.String(64), nullable=True))
    
    # Populate city column from city_id
    op.execute("""
    UPDATE apartments
    SET city = (SELECT name FROM cities WHERE cities.id = apartments.city_id)
    """)
    
    # Drop city_id column
    op.drop_column('apartments', 'city_id') 
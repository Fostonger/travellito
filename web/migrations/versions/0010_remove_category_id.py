"""Remove redundant category_id from Tour model

Revision ID: 0010_remove_category_id
Revises: 0009_landlord_payment_info
Create Date: 2023-05-15 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '0010_remove_category_id'
down_revision: Union[str, None] = '0009_landlord_payment_info'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Use direct SQL to get tours with non-null category_id
    conn = op.get_bind()
    
    # Step 1: Get all tours with non-null category_id
    result = conn.execute(
        text("SELECT id, category_id FROM tours WHERE category_id IS NOT NULL")
    )
    tours_with_category = result.fetchall()
    
    print(f"Found {len(tours_with_category)} tours with a non-null category_id")
    
    # Step 2: For each tour, ensure the category is in the many-to-many relationship
    for tour_id, category_id in tours_with_category:
        # Check if association already exists
        assoc_exists = conn.execute(
            text("SELECT 1 FROM tour_category_associations WHERE tour_id = :tour_id AND category_id = :category_id"),
            {"tour_id": tour_id, "category_id": category_id}
        ).fetchone()
        
        if not assoc_exists:
            print(f"Adding category {category_id} to tour {tour_id}")
            # Create new association
            conn.execute(
                text("INSERT INTO tour_category_associations (tour_id, category_id) VALUES (:tour_id, :category_id)"),
                {"tour_id": tour_id, "category_id": category_id}
            )
    
    # Step 3: Drop the category_id column
    op.drop_column('tours', 'category_id')


def downgrade() -> None:
    # Add the category_id column back
    op.add_column('tours', 
        sa.Column('category_id', sa.Integer, sa.ForeignKey("tour_categories.id"), nullable=True)
    )
    
    # Use direct SQL to set category_id to the first category from associations
    conn = op.get_bind()
    
    # Get all tour_id with associations
    result = conn.execute(
        text("SELECT DISTINCT tour_id FROM tour_category_associations")
    )
    tour_ids = [row[0] for row in result.fetchall()]
    
    # For each tour, get the first category_id and update the tour
    for tour_id in tour_ids:
        first_category = conn.execute(
            text("SELECT category_id FROM tour_category_associations WHERE tour_id = :tour_id LIMIT 1"),
            {"tour_id": tour_id}
        ).fetchone()
        
        if first_category:
            conn.execute(
                text("UPDATE tours SET category_id = :category_id WHERE id = :tour_id"),
                {"tour_id": tour_id, "category_id": first_category[0]}
            ) 
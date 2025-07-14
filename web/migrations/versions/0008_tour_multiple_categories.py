"""Add support for multiple categories per tour

Revision ID: 0008_tour_multiple_categories
Revises: 0007_tour_address
Create Date: 2023-11-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '0008_tour_multiple_categories'
down_revision = '0007_tour_address'
branch_labels = None
depends_on = None


def upgrade():
    # Check if table already exists
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'tour_category_associations' not in tables:
        # Create the association table
        op.create_table(
            'tour_category_associations',
            sa.Column('tour_id', sa.Integer(), nullable=False),
            sa.Column('category_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['tour_id'], ['tours.id'], ),
            sa.ForeignKeyConstraint(['category_id'], ['tour_categories.id'], ),
            sa.PrimaryKeyConstraint('tour_id', 'category_id')
        )
        
        # Migrate existing category relationships to the new association table
        op.execute(
            """
            INSERT INTO tour_category_associations (tour_id, category_id)
            SELECT id, category_id FROM tours
            WHERE category_id IS NOT NULL
            """
        )


def downgrade():
    # Drop the association table if it exists
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    if 'tour_category_associations' in tables:
        op.drop_table('tour_category_associations') 
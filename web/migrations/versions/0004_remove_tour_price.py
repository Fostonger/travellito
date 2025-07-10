"""Remove price field from Tour model

Revision ID: 0004_remove_tour_price
Revises: 0003_repetition_types
Create Date: 2023-11-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import select, Column, Integer, String, ForeignKey, Numeric


# revision identifiers, used by Alembic.
revision = '0004_remove_tour_price'
down_revision = '0003_repetition_types'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade operations:
    1. Ensure ticket_class with id=0 exists
    2. For each tour, create a ticket category with id=0 if not exists
    3. Remove price column from tours table
    """
    # Create a connection
    connection = op.get_bind()
    session = Session(bind=connection)
    
    # 1. Ensure ticket_class with id=0 exists
    ticket_class_table = sa.Table(
        'ticket_classes',
        sa.MetaData(),
        Column('id', Integer, primary_key=True),
        Column('code', String),
        Column('human_name', String)
    )
    
    # Check if ticket_class with id=0 exists
    result = connection.execute(select(ticket_class_table).where(ticket_class_table.c.id == 0))
    default_class = result.fetchone()
    
    if not default_class:
        # Insert default ticket class
        connection.execute(
            ticket_class_table.insert().values(
                id=0,
                code='standard',
                human_name='Стандартный'
            )
        )
    
    # 2. For each tour, create a ticket category with id=0 if not exists
    tour_table = sa.Table(
        'tours',
        sa.MetaData(),
        Column('id', Integer, primary_key=True),
        Column('price', Numeric)
    )
    
    ticket_category_table = sa.Table(
        'ticket_categories',
        sa.MetaData(),
        Column('id', Integer, primary_key=True),
        Column('tour_id', Integer, ForeignKey('tours.id')),
        Column('ticket_class_id', Integer, ForeignKey('ticket_classes.id')),
        Column('name', String),
        Column('price', Numeric)
    )
    
    # Get all tours
    tours = connection.execute(select(tour_table))
    
    for tour in tours:
        # Check if ticket category with class_id=0 exists for this tour
        result = connection.execute(
            select(ticket_category_table).where(
                (ticket_category_table.c.tour_id == tour.id) &
                (ticket_category_table.c.ticket_class_id == 0)
            )
        )
        category = result.fetchone()
        
        if not category:
            # Create default ticket category
            connection.execute(
                ticket_category_table.insert().values(
                    tour_id=tour.id,
                    ticket_class_id=0,
                    name='Стандартный',
                    price=tour.price
                )
            )
    
    # 3. Remove price column from tours table
    op.drop_column('tours', 'price')


def downgrade() -> None:
    """
    Downgrade operations:
    1. Add price column back to tours table
    2. For each tour, set price to the value of the ticket category with id=0
    """
    # Add price column back to tours table
    op.add_column('tours', sa.Column('price', sa.Numeric(10, 2), nullable=True))
    
    # Create a connection
    connection = op.get_bind()
    
    # Get all tours and their default ticket categories
    tour_table = sa.Table(
        'tours',
        sa.MetaData(),
        Column('id', Integer, primary_key=True),
        Column('price', Numeric)
    )
    
    ticket_category_table = sa.Table(
        'ticket_categories',
        sa.MetaData(),
        Column('id', Integer, primary_key=True),
        Column('tour_id', Integer, ForeignKey('tours.id')),
        Column('ticket_class_id', Integer, ForeignKey('ticket_classes.id')),
        Column('name', String),
        Column('price', Numeric)
    )
    
    # Get all tours
    tours = connection.execute(select(tour_table.c.id))
    
    for tour in tours:
        # Get default ticket category
        result = connection.execute(
            select(ticket_category_table.c.price).where(
                (ticket_category_table.c.tour_id == tour.id) &
                (ticket_category_table.c.ticket_class_id == 0)
            )
        )
        category = result.fetchone()
        
        if category:
            # Update tour price
            connection.execute(
                tour_table.update()
                .where(tour_table.c.id == tour.id)
                .values(price=category.price)
            )
    
    # Make price column not nullable
    op.alter_column('tours', 'price', nullable=False) 
"""Add repetition types table

Revision ID: 0003_repetition_types
Revises: 0002_tour_recurrence
Create Date: 2023-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '0003_repetition_types'
down_revision = '0002_tour_recurrence'
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Check if a table exists in the database."""
    conn = op.get_bind()
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table."""
    conn = op.get_bind()
    query = f"""
    SELECT constraint_name FROM information_schema.table_constraints
    WHERE table_name = '{table_name}' AND constraint_name = '{constraint_name}'
    """
    result = conn.execute(sa.text(query))
    return result.scalar() is not None


def upgrade() -> None:
    # Create repetition_types table if it doesn't exist
    if not table_exists('repetition_types'):
        op.create_table(
            'repetition_types',
            sa.Column('code', sa.String(16), primary_key=True),
            sa.Column('name', sa.String(64), nullable=False),
            sa.Column('description', sa.String(255), nullable=True),
        )
        
        # Insert initial data
        op.execute(
            """
            INSERT INTO repetition_types (code, name, description) VALUES
            ('none', 'Без повторения', 'Однократная экскурсия без расписания'),
            ('daily', 'Ежедневно', 'Экскурсия проводится каждый день в одно и то же время'),
            ('weekly', 'Еженедельно', 'Экскурсия проводится в определенные дни недели')
            """
        )
    
    # Add the foreign key constraint if it doesn't exist
    if not constraint_exists('tours', 'fk_tours_repeat_type'):
        op.create_foreign_key(
            'fk_tours_repeat_type', 
            'tours', 'repetition_types',
            ['repeat_type'], ['code']
        )


def downgrade() -> None:
    # Remove foreign key constraint if it exists
    if constraint_exists('tours', 'fk_tours_repeat_type'):
        op.drop_constraint('fk_tours_repeat_type', 'tours', type_='foreignkey')
    
    # Drop repetition_types table if it exists
    if table_exists('repetition_types'):
        op.drop_table('repetition_types') 
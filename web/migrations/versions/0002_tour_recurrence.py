from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '0002_tour_recurrence'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def upgrade() -> None:
    # Add repeat_type column if it doesn't exist
    if not column_exists('tours', 'repeat_type'):
        op.add_column('tours', sa.Column('repeat_type', sa.String(length=16), nullable=False, server_default='none'))
        # remove server_default to keep model clean
        op.alter_column('tours', 'repeat_type', server_default=None)
    
    # Add repeat_weekdays column if it doesn't exist
    if not column_exists('tours', 'repeat_weekdays'):
        op.add_column('tours', sa.Column('repeat_weekdays', sa.JSON(), nullable=True))
    
    # Add repeat_time column if it doesn't exist
    if not column_exists('tours', 'repeat_time'):
        op.add_column('tours', sa.Column('repeat_time', sa.Time(), nullable=True))


def downgrade() -> None:
    # Drop columns if they exist
    if column_exists('tours', 'repeat_time'):
        op.drop_column('tours', 'repeat_time')
    
    if column_exists('tours', 'repeat_weekdays'):
        op.drop_column('tours', 'repeat_weekdays')
    
    if column_exists('tours', 'repeat_type'):
        op.drop_column('tours', 'repeat_type') 
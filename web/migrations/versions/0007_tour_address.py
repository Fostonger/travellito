"""Add address field to tours table

Revision ID: 0007_tour_address
Revises: 0006_apartment_city_fk
Create Date: 2023-08-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007_tour_address'
down_revision: Union[str, None] = '0006_apartment_city_fk'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add address column to tours table
    op.add_column('tours', sa.Column('address', sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove address column from tours table
    op.drop_column('tours', 'address') 
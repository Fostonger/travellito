from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_tour_recurrence'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('tours', sa.Column('repeat_type', sa.String(length=16), nullable=False, server_default='none'))
    op.add_column('tours', sa.Column('repeat_weekdays', sa.JSON(), nullable=True))
    op.add_column('tours', sa.Column('repeat_time', sa.Time(), nullable=True))
    # remove server_default to keep model clean
    op.alter_column('tours', 'repeat_type', server_default=None)


def downgrade() -> None:
    op.drop_column('tours', 'repeat_time')
    op.drop_column('tours', 'repeat_weekdays')
    op.drop_column('tours', 'repeat_type') 
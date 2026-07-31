"""add symbol image_ref

Revision ID: 42f920ece233
Revises: 9b1f2a6c7d3e
Create Date: 2026-07-23 19:05:47.045246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42f920ece233'
down_revision: Union[str, Sequence[str], None] = '9b1f2a6c7d3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('symbols', sa.Column('image_ref', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('symbols', 'image_ref')

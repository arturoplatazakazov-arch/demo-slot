"""add game catalog fields

Revision ID: 294e676b2845
Revises: 42f920ece233
Create Date: 2026-07-23 19:06:06.658784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '294e676b2845'
down_revision: Union[str, Sequence[str], None] = '42f920ece233'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('games', sa.Column('catalog_badge', sa.String(length=64), nullable=True))
    op.add_column('games', sa.Column('catalog_description', sa.String(length=512), nullable=True))
    op.add_column('games', sa.Column('catalog_cover_path', sa.String(length=255), nullable=True))
    op.add_column('games', sa.Column('catalog_play_url', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('games', 'catalog_play_url')
    op.drop_column('games', 'catalog_cover_path')
    op.drop_column('games', 'catalog_description')
    op.drop_column('games', 'catalog_badge')

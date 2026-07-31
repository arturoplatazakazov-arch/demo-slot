"""add symbol is_bomb

Revision ID: 452819e8829c
Revises: e5e23f02939c
Create Date: 2026-07-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '452819e8829c'
down_revision: Union[str, Sequence[str], None] = 'e5e23f02939c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'symbols',
        sa.Column('is_bomb', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Dropping the server default is a Postgres-only cleanup; SQLite (embed/prod
    # profile) can't ALTER COLUMN, and keeping the default is harmless for the app.
    if op.get_bind().dialect.name != 'sqlite':
        op.alter_column('symbols', 'is_bomb', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('symbols', 'is_bomb')

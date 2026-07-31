"""move catalog covers into per-game img folders

The image/animation asset tree was systematised to mirror the sound reorg:
every game's assets now live under front/img/<slug>/ and the separate
front/game-logo/ folder was removed. Three games' catalog hero covers moved
with it (amys-fruit-farm, east-discovery, party-of-goods) and their seed
CATALOG_COVER_PATH constants were updated — but backfill_catalog_fields()
(app/seed/__init__.py) only writes when catalog_badge is None, so already
seeded Game rows keep the stale game-logo/ paths and games.html 404s on them.
This data migration repoints those rows. Path-keyed and idempotent, so it's
safe on any DB whether it still holds the old paths or was seeded fresh with
the new ones.

Revision ID: b7c1a9d4e2f0
Revises: 294e676b2845
Create Date: 2026-07-27 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c1a9d4e2f0'
down_revision: Union[str, Sequence[str], None] = '294e676b2845'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# old game-logo/ path -> new img/<slug>/ path
COVER_MOVES = [
    ("game-logo/logo_AmysFruitFarm-hero.jpg", "img/amys-fruit-farm/img/logo_AmysFruitFarm-hero.jpg"),
    ("game-logo/logo_SouthDiscovery-hero.jpg", "img/east-discovery/img/logo_SouthDiscovery-hero.jpg"),
    ("game-logo/logo_Partyofgoods-hero.jpg", "img/party-of-goods/img/logo_Partyofgoods-hero.jpg"),
]


def _repoint(pairs: Sequence[tuple[str, str]]) -> None:
    conn = op.get_bind()
    stmt = sa.text(
        "UPDATE games SET catalog_cover_path = :new WHERE catalog_cover_path = :old"
    )
    for old, new in pairs:
        conn.execute(stmt, {"new": new, "old": old})


def upgrade() -> None:
    _repoint(COVER_MOVES)


def downgrade() -> None:
    _repoint([(new, old) for old, new in COVER_MOVES])

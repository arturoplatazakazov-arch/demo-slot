"""Общий каркас всех сид-модулей: get_or_seed + реконсиляция ACTIVE-конфига
по сид-файлу. До выноса сюда каждый из 17 сидов носил собственную копию
одного и того же (7 файлов — побайтово идентичную), различаясь только
данными и парой флагов; общая логика правилась ×17.

Реконсиляция — «строгий» вариант, исторически появившийся в сидах игр из
конструктора (dirty_money_mafia и далее): символы и пейлайны приводятся к
точному соответствию сиду (insert + update + delete), ставки/размеры сетки
синхронизируются, feature_configs обновляются и досоздаются (удалять
нечего — max один enabled на feature_type, uq_feature_type_per_config).
Для рукописных игр это надмножество их прежних «update-only» вариантов:
их строки созданы этим же сидом, так что delete-ветка не срабатывает,
а зануление/удаление снятых с сида символов — ровно то, ради чего
реконсиляция вообще существует (сид — источник истины demo-игр; реальный
деплой публикует версии через админ-API, не через это).

SpinRecord хранит сетку кодами в JSON (нет FK на Symbol), удаление
символа истории спинов не ломает.
"""

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import FeatureConfig, Game, GameConfig, Payline, Symbol
from app.models.enums import GameConfigStatus, SymbolType

BuildFn = Callable[[], tuple[Game, GameConfig]]


def _symbol_fields(f: Symbol) -> dict:
    """Мутабельные поля Symbol из транзиентного сид-объекта. Колонковые
    default'ы (is_bomb=False, tier="low", …) применяются только при flush —
    у несохранённого объекта такие атрибуты ещё None, и копировать их в
    существующую NOT NULL-строку как есть нельзя; коалесцируем к тем же
    значениям, которые выставил бы flush."""
    return {
        "name": f.name,
        "symbol_type": f.symbol_type if f.symbol_type is not None else SymbolType.REGULAR.value,
        "wild_subtype": f.wild_subtype,
        "reel_weights": f.reel_weights,
        "paytable": f.paytable if f.paytable is not None else {},
        "max_per_reel": f.max_per_reel,
        "multiplier_value": f.multiplier_value,
        "is_bomb": bool(f.is_bomb),
        "tier": f.tier if f.tier is not None else "low",
        "display_order": f.display_order if f.display_order is not None else 0,
    }


@dataclass(frozen=True)
class CatalogMeta:
    """Каталожные поля Game (front/games.html) + режим их применения.

    force=False — write-once backfill: пишем только когда badge ещё None
    (иначе затёрли бы правки, сделанные через админку/билдер после сида).
    force=True — сид владеет каталогом: расхождение затирается на каждом
    старте (нужно играм, чей Game создал конструктор с черновыми полями —
    например play_url, указывающий на generic-плеер вместо своей страницы).
    display_name задаётся только force-играми, которым конструктор оставил
    черновое имя (Game.name тогда тоже принадлежит сиду)."""

    badge: str
    description: str
    cover_path: str
    play_url: str
    force: bool = False
    display_name: str | None = None


def _apply_catalog(game: Game, catalog: CatalogMeta | None) -> None:
    if catalog is None:
        return
    if catalog.force:
        if catalog.display_name is not None:
            game.name = catalog.display_name
        game.catalog_badge = catalog.badge
        game.catalog_description = catalog.description
        game.catalog_cover_path = catalog.cover_path
        game.catalog_play_url = catalog.play_url
    elif game.catalog_badge is None:
        game.catalog_badge = catalog.badge
        game.catalog_description = catalog.description
        game.catalog_cover_path = catalog.cover_path
        game.catalog_play_url = catalog.play_url


async def sync_config_from_seed(db: AsyncSession, config: GameConfig, fresh: GameConfig) -> None:
    """Привести существующий ACTIVE-конфиг к текущему сиду (см. док модуля).
    `fresh` — свежепостроенный build_game_config()[1], никогда не попадает в
    сессию БД."""
    fresh_symbols = {s.code: s for s in fresh.symbols}
    for symbol in list(config.symbols):
        f = fresh_symbols.pop(symbol.code, None)
        if f is None:
            await db.execute(delete(Symbol).where(Symbol.id == symbol.id))
            config.symbols.remove(symbol)
            continue
        for field, value in _symbol_fields(f).items():
            setattr(symbol, field, value)
    for f in fresh_symbols.values():
        db.add(Symbol(game_config=config, code=f.code, **_symbol_fields(f)))

    fresh_paylines = {p.index: p for p in fresh.paylines}
    for payline in list(config.paylines):
        fp = fresh_paylines.pop(payline.index, None)
        if fp is None:
            await db.execute(delete(Payline).where(Payline.id == payline.id))
            config.paylines.remove(payline)
            continue
        payline.positions = fp.positions
    for fp in fresh_paylines.values():
        db.add(Payline(game_config=config, index=fp.index, positions=fp.positions))

    # Лестница ставок обязана оставаться кратной числу линий
    # (loaders.validate_bet_amount) — синхронизируется вместе с пейлайнами.
    config.num_reels = fresh.num_reels
    config.num_rows = fresh.num_rows
    config.min_bet = fresh.min_bet
    config.max_bet = fresh.max_bet
    config.bet_step = fresh.bet_step
    config.bet_steps = fresh.bet_steps

    fresh_features = {fc.feature_type: fc for fc in fresh.feature_configs}
    for feature_config in config.feature_configs:
        ff = fresh_features.pop(feature_config.feature_type, None)
        if ff is None:
            continue
        feature_config.enabled = ff.enabled
        feature_config.params = ff.params
        feature_config.display_order = ff.display_order
    for ff in fresh_features.values():
        # game_config=config сам по себе не каскадирует новую строку в сессию
        # (config загружен через selectinload, а не сконструирован) —
        # db.add() обязателен, иначе строка молча не сохранится.
        db.add(
            FeatureConfig(
                game_config=config, feature_type=ff.feature_type,
                enabled=ff.enabled, params=ff.params, display_order=ff.display_order,
            )
        )


async def get_or_seed(
    db: AsyncSession,
    *,
    game_code: str,
    build_game_config: BuildFn,
    catalog: CatalogMeta | None = None,
) -> GameConfig:
    """Идемпотентно: вернуть ACTIVE-конфиг игры, создав Game + конфиг при
    первом вызове (dev/test-удобство — реальный деплой управляет конфигами
    через админ-API). На повторных вызовах реконсилирует конфиг и каталожные
    поля по сиду (см. sync_config_from_seed / CatalogMeta)."""
    existing = await db.execute(
        select(GameConfig)
        .join(Game)
        .where(Game.code == game_code, GameConfig.status == GameConfigStatus.ACTIVE.value)
        .options(
            selectinload(GameConfig.symbols),
            selectinload(GameConfig.paylines),
            selectinload(GameConfig.feature_configs),
            selectinload(GameConfig.game),
        )
    )
    config = existing.scalars().first()
    if config is not None:
        await sync_config_from_seed(db, config, build_game_config()[1])
        _apply_catalog(config.game, catalog)
        await db.commit()
        return config

    game, config = build_game_config()
    _apply_catalog(game, catalog)
    db.add(config)
    await db.commit()
    # expire_on_commit=False (app/core/db.py) держит собранные в
    # build_game_config коллекции в памяти — перезагрузка не нужна.
    return config

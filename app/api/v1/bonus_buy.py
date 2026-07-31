"""Bonus-buy purchase resolution and validation, shared by the line-pay and
avalanche feature-buy paths (spin_service.py / spin_avalanche.py). Check
order is part of the API contract the tests pin down: active-round 400 ->
unknown product 404 -> bet validation 400 -> unconfigured target 409 ->
insufficient balance 400."""

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException

from app.api.v1.loaders import find_feature_config, validate_bet_amount
from app.features import default_registry
from app.features.base import BonusFeature
from app.models.config import FeatureConfig, GameConfig
from app.services import free_spins_round


def resolve_bonus_buy_product(game_config: GameConfig, feature_id: str) -> dict | None:
    """A game_config can only have one enabled FeatureConfig row per
    feature_type (DB: uq_feature_type_per_config), so a game selling more
    than one bonus-buy product (East Discovery: free_spins_buy and
    hold_and_win_buy) lists them under the one bonus_buy row's
    params["products"] instead of one row each. Falls back to treating the
    whole params dict as a single implicit product when there's no
    "products" key (Amy's Fruit Farm's original flat shape:
    {"buy_id": ..., "cost_multiplier": ..., "target_feature_id": ...})."""
    bonus_buy_config = find_feature_config(game_config, "bonus_buy")
    if bonus_buy_config is None:
        return None
    products = bonus_buy_config.params.get("products")
    if products is not None:
        for product in products:
            if product.get("buy_id") == feature_id:
                return product
        return None
    if bonus_buy_config.params.get("buy_id") == feature_id:
        return bonus_buy_config.params
    return None


@dataclass
class FeatureBuyPlan:
    bet_amount: int
    cost: Decimal
    target_feature_id: str
    target_feature: BonusFeature
    target_config: FeatureConfig


def prepare_feature_buy(
    game_config: GameConfig,
    state: dict,
    feature_id: str,
    requested_bet_amount: int,
    num_paylines: int,
    balance_before: Decimal,
) -> FeatureBuyPlan:
    """Validate the purchase end to end and return everything the buy spin
    needs; raises HTTPException on any failed check (order documented in the
    module docstring)."""
    if free_spins_round.is_active(state):
        raise HTTPException(status_code=400, detail="a bonus round is already active")

    product = resolve_bonus_buy_product(game_config, feature_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown or disabled feature_id")

    validate_bet_amount(game_config, requested_bet_amount, num_paylines)

    target_feature_id = product.get("target_feature_id", "free_spins")
    target_feature = default_registry.get(target_feature_id)
    target_config = find_feature_config(game_config, target_feature_id)
    if target_feature is None or target_config is None:
        raise HTTPException(status_code=409, detail="bonus_buy target feature is not configured")

    cost = Decimal(str(product.get("cost_multiplier", 100))) * requested_bet_amount
    if balance_before < cost:
        raise HTTPException(status_code=400, detail="insufficient balance for this purchase")

    return FeatureBuyPlan(
        bet_amount=requested_bet_amount,
        cost=cost,
        target_feature_id=target_feature_id,
        target_feature=target_feature,
        target_config=target_config,
    )

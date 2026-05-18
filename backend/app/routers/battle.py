"""ダブルバトル API エンドポイント

素早さ計算、バトル状態管理、HP追跡、ダメージ計算、まもる管理を提供する。
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import (
    AdvanceTurnRequest,
    DamageCalcRequest,
    EVEstimateRequest,
    LogActionRequest,
    PokemonOnFieldSchema,
    ProtectRecordRequest,
    SetSelectionRequest,
    SpeedCalcRequest,
    SpeedCalcResponse,
    StartBattleRequest,
    StartMatchRequest,
    UpdateFieldRequest,
    UpdateHPRequest,
    WeatherCondition,
)
from app.services.battle_state import (
    PokemonOnField,
    Side,
    battle_state_manager,
)
from app.services.damage_calculator import (
    AttackerInfo,
    DamageCategory,
    DefenderInfo,
    MoveData,
    calculate_damage,
    estimate_defense_ev_from_damage,
    estimate_hp_ev,
)
from app.services.hp_tracker import hp_tracker
from app.services.protect_manager import protect_manager
from app.services.speed_calculator import calculate_speed_tiers
from app.services.turn_logger import ActionType, turn_logger

router = APIRouter(prefix="/api/battle", tags=["battle"])


# --- 素早さ計算 (Phase 1) ---


@router.post("/speed-tiers", response_model=SpeedCalcResponse)
def compute_speed_tiers(body: SpeedCalcRequest) -> SpeedCalcResponse:
    """場に出ている最大4体の素早さ順を計算する。

    追い風、トリックルーム、天候、特性、アイテム、ランク変化、状態異常を加味して
    リアルタイムに行動順を返す。
    """
    return calculate_speed_tiers(body)


# --- バトル状態管理 (Phase 3) ---


@router.post("/match/start")
def start_match(body: StartMatchRequest):
    """新しい試合を開始する。"""
    match = battle_state_manager.start_match(
        ally_team=body.ally_team,
        enemy_team=body.enemy_team,
    )
    hp_tracker.reset()
    protect_manager.reset()
    turn_logger.start_match()
    return match.to_dict()


@router.post("/match/selection")
def set_selection(body: SetSelectionRequest):
    """選出を記録する。"""
    battle_state_manager.set_selection(
        ally_leads=body.ally_leads,
        enemy_leads=body.enemy_leads,
    )
    return battle_state_manager.match.to_dict()


@router.post("/match/battle-start")
def start_battle(body: StartBattleRequest):
    """バトルフェーズを開始する。"""
    pokemon_list = []
    for p in body.pokemon_on_field:
        pokemon_list.append(
            PokemonOnField(
                slot=p.slot,
                name=p.name,
                species=p.species,
                ability=p.ability,
                item=p.item,
                base_speed=p.base_speed,
                current_hp=p.current_hp,
                max_hp=p.max_hp,
                hp_percent=p.hp_percent,
                side=Side(p.side),
                status=p.status,
            )
        )
    battle_state_manager.start_battle(pokemon_list)
    return battle_state_manager.match.to_dict()


@router.get("/match/state")
def get_match_state():
    """現在の試合状態を取得する。"""
    return battle_state_manager.match.to_dict()


@router.get("/match/speed-order")
def get_current_speed_order():
    """現在のフィールド上の4体の素早さ順を計算する。"""
    order = battle_state_manager.calculate_current_speed_order()
    return {
        "turn": battle_state_manager.match.turn,
        "trick_room": battle_state_manager.match.field_state.trick_room,
        "speed_order": order,
    }


@router.put("/match/field")
def update_field(body: UpdateFieldRequest):
    """フィールド条件を更新する。"""
    weather = None
    if body.weather is not None:
        try:
            weather = WeatherCondition(body.weather)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Invalid weather: {body.weather}"},
            )

    battle_state_manager.update_field_condition(
        weather=weather,
        tailwind_ally=body.tailwind_ally,
        tailwind_enemy=body.tailwind_enemy,
        trick_room=body.trick_room,
        terrain=body.terrain,
    )

    order = battle_state_manager.calculate_current_speed_order()
    return {
        "field_state": {
            "weather": battle_state_manager.match.field_state.weather.value,
            "tailwind_ally": battle_state_manager.match.field_state.tailwind_ally,
            "tailwind_enemy": battle_state_manager.match.field_state.tailwind_enemy,
            "trick_room": battle_state_manager.match.field_state.trick_room,
            "terrain": battle_state_manager.match.field_state.terrain,
        },
        "speed_order": order,
    }


@router.put("/match/pokemon")
def update_field_pokemon(body: list[PokemonOnFieldSchema]):
    """フィールド上のポケモンを更新する。"""
    pokemon_list = []
    for p in body:
        pokemon_list.append(
            PokemonOnField(
                slot=p.slot,
                name=p.name,
                species=p.species,
                ability=p.ability,
                item=p.item,
                base_speed=p.base_speed,
                current_hp=p.current_hp,
                max_hp=p.max_hp,
                hp_percent=p.hp_percent,
                side=Side(p.side),
                status=p.status,
            )
        )
    battle_state_manager.update_field_pokemon(pokemon_list)
    return battle_state_manager.match.to_dict()


@router.post("/match/advance-turn")
def advance_turn(body: AdvanceTurnRequest):
    """ターンを進める。"""
    record = battle_state_manager.advance_turn(actions=body.actions)
    return {
        "turn_record": record.to_dict(),
        "current_turn": battle_state_manager.match.turn,
        "speed_order": battle_state_manager.calculate_current_speed_order(),
    }


@router.post("/match/end")
def end_match(result: str = ""):
    """試合を終了する。"""
    match = battle_state_manager.end_match(result=result)
    return match.to_dict()


# --- HP追跡 ---


@router.put("/hp/update")
def update_hp(body: UpdateHPRequest):
    """HPを更新する。"""
    damage = battle_state_manager.update_pokemon_hp(
        slot=body.slot,
        current_hp=body.current_hp,
        max_hp=body.max_hp,
        hp_percent=body.hp_percent,
    )

    # HPトラッカーにも反映
    name = ""
    for p in battle_state_manager.match.pokemon_on_field:
        if p.slot == body.slot:
            name = p.name
            break

    hp_tracker.update_hp(
        slot=body.slot,
        name=name,
        current_hp=body.current_hp or 0,
        max_hp=body.max_hp or 0,
        hp_percent=body.hp_percent if body.hp_percent is not None else -1.0,
        source="api",
    )

    return {
        "damage_event": damage,
        "hp_state": hp_tracker.get_current_hp_state(),
    }


@router.get("/hp/state")
def get_hp_state():
    """現在のHP状態を取得する。"""
    return hp_tracker.get_current_hp_state()


@router.get("/hp/damage-history")
def get_damage_history():
    """ダメージ履歴を取得する。"""
    return hp_tracker.get_damage_summary()


# --- ダメージ計算 ---


@router.post("/damage/calc")
def calc_damage(body: DamageCalcRequest):
    """ダメージ計算を行う。"""
    category = DamageCategory(body.move_category)
    move = MoveData(
        name=body.move_name,
        power=body.move_power,
        category=category,
        is_spread=body.is_spread,
    )
    attacker = AttackerInfo(
        name=body.attacker_name,
        attack_stat=body.attacker_stat,
        ability=body.attacker_ability,
        item=body.attacker_item,
        has_stab=body.has_stab,
        type_effectiveness=body.type_effectiveness,
    )
    defender = DefenderInfo(
        name=body.defender_name,
        defense_stat=body.defender_stat,
        max_hp=body.defender_max_hp,
    )
    result = calculate_damage(move, attacker, defender)
    return result.to_dict()


@router.post("/damage/estimate-ev")
def estimate_ev(body: EVEstimateRequest):
    """ダメージ%から防御/特防EVを逆算する。"""
    category = DamageCategory(body.move_category)
    move = MoveData(
        name=body.move_name,
        power=body.move_power,
        category=category,
        is_spread=body.is_spread,
    )
    attacker = AttackerInfo(
        name="attacker",
        attack_stat=body.attacker_stat,
        has_stab=body.has_stab,
        type_effectiveness=body.type_effectiveness,
    )
    result = estimate_defense_ev_from_damage(
        species_base_def=body.species_base_stat,
        damage_percent=body.damage_percent,
        move=move,
        attacker=attacker,
        defender_max_hp=body.defender_max_hp,
    )
    return result.to_dict()


@router.post("/damage/estimate-hp-ev")
def estimate_hp_evs(species_base_hp: int, observed_max_hp: int):
    """HP実数値からHP EVを逆算する。"""
    result = estimate_hp_ev(species_base_hp, observed_max_hp)
    return result.to_dict()


# --- まもる管理 ---


@router.post("/protect/record")
def record_protect(body: ProtectRecordRequest):
    """まもる系技の使用を記録する。"""
    state = protect_manager.record_protect(
        pokemon_name=body.pokemon_name,
        move_name=body.move_name,
        turn=body.turn,
        success=body.success,
    )
    return state.to_dict()


@router.get("/protect/state")
def get_protect_state():
    """全ポケモンのまもる状態を取得する。"""
    return protect_manager.get_all_states()


@router.get("/protect/{pokemon_name}")
def get_pokemon_protect(pokemon_name: str):
    """特定ポケモンのまもる状態を取得する。"""
    state = protect_manager.get_state(pokemon_name)
    if state is None:
        return {"name": pokemon_name, "next_success_rate": 100.0, "total_uses": 0}
    return state


# --- ターンログ ---


@router.post("/log/action")
def log_action(body: LogActionRequest):
    """アクションを記録する。"""
    try:
        action_type = ActionType(body.action_type)
    except ValueError:
        valid = [a.value for a in ActionType]
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid action_type. Valid: {valid}"},
        )

    action = turn_logger.log_action(
        turn=body.turn,
        pokemon_slot=body.pokemon_slot,
        pokemon_name=body.pokemon_name,
        action_type=action_type,
        action_name=body.action_name,
        target_slot=body.target_slot,
        target_name=body.target_name,
    )

    # まもる系技の場合はProtectManagerにも記録
    if protect_manager.is_protect_move(body.action_name):
        protect_manager.record_protect(
            pokemon_name=body.pokemon_name,
            move_name=body.action_name,
            turn=body.turn,
        )
    else:
        protect_manager.record_non_protect_action(body.pokemon_name, body.turn)

    return action.to_dict()


@router.post("/log/commit-turn")
def commit_turn(turn: int):
    """ターンのログをコミットする。"""
    speed_order = battle_state_manager.calculate_current_speed_order()
    hp_snapshot = hp_tracker.get_current_hp_state()
    field_snapshot = {
        "weather": battle_state_manager.match.field_state.weather.value,
        "trick_room": battle_state_manager.match.field_state.trick_room,
        "tailwind_ally": battle_state_manager.match.field_state.tailwind_ally,
        "tailwind_enemy": battle_state_manager.match.field_state.tailwind_enemy,
    }

    log = turn_logger.commit_turn(
        turn=turn,
        speed_order=speed_order,
        hp_snapshot=hp_snapshot,
        field_snapshot=field_snapshot,
    )
    return log.to_dict()


@router.get("/log/all")
def get_all_logs():
    """全ターンのログを取得する。"""
    return turn_logger.get_all_logs()


@router.get("/log/turn/{turn}")
def get_turn_log(turn: int):
    """特定ターンのログを取得する。"""
    log = turn_logger.get_turn_log(turn)
    if log is None:
        return JSONResponse(status_code=404, content={"detail": f"Turn {turn} not found"})
    return log

"""ダブルバトル素早さ計算エンジン

S_effective = S_base × StatStageMultiplier × Modifier_Ability × Modifier_Item × Modifier_Field

フィールド補正:
  - 追い風(Tailwind): ×2.0
  - トリックルーム(Trick Room): 行動順を反転
  - 天候(Weather): すいすい/ようりょくそ/すなかき/ゆきかき → ×2.0

アイテム補正:
  - こだわりスカーフ(Choice Scarf): ×1.5
  - くろいてっきゅう(Iron Ball): ×0.5
  - ルームサービス(Room Service): -(効果は素早さランク低下で反映)
  - せんせいのツメ/イバンのみ等は優先度変更のため本計算では対象外

特性補正:
  - すいすい(Swift Swim): 雨時 ×2.0
  - ようりょくそ(Chlorophyll): 晴れ時 ×2.0
  - すなかき(Sand Rush): 砂嵐時 ×2.0
  - ゆきかき(Slush Rush): 雪時 ×2.0
  - はやあし(Quick Feet): まひ時、まひの速度低下を無効化
  - かるわざ(Unburden): アイテム消費後 ×2.0 (フラグで管理)
  - スロースタート(Slow Start): 5ターン以内 ×0.5

状態異常:
  - まひ(Paralysis): ×0.5 (はやあしの場合無効)
"""

from __future__ import annotations

import math

from app.schemas import (
    BattlePokemon,
    FieldCondition,
    SpeedCalcRequest,
    SpeedCalcResponse,
    SpeedTierEntry,
    WeatherCondition,
)

STAT_STAGE_MULTIPLIERS: dict[int, tuple[int, int]] = {
    -6: (2, 8),
    -5: (2, 7),
    -4: (2, 6),
    -3: (2, 5),
    -2: (2, 4),
    -1: (2, 3),
    0: (2, 2),
    1: (3, 2),
    2: (4, 2),
    3: (5, 2),
    4: (6, 2),
    5: (7, 2),
    6: (8, 2),
}

WEATHER_SPEED_ABILITIES: dict[str, WeatherCondition] = {
    "すいすい": WeatherCondition.RAIN,
    "Swift Swim": WeatherCondition.RAIN,
    "ようりょくそ": WeatherCondition.SUN,
    "Chlorophyll": WeatherCondition.SUN,
    "すなかき": WeatherCondition.SAND,
    "Sand Rush": WeatherCondition.SAND,
    "ゆきかき": WeatherCondition.SNOW,
    "Slush Rush": WeatherCondition.SNOW,
}

SPEED_HALVING_ITEMS: set[str] = {
    "くろいてっきゅう",
    "Iron Ball",
}

CHOICE_SCARF_NAMES: set[str] = {
    "こだわりスカーフ",
    "Choice Scarf",
}

QUICK_FEET_NAMES: set[str] = {
    "はやあし",
    "Quick Feet",
}

UNBURDEN_NAMES: set[str] = {
    "かるわざ",
    "Unburden",
}

SLOW_START_NAMES: set[str] = {
    "スロースタート",
    "Slow Start",
}


def _apply_stat_stage(base_speed: int, stage: int) -> int:
    numerator, denominator = STAT_STAGE_MULTIPLIERS[stage]
    return math.floor(base_speed * numerator / denominator)


def calculate_effective_speed(
    pokemon: BattlePokemon,
    field: FieldCondition,
) -> tuple[float, list[str]]:
    """1体のポケモンの実効素早さを計算する。

    Returns:
        (effective_speed, list of applied modifier descriptions)
    """
    modifiers_applied: list[str] = []
    speed = float(pokemon.base_speed)

    # 1. ランク補正
    stage = int(pokemon.speed_modifier)
    if stage != 0:
        speed = _apply_stat_stage(pokemon.base_speed, stage)
        modifiers_applied.append(f"ランク{stage:+d}")
    else:
        speed = float(pokemon.base_speed)

    # 2. まひ補正 (はやあしの場合は無効)
    if pokemon.is_paralyzed:
        if pokemon.ability in QUICK_FEET_NAMES:
            modifiers_applied.append("はやあし(まひ無効)")
        else:
            speed = math.floor(speed * 0.5)
            modifiers_applied.append("まひ(×0.5)")

    # 3. 特性補正
    if pokemon.ability in WEATHER_SPEED_ABILITIES:
        required_weather = WEATHER_SPEED_ABILITIES[pokemon.ability]
        if field.weather == required_weather:
            speed = math.floor(speed * 2.0)
            modifiers_applied.append(f"{pokemon.ability}(×2.0)")

    if pokemon.ability in UNBURDEN_NAMES and pokemon.item == "":
        speed = math.floor(speed * 2.0)
        modifiers_applied.append("かるわざ(×2.0)")

    if pokemon.ability in SLOW_START_NAMES:
        speed = math.floor(speed * 0.5)
        modifiers_applied.append("スロースタート(×0.5)")

    # 4. アイテム補正
    if pokemon.item in CHOICE_SCARF_NAMES:
        speed = math.floor(speed * 1.5)
        modifiers_applied.append("こだわりスカーフ(×1.5)")

    if pokemon.item in SPEED_HALVING_ITEMS:
        speed = math.floor(speed * 0.5)
        modifiers_applied.append("くろいてっきゅう(×0.5)")

    # 5. 追い風補正
    if field.tailwind:
        speed = math.floor(speed * 2.0)
        modifiers_applied.append("追い風(×2.0)")

    return speed, modifiers_applied


def calculate_speed_tiers(request: SpeedCalcRequest) -> SpeedCalcResponse:
    """場に出ている最大4体の行動順を計算する。"""
    entries: list[SpeedTierEntry] = []

    for pkmn in request.pokemon:
        effective_speed, modifiers = calculate_effective_speed(pkmn, request.field)
        entries.append(
            SpeedTierEntry(
                slot=pkmn.slot,
                name=pkmn.name,
                effective_speed=effective_speed,
                order=0,
                modifiers_applied=modifiers,
            )
        )

    # トリックルーム: 遅い順にソート / 通常: 速い順にソート
    if request.field.trick_room:
        entries.sort(key=lambda e: (e.effective_speed, e.slot))
    else:
        entries.sort(key=lambda e: (-e.effective_speed, e.slot))

    for i, entry in enumerate(entries):
        entry.order = i + 1

    return SpeedCalcResponse(
        tiers=entries,
        trick_room_active=request.field.trick_room,
    )

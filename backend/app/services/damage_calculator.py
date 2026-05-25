"""ダメージ計算・耐久逆算モジュール

HPバーの変動率から相手の耐久調整（EVs）を逆算する。
ポケモンチャンピオンズのダブルバトル（Lv50）に対応。

ダメージ計算式 (第9世代準拠):
  Damage = floor(floor(((2*Level/5+2) * Power * A/D) / 50 + 2) * Modifier * random / 100)

逆算:
  相手のHP%低下から、可能な耐久EV振りの範囲を推定する。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class DamageCategory(str, Enum):
    PHYSICAL = "physical"
    SPECIAL = "special"


@dataclass
class MoveData:
    """技データ。"""

    name: str
    power: int
    category: DamageCategory
    type: str = ""
    is_spread: bool = False  # ダブルで複数対象か
    additional_effect: str = ""


@dataclass
class AttackerInfo:
    """攻撃側の情報。"""

    name: str
    attack_stat: int  # 攻撃 or 特攻の実数値
    level: int = 50
    ability: str = ""
    item: str = ""
    is_terastallized: bool = False
    tera_type: str = ""
    attack_modifier: int = 0  # ランク変化
    has_stab: bool = False  # タイプ一致か
    type_effectiveness: float = 1.0


@dataclass
class DefenderInfo:
    """防御側の情報。"""

    name: str
    defense_stat: int = 0  # 防御 or 特防の実数値 (0なら不明)
    max_hp: int = 0  # 最大HP (0なら不明)
    level: int = 50
    ability: str = ""
    item: str = ""
    defense_modifier: int = 0


@dataclass
class DamageResult:
    """ダメージ計算結果。"""

    min_damage: int
    max_damage: int
    min_percent: float
    max_percent: float
    min_rolls: int = 0
    max_rolls: int = 0

    def to_dict(self) -> dict:
        return {
            "min_damage": self.min_damage,
            "max_damage": self.max_damage,
            "min_percent": round(self.min_percent, 1),
            "max_percent": round(self.max_percent, 1),
        }


@dataclass
class EVEstimate:
    """EV推定結果。"""

    stat_name: str  # "hp", "defense", "sp_defense"
    min_ev: int
    max_ev: int
    min_stat: int
    max_stat: int
    confidence: float

    def to_dict(self) -> dict:
        return {
            "stat_name": self.stat_name,
            "min_ev": self.min_ev,
            "max_ev": self.max_ev,
            "min_stat": self.min_stat,
            "max_stat": self.max_stat,
            "confidence": round(self.confidence, 2),
        }


# ランク補正倍率
STAT_STAGE_MULTIPLIERS: dict[int, float] = {
    -6: 2 / 8,
    -5: 2 / 7,
    -4: 2 / 6,
    -3: 2 / 5,
    -2: 2 / 4,
    -1: 2 / 3,
    0: 1.0,
    1: 3 / 2,
    2: 4 / 2,
    3: 5 / 2,
    4: 6 / 2,
    5: 7 / 2,
    6: 8 / 2,
}

# いのちのたま倍率
LIFE_ORB_MULTIPLIER = 5324 / 4096
# こだわり系倍率
CHOICE_MULTIPLIER = 1.5
# ダブルバトルの範囲技補正
SPREAD_MULTIPLIER = 0.75


def _apply_stat_modifier(stat: int, stage: int) -> int:
    """ランク補正を適用する。"""
    if stage == 0:
        return stat
    mult = STAT_STAGE_MULTIPLIERS.get(stage, 1.0)
    return max(1, math.floor(stat * mult))


def calculate_damage(
    move: MoveData,
    attacker: AttackerInfo,
    defender: DefenderInfo,
) -> DamageResult:
    """ダメージ計算を行う。

    Returns:
        最小〜最大ダメージと%
    """
    if defender.defense_stat <= 0 or defender.max_hp <= 0:
        return DamageResult(0, 0, 0.0, 0.0)

    # 攻撃・防御実数値にランク補正
    atk = _apply_stat_modifier(attacker.attack_stat, attacker.attack_modifier)
    dfn = _apply_stat_modifier(defender.defense_stat, defender.defense_modifier)

    # 基本ダメージ (第9世代準拠)
    base = math.floor(math.floor((2 * attacker.level / 5 + 2) * move.power * atk / dfn) / 50 + 2)

    # 範囲技補正 (ダブルバトル)
    if move.is_spread:
        base = math.floor(base * SPREAD_MULTIPLIER)

    # タイプ一致 (STAB)
    if attacker.has_stab:
        base = math.floor(base * 1.5)

    # タイプ相性
    base = math.floor(base * attacker.type_effectiveness)

    # アイテム補正
    if attacker.item in ("いのちのたま", "Life Orb"):
        base = math.floor(base * LIFE_ORB_MULTIPLIER)
    elif (
        attacker.item in ("こだわりハチマキ", "Choice Band")
        and move.category == DamageCategory.PHYSICAL
    ):
        base = math.floor(base * CHOICE_MULTIPLIER)
    elif (
        attacker.item in ("こだわりメガネ", "Choice Specs")
        and move.category == DamageCategory.SPECIAL
    ):
        base = math.floor(base * CHOICE_MULTIPLIER)

    # 乱数幅 (85-100)
    min_damage = max(1, math.floor(base * 85 / 100))
    max_damage = max(1, base)

    min_percent = round(min_damage / defender.max_hp * 100, 1)
    max_percent = round(max_damage / defender.max_hp * 100, 1)

    return DamageResult(
        min_damage=min_damage,
        max_damage=max_damage,
        min_percent=min_percent,
        max_percent=max_percent,
    )


def estimate_hp_ev(
    species_base_hp: int,
    observed_max_hp: int,
    level: int = 50,
    nature_bonus: bool = False,
) -> EVEstimate:
    """観測されたHP実数値からHP EVを逆算する。

    Lv50時のHP計算式:
        HP = floor((2*Base + IV + floor(EV/4)) * Level/100) + Level + 10
    """
    min_ev = 252
    max_ev = 0
    min_stat = 999
    max_stat = 0

    for ev in range(0, 253, 4):
        for iv in range(0, 32):
            hp = (
                math.floor((2 * species_base_hp + iv + math.floor(ev / 4)) * level / 100)
                + level
                + 10
            )
            if hp == observed_max_hp:
                min_ev = min(min_ev, ev)
                max_ev = max(max_ev, ev)
                min_stat = min(min_stat, hp)
                max_stat = max(max_stat, hp)

    if min_ev > max_ev:
        return EVEstimate("hp", 0, 252, 0, 0, 0.0)

    confidence = 1.0 - (max_ev - min_ev) / 252.0
    return EVEstimate("hp", min_ev, max_ev, min_stat, max_stat, confidence)


def estimate_defense_ev_from_damage(
    species_base_def: int,
    damage_percent: float,
    move: MoveData,
    attacker: AttackerInfo,
    defender_max_hp: int,
    level: int = 50,
) -> EVEstimate:
    """受けたダメージ%から防御/特防EVを逆算する。

    Lv50時のステータス計算式:
        Stat = floor((floor((2*Base + IV + floor(EV/4)) * Level/100) + 5) * Nature)
    """
    stat_name = "defense" if move.category == DamageCategory.PHYSICAL else "sp_defense"

    actual_damage = math.floor(defender_max_hp * damage_percent / 100)
    if actual_damage <= 0:
        return EVEstimate(stat_name, 0, 252, 0, 0, 0.0)

    min_ev = 252
    max_ev = 0
    min_stat = 999
    max_stat = 0

    for ev in range(0, 253, 4):
        for iv in range(0, 32):
            stat = math.floor((2 * species_base_def + iv + math.floor(ev / 4)) * level / 100) + 5
            # 性格補正 (1.1x or 0.9x or 1.0x)
            for nature_mult in (0.9, 1.0, 1.1):
                def_stat = max(1, math.floor(stat * nature_mult))

                defender = DefenderInfo(
                    name="target",
                    defense_stat=def_stat,
                    max_hp=defender_max_hp,
                    level=level,
                )
                result = calculate_damage(move, attacker, defender)

                if result.min_damage <= actual_damage <= result.max_damage:
                    min_ev = min(min_ev, ev)
                    max_ev = max(max_ev, ev)
                    min_stat = min(min_stat, def_stat)
                    max_stat = max(max_stat, def_stat)

    if min_ev > max_ev:
        return EVEstimate(stat_name, 0, 252, 0, 0, 0.0)

    confidence = 1.0 - (max_ev - min_ev) / 252.0
    return EVEstimate(stat_name, min_ev, max_ev, min_stat, max_stat, confidence)

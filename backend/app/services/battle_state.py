"""バトル状態管理

ダブルバトルのターン毎の状態を追跡する。
場に出ている4体のポケモン、フィールド条件、ターン数を管理し、
素早さ計算エンジンと連携してリアルタイムに行動順を提供する。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from app.schemas import BattlePokemon, FieldCondition, SpeedCalcRequest, WeatherCondition
from app.services.speed_calculator import calculate_speed_tiers


class BattlePhase(str, Enum):
    """バトルのフェーズ。"""

    NONE = "none"
    TEAM_PREVIEW = "team_preview"
    SELECTION = "selection"
    IN_BATTLE = "in_battle"
    FINISHED = "finished"


class Side(str, Enum):
    ALLY = "ally"
    ENEMY = "enemy"


@dataclass
class PokemonOnField:
    """フィールド上のポケモンの情報。"""

    slot: int  # 0-3 (0,1=味方, 2,3=相手)
    name: str
    species: str = ""
    ability: str = ""
    item: str = ""
    base_speed: int = 0
    speed_modifier: int = 0
    is_paralyzed: bool = False
    current_hp: int = 0
    max_hp: int = 0
    hp_percent: float = 100.0
    side: Side = Side.ALLY
    is_mega_evolved: bool = False
    is_terastallized: bool = False
    tera_type: str = ""
    status: str = ""  # まひ, ねむり, やけど, etc.


@dataclass
class FieldState:
    """フィールド状態。"""

    weather: WeatherCondition = WeatherCondition.NONE
    weather_turns_left: int = 0
    tailwind_ally: bool = False
    tailwind_ally_turns: int = 0
    tailwind_enemy: bool = False
    tailwind_enemy_turns: int = 0
    trick_room: bool = False
    trick_room_turns: int = 0
    terrain: str = ""
    terrain_turns: int = 0


@dataclass
class TurnRecord:
    """1ターンの記録。"""

    turn: int
    timestamp: float
    actions: list[dict] = field(default_factory=list)
    field_before: FieldState | None = None
    field_after: FieldState | None = None
    speed_order: list[dict] = field(default_factory=list)
    hp_changes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "timestamp": self.timestamp,
            "actions": self.actions,
            "speed_order": self.speed_order,
            "hp_changes": self.hp_changes,
        }


@dataclass
class MatchState:
    """1試合の状態。"""

    match_id: str = ""
    phase: BattlePhase = BattlePhase.NONE
    turn: int = 0
    started_at: float = 0.0

    ally_team: list[str] = field(default_factory=list)
    enemy_team: list[str] = field(default_factory=list)
    ally_leads: list[str] = field(default_factory=list)
    enemy_leads: list[str] = field(default_factory=list)

    pokemon_on_field: list[PokemonOnField] = field(default_factory=list)
    field_state: FieldState = field(default_factory=FieldState)

    turn_history: list[TurnRecord] = field(default_factory=list)
    result: str = ""  # "win", "loss", ""

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "phase": self.phase.value,
            "turn": self.turn,
            "started_at": self.started_at,
            "ally_team": self.ally_team,
            "enemy_team": self.enemy_team,
            "ally_leads": self.ally_leads,
            "enemy_leads": self.enemy_leads,
            "pokemon_on_field": [
                {
                    "slot": p.slot,
                    "name": p.name,
                    "side": p.side.value,
                    "hp_percent": p.hp_percent,
                    "current_hp": p.current_hp,
                    "max_hp": p.max_hp,
                    "status": p.status,
                    "ability": p.ability,
                    "item": p.item,
                    "base_speed": p.base_speed,
                }
                for p in self.pokemon_on_field
            ],
            "field_state": {
                "weather": self.field_state.weather.value,
                "tailwind_ally": self.field_state.tailwind_ally,
                "tailwind_enemy": self.field_state.tailwind_enemy,
                "trick_room": self.field_state.trick_room,
                "terrain": self.field_state.terrain,
            },
            "turn_history_count": len(self.turn_history),
            "result": self.result,
        }


class BattleStateManager:
    """ダブルバトルの状態を管理するクラス。

    ターン毎の4体のポケモン、フィールド条件を追跡し、
    素早さ順位をリアルタイムに計算する。
    """

    def __init__(self) -> None:
        self._match = MatchState()
        self._match_count = 0

    @property
    def match(self) -> MatchState:
        return self._match

    @property
    def is_active(self) -> bool:
        return self._match.phase == BattlePhase.IN_BATTLE

    def start_match(
        self,
        ally_team: list[str] | None = None,
        enemy_team: list[str] | None = None,
    ) -> MatchState:
        """新しい試合を開始する。"""
        self._match_count += 1
        self._match = MatchState(
            match_id=f"match_{self._match_count}_{int(time.time())}",
            phase=BattlePhase.TEAM_PREVIEW,
            started_at=time.time(),
            ally_team=ally_team or [],
            enemy_team=enemy_team or [],
        )
        return self._match

    def set_selection(
        self,
        ally_leads: list[str],
        enemy_leads: list[str] | None = None,
    ) -> None:
        """選出を記録する。"""
        self._match.phase = BattlePhase.SELECTION
        self._match.ally_leads = ally_leads
        if enemy_leads:
            self._match.enemy_leads = enemy_leads

    def start_battle(self, pokemon_on_field: list[PokemonOnField] | None = None) -> None:
        """バトルフェーズを開始する。"""
        self._match.phase = BattlePhase.IN_BATTLE
        self._match.turn = 1
        if pokemon_on_field:
            self._match.pokemon_on_field = pokemon_on_field

    def update_field_pokemon(self, pokemon_on_field: list[PokemonOnField]) -> None:
        """フィールド上のポケモンを更新する。"""
        self._match.pokemon_on_field = pokemon_on_field

    def update_pokemon_hp(
        self,
        slot: int,
        current_hp: int | None = None,
        max_hp: int | None = None,
        hp_percent: float | None = None,
    ) -> dict | None:
        """特定スロットのポケモンのHPを更新し、変化量を返す。"""
        for p in self._match.pokemon_on_field:
            if p.slot == slot:
                old_percent = p.hp_percent
                if current_hp is not None:
                    p.current_hp = current_hp
                if max_hp is not None:
                    p.max_hp = max_hp
                if hp_percent is not None:
                    p.hp_percent = hp_percent
                elif p.max_hp > 0 and p.current_hp >= 0:
                    p.hp_percent = round(p.current_hp / p.max_hp * 100, 1)

                damage_percent = round(old_percent - p.hp_percent, 1)
                if abs(damage_percent) > 0.1:
                    return {
                        "slot": slot,
                        "name": p.name,
                        "old_hp_percent": old_percent,
                        "new_hp_percent": p.hp_percent,
                        "damage_percent": damage_percent,
                    }
                return None
        return None

    def update_field_condition(
        self,
        weather: WeatherCondition | None = None,
        tailwind_ally: bool | None = None,
        tailwind_enemy: bool | None = None,
        trick_room: bool | None = None,
        terrain: str | None = None,
    ) -> None:
        """フィールド条件を更新する。"""
        fs = self._match.field_state
        if weather is not None:
            fs.weather = weather
        if tailwind_ally is not None:
            fs.tailwind_ally = tailwind_ally
        if tailwind_enemy is not None:
            fs.tailwind_enemy = tailwind_enemy
        if trick_room is not None:
            fs.trick_room = trick_room
        if terrain is not None:
            fs.terrain = terrain

    def advance_turn(self, actions: list[dict] | None = None) -> TurnRecord:
        """ターンを進め、記録を作成する。"""
        speed_order = self.calculate_current_speed_order()
        hp_changes: list[dict] = []

        record = TurnRecord(
            turn=self._match.turn,
            timestamp=time.time(),
            actions=actions or [],
            speed_order=speed_order,
            hp_changes=hp_changes,
        )
        self._match.turn_history.append(record)
        self._match.turn += 1

        self._tick_field_conditions()
        return record

    def calculate_current_speed_order(self) -> list[dict]:
        """現在のフィールド上の4体の素早さ順を計算する。"""
        if not self._match.pokemon_on_field:
            return []

        battle_pokemon = []
        for p in self._match.pokemon_on_field:
            if p.base_speed <= 0:
                continue
            bp = BattlePokemon(
                name=p.name,
                base_speed=p.base_speed,
                ability=p.ability,
                item=p.item,
                speed_modifier=p.speed_modifier,
                is_paralyzed=p.is_paralyzed or p.status in ("まひ", "Paralysis"),
                slot=p.slot,
            )
            battle_pokemon.append(bp)

        if not battle_pokemon:
            return []

        fs = self._match.field_state
        field_cond = FieldCondition(
            tailwind=fs.tailwind_ally,
            trick_room=fs.trick_room,
            weather=fs.weather,
        )

        request = SpeedCalcRequest(pokemon=battle_pokemon, field=field_cond)
        result = calculate_speed_tiers(request)

        return [
            {
                "slot": t.slot,
                "name": t.name,
                "effective_speed": t.effective_speed,
                "order": t.order,
                "modifiers": t.modifiers_applied,
            }
            for t in result.tiers
        ]

    def end_match(self, result: str = "") -> MatchState:
        """試合を終了する。"""
        self._match.phase = BattlePhase.FINISHED
        self._match.result = result
        return self._match

    def reset(self) -> None:
        """状態をリセットする。"""
        self._match = MatchState()

    def _tick_field_conditions(self) -> None:
        """フィールド条件のターン経過処理。"""
        fs = self._match.field_state

        if fs.weather_turns_left > 0:
            fs.weather_turns_left -= 1
            if fs.weather_turns_left == 0:
                fs.weather = WeatherCondition.NONE

        if fs.tailwind_ally_turns > 0:
            fs.tailwind_ally_turns -= 1
            if fs.tailwind_ally_turns == 0:
                fs.tailwind_ally = False

        if fs.tailwind_enemy_turns > 0:
            fs.tailwind_enemy_turns -= 1
            if fs.tailwind_enemy_turns == 0:
                fs.tailwind_enemy = False

        if fs.trick_room_turns > 0:
            fs.trick_room_turns -= 1
            if fs.trick_room_turns == 0:
                fs.trick_room = False

        if fs.terrain_turns > 0:
            fs.terrain_turns -= 1
            if fs.terrain_turns == 0:
                fs.terrain = ""


# グローバルインスタンス
battle_state_manager = BattleStateManager()

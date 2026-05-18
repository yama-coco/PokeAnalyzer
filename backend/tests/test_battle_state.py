"""BattleStateManager のテスト"""

from __future__ import annotations

import pytest

from app.schemas import WeatherCondition
from app.services.battle_state import (
    BattlePhase,
    BattleStateManager,
    PokemonOnField,
    Side,
)


@pytest.fixture
def manager():
    mgr = BattleStateManager()
    return mgr


@pytest.fixture
def sample_pokemon():
    return [
        PokemonOnField(
            slot=0,
            name="ガブリアス",
            ability="さめはだ",
            item="きあいのタスキ",
            base_speed=102,
            current_hp=183,
            max_hp=183,
            side=Side.ALLY,
        ),
        PokemonOnField(
            slot=1,
            name="ニンフィア",
            ability="フェアリースキン",
            item="こだわりメガネ",
            base_speed=60,
            current_hp=201,
            max_hp=201,
            side=Side.ALLY,
        ),
        PokemonOnField(
            slot=2,
            name="バンギラス",
            ability="すなおこし",
            item="とつげきチョッキ",
            base_speed=61,
            hp_percent=100.0,
            side=Side.ENEMY,
        ),
        PokemonOnField(
            slot=3,
            name="カイリュー",
            ability="マルチスケイル",
            item="いのちのたま",
            base_speed=80,
            hp_percent=100.0,
            side=Side.ENEMY,
        ),
    ]


class TestMatchLifecycle:
    def test_start_match(self, manager: BattleStateManager):
        match = manager.start_match(
            ally_team=["ガブリアス", "ニンフィア", "リキキリン"],
            enemy_team=["バンギラス", "カイリュー", "ヤレユータン"],
        )
        assert match.phase == BattlePhase.TEAM_PREVIEW
        assert len(match.ally_team) == 3
        assert len(match.enemy_team) == 3
        assert match.match_id.startswith("match_")

    def test_set_selection(self, manager: BattleStateManager):
        manager.start_match()
        manager.set_selection(
            ally_leads=["ガブリアス", "ニンフィア"],
            enemy_leads=["バンギラス", "カイリュー"],
        )
        assert manager.match.phase == BattlePhase.SELECTION
        assert manager.match.ally_leads == ["ガブリアス", "ニンフィア"]

    def test_start_battle(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス", "ニンフィア"])
        manager.start_battle(sample_pokemon)
        assert manager.match.phase == BattlePhase.IN_BATTLE
        assert manager.match.turn == 1
        assert len(manager.match.pokemon_on_field) == 4

    def test_end_match(self, manager: BattleStateManager):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle()
        match = manager.end_match(result="win")
        assert match.phase == BattlePhase.FINISHED
        assert match.result == "win"

    def test_is_active(self, manager: BattleStateManager):
        assert not manager.is_active
        manager.start_match()
        assert not manager.is_active
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle()
        assert manager.is_active
        manager.end_match()
        assert not manager.is_active


class TestFieldConditions:
    def test_update_weather(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        manager.update_field_condition(weather=WeatherCondition.RAIN)
        assert manager.match.field_state.weather == WeatherCondition.RAIN

    def test_update_trick_room(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        manager.update_field_condition(trick_room=True)
        assert manager.match.field_state.trick_room is True

    def test_update_tailwind(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        manager.update_field_condition(tailwind_ally=True)
        assert manager.match.field_state.tailwind_ally is True
        assert manager.match.field_state.tailwind_enemy is False

    def test_field_condition_tick(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        manager.match.field_state.trick_room = True
        manager.match.field_state.trick_room_turns = 2
        manager.advance_turn()
        assert manager.match.field_state.trick_room_turns == 1
        assert manager.match.field_state.trick_room is True
        manager.advance_turn()
        assert manager.match.field_state.trick_room_turns == 0
        assert manager.match.field_state.trick_room is False


class TestSpeedOrder:
    def test_speed_order_normal(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        order = manager.calculate_current_speed_order()
        assert len(order) == 4
        # ガブリアス(102) > カイリュー(80) > バンギラス(61) > ニンフィア(60)
        assert order[0]["name"] == "ガブリアス"
        assert order[0]["order"] == 1
        assert order[1]["name"] == "カイリュー"
        assert order[3]["name"] == "ニンフィア"

    def test_speed_order_trick_room(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        manager.update_field_condition(trick_room=True)
        order = manager.calculate_current_speed_order()
        # トリルで反転: ニンフィア(60) > バンギラス(61) > カイリュー(80) > ガブリアス(102)
        assert order[0]["name"] == "ニンフィア"
        assert order[3]["name"] == "ガブリアス"

    def test_speed_order_tailwind(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        manager.update_field_condition(tailwind_ally=True)
        order = manager.calculate_current_speed_order()
        # 追い風でガブリアス(204), ニンフィア(120)
        gabby = next(o for o in order if o["name"] == "ガブリアス")
        assert gabby["effective_speed"] == 204

    def test_speed_order_empty_field(self, manager: BattleStateManager):
        manager.start_match()
        order = manager.calculate_current_speed_order()
        assert order == []


class TestHPUpdate:
    def test_update_pokemon_hp_value(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        change = manager.update_pokemon_hp(slot=0, current_hp=149, max_hp=183)
        assert change is not None
        assert change["slot"] == 0
        assert change["name"] == "ガブリアス"
        assert change["damage_percent"] > 0

    def test_update_pokemon_hp_percent(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        change = manager.update_pokemon_hp(slot=2, hp_percent=73.0)
        assert change is not None
        assert change["name"] == "バンギラス"
        assert change["new_hp_percent"] == 73.0

    def test_no_change_returns_none(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        change = manager.update_pokemon_hp(slot=0, current_hp=183, max_hp=183)
        assert change is None


class TestTurnAdvance:
    def test_advance_turn(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        assert manager.match.turn == 1
        record = manager.advance_turn(actions=[{"pokemon": "ガブリアス", "move": "じしん"}])
        assert record.turn == 1
        assert len(record.actions) == 1
        assert manager.match.turn == 2

    def test_multiple_turns(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        manager.advance_turn()
        manager.advance_turn()
        manager.advance_turn()
        assert manager.match.turn == 4
        assert len(manager.match.turn_history) == 3


class TestToDict:
    def test_match_to_dict(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match(
            ally_team=["ガブリアス", "ニンフィア"],
            enemy_team=["バンギラス", "カイリュー"],
        )
        manager.set_selection(ally_leads=["ガブリアス", "ニンフィア"])
        manager.start_battle(sample_pokemon)
        d = manager.match.to_dict()
        assert d["phase"] == "in_battle"
        assert d["turn"] == 1
        assert len(d["pokemon_on_field"]) == 4
        assert d["field_state"]["weather"] == "none"

    def test_reset(self, manager: BattleStateManager, sample_pokemon):
        manager.start_match()
        manager.set_selection(ally_leads=["ガブリアス"])
        manager.start_battle(sample_pokemon)
        manager.reset()
        assert manager.match.phase == BattlePhase.NONE
        assert manager.match.pokemon_on_field == []

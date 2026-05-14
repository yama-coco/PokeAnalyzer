"""Damage Calculator のテスト"""

from __future__ import annotations

import pytest

from app.services.damage_calculator import (
    AttackerInfo,
    DamageCategory,
    DefenderInfo,
    MoveData,
    calculate_damage,
    estimate_defense_ev_from_damage,
    estimate_hp_ev,
)


@pytest.fixture
def earthquake_move():
    return MoveData(
        name="じしん",
        power=100,
        category=DamageCategory.PHYSICAL,
        type="じめん",
        is_spread=True,
    )


@pytest.fixture
def hyper_voice_move():
    return MoveData(
        name="ハイパーボイス",
        power=90,
        category=DamageCategory.SPECIAL,
        type="ノーマル",
        is_spread=True,
    )


@pytest.fixture
def draco_meteor_move():
    return MoveData(
        name="りゅうせいぐん",
        power=130,
        category=DamageCategory.SPECIAL,
        type="ドラゴン",
    )


class TestDamageCalculation:
    def test_basic_physical_damage(self, earthquake_move):
        attacker = AttackerInfo(name="ガブリアス", attack_stat=182)
        defender = DefenderInfo(name="バンギラス", defense_stat=130, max_hp=207)
        result = calculate_damage(earthquake_move, attacker, defender)
        assert result.min_damage > 0
        assert result.max_damage >= result.min_damage
        assert result.min_percent > 0
        assert result.max_percent >= result.min_percent

    def test_stab_bonus(self, earthquake_move):
        attacker_no_stab = AttackerInfo(name="カイリュー", attack_stat=186, has_stab=False)
        attacker_stab = AttackerInfo(name="ガブリアス", attack_stat=186, has_stab=True)
        defender = DefenderInfo(name="バンギラス", defense_stat=130, max_hp=207)
        result_no = calculate_damage(earthquake_move, attacker_no_stab, defender)
        result_yes = calculate_damage(earthquake_move, attacker_stab, defender)
        assert result_yes.max_damage > result_no.max_damage

    def test_type_effectiveness(self, earthquake_move):
        attacker = AttackerInfo(name="ガブリアス", attack_stat=182, type_effectiveness=2.0)
        defender = DefenderInfo(name="ジバコイル", defense_stat=115, max_hp=177)
        result = calculate_damage(earthquake_move, attacker, defender)
        # 弱点で大ダメージ
        assert result.max_percent > 50

    def test_spread_move_reduction(self):
        single = MoveData(name="じしん", power=100, category=DamageCategory.PHYSICAL)
        spread = MoveData(
            name="じしん", power=100, category=DamageCategory.PHYSICAL, is_spread=True
        )
        attacker = AttackerInfo(name="ガブリアス", attack_stat=182)
        defender = DefenderInfo(name="バンギラス", defense_stat=130, max_hp=207)
        r_single = calculate_damage(single, attacker, defender)
        r_spread = calculate_damage(spread, attacker, defender)
        # 範囲技は0.75倍
        assert r_spread.max_damage < r_single.max_damage

    def test_life_orb_boost(self, draco_meteor_move):
        attacker = AttackerInfo(name="カイリュー", attack_stat=167)
        attacker_orb = AttackerInfo(name="カイリュー", attack_stat=167, item="いのちのたま")
        defender = DefenderInfo(name="ガブリアス", defense_stat=105, max_hp=183)
        r_normal = calculate_damage(draco_meteor_move, attacker, defender)
        r_orb = calculate_damage(draco_meteor_move, attacker_orb, defender)
        assert r_orb.max_damage > r_normal.max_damage

    def test_choice_band_boost(self, earthquake_move):
        attacker = AttackerInfo(name="ガブリアス", attack_stat=182, item="こだわりハチマキ")
        defender = DefenderInfo(name="バンギラス", defense_stat=130, max_hp=207)
        result = calculate_damage(earthquake_move, attacker, defender)
        assert result.max_damage > 0

    def test_choice_specs_on_physical_no_effect(self, earthquake_move):
        attacker_specs = AttackerInfo(name="ガブリアス", attack_stat=182, item="こだわりメガネ")
        attacker_none = AttackerInfo(name="ガブリアス", attack_stat=182)
        defender = DefenderInfo(name="バンギラス", defense_stat=130, max_hp=207)
        r1 = calculate_damage(earthquake_move, attacker_specs, defender)
        r2 = calculate_damage(earthquake_move, attacker_none, defender)
        # メガネは物理技には効果なし
        assert r1.max_damage == r2.max_damage

    def test_zero_defense_returns_empty(self, earthquake_move):
        attacker = AttackerInfo(name="ガブリアス", attack_stat=182)
        defender = DefenderInfo(name="???", defense_stat=0, max_hp=0)
        result = calculate_damage(earthquake_move, attacker, defender)
        assert result.min_damage == 0

    def test_damage_rolls_range(self, earthquake_move):
        attacker = AttackerInfo(name="ガブリアス", attack_stat=182)
        defender = DefenderInfo(name="バンギラス", defense_stat=130, max_hp=207)
        result = calculate_damage(earthquake_move, attacker, defender)
        # 乱数幅: min は max の85%前後 (floor丸めにより若干のずれあり)
        assert result.min_damage >= result.max_damage * 0.82
        assert result.min_damage <= result.max_damage * 0.86


class TestHPEVEstimation:
    def test_estimate_hp_ev_known(self):
        # ガブリアスHP種族値108, Lv50 H252: HP=215
        result = estimate_hp_ev(species_base_hp=108, observed_max_hp=215)
        assert result.min_ev <= 252
        assert result.max_ev >= 252

    def test_estimate_hp_ev_no_investment(self):
        # ガブリアスHP種族値108, Lv50 無振り(IV31): HP=183
        result = estimate_hp_ev(species_base_hp=108, observed_max_hp=183)
        assert result.min_ev <= 4
        # 無振りでもIV0の場合はEVが必要
        assert result.confidence > 0

    def test_estimate_hp_ev_impossible(self):
        result = estimate_hp_ev(species_base_hp=108, observed_max_hp=500)
        assert result.confidence == 0.0


class TestDefenseEVEstimation:
    def test_estimate_defense_ev(self, earthquake_move):
        attacker = AttackerInfo(name="ガブリアス", attack_stat=182, has_stab=True)
        result = estimate_defense_ev_from_damage(
            species_base_def=110,
            damage_percent=50.0,
            move=earthquake_move,
            attacker=attacker,
            defender_max_hp=207,
        )
        assert result.stat_name == "defense"
        assert 0 <= result.min_ev <= 252
        assert result.max_ev >= result.min_ev

    def test_estimate_sp_defense_ev(self, hyper_voice_move):
        attacker = AttackerInfo(name="ニンフィア", attack_stat=178, has_stab=True)
        result = estimate_defense_ev_from_damage(
            species_base_def=100,
            damage_percent=40.0,
            move=hyper_voice_move,
            attacker=attacker,
            defender_max_hp=207,
        )
        assert result.stat_name == "sp_defense"

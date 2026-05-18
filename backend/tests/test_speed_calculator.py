"""素早さ計算エンジンのテスト"""

from app.schemas import (
    BattlePokemon,
    FieldCondition,
    SpeedCalcRequest,
    StatModifier,
    WeatherCondition,
)
from app.services.speed_calculator import calculate_effective_speed, calculate_speed_tiers


def _make_pokemon(
    name: str = "テスト",
    base_speed: int = 100,
    ability: str = "",
    item: str = "",
    speed_modifier: int = 0,
    is_paralyzed: bool = False,
    slot: int = 0,
) -> BattlePokemon:
    return BattlePokemon(
        name=name,
        base_speed=base_speed,
        ability=ability,
        item=item,
        speed_modifier=StatModifier(speed_modifier),
        is_paralyzed=is_paralyzed,
        slot=slot,
    )


def _default_field(**kwargs) -> FieldCondition:
    return FieldCondition(**kwargs)


class TestEffectiveSpeed:
    def test_base_speed_no_modifiers(self):
        pkmn = _make_pokemon(base_speed=150)
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 150
        assert mods == []

    def test_positive_stat_stage(self):
        pkmn = _make_pokemon(base_speed=100, speed_modifier=1)
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 150  # 100 * 3/2 = 150
        assert any("ランク+1" in m for m in mods)

    def test_negative_stat_stage(self):
        pkmn = _make_pokemon(base_speed=100, speed_modifier=-1)
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 66  # floor(100 * 2/3) = 66
        assert any("ランク-1" in m for m in mods)

    def test_max_stat_stage(self):
        pkmn = _make_pokemon(base_speed=100, speed_modifier=6)
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 400  # 100 * 8/2 = 400

    def test_paralysis(self):
        pkmn = _make_pokemon(base_speed=200, is_paralyzed=True)
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 100  # floor(200 * 0.5) = 100
        assert any("まひ" in m for m in mods)

    def test_quick_feet_ignores_paralysis(self):
        pkmn = _make_pokemon(base_speed=200, ability="はやあし", is_paralyzed=True)
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 200
        assert any("はやあし" in m for m in mods)

    def test_choice_scarf(self):
        pkmn = _make_pokemon(base_speed=100, item="こだわりスカーフ")
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 150  # floor(100 * 1.5) = 150
        assert any("スカーフ" in m for m in mods)

    def test_iron_ball(self):
        pkmn = _make_pokemon(base_speed=100, item="くろいてっきゅう")
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 50  # floor(100 * 0.5) = 50

    def test_tailwind(self):
        pkmn = _make_pokemon(base_speed=100)
        field = _default_field(tailwind=True)
        speed, mods = calculate_effective_speed(pkmn, field)
        assert speed == 200  # 100 * 2 = 200
        assert any("追い風" in m for m in mods)

    def test_swift_swim_in_rain(self):
        pkmn = _make_pokemon(base_speed=80, ability="すいすい")
        field = _default_field(weather=WeatherCondition.RAIN)
        speed, mods = calculate_effective_speed(pkmn, field)
        assert speed == 160  # 80 * 2 = 160
        assert any("すいすい" in m for m in mods)

    def test_swift_swim_without_rain(self):
        pkmn = _make_pokemon(base_speed=80, ability="すいすい")
        field = _default_field(weather=WeatherCondition.SUN)
        speed, mods = calculate_effective_speed(pkmn, field)
        assert speed == 80
        assert not any("すいすい" in m for m in mods)

    def test_chlorophyll_in_sun(self):
        pkmn = _make_pokemon(base_speed=80, ability="ようりょくそ")
        field = _default_field(weather=WeatherCondition.SUN)
        speed, mods = calculate_effective_speed(pkmn, field)
        assert speed == 160

    def test_sand_rush_in_sand(self):
        pkmn = _make_pokemon(base_speed=80, ability="すなかき")
        field = _default_field(weather=WeatherCondition.SAND)
        speed, mods = calculate_effective_speed(pkmn, field)
        assert speed == 160

    def test_slush_rush_in_snow(self):
        pkmn = _make_pokemon(base_speed=80, ability="ゆきかき")
        field = _default_field(weather=WeatherCondition.SNOW)
        speed, mods = calculate_effective_speed(pkmn, field)
        assert speed == 160

    def test_unburden_no_item(self):
        pkmn = _make_pokemon(base_speed=80, ability="かるわざ", item="")
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 160
        assert any("かるわざ" in m for m in mods)

    def test_unburden_with_item(self):
        pkmn = _make_pokemon(base_speed=80, ability="かるわざ", item="きあいのタスキ")
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 80

    def test_slow_start(self):
        pkmn = _make_pokemon(base_speed=100, ability="スロースタート")
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        assert speed == 50

    def test_combined_scarf_and_tailwind(self):
        pkmn = _make_pokemon(base_speed=100, item="こだわりスカーフ")
        field = _default_field(tailwind=True)
        speed, mods = calculate_effective_speed(pkmn, field)
        # 100 -> scarf: floor(150) -> tailwind: floor(300) = 300
        assert speed == 300

    def test_combined_rain_swift_swim_and_tailwind(self):
        pkmn = _make_pokemon(base_speed=80, ability="すいすい")
        field = _default_field(weather=WeatherCondition.RAIN, tailwind=True)
        speed, mods = calculate_effective_speed(pkmn, field)
        # 80 -> swift swim: 160 -> tailwind: 320
        assert speed == 320

    def test_paralysis_with_scarf(self):
        pkmn = _make_pokemon(base_speed=100, item="こだわりスカーフ", is_paralyzed=True)
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        # 100 -> paralysis: floor(50) -> scarf: floor(75) = 75
        assert speed == 75

    def test_stat_stage_plus_paralysis(self):
        pkmn = _make_pokemon(base_speed=100, speed_modifier=2, is_paralyzed=True)
        speed, mods = calculate_effective_speed(pkmn, _default_field())
        # 100 -> +2: 200 -> paralysis: 100
        assert speed == 100


class TestSpeedTiers:
    def test_normal_ordering(self):
        request = SpeedCalcRequest(
            pokemon=[
                _make_pokemon(name="速い", base_speed=150, slot=0),
                _make_pokemon(name="普通", base_speed=100, slot=1),
                _make_pokemon(name="遅い", base_speed=50, slot=2),
                _make_pokemon(name="中間", base_speed=120, slot=3),
            ],
            field=_default_field(),
        )
        result = calculate_speed_tiers(request)
        assert not result.trick_room_active
        assert result.tiers[0].name == "速い"
        assert result.tiers[0].order == 1
        assert result.tiers[1].name == "中間"
        assert result.tiers[1].order == 2
        assert result.tiers[2].name == "普通"
        assert result.tiers[2].order == 3
        assert result.tiers[3].name == "遅い"
        assert result.tiers[3].order == 4

    def test_trick_room_reversal(self):
        request = SpeedCalcRequest(
            pokemon=[
                _make_pokemon(name="速い", base_speed=150, slot=0),
                _make_pokemon(name="遅い", base_speed=50, slot=1),
            ],
            field=_default_field(trick_room=True),
        )
        result = calculate_speed_tiers(request)
        assert result.trick_room_active
        assert result.tiers[0].name == "遅い"
        assert result.tiers[0].order == 1
        assert result.tiers[1].name == "速い"
        assert result.tiers[1].order == 2

    def test_speed_tie_uses_slot_order(self):
        request = SpeedCalcRequest(
            pokemon=[
                _make_pokemon(name="A", base_speed=100, slot=0),
                _make_pokemon(name="B", base_speed=100, slot=1),
            ],
            field=_default_field(),
        )
        result = calculate_speed_tiers(request)
        assert result.tiers[0].name == "A"
        assert result.tiers[1].name == "B"

    def test_tailwind_changes_order(self):
        """追い風で逆転するケース"""
        request = SpeedCalcRequest(
            pokemon=[
                _make_pokemon(name="自軍A", base_speed=80, slot=0),
                _make_pokemon(name="相手B", base_speed=150, slot=1),
            ],
            field=_default_field(tailwind=True),
        )
        result = calculate_speed_tiers(request)
        # 80*2=160 vs 150*2=300 → 相手Bが速い
        assert result.tiers[0].name == "相手B"

    def test_scarf_overtakes(self):
        """スカーフで素早さ逆転するケース"""
        request = SpeedCalcRequest(
            pokemon=[
                _make_pokemon(name="スカーフ持ち", base_speed=100, item="こだわりスカーフ", slot=0),
                _make_pokemon(name="素早い", base_speed=140, slot=1),
            ],
            field=_default_field(),
        )
        result = calculate_speed_tiers(request)
        # 100*1.5=150 vs 140 → スカーフ持ちが速い
        assert result.tiers[0].name == "スカーフ持ち"
        assert result.tiers[0].effective_speed == 150

    def test_real_battle_scenario(self):
        """実戦的なシナリオ: 追い風下でのすいすいvsスカーフ"""
        request = SpeedCalcRequest(
            pokemon=[
                _make_pokemon(name="ペリッパー", base_speed=65, ability="あめふらし", slot=0),
                _make_pokemon(name="カマスジョー", base_speed=136, ability="すいすい", slot=1),
                _make_pokemon(name="ガブリアス", base_speed=154, item="こだわりスカーフ", slot=2),
                _make_pokemon(name="モロバレル", base_speed=30, slot=3),
            ],
            field=_default_field(weather=WeatherCondition.RAIN),
        )
        result = calculate_speed_tiers(request)
        # カマスジョー: 136*2=272 (すいすい)
        # ガブリアス: 154*1.5=231 (スカーフ)
        # ペリッパー: 65
        # モロバレル: 30
        assert result.tiers[0].name == "カマスジョー"
        assert result.tiers[0].effective_speed == 272
        assert result.tiers[1].name == "ガブリアス"
        assert result.tiers[1].effective_speed == 231
        assert result.tiers[2].name == "ペリッパー"
        assert result.tiers[3].name == "モロバレル"

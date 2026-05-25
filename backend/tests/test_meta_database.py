"""MetaDatabase サービスのテスト (Phase 8)"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.meta_database import MetaDatabase, PokemonTemplate


@pytest.fixture
def tmp_data_path(tmp_path: Path) -> str:
    return str(tmp_path / "meta_templates.json")


@pytest.fixture
def sample_templates() -> list[PokemonTemplate]:
    return [
        PokemonTemplate(
            species="ガブリアス",
            archetype_name="スカーフ型",
            ability="さめはだ",
            item="こだわりスカーフ",
            nature="ようき",
            evs={"attack": 252, "speed": 252, "hp": 4},
            moves=["じしん", "げきりん", "ストーンエッジ", "どくづき"],
            usage_rate=0.45,
            tera_type=None,
            can_mega_evolve=False,
            notes="",
        ),
        PokemonTemplate(
            species="ガブリアス",
            archetype_name="タスキ型",
            ability="さめはだ",
            item="きあいのタスキ",
            nature="ようき",
            evs={"attack": 252, "speed": 252, "hp": 4},
            moves=["じしん", "げきりん", "がんせきふうじ", "つるぎのまい"],
            usage_rate=0.30,
            tera_type=None,
            can_mega_evolve=False,
        ),
    ]


@pytest.fixture
def rain_team_templates() -> dict[str, list[PokemonTemplate]]:
    return {
        "ペリッパー": [
            PokemonTemplate(
                species="ペリッパー",
                archetype_name="タスキ型",
                ability="あめふらし",
                item="きあいのタスキ",
                nature="おくびょう",
                evs={"sp_attack": 252, "speed": 252},
                moves=["ぼうふう", "ウェザーボール", "おいかぜ", "まもる"],
                usage_rate=0.20,
            ),
        ],
        "カマスジョー": [
            PokemonTemplate(
                species="カマスジョー",
                archetype_name="珠型",
                ability="すいすい",
                item="いのちのたま",
                nature="ようき",
                evs={"attack": 252, "speed": 252},
                moves=["アクアジェット", "インファイト", "かみくだく", "アクアブレイク"],
                usage_rate=0.15,
            ),
        ],
        "ガブリアス": [
            PokemonTemplate(
                species="ガブリアス",
                archetype_name="スカーフ型",
                ability="さめはだ",
                item="こだわりスカーフ",
                nature="ようき",
                evs={"attack": 252, "speed": 252},
                moves=["じしん", "げきりん", "ストーンエッジ", "どくづき"],
                usage_rate=0.45,
            ),
        ],
        "ミミッキュ": [
            PokemonTemplate(
                species="ミミッキュ",
                archetype_name="珠型",
                ability="ばけのかわ",
                item="いのちのたま",
                nature="ようき",
                evs={"attack": 252, "speed": 252},
                moves=["じゃれつく", "かげうち", "つるぎのまい", "シャドークロー"],
                usage_rate=0.35,
            ),
        ],
        "バンギラス": [
            PokemonTemplate(
                species="バンギラス",
                archetype_name="チョッキ型",
                ability="すなおこし",
                item="とつげきチョッキ",
                nature="いじっぱり",
                evs={"hp": 252, "attack": 252},
                moves=["いわなだれ", "かみくだく", "ばかぢから", "れいとうパンチ"],
                usage_rate=0.25,
            ),
        ],
        "ドリュウズ": [
            PokemonTemplate(
                species="ドリュウズ",
                archetype_name="スカーフ型",
                ability="すなかき",
                item="こだわりスカーフ",
                nature="ようき",
                evs={"attack": 252, "speed": 252},
                moves=["じしん", "アイアンヘッド", "いわなだれ", "つのドリル"],
                usage_rate=0.20,
            ),
        ],
    }


class TestPokemonTemplate:
    def test_to_dict(self, sample_templates: list[PokemonTemplate]):
        t = sample_templates[0]
        d = t.to_dict()
        assert d["species"] == "ガブリアス"
        assert d["archetype_name"] == "スカーフ型"
        assert d["ability"] == "さめはだ"
        assert d["item"] == "こだわりスカーフ"
        assert d["usage_rate"] == 0.45
        assert len(d["moves"]) == 4

    def test_from_dict(self):
        data = {
            "species": "ミミッキュ",
            "archetype_name": "珠型",
            "ability": "ばけのかわ",
            "item": "いのちのたま",
            "moves": ["じゃれつく", "かげうち"],
            "usage_rate": 0.35,
        }
        t = PokemonTemplate.from_dict(data)
        assert t.species == "ミミッキュ"
        assert t.archetype_name == "珠型"
        assert t.usage_rate == 0.35

    def test_from_dict_ignores_extra_keys(self):
        data = {
            "species": "テスト",
            "archetype_name": "型",
            "ability": "特性",
            "item": "持ち物",
            "unknown_key": "should be ignored",
        }
        t = PokemonTemplate.from_dict(data)
        assert t.species == "テスト"
        assert not hasattr(t, "unknown_key")


class TestMetaDatabase:
    def test_init_empty(self, tmp_data_path: str):
        db = MetaDatabase(data_path=tmp_data_path)
        assert len(db.templates) == 0

    def test_save_and_load(self, tmp_data_path: str, sample_templates: list[PokemonTemplate]):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates["ガブリアス"] = sample_templates
        db.save()

        db2 = MetaDatabase(data_path=tmp_data_path)
        assert "ガブリアス" in db2.templates
        assert len(db2.templates["ガブリアス"]) == 2
        assert db2.templates["ガブリアス"][0].archetype_name == "スカーフ型"

    def test_get_templates_sorted_by_usage(
        self, tmp_data_path: str, sample_templates: list[PokemonTemplate]
    ):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates["ガブリアス"] = sample_templates
        result = db.get_templates("ガブリアス")
        assert len(result) == 2
        assert result[0].usage_rate >= result[1].usage_rate

    def test_get_templates_empty(self, tmp_data_path: str):
        db = MetaDatabase(data_path=tmp_data_path)
        result = db.get_templates("存在しない")
        assert result == []

    def test_add_template_new(self, tmp_data_path: str):
        db = MetaDatabase(data_path=tmp_data_path)
        template = PokemonTemplate(
            species="ミミッキュ",
            archetype_name="珠型",
            ability="ばけのかわ",
            item="いのちのたま",
        )
        db.add_template(template)
        assert "ミミッキュ" in db.templates
        assert len(db.templates["ミミッキュ"]) == 1

    def test_add_template_overwrite(
        self, tmp_data_path: str, sample_templates: list[PokemonTemplate]
    ):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates["ガブリアス"] = sample_templates
        updated = PokemonTemplate(
            species="ガブリアス",
            archetype_name="スカーフ型",
            ability="さめはだ",
            item="こだわりスカーフ",
            usage_rate=0.55,
        )
        db.add_template(updated)
        assert len(db.templates["ガブリアス"]) == 2
        scarf = [t for t in db.templates["ガブリアス"] if t.archetype_name == "スカーフ型"]
        assert scarf[0].usage_rate == 0.55

    def test_update_templates(self, tmp_data_path: str):
        db = MetaDatabase(data_path=tmp_data_path)
        new_templates = [
            PokemonTemplate(
                species="テスト",
                archetype_name="型A",
                ability="特性A",
                item="持ち物A",
            ),
        ]
        db.update_templates("テスト", new_templates)
        assert len(db.templates["テスト"]) == 1

    def test_get_usage_ranking(
        self, tmp_data_path: str, rain_team_templates: dict[str, list[PokemonTemplate]]
    ):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates = rain_team_templates
        ranking = db.get_usage_ranking(limit=3)
        assert len(ranking) == 3
        # ランキングはデータの挿入順（外部サイトの使用率順）を保持する
        species_order = [r["species"] for r in ranking]
        expected_order = list(rain_team_templates.keys())[:3]
        assert species_order == expected_order

    def test_get_usage_ranking_empty(self, tmp_data_path: str):
        db = MetaDatabase(data_path=tmp_data_path)
        ranking = db.get_usage_ranking()
        assert ranking == []

    def test_suggest_team_rain(
        self, tmp_data_path: str, rain_team_templates: dict[str, list[PokemonTemplate]]
    ):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates = rain_team_templates
        result = db.suggest_team_composition(
            ["ペリッパー", "カマスジョー", "ガブリアス", "ミミッキュ", "バンギラス", "ドリュウズ"]
        )
        assert "雨" in result["archetype"] or "砂" in result["archetype"]
        assert len(result["key_pokemon"]) > 0
        assert len(result["threats"]) > 0
        assert "ペリッパー" in result["pokemon_details"]

    def test_suggest_team_standard(
        self, tmp_data_path: str, sample_templates: list[PokemonTemplate]
    ):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates["ガブリアス"] = sample_templates
        result = db.suggest_team_composition(["ガブリアス"])
        assert result["archetype"] == "スタン"
        assert "ガブリアス" in result["pokemon_details"]

    def test_suggest_team_unknown_pokemon(self, tmp_data_path: str):
        db = MetaDatabase(data_path=tmp_data_path)
        result = db.suggest_team_composition(["未知のポケモン"])
        assert result["archetype"] == "スタン"
        assert result["pokemon_details"]["未知のポケモン"] == []

    def test_suggest_team_scarf_threat(
        self, tmp_data_path: str, sample_templates: list[PokemonTemplate]
    ):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates["ガブリアス"] = sample_templates
        result = db.suggest_team_composition(["ガブリアス"])
        scarf_threats = [t for t in result["threats"] if "スカーフ" in t]
        assert len(scarf_threats) > 0

    def test_json_persistence_roundtrip(
        self, tmp_data_path: str, sample_templates: list[PokemonTemplate]
    ):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates["ガブリアス"] = sample_templates
        db.save()

        raw = json.loads(Path(tmp_data_path).read_text(encoding="utf-8"))
        assert "last_updated" in raw
        assert "pokemon" in raw
        assert "ガブリアス" in raw["pokemon"]
        assert len(raw["pokemon"]["ガブリアス"]) == 2

    def test_load_corrupted_json(self, tmp_data_path: str):
        Path(tmp_data_path).parent.mkdir(parents=True, exist_ok=True)
        Path(tmp_data_path).write_text("invalid json", encoding="utf-8")
        db = MetaDatabase(data_path=tmp_data_path)
        assert len(db.templates) == 0

    def test_determine_archetype_weather_combinations(
        self, tmp_data_path: str, rain_team_templates: dict[str, list[PokemonTemplate]]
    ):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates = rain_team_templates
        result = db.suggest_team_composition(
            ["ペリッパー", "カマスジョー", "バンギラス", "ドリュウズ", "ガブリアス", "ミミッキュ"]
        )
        # 雨+砂の複合構築を検出
        archetype = result["archetype"]
        assert "雨" in archetype or "砂" in archetype

    def test_suggest_team_mega_detection(self, tmp_data_path: str):
        db = MetaDatabase(data_path=tmp_data_path)
        db.templates["リザードン"] = [
            PokemonTemplate(
                species="リザードン",
                archetype_name="メガY型",
                ability="もうか",
                item="リザードナイトY",
                moves=["ねっぷう", "エアスラッシュ", "まもる", "りゅうのはどう"],
                usage_rate=0.40,
                can_mega_evolve=True,
            ),
        ]
        result = db.suggest_team_composition(["リザードン"])
        mega_keys = [kp for kp in result["key_pokemon"] if "メガシンカ" in kp["role"]]
        assert len(mega_keys) > 0

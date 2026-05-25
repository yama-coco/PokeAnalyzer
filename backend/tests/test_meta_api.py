"""メタゲーム型検索 API のテスト (Phase 8)"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.meta_database import PokemonTemplate, meta_database

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_meta_database():
    """各テスト前にメタデータベースをリセットする。"""
    original = dict(meta_database.templates)
    original_updated = meta_database.last_updated
    meta_database.templates.clear()
    meta_database.last_updated = ""
    yield
    meta_database.templates.clear()
    meta_database.templates.update(original)
    meta_database.last_updated = original_updated


@pytest.fixture
def _populate_meta():
    """テスト用にメタデータを投入する。"""
    meta_database.templates["ガブリアス"] = [
        PokemonTemplate(
            species="ガブリアス",
            archetype_name="スカーフ型",
            ability="さめはだ",
            item="こだわりスカーフ",
            nature="ようき",
            evs={"attack": 252, "speed": 252, "hp": 4},
            moves=["じしん", "げきりん", "ストーンエッジ", "どくづき"],
            usage_rate=0.45,
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
        ),
    ]
    meta_database.templates["ペリッパー"] = [
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
    ]
    meta_database.templates["カマスジョー"] = [
        PokemonTemplate(
            species="カマスジョー",
            archetype_name="珠型",
            ability="すいすい",
            item="いのちのたま",
            nature="ようき",
            evs={"attack": 252, "speed": 252},
            moves=["アクアブレイク", "インファイト", "かみくだく", "アクアジェット"],
            usage_rate=0.15,
        ),
    ]


class TestGetPokemonTemplates:
    def test_empty(self):
        res = client.get("/api/meta/pokemon/ガブリアス")
        assert res.status_code == 200
        assert res.json() == []

    @pytest.mark.usefixtures("_populate_meta")
    def test_found(self):
        res = client.get("/api/meta/pokemon/ガブリアス")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        assert data[0]["archetype_name"] == "スカーフ型"
        assert data[0]["usage_rate"] >= data[1]["usage_rate"]

    @pytest.mark.usefixtures("_populate_meta")
    def test_not_found(self):
        res = client.get("/api/meta/pokemon/未登録ポケモン")
        assert res.status_code == 200
        assert res.json() == []


class TestAnalyzeTeam:
    @pytest.mark.usefixtures("_populate_meta")
    def test_rain_team(self):
        res = client.post(
            "/api/meta/analyze-team",
            json={"enemy_species": ["ペリッパー", "カマスジョー", "ガブリアス"]},
        )
        assert res.status_code == 200
        data = res.json()
        assert "archetype" in data
        assert "key_pokemon" in data
        assert "threats" in data
        assert "pokemon_details" in data
        assert "ペリッパー" in data["pokemon_details"]

    @pytest.mark.usefixtures("_populate_meta")
    def test_standard_team(self):
        res = client.post(
            "/api/meta/analyze-team",
            json={"enemy_species": ["ガブリアス"]},
        )
        assert res.status_code == 200
        data = res.json()
        assert "ガブリアス" in data["pokemon_details"]

    def test_unknown_pokemon(self):
        res = client.post(
            "/api/meta/analyze-team",
            json={"enemy_species": ["未知のポケモン"]},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["archetype"] == "スタン"
        assert data["pokemon_details"]["未知のポケモン"] == []

    def test_empty_request(self):
        res = client.post(
            "/api/meta/analyze-team",
            json={"enemy_species": []},
        )
        assert res.status_code == 422

    def test_too_many_pokemon(self):
        res = client.post(
            "/api/meta/analyze-team",
            json={"enemy_species": ["a", "b", "c", "d", "e", "f", "g"]},
        )
        assert res.status_code == 422


class TestUpdateMeta:
    def test_update(self):
        res = client.post(
            "/api/meta/update",
            json={
                "species": "テストポケモン",
                "templates": [
                    {
                        "species": "テストポケモン",
                        "archetype_name": "テスト型",
                        "ability": "テスト特性",
                        "item": "テスト持ち物",
                        "nature": "ようき",
                        "evs": {"attack": 252},
                        "moves": ["テスト技"],
                        "usage_rate": 0.5,
                        "tera_type": None,
                        "can_mega_evolve": False,
                        "notes": "",
                        "source_url": "",
                    }
                ],
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["species"] == "テストポケモン"
        assert data["template_count"] == 1

        verify = client.get("/api/meta/pokemon/テストポケモン")
        assert len(verify.json()) == 1


class TestUsageRanking:
    def test_empty(self):
        res = client.get("/api/meta/usage-ranking")
        assert res.status_code == 200
        data = res.json()
        assert data["ranking"] == []
        assert data["total_pokemon"] == 0

    @pytest.mark.usefixtures("_populate_meta")
    def test_ranking(self):
        res = client.get("/api/meta/usage-ranking")
        assert res.status_code == 200
        data = res.json()
        assert len(data["ranking"]) == 3
        assert data["ranking"][0]["rank"] == 1
        assert data["total_pokemon"] == 3
        rates = [e["usage_rate"] for e in data["ranking"]]
        assert rates == sorted(rates, reverse=True)

    @pytest.mark.usefixtures("_populate_meta")
    def test_ranking_limit(self):
        res = client.get("/api/meta/usage-ranking?limit=1")
        assert res.status_code == 200
        data = res.json()
        assert len(data["ranking"]) == 1

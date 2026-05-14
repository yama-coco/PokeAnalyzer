"""Battle API エンドポイントのテスト (Phase 3)"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def started_match(client: TestClient):
    """試合を開始済みの状態を作る。"""
    client.post(
        "/api/battle/match/start",
        json={
            "ally_team": ["ガブリアス", "ニンフィア", "リキキリン", "ミロカロス"],
            "enemy_team": ["バンギラス", "カイリュー", "ヤレユータン", "ドリュウズ"],
        },
    )
    client.post(
        "/api/battle/match/selection",
        json={
            "ally_leads": ["ガブリアス", "ニンフィア"],
            "enemy_leads": ["バンギラス", "カイリュー"],
        },
    )
    client.post(
        "/api/battle/match/battle-start",
        json={
            "pokemon_on_field": [
                {
                    "slot": 0,
                    "name": "ガブリアス",
                    "ability": "さめはだ",
                    "item": "きあいのタスキ",
                    "base_speed": 102,
                    "current_hp": 183,
                    "max_hp": 183,
                    "side": "ally",
                },
                {
                    "slot": 1,
                    "name": "ニンフィア",
                    "ability": "フェアリースキン",
                    "item": "こだわりメガネ",
                    "base_speed": 60,
                    "current_hp": 201,
                    "max_hp": 201,
                    "side": "ally",
                },
                {
                    "slot": 2,
                    "name": "バンギラス",
                    "ability": "すなおこし",
                    "base_speed": 61,
                    "hp_percent": 100.0,
                    "side": "enemy",
                },
                {
                    "slot": 3,
                    "name": "カイリュー",
                    "ability": "マルチスケイル",
                    "base_speed": 80,
                    "hp_percent": 100.0,
                    "side": "enemy",
                },
            ]
        },
    )


class TestMatchLifecycleAPI:
    def test_start_match(self, client: TestClient):
        resp = client.post(
            "/api/battle/match/start",
            json={
                "ally_team": ["ガブリアス", "ニンフィア"],
                "enemy_team": ["バンギラス", "カイリュー"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "team_preview"
        assert len(data["ally_team"]) == 2

    def test_set_selection(self, client: TestClient):
        client.post("/api/battle/match/start", json={"ally_team": [], "enemy_team": []})
        resp = client.post(
            "/api/battle/match/selection",
            json={"ally_leads": ["ガブリアス", "ニンフィア"]},
        )
        assert resp.status_code == 200
        assert resp.json()["phase"] == "selection"

    def test_get_match_state(self, client: TestClient, started_match):
        resp = client.get("/api/battle/match/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "in_battle"
        assert len(data["pokemon_on_field"]) == 4

    def test_end_match(self, client: TestClient, started_match):
        resp = client.post("/api/battle/match/end?result=win")
        assert resp.status_code == 200
        assert resp.json()["result"] == "win"
        assert resp.json()["phase"] == "finished"


class TestSpeedOrderAPI:
    def test_get_speed_order(self, client: TestClient, started_match):
        resp = client.get("/api/battle/match/speed-order")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["speed_order"]) == 4
        # ガブリアス(102) が最速
        assert data["speed_order"][0]["name"] == "ガブリアス"

    def test_speed_order_with_trick_room(self, client: TestClient, started_match):
        client.put(
            "/api/battle/match/field",
            json={"trick_room": True},
        )
        resp = client.get("/api/battle/match/speed-order")
        data = resp.json()
        assert data["trick_room"] is True
        # トリルで反転: ニンフィア(60) が最速
        assert data["speed_order"][0]["name"] == "ニンフィア"


class TestFieldUpdateAPI:
    def test_update_weather(self, client: TestClient, started_match):
        resp = client.put(
            "/api/battle/match/field",
            json={"weather": "rain"},
        )
        assert resp.status_code == 200
        assert resp.json()["field_state"]["weather"] == "rain"

    def test_invalid_weather(self, client: TestClient, started_match):
        resp = client.put(
            "/api/battle/match/field",
            json={"weather": "invalid"},
        )
        assert resp.status_code == 400

    def test_update_tailwind(self, client: TestClient, started_match):
        resp = client.put(
            "/api/battle/match/field",
            json={"tailwind_ally": True},
        )
        assert resp.status_code == 200
        assert resp.json()["field_state"]["tailwind_ally"] is True
        # 速度順も変わっている
        speed_order = resp.json()["speed_order"]
        gabby = next(s for s in speed_order if s["name"] == "ガブリアス")
        assert gabby["effective_speed"] == 204  # 102 × 2


class TestHPUpdateAPI:
    def test_update_ally_hp(self, client: TestClient, started_match):
        resp = client.put(
            "/api/battle/hp/update",
            json={"slot": 0, "current_hp": 149, "max_hp": 183},
        )
        assert resp.status_code == 200

    def test_update_enemy_hp_percent(self, client: TestClient, started_match):
        resp = client.put(
            "/api/battle/hp/update",
            json={"slot": 2, "hp_percent": 73.0},
        )
        assert resp.status_code == 200

    def test_get_hp_state(self, client: TestClient, started_match):
        client.put(
            "/api/battle/hp/update",
            json={"slot": 0, "current_hp": 183, "max_hp": 183},
        )
        resp = client.get("/api/battle/hp/state")
        assert resp.status_code == 200

    def test_damage_history(self, client: TestClient, started_match):
        client.put(
            "/api/battle/hp/update",
            json={"slot": 2, "hp_percent": 100.0},
        )
        client.put(
            "/api/battle/hp/update",
            json={"slot": 2, "hp_percent": 73.0},
        )
        resp = client.get("/api/battle/hp/damage-history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1


class TestDamageCalcAPI:
    def test_calc_damage(self, client: TestClient):
        resp = client.post(
            "/api/battle/damage/calc",
            json={
                "move_name": "じしん",
                "move_power": 100,
                "move_category": "physical",
                "is_spread": True,
                "attacker_name": "ガブリアス",
                "attacker_stat": 182,
                "has_stab": True,
                "type_effectiveness": 1.0,
                "defender_name": "バンギラス",
                "defender_stat": 130,
                "defender_max_hp": 207,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_damage"] > 0
        assert data["max_damage"] >= data["min_damage"]

    def test_estimate_hp_ev(self, client: TestClient):
        resp = client.post(
            "/api/battle/damage/estimate-hp-ev?species_base_hp=108&observed_max_hp=183"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "min_ev" in data
        assert "max_ev" in data


class TestProtectAPI:
    def test_record_protect(self, client: TestClient, started_match):
        resp = client.post(
            "/api/battle/protect/record",
            json={
                "pokemon_name": "バンギラス",
                "move_name": "まもる",
                "turn": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["consecutive_uses"] == 1
        assert data["next_success_rate"] == pytest.approx(33.3, abs=0.1)

    def test_get_protect_state(self, client: TestClient, started_match):
        client.post(
            "/api/battle/protect/record",
            json={"pokemon_name": "バンギラス", "move_name": "まもる", "turn": 1},
        )
        resp = client.get("/api/battle/protect/state")
        assert resp.status_code == 200
        assert "バンギラス" in resp.json()

    def test_get_pokemon_protect(self, client: TestClient, started_match):
        client.post(
            "/api/battle/protect/record",
            json={"pokemon_name": "バンギラス", "move_name": "まもる", "turn": 1},
        )
        resp = client.get("/api/battle/protect/バンギラス")
        assert resp.status_code == 200
        assert resp.json()["name"] == "バンギラス"

    def test_unknown_pokemon_protect(self, client: TestClient, started_match):
        resp = client.get("/api/battle/protect/未登録")
        assert resp.status_code == 200
        assert resp.json()["next_success_rate"] == 100.0


class TestTurnLogAPI:
    def test_log_action(self, client: TestClient, started_match):
        resp = client.post(
            "/api/battle/log/action",
            json={
                "turn": 1,
                "pokemon_slot": 0,
                "pokemon_name": "ガブリアス",
                "action_type": "move",
                "action_name": "じしん",
                "target_slot": 2,
                "target_name": "バンギラス",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["action_name"] == "じしん"

    def test_log_invalid_action_type(self, client: TestClient, started_match):
        resp = client.post(
            "/api/battle/log/action",
            json={
                "turn": 1,
                "pokemon_slot": 0,
                "pokemon_name": "ガブリアス",
                "action_type": "invalid",
                "action_name": "???",
            },
        )
        assert resp.status_code == 400

    def test_log_protect_auto_records(self, client: TestClient, started_match):
        client.post(
            "/api/battle/log/action",
            json={
                "turn": 1,
                "pokemon_slot": 2,
                "pokemon_name": "バンギラス",
                "action_type": "move",
                "action_name": "まもる",
            },
        )
        resp = client.get("/api/battle/protect/バンギラス")
        assert resp.json()["total_uses"] == 1

    def test_commit_turn(self, client: TestClient, started_match):
        client.post(
            "/api/battle/log/action",
            json={
                "turn": 1,
                "pokemon_slot": 0,
                "pokemon_name": "ガブリアス",
                "action_type": "move",
                "action_name": "じしん",
            },
        )
        resp = client.post("/api/battle/log/commit-turn?turn=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["turn"] == 1
        assert len(data["speed_order"]) == 4

    def test_get_all_logs(self, client: TestClient, started_match):
        client.post(
            "/api/battle/log/action",
            json={
                "turn": 1,
                "pokemon_slot": 0,
                "pokemon_name": "ガブリアス",
                "action_type": "move",
                "action_name": "じしん",
            },
        )
        client.post("/api/battle/log/commit-turn?turn=1")
        resp = client.get("/api/battle/log/all")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_turn_log(self, client: TestClient, started_match):
        client.post(
            "/api/battle/log/action",
            json={
                "turn": 1,
                "pokemon_slot": 0,
                "pokemon_name": "ガブリアス",
                "action_type": "move",
                "action_name": "じしん",
            },
        )
        client.post("/api/battle/log/commit-turn?turn=1")
        resp = client.get("/api/battle/log/turn/1")
        assert resp.status_code == 200

    def test_get_nonexistent_turn(self, client: TestClient, started_match):
        resp = client.get("/api/battle/log/turn/99")
        assert resp.status_code == 404


class TestAdvanceTurn:
    def test_advance_turn(self, client: TestClient, started_match):
        resp = client.post(
            "/api/battle/match/advance-turn",
            json={"actions": [{"pokemon": "ガブリアス", "move": "じしん"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["turn_record"]["turn"] == 1
        assert data["current_turn"] == 2


class TestPhase1Regression:
    """Phase 1 の素早さ計算APIが引き続き動作することを確認。"""

    def test_speed_tiers_still_works(self, client: TestClient):
        resp = client.post(
            "/api/battle/speed-tiers",
            json={
                "pokemon": [
                    {"name": "ガブリアス", "base_speed": 102, "slot": 0},
                    {"name": "ニンフィア", "base_speed": 60, "slot": 1},
                    {"name": "バンギラス", "base_speed": 61, "slot": 2},
                    {"name": "カイリュー", "base_speed": 80, "slot": 3},
                ],
                "field": {"trick_room": False},
            },
        )
        assert resp.status_code == 200
        tiers = resp.json()["tiers"]
        assert tiers[0]["name"] == "ガブリアス"

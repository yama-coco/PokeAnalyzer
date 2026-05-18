"""パーティ登録 API のテスト"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)

SAMPLE_POKEMON = {
    "species": "ガブリアス",
    "ability": "さめはだ",
    "item": "こだわりスカーフ",
    "moves": ["じしん", "げきりん", "がんせきふうじ", "ほのおのキバ"],
    "stats": {
        "hp": 183,
        "attack": 200,
        "defense": 115,
        "sp_attack": 90,
        "sp_defense": 105,
        "speed": 154,
    },
    "tera_type": "じめん",
    "can_mega_evolve": False,
}

SAMPLE_PARTY = {
    "name": "テストパーティ",
    "pokemon": [SAMPLE_POKEMON],
}


class TestPartyAPI:
    def test_create_party(self):
        response = client.post("/api/parties/", json=SAMPLE_PARTY)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "テストパーティ"
        assert len(data["pokemon"]) == 1
        assert data["pokemon"][0]["species"] == "ガブリアス"
        assert data["id"] is not None

    def test_list_parties(self):
        client.post("/api/parties/", json=SAMPLE_PARTY)
        client.post("/api/parties/", json={**SAMPLE_PARTY, "name": "パーティ2"})
        response = client.get("/api/parties/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_party(self):
        create_resp = client.post("/api/parties/", json=SAMPLE_PARTY)
        party_id = create_resp.json()["id"]
        response = client.get(f"/api/parties/{party_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "テストパーティ"

    def test_get_party_not_found(self):
        response = client.get("/api/parties/9999")
        assert response.status_code == 404

    def test_update_party(self):
        create_resp = client.post("/api/parties/", json=SAMPLE_PARTY)
        party_id = create_resp.json()["id"]
        response = client.put(f"/api/parties/{party_id}", json={"name": "新しい名前"})
        assert response.status_code == 200
        assert response.json()["name"] == "新しい名前"

    def test_delete_party(self):
        create_resp = client.post("/api/parties/", json=SAMPLE_PARTY)
        party_id = create_resp.json()["id"]
        response = client.delete(f"/api/parties/{party_id}")
        assert response.status_code == 204
        get_resp = client.get(f"/api/parties/{party_id}")
        assert get_resp.status_code == 404

    def test_create_party_validation_max_6(self):
        pokemon_7 = [SAMPLE_POKEMON] * 7
        response = client.post("/api/parties/", json={"name": "7体パーティ", "pokemon": pokemon_7})
        assert response.status_code == 422

    def test_create_party_empty_name(self):
        response = client.post("/api/parties/", json={"name": "", "pokemon": [SAMPLE_POKEMON]})
        assert response.status_code == 422


class TestSpeedTierAPI:
    def test_speed_tier_calculation(self):
        body = {
            "pokemon": [
                {"name": "ガブリアス", "base_speed": 154, "slot": 0, "item": "こだわりスカーフ"},
                {"name": "モロバレル", "base_speed": 30, "slot": 1},
            ],
            "field": {},
        }
        response = client.post("/api/battle/speed-tiers", json=body)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tiers"]) == 2
        assert data["tiers"][0]["name"] == "ガブリアス"
        assert data["tiers"][0]["effective_speed"] == 231  # 154 * 1.5

    def test_trick_room_scenario(self):
        body = {
            "pokemon": [
                {"name": "速い", "base_speed": 150, "slot": 0},
                {"name": "遅い", "base_speed": 30, "slot": 1},
            ],
            "field": {"trick_room": True},
        }
        response = client.post("/api/battle/speed-tiers", json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["trick_room_active"] is True
        assert data["tiers"][0]["name"] == "遅い"


class TestHealthEndpoint:
    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "PAL-C"

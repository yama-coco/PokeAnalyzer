"""Vision APIエンドポイントのテスト。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestVisionAPI:
    def test_get_vision_status(self):
        response = client.get("/api/vision/status")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False
        assert data["scene_state"] == "idle"
        assert "components" in data

    def test_get_scene_state(self):
        response = client.get("/api/vision/scene")
        assert response.status_code == 200
        data = response.json()
        assert data["current_state"] == "idle"
        assert "confidence" in data
        assert "history" in data

    def test_get_components_status(self):
        response = client.get("/api/vision/components")
        assert response.status_code == 200
        data = response.json()
        assert "ocr_available" in data
        assert "yolo_available" in data
        assert "template_count" in data

    def test_control_start(self):
        response = client.post(
            "/api/vision/control",
            json={"action": "start"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        # Clean up
        client.post("/api/vision/control", json={"action": "stop"})

    def test_control_stop(self):
        # Start first
        client.post("/api/vision/control", json={"action": "start"})
        response = client.post(
            "/api/vision/control",
            json={"action": "stop"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False

    def test_force_scene_transition(self):
        response = client.post(
            "/api/vision/scene/force",
            params={"state": "matching"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "matching"

        # Reset
        client.post("/api/vision/scene/force", params={"state": "idle"})

    def test_force_scene_invalid_state(self):
        response = client.post(
            "/api/vision/scene/force",
            params={"state": "invalid_state"},
        )
        assert response.status_code == 400

    def test_analyze_frame_no_image(self):
        """画像なし・OBSキャプチャなしの場合は400を返す。"""
        response = client.post("/api/vision/analyze-frame")
        assert response.status_code == 400

    def test_existing_endpoints_still_work(self):
        """Phase 1のエンドポイントが引き続き動作すること。"""
        # Health check
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        # Root
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "PAL-C"

        # OBS status
        response = client.get("/api/obs/status")
        assert response.status_code == 200

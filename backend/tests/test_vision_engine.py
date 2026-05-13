"""Vision Engineの統合テスト。"""

import numpy as np
import pytest

from app.services.vision_engine import VisionEngine, VisionState


def _make_frame(w: int = 1920, h: int = 1080, color: tuple = (128, 128, 128)) -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = color
    return frame


class TestVisionState:
    def test_default_state(self):
        state = VisionState()
        assert not state.running
        assert state.fps == 0.0
        assert state.total_frames == 0
        assert state.detected_pokemon == []

    def test_to_dict(self):
        state = VisionState()
        d = state.to_dict()
        assert d["running"] is False
        assert d["scene"]["state"] == "idle"
        assert d["fps"] == 0.0
        assert d["detected_pokemon"] == []


class TestVisionEngine:
    def test_initialization(self):
        engine = VisionEngine()
        assert not engine.is_running
        assert engine.scene_state.value == "idle"

    def test_components_status(self):
        engine = VisionEngine()
        status = engine.components_status
        assert "ocr_available" in status
        assert "yolo_available" in status
        assert "template_count" in status
        assert "scene_state" in status
        assert status["scene_state"] == "idle"

    @pytest.mark.asyncio
    async def test_analyze_single_frame(self):
        engine = VisionEngine()
        frame = _make_frame()
        result = await engine.analyze_single_frame(frame)
        assert isinstance(result, dict)
        assert "running" in result
        assert "scene" in result

    @pytest.mark.asyncio
    async def test_analyze_frame_increments_counter(self):
        engine = VisionEngine()
        frame = _make_frame()
        await engine.analyze_single_frame(frame)
        assert engine.state.total_frames == 1
        await engine.analyze_single_frame(frame)
        assert engine.state.total_frames == 2

    @pytest.mark.asyncio
    async def test_analyze_different_frames(self):
        engine = VisionEngine()
        frame1 = _make_frame(color=(0, 0, 0))
        frame2 = _make_frame(color=(255, 255, 255))
        await engine.analyze_single_frame(frame1)
        await engine.analyze_single_frame(frame2)
        assert engine.state.total_frames == 2

    def test_state_not_running_initially(self):
        engine = VisionEngine()
        assert not engine.state.running

    def test_websocket_client_management(self):
        engine = VisionEngine()

        # Mock WebSocket
        class MockWS:
            pass

        ws = MockWS()
        engine.add_client(ws)
        assert len(engine._clients) == 1
        engine.remove_client(ws)
        assert len(engine._clients) == 0

    def test_count_edges(self):
        # Black frame → 0 edges
        black = np.zeros((100, 100, 3), dtype=np.uint8)
        assert VisionEngine._count_edges(black) == 0

        # Frame with sharp edges
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[40:60, 40:60] = (255, 255, 255)
        edge_count = VisionEngine._count_edges(frame)
        assert edge_count > 0

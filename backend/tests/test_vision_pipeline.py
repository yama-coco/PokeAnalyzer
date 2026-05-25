"""Vision Pipeline (Phase 5) のテスト。

OBS仮想カメラ → Vision Engine のリアルタイム連携パイプラインのテスト。
- パイプラインのライフサイクル (start/stop)
- OBS未接続時のgraceful degradation
- フレーム取得→解析の結合テスト
- APIエンドポイントのテスト
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import OBSCaptureStatus
from app.services.battle_state import BattlePhase
from app.services.obs_connector import OBSConnector
from app.services.scene_state import SceneState
from app.services.vision_engine import VisionEngine
from app.services.vision_pipeline import PipelineStats, VisionPipeline

client = TestClient(app)


def _make_frame(w: int = 1920, h: int = 1080, color: tuple = (128, 128, 128)) -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = color
    return frame


class TestPipelineStats:
    def test_default_stats(self):
        stats = PipelineStats()
        assert stats.total_frames_fed == 0
        assert stats.total_frames_processed == 0
        assert stats.total_events_dispatched == 0
        assert stats.pipeline_fps == 0.0

    def test_record_frame(self):
        stats = PipelineStats()
        stats.record_frame()
        assert stats.total_frames_fed == 1
        assert stats.last_frame_at > 0

    def test_to_dict(self):
        stats = PipelineStats()
        d = stats.to_dict()
        assert "total_frames_fed" in d
        assert "total_frames_processed" in d
        assert "pipeline_fps" in d
        assert "capture_errors" in d

    def test_fps_calculation(self):
        stats = PipelineStats()
        stats.record_frame()
        stats.record_frame()
        d = stats.to_dict()
        assert isinstance(d["pipeline_fps"], float)


class TestVisionPipelineInit:
    def test_default_initialization(self):
        pipeline = VisionPipeline()
        assert not pipeline.is_running
        assert pipeline.target_fps == 5
        assert pipeline.device_index == 0

    def test_custom_initialization(self):
        engine = VisionEngine()
        obs = OBSConnector()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=obs)
        assert not pipeline.is_running

    def test_initial_stats(self):
        pipeline = VisionPipeline()
        stats = pipeline.stats
        assert stats.total_frames_fed == 0


class TestVisionPipelineStart:
    @pytest.mark.asyncio
    async def test_start_with_obs_unavailable(self):
        """OBS仮想カメラが未接続時のgraceful degradation。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(active=False)
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(active=False)

        pipeline = VisionPipeline(obs_conn=mock_obs)
        result = await pipeline.start()

        assert result["running"] is False
        assert "error" in result
        assert not pipeline.is_running

    @pytest.mark.asyncio
    async def test_start_with_obs_connected(self):
        """OBS仮想カメラ接続時にパイプラインが正常に開始される。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.read_frame_async = AsyncMock(return_value=None)
        mock_obs.stop_capture = MagicMock()

        engine = VisionEngine()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)

        result = await pipeline.start()
        assert result["running"] is True
        assert pipeline.is_running

        # Clean up
        await pipeline.stop()
        assert not pipeline.is_running

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """既に実行中のパイプラインに対するstart呼び出し。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.read_frame_async = AsyncMock(return_value=None)
        mock_obs.stop_capture = MagicMock()

        engine = VisionEngine()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)

        await pipeline.start()
        result = await pipeline.start()  # Second start
        assert result["running"] is True

        await pipeline.stop()

    @pytest.mark.asyncio
    async def test_start_with_custom_params(self):
        """カスタムパラメータでのパイプライン開始。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.read_frame_async = AsyncMock(return_value=None)
        mock_obs.stop_capture = MagicMock()

        engine = VisionEngine()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)

        result = await pipeline.start(
            device_index=1,
            target_fps=10,
            scene_confidence_threshold=0.8,
            noise_frame_count=5,
        )
        assert result["running"] is True
        assert pipeline.target_fps == 10
        assert pipeline.device_index == 1

        await pipeline.stop()

    @pytest.mark.asyncio
    async def test_start_clamps_fps(self):
        """FPSが有効範囲にクランプされる。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.read_frame_async = AsyncMock(return_value=None)
        mock_obs.stop_capture = MagicMock()

        engine = VisionEngine()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)

        await pipeline.start(target_fps=100)
        assert pipeline.target_fps == 30

        await pipeline.stop()


class TestVisionPipelineStop:
    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """未実行のパイプラインに対するstop呼び出し。"""
        pipeline = VisionPipeline()
        result = await pipeline.stop()
        assert result["running"] is False

    @pytest.mark.asyncio
    async def test_stop_running_pipeline(self):
        """実行中のパイプラインを正常に停止。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(active=False)
        mock_obs.read_frame_async = AsyncMock(return_value=None)
        mock_obs.stop_capture = MagicMock()

        engine = VisionEngine()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)

        await pipeline.start()
        assert pipeline.is_running

        result = await pipeline.stop()
        assert result["running"] is False
        assert not pipeline.is_running
        mock_obs.stop_capture.assert_called()


class TestVisionPipelineStatus:
    def test_get_status_not_running(self):
        """未実行時のステータス取得。"""
        pipeline = VisionPipeline()
        status = pipeline.get_status()
        assert status["running"] is False
        assert "capture" in status
        assert "vision" in status
        assert "stats" in status
        assert "components" in status

    @pytest.mark.asyncio
    async def test_get_status_running(self):
        """実行中のステータス取得。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.read_frame_async = AsyncMock(return_value=None)
        mock_obs.stop_capture = MagicMock()

        engine = VisionEngine()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)

        await pipeline.start()
        status = pipeline.get_status()
        assert status["running"] is True
        assert status["capture"]["active"] is True
        assert status["target_fps"] == 5
        assert status["device_index"] == 0

        await pipeline.stop()


class TestVisionPipelineSceneDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_matching_start(self):
        """MATCHING開始イベントの正常処理。"""
        mock_obs = MagicMock(spec=OBSConnector)
        engine = MagicMock(spec=VisionEngine)
        engine.scene_state = SceneState.MATCHING

        mock_state = MagicMock()
        mock_state.detected_pokemon = ["ガブリアス", "バンギラス"]
        mock_state.running = False
        mock_state.scene.state.value = "matching"
        mock_state.scene.confidence = 0.8
        mock_state.fps = 0.0
        mock_state.total_frames = 0
        mock_state.last_text_analysis = {}
        engine.state = mock_state
        engine.components_status = {
            "ocr_available": False,
            "yolo_available": False,
            "template_count": 0,
            "scene_state": "matching",
        }

        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)
        pipeline._previous_scene = SceneState.IDLE

        with patch(
            "app.services.vision_pipeline.battle_state_manager"
        ) as mock_bsm:
            await pipeline._dispatch_scene_events()
            mock_bsm.start_match.assert_called_once_with(
                enemy_team=["ガブリアス", "バンギラス"]
            )

    @pytest.mark.asyncio
    async def test_dispatch_battle_start(self):
        """BATTLE開始イベントの正常処理。"""
        mock_obs = MagicMock(spec=OBSConnector)
        engine = MagicMock(spec=VisionEngine)
        engine.scene_state = SceneState.BATTLE

        mock_state = MagicMock()
        mock_state.detected_pokemon = []
        mock_state.detected_moves = []
        mock_state.detected_abilities = []
        mock_state.running = False
        mock_state.scene.state.value = "battle"
        mock_state.scene.confidence = 0.9
        mock_state.fps = 0.0
        mock_state.total_frames = 0
        engine.state = mock_state
        engine.components_status = {}

        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)
        pipeline._previous_scene = SceneState.SELECTION

        with (
            patch(
                "app.services.vision_pipeline.battle_state_manager"
            ) as mock_bsm,
            patch(
                "app.services.vision_pipeline.turn_logger"
            ) as mock_tl,
            patch(
                "app.services.vision_pipeline.hp_tracker"
            ) as mock_hp,
        ):
            mock_bsm.match.phase = BattlePhase.TEAM_PREVIEW
            mock_bsm.match.match_id = "test_match"
            await pipeline._dispatch_scene_events()
            mock_bsm.start_battle.assert_called_once()
            mock_tl.start_match.assert_called_once()
            mock_hp.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_result_win(self):
        """RESULT (勝利) イベントの正常処理。"""
        mock_obs = MagicMock(spec=OBSConnector)
        engine = MagicMock(spec=VisionEngine)
        engine.scene_state = SceneState.RESULT

        mock_state = MagicMock()
        mock_state.detected_pokemon = []
        mock_state.running = False
        mock_state.scene.state.value = "result"
        mock_state.scene.confidence = 0.9
        mock_state.fps = 0.0
        mock_state.total_frames = 0
        mock_state.last_text_analysis = {"result_text": "あなたのかちです"}
        engine.state = mock_state
        engine.components_status = {}

        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)
        pipeline._previous_scene = SceneState.BATTLE

        with patch(
            "app.services.vision_pipeline.battle_state_manager"
        ) as mock_bsm:
            await pipeline._dispatch_scene_events()
            mock_bsm.end_match.assert_called_once_with(result="win")

    @pytest.mark.asyncio
    async def test_dispatch_result_loss(self):
        """RESULT (敗北) イベントの正常処理。"""
        mock_obs = MagicMock(spec=OBSConnector)
        engine = MagicMock(spec=VisionEngine)
        engine.scene_state = SceneState.RESULT

        mock_state = MagicMock()
        mock_state.detected_pokemon = []
        mock_state.running = False
        mock_state.scene.state.value = "result"
        mock_state.scene.confidence = 0.9
        mock_state.fps = 0.0
        mock_state.total_frames = 0
        mock_state.last_text_analysis = {"result_text": "あなたのまけです"}
        engine.state = mock_state
        engine.components_status = {}

        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)
        pipeline._previous_scene = SceneState.BATTLE

        with patch(
            "app.services.vision_pipeline.battle_state_manager"
        ) as mock_bsm:
            await pipeline._dispatch_scene_events()
            mock_bsm.end_match.assert_called_once_with(result="loss")

    @pytest.mark.asyncio
    async def test_dispatch_return_to_idle(self):
        """IDLE復帰イベントの正常処理。"""
        mock_obs = MagicMock(spec=OBSConnector)
        engine = MagicMock(spec=VisionEngine)
        engine.scene_state = SceneState.IDLE

        mock_state = MagicMock()
        mock_state.detected_pokemon = []
        mock_state.detected_moves = []
        mock_state.detected_abilities = []
        mock_state.running = False
        mock_state.scene.state.value = "idle"
        mock_state.scene.confidence = 1.0
        mock_state.fps = 0.0
        mock_state.total_frames = 0
        engine.state = mock_state
        engine.components_status = {}

        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)
        pipeline._previous_scene = SceneState.RESULT

        with (
            patch(
                "app.services.vision_pipeline.battle_state_manager"
            ) as mock_bsm,
            patch(
                "app.services.vision_pipeline.turn_logger"
            ) as mock_tl,
            patch(
                "app.services.vision_pipeline.hp_tracker"
            ) as mock_hp,
        ):
            mock_bsm.match.phase = BattlePhase.FINISHED
            await pipeline._dispatch_scene_events()
            mock_bsm.reset.assert_called_once()
            mock_tl.reset.assert_called_once()
            mock_hp.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_dispatch_on_same_scene(self):
        """シーン変化なしの場合はシーン遷移イベントが発火しない。"""
        mock_obs = MagicMock(spec=OBSConnector)
        engine = MagicMock(spec=VisionEngine)
        engine.scene_state = SceneState.IDLE

        mock_state = MagicMock()
        mock_state.detected_pokemon = []
        mock_state.detected_moves = []
        mock_state.detected_abilities = []
        mock_state.running = False
        engine.state = mock_state
        engine.components_status = {}

        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)
        pipeline._previous_scene = SceneState.IDLE

        with patch(
            "app.services.vision_pipeline.battle_state_manager"
        ) as mock_bsm:
            await pipeline._dispatch_scene_events()
            mock_bsm.start_match.assert_not_called()
            mock_bsm.start_battle.assert_not_called()
            mock_bsm.end_match.assert_not_called()


class TestVisionPipelineFrameFeed:
    @pytest.mark.asyncio
    async def test_frame_feed_with_frames(self):
        """フレーム供給ループがフレームをキューに供給する。"""
        mock_obs = MagicMock(spec=OBSConnector)
        frame = _make_frame()
        call_count = 0

        async def mock_read():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return frame
            return None

        mock_obs.read_frame_async = mock_read

        engine = MagicMock(spec=VisionEngine)
        engine.scene_state = SceneState.IDLE
        mock_state = MagicMock()
        mock_state.detected_pokemon = []
        mock_state.detected_moves = []
        mock_state.detected_abilities = []
        mock_state.running = False
        engine.state = mock_state
        engine.components_status = {}

        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)
        pipeline._running = True
        pipeline._frame_queue = asyncio.Queue(maxsize=10)

        # Run the feed loop briefly
        task = asyncio.create_task(pipeline._frame_feed_loop())
        await asyncio.sleep(0.3)
        pipeline._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert pipeline.stats.total_frames_fed > 0

    @pytest.mark.asyncio
    async def test_frame_feed_handles_errors(self):
        """フレーム供給ループがエラーを適切にハンドリングする。"""
        mock_obs = MagicMock(spec=OBSConnector)
        call_count = 0

        async def mock_read():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error")
            return None

        mock_obs.read_frame_async = mock_read

        engine = MagicMock(spec=VisionEngine)
        engine.scene_state = SceneState.IDLE
        mock_state = MagicMock()
        mock_state.detected_pokemon = []
        mock_state.detected_moves = []
        mock_state.detected_abilities = []
        mock_state.running = False
        engine.state = mock_state
        engine.components_status = {}

        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)
        pipeline._running = True
        pipeline._frame_queue = asyncio.Queue(maxsize=10)

        task = asyncio.create_task(pipeline._frame_feed_loop())
        await asyncio.sleep(0.8)
        pipeline._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert pipeline.stats.capture_errors >= 1


class TestVisionPipelineAPI:
    def test_pipeline_status_endpoint(self):
        """GET /api/vision/pipeline/status が正常に動作する。"""
        response = client.get("/api/vision/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False
        assert "capture" in data
        assert "vision" in data
        assert "stats" in data
        assert "components" in data

    def test_pipeline_start_obs_unavailable(self):
        """OBS未接続時のパイプライン開始。"""
        response = client.post(
            "/api/vision/pipeline/start",
            json={
                "device_index": 0,
                "target_fps": 5,
                "scene_confidence_threshold": 0.6,
                "noise_frame_count": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False
        assert data.get("error") is not None

    def test_pipeline_stop_not_running(self):
        """未実行時のパイプライン停止。"""
        response = client.post("/api/vision/pipeline/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False

    def test_pipeline_start_default_params(self):
        """デフォルトパラメータでのパイプライン開始。"""
        response = client.post("/api/vision/pipeline/start", json={})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["target_fps"], int)
        assert isinstance(data["device_index"], int)

    def test_pipeline_status_schema_fields(self):
        """ステータスレスポンスに必要なフィールドがすべて含まれている。"""
        response = client.get("/api/vision/pipeline/status")
        assert response.status_code == 200
        data = response.json()

        assert "running" in data
        assert "target_fps" in data
        assert "device_index" in data
        assert "scene_confidence_threshold" in data
        assert "noise_frame_count" in data
        assert "capture" in data
        assert "vision" in data
        assert "stats" in data
        assert "components" in data

        # Nested field checks
        capture = data["capture"]
        assert "active" in capture

        vision = data["vision"]
        assert "running" in vision
        assert "scene_state" in vision

        stats = data["stats"]
        assert "total_frames_fed" in stats
        assert "pipeline_fps" in stats

    def test_existing_vision_endpoints_still_work(self):
        """既存のVision APIエンドポイントがPhase 5追加後も動作する。"""
        response = client.get("/api/vision/status")
        assert response.status_code == 200

        response = client.get("/api/vision/scene")
        assert response.status_code == 200

        response = client.get("/api/vision/components")
        assert response.status_code == 200


class TestVisionPipelineLifecycle:
    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """パイプラインの完全なライフサイクル: 作成 → 開始 → ステータス → 停止。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.read_frame_async = AsyncMock(return_value=None)
        mock_obs.stop_capture = MagicMock()

        engine = VisionEngine()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)

        # 1. Initial status
        status = pipeline.get_status()
        assert status["running"] is False

        # 2. Start
        result = await pipeline.start(target_fps=10)
        assert result["running"] is True
        assert pipeline.is_running

        # 3. Status while running
        status = pipeline.get_status()
        assert status["running"] is True
        assert status["target_fps"] == 10

        # 4. Stop
        result = await pipeline.stop()
        assert result["running"] is False
        assert not pipeline.is_running

    @pytest.mark.asyncio
    async def test_restart_pipeline(self):
        """パイプラインの再起動。"""
        mock_obs = MagicMock(spec=OBSConnector)
        mock_obs.start_capture.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.get_capture_status.return_value = OBSCaptureStatus(
            active=True, width=1920, height=1080, fps=30.0
        )
        mock_obs.read_frame_async = AsyncMock(return_value=None)
        mock_obs.stop_capture = MagicMock()

        engine = VisionEngine()
        pipeline = VisionPipeline(vision_eng=engine, obs_conn=mock_obs)

        # Start → Stop → Start
        await pipeline.start()
        await pipeline.stop()
        result = await pipeline.start(target_fps=15)
        assert result["running"] is True
        assert pipeline.target_fps == 15

        await pipeline.stop()

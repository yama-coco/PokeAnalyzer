"""リアルタイム映像連携パイプライン (Phase 5)

OBS仮想カメラ → Vision Engine のリアルタイム連携パイプライン。
フレーム取得 → 解析 → 状態更新 → WebSocket配信 を自動的に行う。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from app.services.battle_state import BattlePhase, battle_state_manager
from app.services.hp_tracker import hp_tracker
from app.services.obs_connector import OBSConnector, obs_connector
from app.services.scene_state import SceneState
from app.services.turn_logger import turn_logger
from app.services.vision_engine import VisionEngine, vision_engine

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """パイプラインの実行統計。"""

    started_at: float = 0.0
    total_frames_fed: int = 0
    total_frames_processed: int = 0
    total_events_dispatched: int = 0
    last_frame_at: float = 0.0
    capture_errors: int = 0
    pipeline_fps: float = 0.0
    _frame_times: list[float] = field(default_factory=list)

    def record_frame(self) -> None:
        now = time.time()
        self.total_frames_fed += 1
        self.last_frame_at = now
        self._frame_times.append(now)
        if len(self._frame_times) > 30:
            self._frame_times = self._frame_times[-30:]
        if len(self._frame_times) >= 2:
            elapsed = self._frame_times[-1] - self._frame_times[0]
            if elapsed > 0:
                self.pipeline_fps = (len(self._frame_times) - 1) / elapsed

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at,
            "total_frames_fed": self.total_frames_fed,
            "total_frames_processed": self.total_frames_processed,
            "total_events_dispatched": self.total_events_dispatched,
            "last_frame_at": self.last_frame_at,
            "capture_errors": self.capture_errors,
            "pipeline_fps": round(self.pipeline_fps, 1),
        }


class VisionPipeline:
    """OBS仮想カメラ → Vision Engine のリアルタイム連携パイプライン。

    OBSコネクタからフレームを取得し、VisionEngineで解析した結果を
    BattleStateManager / HPTracker / TurnLogger に自動的に反映する。
    """

    DEFAULT_TARGET_FPS = 5
    DEFAULT_DEVICE_INDEX = 0
    DEFAULT_SCENE_CONFIDENCE_THRESHOLD = 0.6
    DEFAULT_NOISE_FRAME_COUNT = 3

    def __init__(
        self,
        vision_eng: VisionEngine | None = None,
        obs_conn: OBSConnector | None = None,
    ) -> None:
        self._vision_engine = vision_eng or vision_engine
        self._obs = obs_conn or obs_connector
        self._running = False
        self._target_fps = self.DEFAULT_TARGET_FPS
        self._device_index = self.DEFAULT_DEVICE_INDEX
        self._scene_confidence_threshold = self.DEFAULT_SCENE_CONFIDENCE_THRESHOLD
        self._noise_frame_count = self.DEFAULT_NOISE_FRAME_COUNT
        self._frame_queue: asyncio.Queue | None = None
        self._feed_task: asyncio.Task | None = None
        self._stats = PipelineStats()
        self._previous_scene: SceneState = SceneState.IDLE

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> PipelineStats:
        return self._stats

    @property
    def target_fps(self) -> int:
        return self._target_fps

    @property
    def device_index(self) -> int:
        return self._device_index

    async def start(
        self,
        device_index: int | None = None,
        target_fps: int | None = None,
        scene_confidence_threshold: float | None = None,
        noise_frame_count: int | None = None,
    ) -> dict:
        """パイプライン開始。OBS仮想カメラからフレーム取得を開始する。

        Returns:
            パイプラインの状態を示す辞書。
        """
        if self._running:
            logger.warning("Pipeline is already running")
            return self.get_status()

        if device_index is not None:
            self._device_index = device_index
        if target_fps is not None:
            self._target_fps = max(1, min(target_fps, 30))
        if scene_confidence_threshold is not None:
            self._scene_confidence_threshold = scene_confidence_threshold
        if noise_frame_count is not None:
            self._noise_frame_count = max(1, noise_frame_count)

        capture_status = self._obs.start_capture(self._device_index)
        if not capture_status.active:
            logger.error("Failed to start OBS capture on device %d", self._device_index)
            return {
                "running": False,
                "error": f"OBS仮想カメラ (device {self._device_index}) に接続できません",
                "capture": {"active": False},
                "stats": self._stats.to_dict(),
            }

        self._frame_queue = asyncio.Queue(maxsize=10)
        await self._vision_engine.start(self._frame_queue)

        self._running = True
        self._stats = PipelineStats(started_at=time.time())
        self._previous_scene = self._vision_engine.scene_state

        self._feed_task = asyncio.create_task(self._frame_feed_loop())

        logger.info(
            "Vision pipeline started: device=%d, fps=%d",
            self._device_index,
            self._target_fps,
        )
        return self.get_status()

    async def stop(self) -> dict:
        """パイプライン停止。

        Returns:
            パイプラインの最終状態を示す辞書。
        """
        if not self._running:
            return self.get_status()

        self._running = False

        if self._feed_task is not None:
            self._feed_task.cancel()
            try:
                await self._feed_task
            except asyncio.CancelledError:
                pass
            self._feed_task = None

        await self._vision_engine.stop()
        self._obs.stop_capture()
        self._frame_queue = None

        logger.info("Vision pipeline stopped")
        return self.get_status()

    def get_status(self) -> dict:
        """パイプライン状態取得。"""
        capture_status = self._obs.get_capture_status()
        vision_state = self._vision_engine.state

        return {
            "running": self._running,
            "target_fps": self._target_fps,
            "device_index": self._device_index,
            "scene_confidence_threshold": self._scene_confidence_threshold,
            "noise_frame_count": self._noise_frame_count,
            "capture": {
                "active": capture_status.active,
                "width": capture_status.width,
                "height": capture_status.height,
                "fps": capture_status.fps,
            },
            "vision": {
                "running": vision_state.running,
                "scene_state": vision_state.scene.state.value,
                "scene_confidence": vision_state.scene.confidence,
                "fps": round(vision_state.fps, 1),
                "total_frames": vision_state.total_frames,
                "detected_pokemon": vision_state.detected_pokemon,
            },
            "stats": self._stats.to_dict(),
            "components": self._vision_engine.components_status,
        }

    async def _frame_feed_loop(self) -> None:
        """フレーム供給ループ: OBSからフレームを取得してキューに供給する。"""
        interval = 1.0 / self._target_fps
        while self._running:
            try:
                frame = await self._obs.read_frame_async()
                if frame is not None:
                    self._stats.record_frame()
                    if self._frame_queue is not None:
                        if self._frame_queue.full():
                            try:
                                self._frame_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                        await self._frame_queue.put(frame)
                    await self._dispatch_scene_events()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._stats.capture_errors += 1
                logger.error("Frame feed error: %s", e)
                await asyncio.sleep(0.5)

    async def _dispatch_scene_events(self) -> None:
        """解析結果に基づいてシーン遷移イベントをディスパッチする。"""
        current_scene = self._vision_engine.scene_state
        self._stats.total_frames_processed += 1

        if current_scene == self._previous_scene:
            self._dispatch_in_scene_events(current_scene)
            return

        logger.info(
            "Pipeline scene transition: %s -> %s",
            self._previous_scene.value,
            current_scene.value,
        )
        self._stats.total_events_dispatched += 1

        if (
            self._previous_scene == SceneState.IDLE
            and current_scene == SceneState.MATCHING
        ):
            self._on_matching_start()
        elif (
            self._previous_scene == SceneState.MATCHING
            and current_scene == SceneState.SELECTION
        ):
            self._on_selection_start()
        elif (
            self._previous_scene == SceneState.SELECTION
            and current_scene == SceneState.BATTLE
        ):
            self._on_battle_start()
        elif (
            self._previous_scene == SceneState.BATTLE
            and current_scene == SceneState.RESULT
        ):
            self._on_result()
        elif current_scene == SceneState.IDLE:
            self._on_return_to_idle()

        self._previous_scene = current_scene

    def _dispatch_in_scene_events(self, scene: SceneState) -> None:
        """シーン内でのイベントディスパッチ (HP更新・テキスト検出)。"""
        if scene != SceneState.BATTLE:
            return

        vision_state = self._vision_engine.state

        if vision_state.detected_moves:
            for move_name in vision_state.detected_moves:
                self._stats.total_events_dispatched += 1
                logger.debug("Detected move: %s", move_name)

        if vision_state.detected_abilities:
            for ability_name in vision_state.detected_abilities:
                self._stats.total_events_dispatched += 1
                logger.debug("Detected ability: %s", ability_name)

    def _on_matching_start(self) -> None:
        """MATCHING開始: VS画面が検出された。"""
        logger.info("Pipeline: MATCHING started - scanning opponent team")
        detected = self._vision_engine.state.detected_pokemon
        if detected:
            battle_state_manager.start_match(enemy_team=detected)
            logger.info("Opponent team detected: %s", detected)

    def _on_selection_start(self) -> None:
        """SELECTION開始: 選出画面に遷移。"""
        logger.info("Pipeline: SELECTION started")
        detected = self._vision_engine.state.detected_pokemon
        if detected and battle_state_manager.match.phase == BattlePhase.NONE:
            battle_state_manager.start_match(enemy_team=detected)

    def _on_battle_start(self) -> None:
        """BATTLE開始: バトルフェーズに遷移。"""
        logger.info("Pipeline: BATTLE started")
        match = battle_state_manager.match
        if match.phase in (BattlePhase.TEAM_PREVIEW, BattlePhase.SELECTION):
            battle_state_manager.start_battle()
            turn_logger.start_match()
            hp_tracker.reset()
            logger.info("Battle state initialized for match %s", match.match_id)

    def _on_result(self) -> None:
        """RESULT: 勝敗画面に遷移。"""
        logger.info("Pipeline: RESULT detected")
        text_analysis = self._vision_engine.state.last_text_analysis
        result_text = text_analysis.get("result_text", "")

        result = ""
        if "かち" in result_text or "勝" in result_text:
            result = "win"
        elif "まけ" in result_text or "負" in result_text:
            result = "loss"

        battle_state_manager.end_match(result=result)
        logger.info("Match ended with result: %s", result or "unknown")

    def _on_return_to_idle(self) -> None:
        """IDLE復帰: 試合終了後のリセット。"""
        logger.info("Pipeline: Returned to IDLE")
        if battle_state_manager.match.phase == BattlePhase.FINISHED:
            battle_state_manager.reset()
            turn_logger.reset()
            hp_tracker.reset()


vision_pipeline = VisionPipeline()

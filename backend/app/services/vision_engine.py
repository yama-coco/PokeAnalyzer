"""Vision Engine

OBS仮想カメラからのフレームをリアルタイムに解析し、
ゲーム状態の推定・ポケモン検出・テキスト抽出を行う
メインパイプライン。

全コンポーネントを統合し、WebSocket経由で
解析結果をブロードキャストする。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

import numpy as np
from fastapi import WebSocket

from app.services.frame_processor import (
    FrameProcessor,
)
from app.services.ocr_engine import OCREngine
from app.services.scene_state import SceneContext, SceneIndicator, SceneState, SceneStateMachine
from app.services.template_matcher import TemplateMatcher
from app.services.yolo_detector import YOLODetector

logger = logging.getLogger(__name__)


@dataclass
class VisionState:
    """Vision Engineの現在の状態。"""

    running: bool = False
    scene: SceneContext = field(default_factory=SceneContext)
    fps: float = 0.0
    total_frames: int = 0
    last_detections: list[dict] = field(default_factory=list)
    last_text_analysis: dict = field(default_factory=dict)
    detected_pokemon: list[str] = field(default_factory=list)
    detected_moves: list[str] = field(default_factory=list)
    detected_abilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "running": self.running,
            "scene": {
                "state": self.scene.state.value,
                "confidence": self.scene.confidence,
                "frame_count": self.scene.frame_count,
            },
            "fps": round(self.fps, 1),
            "total_frames": self.total_frames,
            "detected_pokemon": self.detected_pokemon,
            "detected_moves": self.detected_moves,
            "detected_abilities": self.detected_abilities,
            "last_detections": self.last_detections,
        }


class VisionEngine:
    """映像解析エンジン。

    OBSコネクタからフレームを取得し、以下のパイプラインで処理する:
    1. フレーム前処理 (リサイズ、正規化)
    2. 変化検知 (差分が大きい場合のみ詳細解析)
    3. シーン状態判定
    4. シーンに応じた解析:
       - MATCHING: VS画面のポケモンアイコン検出
       - SELECTION: 選出画面の認識
       - BATTLE: テキストボックスOCR、HPバー解析
       - RESULT: 勝敗テキスト認識
    5. 結果のブロードキャスト
    """

    TARGET_FPS = 5.0
    SKIP_UNCHANGED_FRAMES = True

    def __init__(
        self,
        template_dir: str | None = None,
        yolo_model_path: str | None = None,
        use_gpu: bool = False,
    ) -> None:
        self._frame_processor = FrameProcessor()
        self._scene_machine = SceneStateMachine()
        self._template_matcher = TemplateMatcher(template_dir)
        self._ocr_engine = OCREngine(use_gpu=use_gpu)
        self._yolo_detector = YOLODetector(yolo_model_path, use_gpu=use_gpu)

        self._state = VisionState()
        self._running = False
        self._task: asyncio.Task | None = None
        self._clients: set[WebSocket] = set()
        self._frame_times: list[float] = []

    @property
    def state(self) -> VisionState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def scene_state(self) -> SceneState:
        return self._scene_machine.current_state

    @property
    def components_status(self) -> dict:
        """各コンポーネントの利用可能状態。"""
        return {
            "ocr_available": self._ocr_engine.is_available,
            "yolo_available": self._yolo_detector.is_available,
            "template_count": self._template_matcher.template_count,
            "scene_state": self._scene_machine.current_state.value,
        }

    def add_client(self, ws: WebSocket) -> None:
        self._clients.add(ws)
        logger.info("WebSocket client connected. Total: %d", len(self._clients))

    def remove_client(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        logger.info("WebSocket client disconnected. Total: %d", len(self._clients))

    async def start(self, frame_source: asyncio.Queue) -> None:
        """フレームソースからの解析ループを開始する。"""
        if self._running:
            logger.warning("Vision engine is already running")
            return

        self._running = True
        self._state.running = True
        self._task = asyncio.create_task(self._analysis_loop(frame_source))
        logger.info("Vision engine started")

    async def stop(self) -> None:
        """解析ループを停止する。"""
        self._running = False
        self._state.running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._frame_processor.reset()
        self._scene_machine.reset()
        logger.info("Vision engine stopped")

    async def analyze_single_frame(self, frame: np.ndarray) -> dict:
        """単一フレームを解析して結果を返す（テスト・デバッグ用）。"""
        return self._process_frame(frame)

    def _process_frame(self, frame: np.ndarray) -> dict:
        """フレームを解析するメインパイプライン。"""
        start_time = time.perf_counter()
        self._state.total_frames += 1

        # 1. 前処理
        analysis = self._frame_processor.process_frame(frame)

        # 2. 変化検知 (変化なしなら軽量処理のみ)
        if self.SKIP_UNCHANGED_FRAMES and not analysis.has_significant_change:
            return self._state.to_dict()

        # 3. シーン指標の構築
        indicator = self._build_scene_indicator(analysis.roi_frames)

        # 4. シーン状態更新
        self._scene_machine.update(indicator)
        self._state.scene = self._scene_machine.context

        # 5. シーンに応じた詳細解析
        result = self._analyze_by_scene(frame, analysis.roi_frames)

        # 6. FPS計算
        elapsed = time.perf_counter() - start_time
        self._update_fps(elapsed)

        return result

    def _build_scene_indicator(self, roi_frames: dict[str, np.ndarray]) -> SceneIndicator:
        """ROIフレームからシーン指標を構築する。"""
        indicator = SceneIndicator()

        # VS画面のアイコン領域に十分なコンテンツがあるか
        if "vs_icons" in roi_frames:
            vs_roi = roi_frames["vs_icons"]
            edges = self._count_edges(vs_roi)
            if edges > 5000:
                indicator.has_vs_screen_layout = True

        # HPバーの存在チェック
        for key in ["hp_ally_1", "hp_ally_2", "hp_enemy_1", "hp_enemy_2"]:
            if key in roi_frames:
                hp = self._frame_processor.detect_hp_bar(roi_frames[key])
                if hp is not None:
                    indicator.has_hp_bars = True
                    break

        # テキストボックスにテキストがあるか
        if "text_box" in roi_frames:
            text_roi = roi_frames["text_box"]
            edges = self._count_edges(text_roi)
            if edges > 3000:
                indicator.has_text_box = True

        # コマンドメニューの存在チェック
        if "command_menu" in roi_frames:
            cmd_roi = roi_frames["command_menu"]
            edges = self._count_edges(cmd_roi)
            if edges > 2000:
                indicator.has_command_menu = True

        return indicator

    def _analyze_by_scene(self, frame: np.ndarray, roi_frames: dict[str, np.ndarray]) -> dict:
        """現在のシーンに応じた詳細解析を行う。"""
        scene = self._scene_machine.current_state

        if scene == SceneState.MATCHING:
            return self._analyze_matching(frame, roi_frames)
        elif scene == SceneState.BATTLE:
            return self._analyze_battle(frame, roi_frames)
        elif scene == SceneState.RESULT:
            return self._analyze_result(frame, roi_frames)

        return self._state.to_dict()

    def _analyze_matching(self, frame: np.ndarray, roi_frames: dict[str, np.ndarray]) -> dict:
        """VS画面の解析: 相手の6体を特定する。"""
        detections: list[dict] = []

        # YOLOで検出を試みる
        if self._yolo_detector.is_available:
            vs_roi = roi_frames.get("vs_icons")
            if vs_roi is not None:
                result = self._yolo_detector.detect(vs_roi)
                detections = [
                    {
                        "name": d.class_name,
                        "confidence": d.confidence,
                        "bbox": list(d.bbox),
                    }
                    for d in result.detections
                ]

        # テンプレートマッチングでも検出
        if self._template_matcher.template_count > 0:
            vs_roi = roi_frames.get("vs_icons")
            if vs_roi is not None:
                matches = self._template_matcher.match_category(vs_roi, "pokemon")
                for m in matches:
                    detections.append(
                        {
                            "name": m.template_name,
                            "confidence": m.confidence,
                            "bbox": list(m.bbox),
                            "source": "template",
                        }
                    )

        self._state.last_detections = detections
        self._state.detected_pokemon = list({d["name"] for d in detections})
        return self._state.to_dict()

    def _analyze_battle(self, frame: np.ndarray, roi_frames: dict[str, np.ndarray]) -> dict:
        """バトル画面の解析: テキストOCR、HPバー解析。"""
        # テキストボックスのOCR
        if self._ocr_engine.is_available:
            text_roi = roi_frames.get("text_box")
            if text_roi is not None:
                text_analysis = self._ocr_engine.analyze_text(text_roi)
                self._state.detected_moves = text_analysis.moves
                self._state.detected_abilities = text_analysis.abilities
                self._state.last_text_analysis = {
                    "moves": text_analysis.moves,
                    "abilities": text_analysis.abilities,
                    "items": text_analysis.items,
                    "status": text_analysis.status_texts,
                    "raw_count": len(text_analysis.raw_results),
                }

        return self._state.to_dict()

    def _analyze_result(self, frame: np.ndarray, roi_frames: dict[str, np.ndarray]) -> dict:
        """勝敗画面の解析。"""
        if self._ocr_engine.is_available:
            text_analysis = self._ocr_engine.analyze_text(frame)
            result_text = " ".join(r.text for r in text_analysis.raw_results)
            self._state.last_text_analysis = {
                "result_text": result_text,
                "scene_keywords": text_analysis.scene_keywords,
            }
        return self._state.to_dict()

    async def _analysis_loop(self, frame_source: asyncio.Queue) -> None:
        """フレーム解析のメインループ。"""
        interval = 1.0 / self.TARGET_FPS
        while self._running:
            try:
                frame = await asyncio.wait_for(frame_source.get(), timeout=1.0)
                result = self._process_frame(frame)
                await self._broadcast(result)
                await asyncio.sleep(interval)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Vision engine error: %s", e)
                await asyncio.sleep(0.1)

    async def _broadcast(self, data: dict) -> None:
        """全WebSocketクライアントにデータを送信する。"""
        if not self._clients:
            return
        message = json.dumps(data, ensure_ascii=False)
        disconnected: set[WebSocket] = set()
        for ws in self._clients:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        self._clients -= disconnected

    def _update_fps(self, elapsed: float) -> None:
        """FPSを更新する。"""
        self._frame_times.append(elapsed)
        if len(self._frame_times) > 30:
            self._frame_times = self._frame_times[-30:]
        avg = sum(self._frame_times) / len(self._frame_times)
        self._state.fps = 1.0 / avg if avg > 0 else 0.0

    @staticmethod
    def _count_edges(frame: np.ndarray) -> int:
        """フレームのエッジピクセル数を数える（コンテンツ量の指標）。"""
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        return int(np.count_nonzero(edges))


# Singleton instance
vision_engine = VisionEngine()

"""Vision Engine APIエンドポイント

映像解析エンジンの制御とリアルタイム状態配信を行う。
"""

from __future__ import annotations

import asyncio
import base64
import logging

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.schemas import (
    SceneStateResponse,
    VisionAnalysisResult,
    VisionDetection,
    VisionEngineAction,
    VisionEngineRequest,
    VisionStatus,
)
from app.services.obs_connector import obs_connector
from app.services.vision_engine import vision_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vision", tags=["vision"])

# OBSキャプチャからフレームを供給するキュー
_frame_queue: asyncio.Queue | None = None
_capture_task: asyncio.Task | None = None


@router.post("/control", response_model=VisionStatus)
async def control_vision_engine(request: VisionEngineRequest):
    """映像解析エンジンの起動・停止を制御する。"""
    global _frame_queue, _capture_task

    if request.action == VisionEngineAction.START:
        if vision_engine.is_running:
            return _build_status()

        _frame_queue = asyncio.Queue(maxsize=10)
        await vision_engine.start(_frame_queue)

        # OBSキャプチャが有効ならフレーム供給タスクを開始
        if obs_connector.is_connected:
            _capture_task = asyncio.create_task(_feed_frames_from_obs(_frame_queue))

        return _build_status()

    elif request.action == VisionEngineAction.STOP:
        await vision_engine.stop()
        if _capture_task is not None:
            _capture_task.cancel()
            try:
                await _capture_task
            except asyncio.CancelledError:
                pass
            _capture_task = None
        _frame_queue = None
        return _build_status()

    return _build_status()


@router.get("/status", response_model=VisionStatus)
async def get_vision_status():
    """映像解析エンジンの現在の状態を取得する。"""
    return _build_status()


@router.get("/scene", response_model=SceneStateResponse)
async def get_scene_state():
    """現在のシーン状態と遷移履歴を取得する。"""
    from app.services.vision_engine import vision_engine

    context = vision_engine.state.scene
    history = [
        {
            "from": t.from_state.value,
            "to": t.to_state.value,
            "timestamp": t.timestamp,
            "confidence": t.confidence,
        }
        for t in vision_engine._scene_machine.history
    ]
    return SceneStateResponse(
        current_state=context.state.value,
        confidence=context.confidence,
        entered_at=context.entered_at,
        frame_count=context.frame_count,
        history=history,
    )


@router.post("/scene/force")
async def force_scene_transition(state: str):
    """シーン状態を強制的に遷移させる（デバッグ用）。"""
    from app.services.scene_state import SceneState

    try:
        target = SceneState(state)
    except ValueError:
        valid = [s.value for s in SceneState]
        return JSONResponse(
            status_code=400,
            content={"detail": f"Invalid state. Valid: {valid}"},
        )

    vision_engine._scene_machine.force_transition(target)
    return {"state": target.value, "message": f"Forced transition to {target.value}"}


@router.post("/analyze-frame", response_model=VisionAnalysisResult)
async def analyze_single_frame(image_base64: str | None = None):
    """単一フレームを解析する（テスト・デバッグ用）。

    Base64エンコードされた画像を受け取り、解析結果を返す。
    画像が指定されない場合、OBSキャプチャから1フレームを取得する。
    """
    frame = None

    if image_base64:
        try:
            img_bytes = base64.b64decode(image_base64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Invalid image data: {e}"},
            )
    else:
        frame = await obs_connector.read_frame_async()

    if frame is None:
        return JSONResponse(
            status_code=400,
            content={"detail": "No frame available. Provide image_base64 or start OBS capture."},
        )

    result = await vision_engine.analyze_single_frame(frame)

    detections = [
        VisionDetection(
            name=d.get("name", ""),
            confidence=d.get("confidence", 0.0),
            bbox=d.get("bbox", []),
            source=d.get("source", ""),
        )
        for d in result.get("last_detections", [])
    ]

    return VisionAnalysisResult(
        scene_state=result.get("scene", {}).get("state", "idle"),
        detections=detections,
        text_analysis=result.get("last_text_analysis", {}),
    )


@router.get("/components")
async def get_components_status():
    """各コンポーネント（OCR, YOLO, テンプレート）の状態を取得する。"""
    return vision_engine.components_status


@router.websocket("/ws")
async def vision_websocket(websocket: WebSocket):
    """リアルタイム解析結果をWebSocketで配信する。"""
    await websocket.accept()
    vision_engine.add_client(websocket)
    try:
        while True:
            # クライアントからのpingを受け付ける
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        vision_engine.remove_client(websocket)


async def _feed_frames_from_obs(queue: asyncio.Queue) -> None:
    """OBSキャプチャからフレームをキューに供給する。"""
    interval = 1.0 / 5.0  # 5 FPS
    while True:
        try:
            frame = await obs_connector.read_frame_async()
            if frame is not None:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                await queue.put(frame)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Frame feed error: %s", e)
            await asyncio.sleep(0.5)


def _build_status() -> VisionStatus:
    """現在のVisionEngineの状態をレスポンス形式で返す。"""
    state = vision_engine.state
    return VisionStatus(
        running=state.running,
        scene_state=state.scene.state.value,
        scene_confidence=state.scene.confidence,
        fps=state.fps,
        total_frames=state.total_frames,
        detected_pokemon=state.detected_pokemon,
        detected_moves=state.detected_moves,
        detected_abilities=state.detected_abilities,
        components=vision_engine.components_status,
    )

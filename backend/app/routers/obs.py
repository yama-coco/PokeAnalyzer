"""OBS WebSocket 連携 API エンドポイント"""

from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException

from app.schemas import (
    OBSCaptureStatus,
    OBSConnectionStatus,
    OBSRecordingAction,
    OBSRecordingRequest,
    OBSRecordingStatus,
    OBSSceneRequest,
)
from app.services.obs_connector import obs_connector

router = APIRouter(prefix="/api/obs", tags=["obs"])


@router.post("/connect", response_model=OBSConnectionStatus)
async def connect_obs() -> OBSConnectionStatus:
    """OBS WebSocket サーバーに接続する。"""
    return await obs_connector.connect()


@router.post("/disconnect")
async def disconnect_obs() -> dict[str, str]:
    """OBS WebSocket 接続を切断する。"""
    await obs_connector.disconnect()
    return {"status": "disconnected"}


@router.get("/status", response_model=OBSConnectionStatus)
async def get_obs_status() -> OBSConnectionStatus:
    """OBS 接続状態を取得する。"""
    return OBSConnectionStatus(connected=obs_connector.is_connected)


@router.post("/recording", response_model=OBSRecordingStatus)
async def control_recording(body: OBSRecordingRequest) -> OBSRecordingStatus:
    """録画を制御する。"""
    if not obs_connector.is_connected:
        raise HTTPException(status_code=503, detail="OBSに接続されていません")
    if body.action == OBSRecordingAction.START:
        return await obs_connector.start_recording()
    elif body.action == OBSRecordingAction.STOP:
        return await obs_connector.stop_recording()
    else:
        status = await obs_connector.get_recording_status()
        if status.is_recording:
            return await obs_connector.stop_recording()
        return await obs_connector.start_recording()


@router.get("/recording/status", response_model=OBSRecordingStatus)
async def get_recording_status() -> OBSRecordingStatus:
    """録画状態を取得する。"""
    if not obs_connector.is_connected:
        return OBSRecordingStatus(is_recording=False)
    return await obs_connector.get_recording_status()


@router.post("/scene")
async def switch_scene(body: OBSSceneRequest) -> dict[str, str]:
    """シーンを切り替える。"""
    if not obs_connector.is_connected:
        raise HTTPException(status_code=503, detail="OBSに接続されていません")
    success = await obs_connector.switch_scene(body.scene_name)
    if not success:
        raise HTTPException(status_code=500, detail="シーン切替に失敗しました")
    return {"scene": body.scene_name}


@router.get("/scenes")
async def list_scenes() -> list[str]:
    """利用可能なシーン一覧を取得する。"""
    if not obs_connector.is_connected:
        raise HTTPException(status_code=503, detail="OBSに接続されていません")
    return await obs_connector.get_scene_list()


@router.post("/capture/start", response_model=OBSCaptureStatus)
async def start_capture(device_index: int = 0) -> OBSCaptureStatus:
    """OBS仮想カメラからの映像キャプチャを開始する。"""
    return obs_connector.start_capture(device_index)


@router.post("/capture/stop")
async def stop_capture() -> dict[str, str]:
    """映像キャプチャを停止する。"""
    obs_connector.stop_capture()
    return {"status": "stopped"}


@router.get("/capture/status", response_model=OBSCaptureStatus)
async def get_capture_status() -> OBSCaptureStatus:
    """キャプチャ状態を取得する。"""
    return obs_connector.get_capture_status()


@router.get("/capture/frame")
async def get_current_frame() -> dict[str, str | None]:
    """現在のフレームをBase64エンコードで取得する。

    フロントエンドでのプレビュー表示用。
    """
    import cv2

    frame = await obs_connector.read_frame_async()
    if frame is None:
        raise HTTPException(status_code=503, detail="フレームを取得できません")
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    encoded = base64.b64encode(buffer).decode("utf-8")
    return {"image": f"data:image/jpeg;base64,{encoded}"}

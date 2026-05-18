"""OBS WebSocket 5.x 接続・映像キャプチャ管理サービス

OBS Studio の WebSocket サーバー (デフォルト ws://localhost:4455) と接続し、
録画制御・シーン切替・仮想カメラからのフレーム取得を行う。

依存: obs-websocket-py (obsws-python), opencv-python-headless
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import cv2
import numpy as np

from app.core.config import OBS_WS_HOST, OBS_WS_PASSWORD, OBS_WS_PORT
from app.schemas import OBSCaptureStatus, OBSConnectionStatus, OBSRecordingStatus

logger = logging.getLogger(__name__)


class OBSConnector:
    """OBS WebSocket 5.x との接続を管理するクラス。"""

    def __init__(
        self,
        host: str = OBS_WS_HOST,
        port: int = OBS_WS_PORT,
        password: str = OBS_WS_PASSWORD,
    ) -> None:
        self._host = host
        self._port = port
        self._password = password
        self._ws: Any = None
        self._connected = False
        self._capture: cv2.VideoCapture | None = None
        self._capture_active = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> OBSConnectionStatus:
        """OBS WebSocket サーバーに接続する。"""
        try:
            import obsws_python as obsws

            self._ws = obsws.ReqClient(
                host=self._host,
                port=self._port,
                password=self._password,
                timeout=5,
            )
            version_info = self._ws.get_version()
            self._connected = True
            logger.info("OBS WebSocket connected: %s", version_info.obs_version)
            return OBSConnectionStatus(
                connected=True,
                obs_version=version_info.obs_version,
                websocket_version=version_info.obs_web_socket_version,
            )
        except ImportError:
            logger.warning("obsws_python not installed")
            return OBSConnectionStatus(
                connected=False,
                error="obsws_python パッケージがインストールされていません",
            )
        except Exception as e:
            self._connected = False
            logger.error("OBS connection failed: %s", e)
            return OBSConnectionStatus(connected=False, error=str(e))

    async def disconnect(self) -> None:
        """OBS WebSocket 接続を切断する。"""
        if self._ws is not None:
            try:
                self._ws.base_client.ws.close()
            except Exception:
                pass
            self._ws = None
        self._connected = False
        self.stop_capture()
        logger.info("OBS WebSocket disconnected")

    async def start_recording(self) -> OBSRecordingStatus:
        """録画を開始する。"""
        if not self._connected or self._ws is None:
            return OBSRecordingStatus(is_recording=False)
        try:
            self._ws.start_record()
            return OBSRecordingStatus(is_recording=True)
        except Exception as e:
            logger.error("Failed to start recording: %s", e)
            return OBSRecordingStatus(is_recording=False)

    async def stop_recording(self) -> OBSRecordingStatus:
        """録画を停止する。"""
        if not self._connected or self._ws is None:
            return OBSRecordingStatus(is_recording=False)
        try:
            result = self._ws.stop_record()
            output_path = getattr(result, "output_path", None)
            return OBSRecordingStatus(is_recording=False, output_path=output_path)
        except Exception as e:
            logger.error("Failed to stop recording: %s", e)
            return OBSRecordingStatus(is_recording=False)

    async def get_recording_status(self) -> OBSRecordingStatus:
        """録画状態を取得する。"""
        if not self._connected or self._ws is None:
            return OBSRecordingStatus(is_recording=False)
        try:
            status = self._ws.get_record_status()
            return OBSRecordingStatus(
                is_recording=status.output_active,
                output_path=getattr(status, "output_path", None),
            )
        except Exception as e:
            logger.error("Failed to get recording status: %s", e)
            return OBSRecordingStatus(is_recording=False)

    async def switch_scene(self, scene_name: str) -> bool:
        """シーンを切り替える。"""
        if not self._connected or self._ws is None:
            return False
        try:
            self._ws.set_current_program_scene(scene_name)
            logger.info("Switched to scene: %s", scene_name)
            return True
        except Exception as e:
            logger.error("Failed to switch scene: %s", e)
            return False

    async def get_scene_list(self) -> list[str]:
        """利用可能なシーン一覧を取得する。"""
        if not self._connected or self._ws is None:
            return []
        try:
            result = self._ws.get_scene_list()
            return [scene["sceneName"] for scene in result.scenes]
        except Exception as e:
            logger.error("Failed to get scene list: %s", e)
            return []

    def start_capture(self, device_index: int = 0) -> OBSCaptureStatus:
        """OBS仮想カメラからの映像キャプチャを開始する。

        OBS Studioで仮想カメラを有効にした状態で、
        OpenCVのVideoCaptureでフレームを取得する。
        """
        try:
            self._capture = cv2.VideoCapture(device_index)
            if not self._capture.isOpened():
                logger.error("Failed to open video capture device %d", device_index)
                return OBSCaptureStatus(active=False)

            width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self._capture.get(cv2.CAP_PROP_FPS)
            self._capture_active = True
            logger.info("Video capture started: %dx%d @ %.1f fps", width, height, fps)
            return OBSCaptureStatus(
                active=True,
                width=width,
                height=height,
                fps=fps,
            )
        except Exception as e:
            logger.error("Failed to start capture: %s", e)
            return OBSCaptureStatus(active=False)

    def stop_capture(self) -> None:
        """映像キャプチャを停止する。"""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._capture_active = False
        logger.info("Video capture stopped")

    def read_frame(self) -> np.ndarray | None:
        """現在のフレームを取得する。

        Returns:
            BGR形式のnumpy配列。取得失敗時はNone。
        """
        if self._capture is None or not self._capture_active:
            return None
        ret, frame = self._capture.read()
        if not ret:
            return None
        return frame

    async def read_frame_async(self) -> np.ndarray | None:
        """非同期でフレームを取得する。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.read_frame)

    def get_capture_status(self) -> OBSCaptureStatus:
        """キャプチャの現在の状態を取得する。"""
        if self._capture is None or not self._capture_active:
            return OBSCaptureStatus(active=False)
        return OBSCaptureStatus(
            active=True,
            width=int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            fps=self._capture.get(cv2.CAP_PROP_FPS),
        )


# Singleton instance
obs_connector = OBSConnector()

"""学習データキャプチャスクリプト

OBS仮想カメラからVS画面・選出画面を自動キャプチャし、
YOLOv10学習用の画像データを保存する。

使い方:
  1. OBS Studio で仮想カメラを開始
  2. ゲームでランクマッチに潜る
  3. 本スクリプトを実行:
     cd backend && uv run python scripts/capture_training_data.py
  4. VS画面/選出画面を検知すると自動保存

保存先: backend/training_data/raw/{timestamp}.png

オプション:
  --device      OpenCV デバイスインデックス (default: 0)
  --output-dir  保存先ディレクトリ (default: training_data/raw)
  --interval    キャプチャ間隔 秒 (default: 0.5)
  --edge-threshold  エッジ密度閾値 (default: 30)
  --max-images  最大保存枚数 (default: 無制限)
  --roi-mode    ROI切り出しモード (vs / selection / both, default: both)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# プロジェクトルートをパスに追加 (app モジュールをインポートするため)
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from app.services.frame_processor import (  # noqa: E402
    SELECTION_ENEMY_ICONS,
    VS_SCREEN_ICONS,
    FrameProcessor,
    RegionOfInterest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_OUTPUT_DIR = Path("training_data/raw")
DEFAULT_DEVICE_INDEX = 0
DEFAULT_INTERVAL = 0.5
DEFAULT_EDGE_THRESHOLD = 30.0
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

# ROI定義 (frame_processor から取得)
ROI_CONFIGS: dict[str, RegionOfInterest] = {
    "vs": VS_SCREEN_ICONS,
    "selection": SELECTION_ENEMY_ICONS,
}


def compute_edge_density(roi_frame: np.ndarray) -> float:
    """ROI領域のエッジ密度を計算する。

    Args:
        roi_frame: BGR形式のROI画像。

    Returns:
        エッジ密度 (0.0〜255.0)。値が高いほどアイコン等のコンテンツが多い。
    """
    if roi_frame.size == 0:
        return 0.0
    gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    return float(edges.sum() / edges.size)


def has_sufficient_content(roi_frame: np.ndarray, threshold: float) -> bool:
    """ROI内に十分なコンテンツ（アイコン等）が存在するか判定する。"""
    return compute_edge_density(roi_frame) > threshold


def detect_scene_type(
    frame: np.ndarray,
    processor: FrameProcessor,
    threshold: float,
) -> str | None:
    """フレームからVS画面・選出画面を判定する。

    Returns:
        "vs", "selection", または None (該当シーンなし)。
    """
    for scene_name, roi in ROI_CONFIGS.items():
        roi_frame = processor.extract_roi(frame, roi)
        if has_sufficient_content(roi_frame, threshold):
            return scene_name
    return None


def save_frame(
    frame: np.ndarray,
    output_dir: Path,
    scene_type: str,
    processor: FrameProcessor,
    save_roi: bool = True,
) -> tuple[Path, Path | None]:
    """フレームと（オプションで）ROI切り出し画像を保存する。

    Returns:
        (フルフレームのパス, ROI画像のパス or None)
    """
    timestamp_ms = int(time.time() * 1000)
    full_dir = output_dir / "full"
    full_dir.mkdir(parents=True, exist_ok=True)
    full_path = full_dir / f"{scene_type}_{timestamp_ms}.png"
    cv2.imwrite(str(full_path), frame)

    roi_path = None
    if save_roi and scene_type in ROI_CONFIGS:
        roi_dir = output_dir / "roi" / scene_type
        roi_dir.mkdir(parents=True, exist_ok=True)
        roi_frame = processor.extract_roi(frame, ROI_CONFIGS[scene_type])
        roi_path = roi_dir / f"{scene_type}_{timestamp_ms}.png"
        cv2.imwrite(str(roi_path), roi_frame)

    return full_path, roi_path


def create_capture(device_index: int) -> cv2.VideoCapture:
    """OBS仮想カメラへのVideoCapture接続を作成する。"""
    cap = cv2.VideoCapture(device_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"デバイス {device_index} をオープンできません。"
            "OBS仮想カメラが有効か確認してください。"
        )
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    logger.info("キャプチャ開始: %dx%d @ %.1f fps (device=%d)", width, height, fps, device_index)
    return cap


def run_capture_loop(
    device_index: int = DEFAULT_DEVICE_INDEX,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    interval: float = DEFAULT_INTERVAL,
    edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
    max_images: int | None = None,
    roi_mode: str = "both",
) -> int:
    """メインキャプチャループ。

    Args:
        device_index: OpenCVデバイスインデックス。
        output_dir: 画像保存先。
        interval: キャプチャ間隔（秒）。
        edge_threshold: シーン検知のエッジ密度閾値。
        max_images: 最大保存枚数 (Noneで無制限)。
        roi_mode: "vs", "selection", "both" のいずれか。

    Returns:
        保存した画像の枚数。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    processor = FrameProcessor(target_width=FRAME_WIDTH, target_height=FRAME_HEIGHT)

    cap = create_capture(device_index)
    saved_count = 0
    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("フレーム取得失敗。リトライします...")
                time.sleep(0.1)
                continue

            frame_count += 1
            processed = processor.preprocess(frame)
            scene_type = detect_scene_type(processed, processor, edge_threshold)

            if scene_type is not None:
                if roi_mode != "both" and scene_type != roi_mode:
                    time.sleep(interval)
                    continue

                full_path, roi_path = save_frame(
                    processed, output_dir, scene_type, processor
                )
                saved_count += 1
                logger.info(
                    "[%d] 保存: %s (scene=%s, frame=%d)",
                    saved_count,
                    full_path.name,
                    scene_type,
                    frame_count,
                )
                if roi_path:
                    logger.info("  ROI: %s", roi_path.name)

                if max_images is not None and saved_count >= max_images:
                    logger.info("最大枚数 (%d) に到達。終了します。", max_images)
                    break

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("キャプチャ中断 (Ctrl+C)")
    finally:
        cap.release()
        logger.info("合計 %d 枚保存 (処理フレーム: %d)", saved_count, frame_count)

    return saved_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OBS仮想カメラからYOLO学習データを自動キャプチャ",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=DEFAULT_DEVICE_INDEX,
        help=f"OpenCV デバイスインデックス (default: {DEFAULT_DEVICE_INDEX})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"保存先ディレクトリ (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"キャプチャ間隔 秒 (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=DEFAULT_EDGE_THRESHOLD,
        help=f"エッジ密度閾値 (default: {DEFAULT_EDGE_THRESHOLD})",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=None,
        help="最大保存枚数 (default: 無制限)",
    )
    parser.add_argument(
        "--roi-mode",
        choices=["vs", "selection", "both"],
        default="both",
        help="ROI切り出しモード (default: both)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("=== YOLO学習データキャプチャ ===")
    logger.info("デバイス: %d", args.device)
    logger.info("保存先: %s", args.output_dir)
    logger.info("間隔: %.2f秒", args.interval)
    logger.info("エッジ閾値: %.1f", args.edge_threshold)
    logger.info("ROIモード: %s", args.roi_mode)
    if args.max_images:
        logger.info("最大枚数: %d", args.max_images)

    run_capture_loop(
        device_index=args.device,
        output_dir=args.output_dir,
        interval=args.interval,
        edge_threshold=args.edge_threshold,
        max_images=args.max_images,
        roi_mode=args.roi_mode,
    )


if __name__ == "__main__":
    main()

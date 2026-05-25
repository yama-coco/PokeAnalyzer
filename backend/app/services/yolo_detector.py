"""YOLOデテクター

YOLOv10モデルを使用してフレーム内のポケモンアイコンを検出する。

学習済みモデルが無い場合はフォールバックモードで動作し、
テンプレートマッチング結果をYOLO形式に変換して返す。

Phase 6: 学習データ管理・NMSパラメータ調整・推論ベンチマーク機能を追加。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """物体検出結果。"""

    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)

    @property
    def center(self) -> tuple[int, int]:
        return (
            (self.bbox[0] + self.bbox[2]) // 2,
            (self.bbox[1] + self.bbox[3]) // 2,
        )

    @property
    def width(self) -> int:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        return self.bbox[3] - self.bbox[1]

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class DetectionResult:
    """検出全体の結果。"""

    detections: list[Detection] = field(default_factory=list)
    inference_time_ms: float = 0.0
    model_name: str = ""
    frame_size: tuple[int, int] = (0, 0)  # (width, height)

    @property
    def count(self) -> int:
        return len(self.detections)

    def filter_by_class(self, class_name: str) -> list[Detection]:
        return [d for d in self.detections if d.class_name == class_name]

    def filter_by_confidence(self, min_conf: float) -> list[Detection]:
        return [d for d in self.detections if d.confidence >= min_conf]


class YOLODetector:
    """YOLOベースの物体検出器。

    ultralytics パッケージを使用してYOLOv10推論を行う。
    モデルファイルが存在しない場合はフォールバックモードとなる。

    使用方法:
        1. 学習済みモデルファイル (.pt) を models/ ディレクトリに配置
        2. YOLODetector(model_path="models/pokemon_icons.pt") で初期化
        3. detect(frame) でフレーム内の検出を実行
    """

    DEFAULT_CONFIDENCE = 0.25
    DEFAULT_IOU_THRESHOLD = 0.45

    def __init__(
        self,
        model_path: str | Path | None = None,
        confidence: float = DEFAULT_CONFIDENCE,
        iou_threshold: float = DEFAULT_IOU_THRESHOLD,
        use_gpu: bool = False,
    ) -> None:
        self._model = None
        self._model_path = Path(model_path) if model_path else None
        self._confidence = confidence
        self._iou_threshold = iou_threshold
        self._use_gpu = use_gpu
        self._available = False
        self._class_names: dict[int, str] = {}
        self._init_model()

    def _init_model(self) -> None:
        """YOLOモデルを初期化する。"""
        if self._model_path is None or not self._model_path.exists():
            logger.info(
                "YOLO model not found at %s. Running in fallback mode.",
                self._model_path,
            )
            self._available = False
            return

        try:
            from ultralytics import YOLO

            device = "cuda:0" if self._use_gpu else "cpu"
            self._model = YOLO(str(self._model_path))
            self._model.to(device)
            if hasattr(self._model, "names"):
                self._class_names = dict(self._model.names)
            self._available = True
            logger.info(
                "YOLO model loaded: %s (%d classes)",
                self._model_path,
                len(self._class_names),
            )
        except ImportError:
            logger.warning("ultralytics not available. Install with: pip install ultralytics")
            self._available = False
        except Exception as e:
            logger.warning("YOLO model initialization failed: %s", e)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def class_names(self) -> dict[int, str]:
        return dict(self._class_names)

    @property
    def confidence(self) -> float:
        """現在のconfidence閾値。"""
        return self._confidence

    @confidence.setter
    def confidence(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {value}")
        self._confidence = value

    @property
    def iou_threshold(self) -> float:
        """現在のIoU閾値 (NMS用)。"""
        return self._iou_threshold

    @iou_threshold.setter
    def iou_threshold(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"iou_threshold must be 0.0-1.0, got {value}")
        self._iou_threshold = value

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """フレーム内の物体を検出する。"""
        if not self._available or self._model is None:
            return DetectionResult(
                model_name="fallback",
                frame_size=(frame.shape[1], frame.shape[0]),
            )

        start = time.perf_counter()
        try:
            results = self._model.predict(
                frame,
                conf=self._confidence,
                iou=self._iou_threshold,
                verbose=False,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            detections: list[Detection] = []
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = self._class_names.get(cls_id, f"class_{cls_id}")
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append(
                        Detection(
                            class_id=cls_id,
                            class_name=cls_name,
                            confidence=conf,
                            bbox=(int(x1), int(y1), int(x2), int(y2)),
                        )
                    )

            return DetectionResult(
                detections=detections,
                inference_time_ms=elapsed_ms,
                model_name=str(self._model_path),
                frame_size=(frame.shape[1], frame.shape[0]),
            )
        except Exception as e:
            logger.error("YOLO detection failed: %s", e)
            return DetectionResult(
                model_name="error",
                frame_size=(frame.shape[1], frame.shape[0]),
            )

    def detect_pokemon_icons(
        self, frame: np.ndarray, min_confidence: float = 0.5
    ) -> list[Detection]:
        """ポケモンアイコンのみを検出する。"""
        result = self.detect(frame)
        return [
            d
            for d in result.detections
            if d.confidence >= min_confidence
            and ("pokemon" in d.class_name.lower() or "icon" in d.class_name.lower())
        ]

    def benchmark(self, frame: np.ndarray, iterations: int = 10) -> dict:
        """推論速度のベンチマークを実行する。

        Args:
            frame: テスト用フレーム (BGR numpy配列)。
            iterations: 計測回数。

        Returns:
            ベンチマーク結果を含む辞書。
        """
        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            self.detect(frame)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)

        return {
            "iterations": iterations,
            "avg_ms": sum(times) / len(times) if times else 0.0,
            "min_ms": min(times) if times else 0.0,
            "max_ms": max(times) if times else 0.0,
            "model_available": self._available,
            "frame_size": (frame.shape[1], frame.shape[0]),
        }

    @staticmethod
    def create_training_config(
        data_dir: str | Path,
        num_classes: int,
        class_names: list[str],
    ) -> dict:
        """YOLO学習用のデータ設定を生成する。

        学習はこの関数の出力をYAMLファイルに保存し、
        yolo train data=config.yaml で実行する。

        ディレクトリ構造 (YOLO形式):
            data_dir/
            ├── images/
            │   ├── train/
            │   └── val/
            └── labels/
                ├── train/
                └── val/
        """
        data_dir = Path(data_dir)
        return {
            "path": str(data_dir),
            "train": "images/train",
            "val": "images/val",
            "nc": num_classes,
            "names": {i: name for i, name in enumerate(class_names)},
        }

    @staticmethod
    def setup_training_dirs(base_dir: str | Path) -> dict[str, Path]:
        """YOLO学習用のディレクトリ構造を作成する。

        Args:
            base_dir: 学習データのベースディレクトリ。

        Returns:
            作成されたディレクトリのパスを含む辞書。
        """
        base = Path(base_dir)
        dirs = {
            "images_train": base / "images" / "train",
            "images_val": base / "images" / "val",
            "labels_train": base / "labels" / "train",
            "labels_val": base / "labels" / "val",
        }
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        return dirs

    @staticmethod
    def convert_bbox_to_yolo(
        bbox: tuple[int, int, int, int],
        frame_width: int,
        frame_height: int,
    ) -> tuple[float, float, float, float]:
        """ピクセル座標 (x1, y1, x2, y2) をYOLO正規化座標 (cx, cy, w, h) に変換する。

        Args:
            bbox: (x1, y1, x2, y2) ピクセル座標。
            frame_width: フレーム幅。
            frame_height: フレーム高さ。

        Returns:
            (cx, cy, w, h) 正規化座標 (0.0-1.0)。
        """
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0 / frame_width
        cy = (y1 + y2) / 2.0 / frame_height
        w = (x2 - x1) / frame_width
        h = (y2 - y1) / frame_height
        return (cx, cy, w, h)

    @staticmethod
    def convert_yolo_to_bbox(
        yolo_coords: tuple[float, float, float, float],
        frame_width: int,
        frame_height: int,
    ) -> tuple[int, int, int, int]:
        """YOLO正規化座標 (cx, cy, w, h) をピクセル座標 (x1, y1, x2, y2) に変換する。

        Args:
            yolo_coords: (cx, cy, w, h) 正規化座標。
            frame_width: フレーム幅。
            frame_height: フレーム高さ。

        Returns:
            (x1, y1, x2, y2) ピクセル座標。
        """
        cx, cy, w, h = yolo_coords
        x1 = int((cx - w / 2) * frame_width)
        y1 = int((cy - h / 2) * frame_height)
        x2 = int((cx + w / 2) * frame_width)
        y2 = int((cy + h / 2) * frame_height)
        return (x1, y1, x2, y2)

    @staticmethod
    def compute_iou(
        box1: tuple[int, int, int, int],
        box2: tuple[int, int, int, int],
    ) -> float:
        """2つのバウンディングボックスのIoU (Intersection over Union) を計算する。

        Args:
            box1: (x1, y1, x2, y2) 1つ目のボックス。
            box2: (x1, y1, x2, y2) 2つ目のボックス。

        Returns:
            IoU値 (0.0-1.0)。
        """
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        if intersection == 0:
            return 0.0

        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def apply_nms(
        detections: list[Detection],
        iou_threshold: float = 0.45,
    ) -> list[Detection]:
        """検出結果にNMS (Non-Maximum Suppression) を適用する。

        Args:
            detections: 検出結果のリスト。
            iou_threshold: 重複除去のIoU閾値。

        Returns:
            NMS適用後の検出結果リスト。
        """
        if len(detections) <= 1:
            return list(detections)

        sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
        kept: list[Detection] = []

        for candidate in sorted_dets:
            should_keep = True
            for existing in kept:
                iou = YOLODetector.compute_iou(candidate.bbox, existing.bbox)
                if iou > iou_threshold:
                    should_keep = False
                    break
            if should_keep:
                kept.append(candidate)

        return kept

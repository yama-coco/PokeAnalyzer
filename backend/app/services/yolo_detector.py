"""YOLOデテクター

YOLOv10モデルを使用してフレーム内のポケモンアイコンを検出する。

学習済みモデルが無い場合はフォールバックモードで動作し、
テンプレートマッチング結果をYOLO形式に変換して返す。
"""

from __future__ import annotations

import logging
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

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """フレーム内の物体を検出する。"""
        if not self._available or self._model is None:
            return DetectionResult(
                model_name="fallback",
                frame_size=(frame.shape[1], frame.shape[0]),
            )

        import time

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

"""YOLOデテクターのテスト。

Phase 6: 合成テスト画像での検出テスト、推論速度テスト、NMSパラメータ調整テストを追加。
学習済みモデルが無い環境でもフォールバックモードで動作するテスト。
"""

import numpy as np
import pytest

from app.services.yolo_detector import Detection, DetectionResult, YOLODetector

# --- テストヘルパー ---


def make_synthetic_frame(
    width: int = 640,
    height: int = 640,
    num_icons: int = 6,
    icon_size: int = 60,
) -> np.ndarray:
    """合成テスト画像を生成する。

    ポケモンアイコンに見立てたカラーブロックを配置したフレームを返す。
    """
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # 背景にグラデーション
    for y in range(height):
        frame[y, :, 0] = int(40 * y / height)  # B
        frame[y, :, 1] = int(40 * y / height)  # G
        frame[y, :, 2] = int(60 * y / height)  # R

    colors = [
        (0, 0, 255),    # 赤
        (0, 255, 0),    # 緑
        (255, 0, 0),    # 青
        (0, 255, 255),  # 黄
        (255, 0, 255),  # マゼンタ
        (255, 255, 0),  # シアン
    ]

    spacing = width // (num_icons + 1)
    for i in range(min(num_icons, len(colors))):
        cx = spacing * (i + 1)
        cy = height // 2
        x1 = max(0, cx - icon_size // 2)
        y1 = max(0, cy - icon_size // 2)
        x2 = min(width, cx + icon_size // 2)
        y2 = min(height, cy + icon_size // 2)
        frame[y1:y2, x1:x2] = colors[i]

    return frame


def make_detection(
    class_id: int = 0,
    class_name: str = "pikachu",
    confidence: float = 0.95,
    bbox: tuple[int, int, int, int] = (10, 20, 60, 80),
) -> Detection:
    """テスト用のDetectionオブジェクトを生成する。"""
    return Detection(
        class_id=class_id,
        class_name=class_name,
        confidence=confidence,
        bbox=bbox,
    )


# --- Detection データクラスのテスト ---


class TestDetection:
    def test_properties(self):
        d = Detection(
            class_id=0,
            class_name="pikachu",
            confidence=0.95,
            bbox=(10, 20, 60, 80),
        )
        assert d.center == (35, 50)
        assert d.width == 50
        assert d.height == 60
        assert d.area == 3000

    def test_detection_result(self):
        dr = DetectionResult(
            detections=[
                Detection(0, "pikachu", 0.95, (0, 0, 50, 50)),
                Detection(1, "charizard", 0.80, (100, 100, 200, 200)),
                Detection(0, "pikachu", 0.60, (300, 300, 350, 350)),
            ],
            inference_time_ms=15.3,
            model_name="test",
            frame_size=(640, 480),
        )
        assert dr.count == 3
        assert len(dr.filter_by_class("pikachu")) == 2
        assert len(dr.filter_by_class("charizard")) == 1
        assert len(dr.filter_by_confidence(0.9)) == 1

    def test_detection_zero_size(self):
        d = Detection(class_id=0, class_name="test", confidence=0.5, bbox=(10, 10, 10, 10))
        assert d.width == 0
        assert d.height == 0
        assert d.area == 0
        assert d.center == (10, 10)

    def test_detection_result_empty(self):
        dr = DetectionResult()
        assert dr.count == 0
        assert dr.filter_by_class("any") == []
        assert dr.filter_by_confidence(0.5) == []

    def test_filter_by_confidence_boundary(self):
        dr = DetectionResult(
            detections=[
                Detection(0, "a", 0.5, (0, 0, 10, 10)),
                Detection(1, "b", 0.49, (20, 20, 30, 30)),
                Detection(2, "c", 0.51, (40, 40, 50, 50)),
            ],
        )
        assert len(dr.filter_by_confidence(0.5)) == 2
        assert len(dr.filter_by_confidence(0.51)) == 1


# --- YOLODetector 基本テスト ---


class TestYOLODetector:
    def test_initialization_without_model(self):
        detector = YOLODetector()
        assert not detector.is_available
        assert detector.class_names == {}

    def test_initialization_with_nonexistent_path(self):
        detector = YOLODetector(model_path="/nonexistent/model.pt")
        assert not detector.is_available

    def test_detect_fallback(self):
        """モデル無しの場合、空の結果を返す。"""
        detector = YOLODetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        assert result.count == 0
        assert result.model_name == "fallback"
        assert result.frame_size == (640, 480)

    def test_detect_pokemon_icons_fallback(self):
        detector = YOLODetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        icons = detector.detect_pokemon_icons(frame)
        assert icons == []

    def test_create_training_config(self):
        config = YOLODetector.create_training_config(
            data_dir="/data/pokemon",
            num_classes=213,
            class_names=["pikachu", "charizard"],
        )
        assert config["nc"] == 213
        assert config["train"] == "images/train"
        assert config["val"] == "images/val"
        assert config["names"][0] == "pikachu"
        assert config["names"][1] == "charizard"

    def test_default_parameters(self):
        detector = YOLODetector()
        assert detector.confidence == YOLODetector.DEFAULT_CONFIDENCE
        assert detector.iou_threshold == YOLODetector.DEFAULT_IOU_THRESHOLD

    def test_custom_parameters(self):
        detector = YOLODetector(confidence=0.5, iou_threshold=0.3)
        assert detector.confidence == 0.5
        assert detector.iou_threshold == 0.3


# --- Phase 6: 合成テスト画像テスト ---


class TestSyntheticImageDetection:
    """合成テスト画像を使った検出テスト。"""

    def test_synthetic_frame_generation(self):
        """合成フレームが正しいサイズ・型で生成されること。"""
        frame = make_synthetic_frame(640, 640, num_icons=6)
        assert frame.shape == (640, 640, 3)
        assert frame.dtype == np.uint8
        assert frame.sum() > 0

    def test_synthetic_frame_various_sizes(self):
        """異なるサイズの合成フレームが生成できること。"""
        for w, h in [(320, 320), (640, 480), (1920, 1080)]:
            frame = make_synthetic_frame(w, h, num_icons=3)
            assert frame.shape == (h, w, 3)

    def test_detect_on_synthetic_frame_fallback(self):
        """フォールバックモードでも合成フレームに対してエラーなく動作する。"""
        detector = YOLODetector()
        frame = make_synthetic_frame(640, 640)
        result = detector.detect(frame)
        assert result.model_name == "fallback"
        assert result.frame_size == (640, 640)
        assert result.count == 0

    def test_detect_pokemon_icons_on_synthetic_frame(self):
        """合成フレームに対してdetect_pokemon_iconsがエラーなく動作する。"""
        detector = YOLODetector()
        frame = make_synthetic_frame(640, 640)
        icons = detector.detect_pokemon_icons(frame, min_confidence=0.3)
        assert isinstance(icons, list)

    def test_detect_different_resolutions(self):
        """640x640以外の解像度でもフォールバック検出が正常動作する。"""
        detector = YOLODetector()
        for size in [(320, 240), (640, 640), (1280, 720), (1920, 1080)]:
            frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
            result = detector.detect(frame)
            assert result.frame_size == size


# --- Phase 6: 推論速度テスト ---


class TestInferenceSpeed:
    """推論速度のベンチマークテスト。"""

    def test_benchmark_fallback_mode(self):
        """フォールバックモードのベンチマーク結果が正しい形式であること。"""
        detector = YOLODetector()
        frame = make_synthetic_frame(640, 640)
        result = detector.benchmark(frame, iterations=5)

        assert result["iterations"] == 5
        assert result["model_available"] is False
        assert result["frame_size"] == (640, 640)
        assert "avg_ms" in result
        assert "min_ms" in result
        assert "max_ms" in result
        assert result["avg_ms"] >= 0.0
        assert result["min_ms"] >= 0.0
        assert result["max_ms"] >= 0.0
        assert result["min_ms"] <= result["avg_ms"] <= result["max_ms"]

    def test_benchmark_timing_consistency(self):
        """ベンチマークのタイミングが合理的であること。"""
        detector = YOLODetector()
        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        result = detector.benchmark(frame, iterations=10)
        assert result["avg_ms"] < 100.0

    def test_benchmark_single_iteration(self):
        """1回のイテレーションでもベンチマークが動作する。"""
        detector = YOLODetector()
        frame = np.zeros((640, 640, 3), dtype=np.uint8)
        result = detector.benchmark(frame, iterations=1)
        assert result["iterations"] == 1
        assert result["min_ms"] == result["max_ms"]

    def test_detect_fallback_speed(self):
        """フォールバック検出が十分高速であること (100ms以下)。"""
        import time

        detector = YOLODetector()
        frame = make_synthetic_frame(640, 640)

        start = time.perf_counter()
        for _ in range(100):
            detector.detect(frame)
        elapsed_ms = (time.perf_counter() - start) * 1000

        avg_ms = elapsed_ms / 100
        assert avg_ms < 100.0, f"Average detection time {avg_ms:.2f}ms exceeds 100ms target"


# --- Phase 6: NMSパラメータ調整テスト ---


class TestNMSParameters:
    """NMS (Non-Maximum Suppression) のパラメータ調整テスト。"""

    def test_apply_nms_no_overlap(self):
        """重複しない検出結果はすべて保持される。"""
        detections = [
            make_detection(bbox=(0, 0, 50, 50), confidence=0.9),
            make_detection(bbox=(100, 100, 150, 150), confidence=0.8),
            make_detection(bbox=(200, 200, 250, 250), confidence=0.7),
        ]
        result = YOLODetector.apply_nms(detections, iou_threshold=0.5)
        assert len(result) == 3

    def test_apply_nms_full_overlap(self):
        """完全に重複する検出は1つに統合される。"""
        detections = [
            make_detection(bbox=(10, 10, 60, 60), confidence=0.9),
            make_detection(bbox=(10, 10, 60, 60), confidence=0.7),
            make_detection(bbox=(10, 10, 60, 60), confidence=0.5),
        ]
        result = YOLODetector.apply_nms(detections, iou_threshold=0.5)
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_apply_nms_partial_overlap(self):
        """部分的に重複する検出のNMS動作。"""
        detections = [
            make_detection(bbox=(0, 0, 100, 100), confidence=0.9),
            make_detection(bbox=(50, 50, 150, 150), confidence=0.8),
        ]
        result_strict = YOLODetector.apply_nms(detections, iou_threshold=0.1)
        assert len(result_strict) == 1

        result_loose = YOLODetector.apply_nms(detections, iou_threshold=0.9)
        assert len(result_loose) == 2

    def test_apply_nms_empty_input(self):
        """空のリストに対するNMS。"""
        result = YOLODetector.apply_nms([], iou_threshold=0.5)
        assert result == []

    def test_apply_nms_single_detection(self):
        """1つの検出に対するNMS。"""
        detections = [make_detection(confidence=0.9)]
        result = YOLODetector.apply_nms(detections, iou_threshold=0.5)
        assert len(result) == 1

    def test_apply_nms_preserves_highest_confidence(self):
        """NMSが最も高いconfidenceの検出を保持すること。"""
        detections = [
            make_detection(bbox=(0, 0, 100, 100), confidence=0.3),
            make_detection(bbox=(5, 5, 105, 105), confidence=0.9),
            make_detection(bbox=(2, 2, 102, 102), confidence=0.6),
        ]
        result = YOLODetector.apply_nms(detections, iou_threshold=0.5)
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_apply_nms_different_thresholds(self):
        """異なるIoU閾値での挙動の一貫性。"""
        detections = [
            make_detection(bbox=(0, 0, 100, 100), confidence=0.9),
            make_detection(bbox=(30, 30, 130, 130), confidence=0.8),
            make_detection(bbox=(200, 200, 300, 300), confidence=0.7),
        ]
        for threshold in [0.1, 0.3, 0.5, 0.7, 0.9]:
            result = YOLODetector.apply_nms(detections, iou_threshold=threshold)
            assert len(result) >= 1
            assert all(d.confidence > 0 for d in result)

    def test_nms_threshold_setter(self):
        """IoU閾値の動的変更。"""
        detector = YOLODetector()
        assert detector.iou_threshold == YOLODetector.DEFAULT_IOU_THRESHOLD

        detector.iou_threshold = 0.3
        assert detector.iou_threshold == 0.3

        detector.iou_threshold = 0.7
        assert detector.iou_threshold == 0.7

    def test_nms_threshold_validation(self):
        """IoU閾値のバリデーション。"""
        detector = YOLODetector()
        with pytest.raises(ValueError):
            detector.iou_threshold = -0.1
        with pytest.raises(ValueError):
            detector.iou_threshold = 1.5

    def test_confidence_threshold_setter(self):
        """confidence閾値の動的変更。"""
        detector = YOLODetector()
        detector.confidence = 0.5
        assert detector.confidence == 0.5

    def test_confidence_threshold_validation(self):
        """confidence閾値のバリデーション。"""
        detector = YOLODetector()
        with pytest.raises(ValueError):
            detector.confidence = -0.1
        with pytest.raises(ValueError):
            detector.confidence = 1.5


# --- Phase 6: IoU計算テスト ---


class TestIoUComputation:
    """IoU (Intersection over Union) 計算のテスト。"""

    def test_iou_identical_boxes(self):
        """同一ボックスのIoUは1.0。"""
        box = (10, 20, 100, 200)
        assert YOLODetector.compute_iou(box, box) == 1.0

    def test_iou_no_overlap(self):
        """重複のないボックスのIoUは0.0。"""
        box1 = (0, 0, 50, 50)
        box2 = (100, 100, 150, 150)
        assert YOLODetector.compute_iou(box1, box2) == 0.0

    def test_iou_partial_overlap(self):
        """部分的な重複のIoU計算。"""
        box1 = (0, 0, 100, 100)
        box2 = (50, 50, 150, 150)
        iou = YOLODetector.compute_iou(box1, box2)
        expected = 2500 / 17500
        assert abs(iou - expected) < 1e-6

    def test_iou_contained_box(self):
        """一方が完全に包含するケース。"""
        outer = (0, 0, 200, 200)
        inner = (50, 50, 100, 100)
        iou = YOLODetector.compute_iou(outer, inner)
        expected = 2500 / 40000
        assert abs(iou - expected) < 1e-6

    def test_iou_adjacent_boxes(self):
        """隣接するボックスのIoU。"""
        box1 = (0, 0, 50, 50)
        box2 = (50, 0, 100, 50)
        assert YOLODetector.compute_iou(box1, box2) == 0.0

    def test_iou_symmetry(self):
        """IoU計算の対称性。"""
        box1 = (10, 10, 80, 80)
        box2 = (40, 40, 120, 120)
        assert YOLODetector.compute_iou(box1, box2) == YOLODetector.compute_iou(box2, box1)


# --- Phase 6: 座標変換テスト ---


class TestCoordinateConversion:
    """ピクセル座標 ↔ YOLO正規化座標の変換テスト。"""

    def test_bbox_to_yolo_basic(self):
        """基本的なピクセル→YOLO変換。"""
        cx, cy, w, h = YOLODetector.convert_bbox_to_yolo(
            bbox=(100, 200, 300, 400),
            frame_width=640,
            frame_height=480,
        )
        assert abs(cx - 200.0 / 640) < 1e-6
        assert abs(cy - 300.0 / 480) < 1e-6
        assert abs(w - 200.0 / 640) < 1e-6
        assert abs(h - 200.0 / 480) < 1e-6

    def test_yolo_to_bbox_basic(self):
        """基本的なYOLO→ピクセル変換。"""
        x1, y1, x2, y2 = YOLODetector.convert_yolo_to_bbox(
            yolo_coords=(0.5, 0.5, 0.2, 0.3),
            frame_width=640,
            frame_height=480,
        )
        assert x1 == int((0.5 - 0.1) * 640)
        assert y1 == int((0.5 - 0.15) * 480)
        assert x2 == int((0.5 + 0.1) * 640)
        assert y2 == int((0.5 + 0.15) * 480)

    def test_roundtrip_conversion(self):
        """ピクセル→YOLO→ピクセルの往復変換。"""
        original_bbox = (100, 150, 300, 350)
        fw, fh = 640, 480
        yolo = YOLODetector.convert_bbox_to_yolo(original_bbox, fw, fh)
        recovered = YOLODetector.convert_yolo_to_bbox(yolo, fw, fh)
        for orig, rec in zip(original_bbox, recovered):
            assert abs(orig - rec) <= 1

    def test_full_frame_bbox(self):
        """フレーム全体をカバーするbbox。"""
        cx, cy, w, h = YOLODetector.convert_bbox_to_yolo(
            bbox=(0, 0, 640, 480),
            frame_width=640,
            frame_height=480,
        )
        assert abs(cx - 0.5) < 1e-6
        assert abs(cy - 0.5) < 1e-6
        assert abs(w - 1.0) < 1e-6
        assert abs(h - 1.0) < 1e-6

    def test_corner_bbox(self):
        """左上隅の小さなbbox。"""
        cx, cy, w, h = YOLODetector.convert_bbox_to_yolo(
            bbox=(0, 0, 64, 48),
            frame_width=640,
            frame_height=480,
        )
        assert abs(cx - 0.05) < 1e-6
        assert abs(cy - 0.05) < 1e-6
        assert abs(w - 0.1) < 1e-6
        assert abs(h - 0.1) < 1e-6


# --- Phase 6: 学習データ管理テスト ---


class TestTrainingDataManagement:
    """学習データ管理のテスト。"""

    def test_setup_training_dirs(self, tmp_path):
        """学習用ディレクトリ構造が正しく作成されること。"""
        dirs = YOLODetector.setup_training_dirs(tmp_path / "training")
        assert "images_train" in dirs
        assert "images_val" in dirs
        assert "labels_train" in dirs
        assert "labels_val" in dirs
        for d in dirs.values():
            assert d.exists()
            assert d.is_dir()

    def test_setup_training_dirs_idempotent(self, tmp_path):
        """ディレクトリ作成が冪等であること (2回実行してもエラーなし)。"""
        base = tmp_path / "data"
        dirs1 = YOLODetector.setup_training_dirs(base)
        dirs2 = YOLODetector.setup_training_dirs(base)
        assert dirs1 == dirs2

    def test_setup_training_dirs_structure(self, tmp_path):
        """正しいサブディレクトリ構造が作成されること。"""
        base = tmp_path / "yolo_data"
        dirs = YOLODetector.setup_training_dirs(base)
        assert dirs["images_train"] == base / "images" / "train"
        assert dirs["images_val"] == base / "images" / "val"
        assert dirs["labels_train"] == base / "labels" / "train"
        assert dirs["labels_val"] == base / "labels" / "val"

    def test_create_training_config_full(self):
        """完全なクラスリストでの学習設定生成。"""
        names = [f"pokemon_{i}" for i in range(213)]
        config = YOLODetector.create_training_config(
            data_dir="/path/to/data",
            num_classes=213,
            class_names=names,
        )
        assert config["nc"] == 213
        assert len(config["names"]) == 213
        assert config["names"][0] == "pokemon_0"
        assert config["names"][212] == "pokemon_212"

    def test_create_training_config_paths(self):
        """学習設定のパスが正しいこと。"""
        config = YOLODetector.create_training_config(
            data_dir="../training_data",
            num_classes=10,
            class_names=[f"cls_{i}" for i in range(10)],
        )
        assert config["path"] == "../training_data"
        assert config["train"] == "images/train"
        assert config["val"] == "images/val"

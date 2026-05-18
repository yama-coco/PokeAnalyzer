"""YOLOデテクターのテスト。

学習済みモデルが無い環境でもフォールバックモードで動作するテスト。
"""

import numpy as np

from app.services.yolo_detector import Detection, DetectionResult, YOLODetector


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

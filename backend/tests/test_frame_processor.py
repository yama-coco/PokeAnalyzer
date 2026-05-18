"""フレームプロセッサのテスト。"""

import numpy as np

from app.services.frame_processor import (
    STANDARD_HEIGHT,
    STANDARD_WIDTH,
    FrameProcessor,
    RegionOfInterest,
)


def _make_frame(
    w: int = STANDARD_WIDTH,
    h: int = STANDARD_HEIGHT,
    color: tuple[int, int, int] = (128, 128, 128),
) -> np.ndarray:
    """テスト用のダミーフレーム (BGR) を生成する。"""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = color
    return frame


class TestRegionOfInterest:
    def test_to_pixel(self):
        roi = RegionOfInterest("test", 0.1, 0.2, 0.3, 0.4)
        px, py, pw, ph = roi.to_pixel(1920, 1080)
        assert px == 192
        assert py == 216
        assert pw == 576
        assert ph == 432

    def test_to_pixel_full_frame(self):
        roi = RegionOfInterest("full", 0.0, 0.0, 1.0, 1.0)
        px, py, pw, ph = roi.to_pixel(1920, 1080)
        assert px == 0
        assert py == 0
        assert pw == 1920
        assert ph == 1080


class TestFrameProcessor:
    def test_preprocess_no_resize(self):
        fp = FrameProcessor()
        frame = _make_frame()
        result = fp.preprocess(frame)
        assert result.shape == frame.shape

    def test_preprocess_resize(self):
        fp = FrameProcessor()
        frame = _make_frame(640, 480)
        result = fp.preprocess(frame)
        assert result.shape == (STANDARD_HEIGHT, STANDARD_WIDTH, 3)

    def test_extract_roi(self):
        fp = FrameProcessor()
        frame = _make_frame()
        roi = RegionOfInterest("test", 0.0, 0.0, 0.5, 0.5)
        cropped = fp.extract_roi(frame, roi)
        assert cropped.shape[0] == STANDARD_HEIGHT // 2
        assert cropped.shape[1] == STANDARD_WIDTH // 2

    def test_extract_all_rois(self):
        fp = FrameProcessor()
        frame = _make_frame()
        rois = fp.extract_all_rois(frame)
        assert "text_box" in rois
        assert "vs_icons" in rois
        assert "hp_ally_1" in rois
        for name, roi_frame in rois.items():
            assert roi_frame.shape[0] > 0
            assert roi_frame.shape[1] > 0

    def test_detect_change_first_frame(self):
        fp = FrameProcessor()
        frame = _make_frame()
        changed, ratio = fp.detect_change(frame)
        assert not changed
        assert ratio == 0.0

    def test_detect_change_identical_frames(self):
        fp = FrameProcessor()
        frame = _make_frame()
        fp.detect_change(frame)  # First frame
        changed, ratio = fp.detect_change(frame.copy())
        assert not changed
        assert ratio == 0.0

    def test_detect_change_different_frames(self):
        fp = FrameProcessor()
        frame1 = _make_frame(color=(0, 0, 0))
        frame2 = _make_frame(color=(255, 255, 255))
        fp.detect_change(frame1)
        changed, ratio = fp.detect_change(frame2)
        assert changed
        assert ratio > 0.5

    def test_analyze_brightness(self):
        fp = FrameProcessor()
        black = _make_frame(color=(0, 0, 0))
        white = _make_frame(color=(255, 255, 255))
        assert fp.analyze_brightness(black) < 1.0
        assert fp.analyze_brightness(white) > 254.0

    def test_get_dominant_colors(self):
        fp = FrameProcessor()
        red_frame = _make_frame(color=(0, 0, 255))  # BGR
        colors = fp.get_dominant_colors(red_frame, k=1)
        assert len(colors) == 1
        # Should be approximately red (255, 0, 0) in RGB
        r, g, b = colors[0]
        assert r > 200
        assert g < 50
        assert b < 50

    def test_detect_color_region(self):
        fp = FrameProcessor()
        # Create a green frame
        green_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
        green_bgr[:] = (0, 255, 0)  # BGR green
        # Detect green in HSV (H: 35-85)
        ratio = fp.detect_color_region(green_bgr, (35, 100, 100), (85, 255, 255))
        assert ratio > 0.9

    def test_detect_hp_bar_green(self):
        fp = FrameProcessor()
        # Create a frame with green bar
        bar = np.zeros((20, 100, 3), dtype=np.uint8)
        bar[:, :80] = (0, 255, 0)  # 80% green bar
        hp = fp.detect_hp_bar(bar)
        assert hp is not None
        assert 0.7 < hp < 0.9

    def test_detect_hp_bar_empty(self):
        fp = FrameProcessor()
        bar = np.zeros((20, 100, 3), dtype=np.uint8)
        hp = fp.detect_hp_bar(bar)
        assert hp is None

    def test_process_frame(self):
        fp = FrameProcessor()
        frame = _make_frame()
        analysis = fp.process_frame(frame)
        assert analysis.frame_id == 1
        assert len(analysis.dominant_colors) == 3
        assert analysis.brightness > 0

    def test_reset(self):
        fp = FrameProcessor()
        frame = _make_frame()
        fp.process_frame(frame)
        fp.reset()
        assert fp._frame_counter == 0
        assert fp._prev_frame_gray is None

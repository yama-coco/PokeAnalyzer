"""テンプレートマッチャーのテスト。"""

import numpy as np

from app.services.template_matcher import TemplateMatcher


def _make_icon(w: int = 50, h: int = 50, color: tuple[int, int, int] = (0, 0, 255)) -> np.ndarray:
    """テスト用のアイコン画像を生成する。"""
    icon = np.zeros((h, w, 3), dtype=np.uint8)
    icon[10:40, 10:40] = color
    return icon


def _make_frame_with_icon(
    icon: np.ndarray,
    x: int = 100,
    y: int = 100,
    frame_w: int = 640,
    frame_h: int = 480,
) -> np.ndarray:
    """アイコンを含むテスト用フレームを生成する。"""
    frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
    frame[:] = (128, 128, 128)  # Gray background
    ih, iw = icon.shape[:2]
    frame[y : y + ih, x : x + iw] = icon
    return frame


class TestTemplateMatcher:
    def test_empty_matcher(self):
        tm = TemplateMatcher()
        assert tm.template_count == 0
        assert tm.template_names == []

    def test_add_template(self):
        tm = TemplateMatcher()
        icon = _make_icon()
        assert tm.add_template("pikachu", icon, "pokemon")
        assert tm.template_count == 1
        assert "pikachu" in tm.template_names

    def test_add_empty_template(self):
        tm = TemplateMatcher()
        empty = np.array([], dtype=np.uint8)
        assert not tm.add_template("empty", empty)
        assert tm.template_count == 0

    def test_remove_template(self):
        tm = TemplateMatcher()
        icon = _make_icon()
        tm.add_template("test", icon)
        assert tm.remove_template("test")
        assert tm.template_count == 0
        assert not tm.remove_template("nonexistent")

    def test_match_single_exact(self):
        tm = TemplateMatcher()
        icon = _make_icon()
        tm.add_template("red_square", icon, "test")
        frame = _make_frame_with_icon(icon, x=100, y=100)
        results = tm.match_single(frame, "red_square", threshold=0.9, multi_scale=False)
        assert len(results) > 0
        best = max(results, key=lambda r: r.confidence)
        assert best.confidence > 0.9
        assert best.template_name == "red_square"
        # Location should be near (100, 100)
        assert abs(best.location[0] - 100) < 5
        assert abs(best.location[1] - 100) < 5

    def test_match_nonexistent_template(self):
        tm = TemplateMatcher()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = tm.match_single(frame, "nonexistent")
        assert results == []

    def test_match_category(self):
        tm = TemplateMatcher()
        icon1 = _make_icon(color=(0, 0, 255))
        icon2 = _make_icon(color=(0, 255, 0))
        tm.add_template("mon1", icon1, "pokemon")
        tm.add_template("mon2", icon2, "pokemon")
        tm.add_template("ui_bar", _make_icon(color=(255, 0, 0)), "ui")
        frame = _make_frame_with_icon(icon1)
        results = tm.match_category(frame, "pokemon", threshold=0.7, multi_scale=False)
        # Should find matches from pokemon category
        assert any(r.template_name in ("mon1", "mon2") for r in results)

    def test_match_all(self):
        tm = TemplateMatcher()
        icon = _make_icon()
        tm.add_template("test1", icon, "a")
        tm.add_template("test2", icon, "b")
        frame = _make_frame_with_icon(icon)
        results = tm.match_all(frame, threshold=0.9, multi_scale=False)
        assert len(results) >= 1

    def test_find_best_match(self):
        tm = TemplateMatcher()
        icon = _make_icon(color=(255, 0, 0))
        tm.add_template("blue", icon, "pokemon")
        frame = _make_frame_with_icon(icon)
        best = tm.find_best_match(frame, threshold=0.8)
        assert best is not None
        assert best.template_name == "blue"

    def test_find_best_match_no_match(self):
        tm = TemplateMatcher()
        icon = _make_icon(color=(255, 0, 0))
        tm.add_template("blue", icon, "pokemon")
        # Completely different frame
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        best = tm.find_best_match(frame, threshold=0.99)
        assert best is None

    def test_nms_deduplication(self):
        """NMSで重複結果が除去されるか。"""
        tm = TemplateMatcher()
        icon = _make_icon()
        tm.add_template("test", icon, "pokemon")
        frame = _make_frame_with_icon(icon)
        results = tm.match_single(frame, "test", threshold=0.5, multi_scale=True)
        # Multi-scale search may find multiple overlapping results, NMS should reduce
        locations = [r.location for r in results]
        # All results should be near the same location (deduped)
        if len(locations) > 1:
            for loc in locations[1:]:
                assert abs(loc[0] - locations[0][0]) > 10 or abs(loc[1] - locations[0][1]) > 10

    def test_iou_computation(self):
        assert TemplateMatcher._compute_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
        assert TemplateMatcher._compute_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
        iou = TemplateMatcher._compute_iou((0, 0, 10, 10), (5, 5, 15, 15))
        assert 0.1 < iou < 0.2

    def test_bbox_property(self):
        from app.services.template_matcher import MatchResult

        mr = MatchResult("test", 0.9, (10, 20), (50, 60))
        assert mr.bbox == (10, 20, 60, 80)
        assert mr.center == (35, 50)

    def test_clear(self):
        tm = TemplateMatcher()
        tm.add_template("a", _make_icon(), "x")
        tm.add_template("b", _make_icon(), "y")
        tm.clear()
        assert tm.template_count == 0

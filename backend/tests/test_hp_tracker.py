"""HP Tracker のテスト"""

from __future__ import annotations

import numpy as np
import pytest

from app.services.hp_tracker import HPTracker


@pytest.fixture
def tracker():
    t = HPTracker()
    return t


class TestHPValueParsing:
    def test_parse_standard_hp(self, tracker: HPTracker):
        result = tracker.parse_hp_value("149/185")
        assert result == (149, 185)

    def test_parse_hp_with_spaces(self, tracker: HPTracker):
        result = tracker.parse_hp_value("149 / 185")
        assert result == (149, 185)

    def test_parse_full_hp(self, tracker: HPTracker):
        result = tracker.parse_hp_value("172/172")
        assert result == (172, 172)

    def test_parse_zero_hp(self, tracker: HPTracker):
        result = tracker.parse_hp_value("0/185")
        assert result == (0, 185)

    def test_parse_invalid_hp(self, tracker: HPTracker):
        result = tracker.parse_hp_value("abc")
        assert result is None

    def test_parse_over_max_hp(self, tracker: HPTracker):
        result = tracker.parse_hp_value("200/100")
        assert result is None

    def test_parse_empty(self, tracker: HPTracker):
        result = tracker.parse_hp_value("")
        assert result is None

    def test_parse_hp_in_text(self, tracker: HPTracker):
        result = tracker.parse_hp_value("ガブリアス 149/185 HP")
        assert result == (149, 185)


class TestHPPercentParsing:
    def test_parse_percent(self, tracker: HPTracker):
        result = tracker.parse_hp_percent("73%")
        assert result == 73.0

    def test_parse_percent_with_space(self, tracker: HPTracker):
        result = tracker.parse_hp_percent("73 %")
        assert result == 73.0

    def test_parse_100_percent(self, tracker: HPTracker):
        result = tracker.parse_hp_percent("100%")
        assert result == 100.0

    def test_parse_0_percent(self, tracker: HPTracker):
        result = tracker.parse_hp_percent("0%")
        assert result == 0.0

    def test_parse_invalid_percent(self, tracker: HPTracker):
        result = tracker.parse_hp_percent("abc")
        assert result is None

    def test_parse_over_100(self, tracker: HPTracker):
        result = tracker.parse_hp_percent("150%")
        assert result is None

    def test_parse_percent_in_text(self, tracker: HPTracker):
        result = tracker.parse_hp_percent("バンギラス 38%")
        assert result == 38.0


class TestHPBarDetection:
    def test_detect_full_green_bar(self, tracker: HPTracker):
        roi = np.zeros((20, 200, 3), dtype=np.uint8)
        # 緑色のHPバー (BGR: 0, 200, 0 → HSV: ~60, ~255, ~200)
        roi[:, :, 1] = 200  # Green
        ratio = tracker.detect_hp_bar_ratio(roi)
        assert ratio is not None
        assert ratio > 0.8

    def test_detect_half_bar(self, tracker: HPTracker):
        roi = np.zeros((20, 200, 3), dtype=np.uint8)
        # 左半分だけ緑
        roi[:, :100, 1] = 200
        # 右半分はグレー (背景)
        roi[:, 100:, :] = 80
        ratio = tracker.detect_hp_bar_ratio(roi)
        assert ratio is not None
        assert 0.3 < ratio < 0.7

    def test_detect_empty_roi(self, tracker: HPTracker):
        roi = np.zeros((0, 0, 3), dtype=np.uint8)
        ratio = tracker.detect_hp_bar_ratio(roi)
        assert ratio is None

    def test_detect_no_hp_bar(self, tracker: HPTracker):
        roi = np.zeros((20, 200, 3), dtype=np.uint8)
        roi[:, :, :] = 50  # 暗いグレー
        ratio = tracker.detect_hp_bar_ratio(roi)
        assert ratio is None


class TestHPTracking:
    def test_update_hp_with_values(self, tracker: HPTracker):
        event = tracker.update_hp(
            slot=0, name="ガブリアス", current_hp=183, max_hp=183, source="ocr_value"
        )
        assert event is None  # 初回は変化なし
        assert tracker.last_readings[0].hp_percent == 100.0

    def test_detect_damage(self, tracker: HPTracker):
        tracker.update_hp(slot=0, name="ガブリアス", current_hp=183, max_hp=183)
        event = tracker.update_hp(slot=0, name="ガブリアス", current_hp=149, max_hp=183)
        assert event is not None
        assert event.damage_percent > 0
        assert event.hp_before == 100.0
        assert event.hp_after == pytest.approx(149 / 183 * 100, abs=0.5)

    def test_detect_damage_percent(self, tracker: HPTracker):
        tracker.update_hp(slot=2, name="バンギラス", hp_percent=100.0)
        event = tracker.update_hp(slot=2, name="バンギラス", hp_percent=73.0)
        assert event is not None
        assert event.damage_percent == 27.0

    def test_no_damage_small_change(self, tracker: HPTracker):
        tracker.update_hp(slot=0, name="ガブリアス", hp_percent=100.0)
        event = tracker.update_hp(slot=0, name="ガブリアス", hp_percent=99.8)
        assert event is None  # 0.5% 以下の変化はノイズ

    def test_damage_history(self, tracker: HPTracker):
        tracker.update_hp(slot=0, name="ガブリアス", hp_percent=100.0)
        tracker.update_hp(slot=0, name="ガブリアス", hp_percent=70.0)
        tracker.update_hp(slot=0, name="ガブリアス", hp_percent=40.0)
        history = tracker.get_damage_summary()
        assert len(history) == 2

    def test_process_ally_hp_text(self, tracker: HPTracker):
        reading = tracker.process_ally_hp_text(0, "ガブリアス", "149/185")
        assert reading is not None
        assert reading.current_hp == 149
        assert reading.max_hp == 185
        assert reading.source == "ocr_value"

    def test_process_enemy_hp_text(self, tracker: HPTracker):
        reading = tracker.process_enemy_hp_text(2, "バンギラス", "73%")
        assert reading is not None
        assert reading.hp_percent == 73.0
        assert reading.source == "ocr_percent"

    def test_reset(self, tracker: HPTracker):
        tracker.update_hp(slot=0, name="ガブリアス", hp_percent=100.0)
        tracker.update_hp(slot=0, name="ガブリアス", hp_percent=50.0)
        tracker.reset()
        assert len(tracker.last_readings) == 0
        assert len(tracker.damage_history) == 0

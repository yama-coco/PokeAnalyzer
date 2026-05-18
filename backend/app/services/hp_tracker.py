"""HP追跡モジュール

フレームからHPバー・HP数値を検出し、ダメージ履歴を追跡する。

自分のHP: OCRで実数値を読み取る (例: 149/185)
相手のHP: OCRでパーセンテージを読み取る (例: 73%)
         またはHPバーのピクセル長比率から推定する
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class HPReading:
    """1回のHP読取結果。"""

    slot: int
    name: str
    current_hp: int = 0
    max_hp: int = 0
    hp_percent: float = 100.0
    source: str = ""  # "ocr_value", "ocr_percent", "bar_pixel"
    timestamp: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "slot": self.slot,
            "name": self.name,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "hp_percent": self.hp_percent,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class DamageEvent:
    """ダメージイベント。"""

    turn: int
    slot: int
    name: str
    damage_percent: float
    hp_before: float
    hp_after: float
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "slot": self.slot,
            "name": self.name,
            "damage_percent": round(self.damage_percent, 1),
            "hp_before": round(self.hp_before, 1),
            "hp_after": round(self.hp_after, 1),
        }


# HP実数値パターン: "149/185" or "149 / 185"
HP_VALUE_PATTERN = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})")
# HPパーセンテージパターン: "73%" or "73 %"
HP_PERCENT_PATTERN = re.compile(r"(\d{1,3})\s*%")


class HPTracker:
    """HPの追跡と変化検出を行うクラス。"""

    # HPバーのHSV色範囲
    HP_GREEN_LOWER = np.array([35, 100, 100])
    HP_GREEN_UPPER = np.array([85, 255, 255])
    HP_YELLOW_LOWER = np.array([20, 100, 100])
    HP_YELLOW_UPPER = np.array([35, 255, 255])
    HP_RED_LOWER_1 = np.array([0, 100, 100])
    HP_RED_UPPER_1 = np.array([10, 255, 255])
    HP_RED_LOWER_2 = np.array([170, 100, 100])
    HP_RED_UPPER_2 = np.array([180, 255, 255])

    # 相手HPバーの背景色（グレー系）
    HP_BG_LOWER = np.array([0, 0, 40])
    HP_BG_UPPER = np.array([180, 50, 120])

    def __init__(self) -> None:
        self._last_readings: dict[int, HPReading] = {}
        self._damage_history: list[DamageEvent] = []
        self._current_turn = 0

    @property
    def last_readings(self) -> dict[int, HPReading]:
        return self._last_readings

    @property
    def damage_history(self) -> list[DamageEvent]:
        return self._damage_history

    def set_turn(self, turn: int) -> None:
        self._current_turn = turn

    def parse_hp_value(self, text: str) -> tuple[int, int] | None:
        """OCRテキストからHP実数値を解析する。

        Args:
            text: OCR結果テキスト (例: "149/185")

        Returns:
            (current_hp, max_hp) or None
        """
        match = HP_VALUE_PATTERN.search(text)
        if match:
            current = int(match.group(1))
            maximum = int(match.group(2))
            if 0 <= current <= maximum <= 999 and maximum > 0:
                return current, maximum
        return None

    def parse_hp_percent(self, text: str) -> float | None:
        """OCRテキストからHP%を解析する。

        Args:
            text: OCR結果テキスト (例: "73%")

        Returns:
            HP percentage (0-100) or None
        """
        match = HP_PERCENT_PATTERN.search(text)
        if match:
            percent = int(match.group(1))
            if 0 <= percent <= 100:
                return float(percent)
        return None

    def detect_hp_bar_ratio(self, roi: np.ndarray) -> float | None:
        """HPバーROIからHP割合をピクセル比率で推定する。

        Args:
            roi: HPバー領域の画像

        Returns:
            HP割合 (0.0-1.0) or None
        """
        if roi.size == 0 or roi.shape[0] < 3 or roi.shape[1] < 10:
            return None

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        green = cv2.inRange(hsv, self.HP_GREEN_LOWER, self.HP_GREEN_UPPER)
        yellow = cv2.inRange(hsv, self.HP_YELLOW_LOWER, self.HP_YELLOW_UPPER)
        red1 = cv2.inRange(hsv, self.HP_RED_LOWER_1, self.HP_RED_UPPER_1)
        red2 = cv2.inRange(hsv, self.HP_RED_LOWER_2, self.HP_RED_UPPER_2)

        hp_mask = green | yellow | red1 | red2

        if np.count_nonzero(hp_mask) == 0:
            return None

        # 最もHPバーピクセルが多い行を基準にする
        row_sums = np.sum(hp_mask > 0, axis=1)
        if row_sums.max() == 0:
            return None

        best_row = int(np.argmax(row_sums))
        bar_pixels = int(row_sums[best_row])
        total_width = hp_mask.shape[1]

        # HPバー背景（灰色部分）を含めた全体幅を推定
        bg_mask = cv2.inRange(hsv, self.HP_BG_LOWER, self.HP_BG_UPPER)
        combined = hp_mask | bg_mask
        row_combined = np.sum(combined[best_row] > 0)

        if row_combined > bar_pixels:
            return bar_pixels / row_combined

        return bar_pixels / total_width

    def update_hp(
        self,
        slot: int,
        name: str,
        current_hp: int = 0,
        max_hp: int = 0,
        hp_percent: float = -1.0,
        source: str = "manual",
        confidence: float = 1.0,
    ) -> DamageEvent | None:
        """HPを更新し、変化があればDamageEventを返す。"""
        now = time.time()

        if hp_percent < 0 and max_hp > 0:
            hp_percent = round(current_hp / max_hp * 100, 1)

        reading = HPReading(
            slot=slot,
            name=name,
            current_hp=current_hp,
            max_hp=max_hp,
            hp_percent=hp_percent,
            source=source,
            timestamp=now,
            confidence=confidence,
        )

        old = self._last_readings.get(slot)
        self._last_readings[slot] = reading

        if old is not None and abs(old.hp_percent - hp_percent) > 0.5:
            event = DamageEvent(
                turn=self._current_turn,
                slot=slot,
                name=name,
                damage_percent=round(old.hp_percent - hp_percent, 1),
                hp_before=old.hp_percent,
                hp_after=hp_percent,
                timestamp=now,
            )
            self._damage_history.append(event)
            return event

        return None

    def process_ally_hp_text(self, slot: int, name: str, text: str) -> HPReading | None:
        """味方のHP OCRテキストを処理する。"""
        result = self.parse_hp_value(text)
        if result is None:
            return None

        current, maximum = result
        self.update_hp(
            slot=slot,
            name=name,
            current_hp=current,
            max_hp=maximum,
            source="ocr_value",
        )
        return self._last_readings.get(slot)

    def process_enemy_hp_text(self, slot: int, name: str, text: str) -> HPReading | None:
        """相手のHP OCRテキスト（パーセンテージ）を処理する。"""
        percent = self.parse_hp_percent(text)
        if percent is None:
            return None

        self.update_hp(
            slot=slot,
            name=name,
            hp_percent=percent,
            source="ocr_percent",
        )
        return self._last_readings.get(slot)

    def process_hp_bar(self, slot: int, name: str, roi: np.ndarray) -> HPReading | None:
        """HPバーROIからHP割合を推定する。"""
        ratio = self.detect_hp_bar_ratio(roi)
        if ratio is None:
            return None

        self.update_hp(
            slot=slot,
            name=name,
            hp_percent=round(ratio * 100, 1),
            source="bar_pixel",
            confidence=0.8,
        )
        return self._last_readings.get(slot)

    def get_damage_summary(self) -> list[dict]:
        """全ダメージ履歴を取得する。"""
        return [e.to_dict() for e in self._damage_history]

    def get_current_hp_state(self) -> dict[int, dict]:
        """現在のHP状態を取得する。"""
        return {slot: r.to_dict() for slot, r in self._last_readings.items()}

    def reset(self) -> None:
        """状態をリセットする。"""
        self._last_readings.clear()
        self._damage_history.clear()
        self._current_turn = 0


# グローバルインスタンス
hp_tracker = HPTracker()

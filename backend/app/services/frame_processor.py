"""フレームプロセッサ

OBS仮想カメラから取得したフレームの前処理、
ROI（関心領域）抽出、変化検知を行う。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ポケモンチャンピオンズの標準解像度 (1920x1080 を想定)
STANDARD_WIDTH = 1920
STANDARD_HEIGHT = 1080


@dataclass
class RegionOfInterest:
    """画面上の関心領域 (ROI) の定義。

    座標は正規化値 (0.0-1.0) で指定し、
    任意の解像度に対応できるようにする。
    """

    name: str
    x: float  # 左上X (0.0-1.0)
    y: float  # 左上Y (0.0-1.0)
    w: float  # 幅 (0.0-1.0)
    h: float  # 高さ (0.0-1.0)

    def to_pixel(self, frame_w: int, frame_h: int) -> tuple[int, int, int, int]:
        """正規化座標をピクセル座標に変換する。"""
        px = int(self.x * frame_w)
        py = int(self.y * frame_h)
        pw = int(self.w * frame_w)
        ph = int(self.h * frame_h)
        return px, py, pw, ph


# VS画面: 相手の6体アイコンが表示される領域 (仮の位置)
VS_SCREEN_ICONS = RegionOfInterest("vs_icons", 0.55, 0.15, 0.40, 0.70)

# 選出画面: パーティ一覧
SELECTION_AREA = RegionOfInterest("selection", 0.05, 0.10, 0.90, 0.80)

# バトル画面: テキストボックス (画面下部)
TEXT_BOX = RegionOfInterest("text_box", 0.0, 0.75, 1.0, 0.25)

# バトル画面: HPバー領域 (味方・相手)
HP_BAR_ALLY_1 = RegionOfInterest("hp_ally_1", 0.55, 0.55, 0.20, 0.05)
HP_BAR_ALLY_2 = RegionOfInterest("hp_ally_2", 0.75, 0.65, 0.20, 0.05)
HP_BAR_ENEMY_1 = RegionOfInterest("hp_enemy_1", 0.05, 0.15, 0.20, 0.05)
HP_BAR_ENEMY_2 = RegionOfInterest("hp_enemy_2", 0.25, 0.25, 0.20, 0.05)

# バトル画面: コマンドメニュー
COMMAND_MENU = RegionOfInterest("command_menu", 0.60, 0.60, 0.38, 0.38)

# 全定義済みROIのリスト
ALL_ROIS = [
    VS_SCREEN_ICONS,
    SELECTION_AREA,
    TEXT_BOX,
    HP_BAR_ALLY_1,
    HP_BAR_ALLY_2,
    HP_BAR_ENEMY_1,
    HP_BAR_ENEMY_2,
    COMMAND_MENU,
]


@dataclass
class FrameAnalysis:
    """フレーム解析結果。"""

    frame_id: int = 0
    has_significant_change: bool = False
    dominant_colors: list[tuple[int, int, int]] = field(default_factory=list)
    brightness: float = 0.0
    roi_frames: dict[str, np.ndarray] = field(default_factory=dict)


class FrameProcessor:
    """フレームの前処理と解析を行うクラス。"""

    CHANGE_THRESHOLD = 30.0
    MIN_CHANGE_AREA_RATIO = 0.05

    def __init__(self, target_width: int = STANDARD_WIDTH, target_height: int = STANDARD_HEIGHT):
        self._target_width = target_width
        self._target_height = target_height
        self._prev_frame_gray: np.ndarray | None = None
        self._frame_counter = 0

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """フレームを標準サイズにリサイズし前処理を行う。"""
        h, w = frame.shape[:2]
        if w != self._target_width or h != self._target_height:
            frame = cv2.resize(frame, (self._target_width, self._target_height))
        return frame

    def extract_roi(self, frame: np.ndarray, roi: RegionOfInterest) -> np.ndarray:
        """フレームからROI領域を切り出す。"""
        h, w = frame.shape[:2]
        px, py, pw, ph = roi.to_pixel(w, h)
        px = max(0, min(px, w))
        py = max(0, min(py, h))
        pw = max(1, min(pw, w - px))
        ph = max(1, min(ph, h - py))
        return frame[py : py + ph, px : px + pw].copy()

    def extract_all_rois(self, frame: np.ndarray) -> dict[str, np.ndarray]:
        """全定義済みROIを切り出す。"""
        return {roi.name: self.extract_roi(frame, roi) for roi in ALL_ROIS}

    def detect_change(self, frame: np.ndarray) -> tuple[bool, float]:
        """前フレームとの差分から変化を検知する。

        Returns:
            (significant_change: bool, change_ratio: float)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self._prev_frame_gray is None:
            self._prev_frame_gray = gray
            return False, 0.0

        diff = cv2.absdiff(self._prev_frame_gray, gray)
        _, thresh = cv2.threshold(diff, self.CHANGE_THRESHOLD, 255, cv2.THRESH_BINARY)
        change_ratio = float(np.count_nonzero(thresh)) / thresh.size

        self._prev_frame_gray = gray
        significant = change_ratio > self.MIN_CHANGE_AREA_RATIO
        return significant, change_ratio

    def analyze_brightness(self, frame: np.ndarray) -> float:
        """フレームの平均輝度を計算する。"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    def get_dominant_colors(self, frame: np.ndarray, k: int = 3) -> list[tuple[int, int, int]]:
        """フレームの支配的な色をK-meansクラスタリングで取得する。"""
        small = cv2.resize(frame, (64, 64))
        pixels = small.reshape(-1, 3).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, _, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
        return [(int(c[2]), int(c[1]), int(c[0])) for c in centers]

    def detect_color_region(
        self,
        frame: np.ndarray,
        lower_hsv: tuple[int, int, int],
        upper_hsv: tuple[int, int, int],
    ) -> float:
        """指定HSV範囲の色領域の面積比率を返す。"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower_hsv), np.array(upper_hsv))
        return float(np.count_nonzero(mask)) / mask.size

    def detect_hp_bar(self, roi_frame: np.ndarray) -> float | None:
        """HPバー領域からHP割合を推定する。

        緑〜黄〜赤のグラデーションを検出し、バーの長さ比率を返す。
        Returns:
            HP割合 (0.0-1.0)。検出失敗時はNone。
        """
        if roi_frame.size == 0:
            return None

        hsv = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2HSV)

        # HPバーの緑 (H: 35-85)
        green_mask = cv2.inRange(hsv, np.array([35, 100, 100]), np.array([85, 255, 255]))
        # HPバーの黄 (H: 20-35)
        yellow_mask = cv2.inRange(hsv, np.array([20, 100, 100]), np.array([35, 255, 255]))
        # HPバーの赤 (H: 0-10 or 170-180)
        red_mask1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        red_mask2 = cv2.inRange(hsv, np.array([170, 100, 100]), np.array([180, 255, 255]))

        hp_mask = green_mask | yellow_mask | red_mask1 | red_mask2

        if np.count_nonzero(hp_mask) == 0:
            return None

        # 行ごとにHPバーピクセルを集計し、最も多い行の比率をHP%とする
        row_sums = np.sum(hp_mask > 0, axis=1)
        if row_sums.max() == 0:
            return None

        best_row = int(np.argmax(row_sums))
        bar_pixels = int(row_sums[best_row])
        total_width = hp_mask.shape[1]

        return bar_pixels / total_width

    def process_frame(self, frame: np.ndarray) -> FrameAnalysis:
        """フレームを総合的に解析する。"""
        self._frame_counter += 1
        processed = self.preprocess(frame)
        has_change, _ = self.detect_change(processed)
        brightness = self.analyze_brightness(processed)
        dominant = self.get_dominant_colors(processed)
        rois = self.extract_all_rois(processed)

        return FrameAnalysis(
            frame_id=self._frame_counter,
            has_significant_change=has_change,
            dominant_colors=dominant,
            brightness=brightness,
            roi_frames=rois,
        )

    def reset(self) -> None:
        """内部状態をリセットする。"""
        self._prev_frame_gray = None
        self._frame_counter = 0

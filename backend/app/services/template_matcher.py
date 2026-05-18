"""テンプレートマッチング

ポケモンアイコンのテンプレート画像をフレームと照合し、
VS画面・選出画面でのポケモン特定を行う。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """テンプレートマッチングの結果。"""

    template_name: str
    confidence: float
    location: tuple[int, int]  # (x, y) マッチ位置の左上
    size: tuple[int, int]  # (width, height) テンプレートサイズ

    @property
    def center(self) -> tuple[int, int]:
        return (
            self.location[0] + self.size[0] // 2,
            self.location[1] + self.size[1] // 2,
        )

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        """(x1, y1, x2, y2) バウンディングボックス。"""
        return (
            self.location[0],
            self.location[1],
            self.location[0] + self.size[0],
            self.location[1] + self.size[1],
        )


@dataclass
class TemplateInfo:
    """テンプレート画像の情報。"""

    name: str
    image: np.ndarray
    width: int
    height: int
    category: str = ""


class TemplateMatcher:
    """テンプレートマッチングによるポケモンアイコン検出。

    テンプレート画像をディレクトリから読み込み、
    マルチスケールでフレーム内を探索する。

    ディレクトリ構造:
        templates/
        ├── pokemon/          # ポケモンアイコン
        │   ├── pikachu.png
        │   └── ...
        ├── ui/               # UIパーツ (HPバー、メニュー等)
        │   ├── hp_bar.png
        │   └── ...
        └── scene/            # シーン識別用テンプレート
            ├── vs_screen.png
            └── ...
    """

    DEFAULT_THRESHOLD = 0.7
    SCALES = [0.8, 0.9, 1.0, 1.1, 1.2]

    def __init__(self, template_dir: str | Path | None = None) -> None:
        self._templates: dict[str, TemplateInfo] = {}
        self._template_dir = Path(template_dir) if template_dir else None
        if self._template_dir and self._template_dir.exists():
            self._load_templates()

    @property
    def template_count(self) -> int:
        return len(self._templates)

    @property
    def template_names(self) -> list[str]:
        return list(self._templates.keys())

    def _load_templates(self) -> None:
        """テンプレートディレクトリから画像を読み込む。"""
        if self._template_dir is None:
            return

        for category_dir in self._template_dir.iterdir():
            if not category_dir.is_dir():
                continue
            category = category_dir.name
            for img_path in category_dir.glob("*.png"):
                self.add_template_from_file(str(img_path), img_path.stem, category)

    def add_template_from_file(self, filepath: str, name: str, category: str = "") -> bool:
        """ファイルからテンプレートを追加する。"""
        img = cv2.imread(filepath, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("Failed to load template: %s", filepath)
            return False
        return self.add_template(name, img, category)

    def add_template(self, name: str, image: np.ndarray, category: str = "") -> bool:
        """numpy配列からテンプレートを追加する。"""
        if image.size == 0:
            return False
        h, w = image.shape[:2]
        self._templates[name] = TemplateInfo(
            name=name, image=image, width=w, height=h, category=category
        )
        logger.debug("Template added: %s (%dx%d, category=%s)", name, w, h, category)
        return True

    def remove_template(self, name: str) -> bool:
        """テンプレートを削除する。"""
        if name in self._templates:
            del self._templates[name]
            return True
        return False

    def match_single(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: float = DEFAULT_THRESHOLD,
        multi_scale: bool = True,
    ) -> list[MatchResult]:
        """単一テンプレートをフレーム内で探索する。"""
        if template_name not in self._templates:
            return []

        template_info = self._templates[template_name]
        return self._match_template(frame, template_info, threshold, multi_scale)

    def match_category(
        self,
        frame: np.ndarray,
        category: str,
        threshold: float = DEFAULT_THRESHOLD,
        multi_scale: bool = True,
    ) -> list[MatchResult]:
        """指定カテゴリの全テンプレートをフレーム内で探索する。"""
        results: list[MatchResult] = []
        for t in self._templates.values():
            if t.category == category:
                results.extend(self._match_template(frame, t, threshold, multi_scale))
        return results

    def match_all(
        self,
        frame: np.ndarray,
        threshold: float = DEFAULT_THRESHOLD,
        multi_scale: bool = False,
    ) -> list[MatchResult]:
        """全テンプレートをフレーム内で探索する。"""
        results: list[MatchResult] = []
        for t in self._templates.values():
            results.extend(self._match_template(frame, t, threshold, multi_scale))
        return results

    def find_best_match(
        self,
        frame: np.ndarray,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> MatchResult | None:
        """全テンプレートの中から最もconfidenceの高いマッチを返す。"""
        all_matches = self.match_all(frame, threshold, multi_scale=True)
        if not all_matches:
            return None
        return max(all_matches, key=lambda m: m.confidence)

    def _match_template(
        self,
        frame: np.ndarray,
        template_info: TemplateInfo,
        threshold: float,
        multi_scale: bool,
    ) -> list[MatchResult]:
        """テンプレートマッチングの内部実装。"""
        results: list[MatchResult] = []
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tmpl_gray = cv2.cvtColor(template_info.image, cv2.COLOR_BGR2GRAY)
        frame_h, frame_w = frame_gray.shape[:2]

        scales = self.SCALES if multi_scale else [1.0]

        for scale in scales:
            sw = int(tmpl_gray.shape[1] * scale)
            sh = int(tmpl_gray.shape[0] * scale)

            if sw > frame_w or sh > frame_h or sw < 10 or sh < 10:
                continue

            scaled = cv2.resize(tmpl_gray, (sw, sh))
            result = cv2.matchTemplate(frame_gray, scaled, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= threshold)

            for pt in zip(*locations[::-1]):
                confidence = float(result[pt[1], pt[0]])
                match = MatchResult(
                    template_name=template_info.name,
                    confidence=confidence,
                    location=(int(pt[0]), int(pt[1])),
                    size=(sw, sh),
                )
                results.append(match)

        return self._non_max_suppression(results)

    def _non_max_suppression(
        self, results: list[MatchResult], overlap_threshold: float = 0.5
    ) -> list[MatchResult]:
        """重複するマッチ結果をNMSで除去する。"""
        if len(results) <= 1:
            return results

        sorted_results = sorted(results, key=lambda r: r.confidence, reverse=True)
        kept: list[MatchResult] = []

        for candidate in sorted_results:
            should_keep = True
            for existing in kept:
                if self._compute_iou(candidate.bbox, existing.bbox) > overlap_threshold:
                    should_keep = False
                    break
            if should_keep:
                kept.append(candidate)

        return kept

    @staticmethod
    def _compute_iou(box1: tuple[int, int, int, int], box2: tuple[int, int, int, int]) -> float:
        """2つのバウンディングボックスのIoUを計算する。"""
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

    def clear(self) -> None:
        """全テンプレートをクリアする。"""
        self._templates.clear()

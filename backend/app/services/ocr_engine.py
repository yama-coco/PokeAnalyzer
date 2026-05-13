"""OCRエンジン

PaddleOCRを使用してゲーム画面のテキストボックスから
技名・特性・アイテム名を抽出する。

PaddleOCRが利用できない場合はフォールバックとしてダミー結果を返す。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """OCRの認識結果。"""

    text: str
    confidence: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    category: str = ""  # "move", "ability", "item", "status", "misc"


@dataclass
class TextAnalysis:
    """テキスト解析の総合結果。"""

    raw_results: list[OCRResult] = field(default_factory=list)
    moves: list[str] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    status_texts: list[str] = field(default_factory=list)
    scene_keywords: list[str] = field(default_factory=list)


# 技名・特性・アイテムのパターン
# 実際にはポケモンデータベースとの照合が必要だが、
# ここでは基本的なパターンマッチングを行う
MOVE_KEYWORDS = [
    "まもる",
    "ねこだまし",
    "このゆびとまれ",
    "いかりのこな",
    "おいかぜ",
    "トリックルーム",
    "じしん",
    "いわなだれ",
    "ハイパーボイス",
    "ムーンフォース",
    "りゅうせいぐん",
    "だいちのちから",
    "ねっぷう",
    "ふぶき",
    "10まんボルト",
    "サイコキネシス",
    "あくのはどう",
    "シャドーボール",
    "インファイト",
    "アイアンヘッド",
    "げきりん",
    "テラバースト",
    "すてみタックル",
    "ハイドロポンプ",
]

ABILITY_KEYWORDS = [
    "いかく",
    "あめふらし",
    "ひでり",
    "すなおこし",
    "ゆきふらし",
    "すいすい",
    "ようりょくそ",
    "すなかき",
    "ゆきかき",
    "かるわざ",
    "スロースタート",
    "はやあし",
    "トレース",
    "ダウンロード",
    "てんねん",
    "もらいび",
    "ちょすい",
    "ひらいしん",
    "よびみず",
    "ふゆう",
    "かたやぶり",
    "てきおうりょく",
]

ITEM_KEYWORDS = [
    "こだわりスカーフ",
    "こだわりハチマキ",
    "こだわりメガネ",
    "きあいのタスキ",
    "いのちのたま",
    "とつげきチョッキ",
    "くろいてっきゅう",
    "しめったいわ",
    "あついいわ",
    "オボンのみ",
    "ラムのみ",
    "ピンチベリー",
    "メガストーン",
    "Zクリスタル",
]

STATUS_KEYWORDS = [
    "まひ",
    "やけど",
    "どく",
    "もうどく",
    "ねむり",
    "こおり",
    "こんらん",
    "メロメロ",
    "ちょうはつ",
    "アンコール",
]

SCENE_KEYWORDS = [
    "VS",
    "たいせん",
    "えらぶ",
    "選出",
    "かち",
    "まけ",
    "勝",
    "負",
    "バトル",
    "ターン",
]


class OCREngine:
    """PaddleOCRベースのテキスト認識エンジン。

    PaddleOCRが利用可能な場合はそれを使用し、
    利用不可の場合はフォールバックモードで動作する。
    """

    def __init__(self, use_gpu: bool = False) -> None:
        self._ocr = None
        self._available = False
        self._use_gpu = use_gpu
        self._init_ocr()

    def _init_ocr(self) -> None:
        """PaddleOCRを初期化する。"""
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang="japan",
                use_gpu=self._use_gpu,
                show_log=False,
            )
            self._available = True
            logger.info("PaddleOCR initialized (lang=japan, gpu=%s)", self._use_gpu)
        except ImportError:
            logger.warning(
                "PaddleOCR not available. Install with: pip install paddleocr paddlepaddle"
            )
            self._available = False
        except Exception as e:
            logger.warning("PaddleOCR initialization failed: %s", e)
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def recognize(self, frame: np.ndarray) -> list[OCRResult]:
        """フレームからテキストを認識する。"""
        if not self._available or self._ocr is None:
            return []

        try:
            results = self._ocr.ocr(frame, cls=True)
            if not results or results[0] is None:
                return []

            ocr_results: list[OCRResult] = []
            for line in results[0]:
                bbox_points, (text, confidence) = line
                x1 = int(min(p[0] for p in bbox_points))
                y1 = int(min(p[1] for p in bbox_points))
                x2 = int(max(p[0] for p in bbox_points))
                y2 = int(max(p[1] for p in bbox_points))
                category = self._classify_text(text)
                ocr_results.append(
                    OCRResult(
                        text=text,
                        confidence=float(confidence),
                        bbox=(x1, y1, x2, y2),
                        category=category,
                    )
                )
            return ocr_results
        except Exception as e:
            logger.error("OCR recognition failed: %s", e)
            return []

    def recognize_region(
        self, frame: np.ndarray, roi: tuple[int, int, int, int]
    ) -> list[OCRResult]:
        """指定領域のテキストのみを認識する。"""
        x, y, w, h = roi
        cropped = frame[y : y + h, x : x + w]
        results = self.recognize(cropped)
        # ROIオフセットを加算
        for r in results:
            r.bbox = (r.bbox[0] + x, r.bbox[1] + y, r.bbox[2] + x, r.bbox[3] + y)
        return results

    def preprocess_for_ocr(self, frame: np.ndarray) -> np.ndarray:
        """OCR精度向上のための前処理。"""
        # グレースケール化
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # コントラスト調整 (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        # 二値化 (大津の方法)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # BGRに戻す (PaddleOCRはBGR入力を期待)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    def analyze_text(self, frame: np.ndarray) -> TextAnalysis:
        """フレーム内のテキストを認識し、カテゴリ別に分類する。"""
        preprocessed = self.preprocess_for_ocr(frame)
        raw_results = self.recognize(preprocessed)
        return self._build_analysis(raw_results)

    def _build_analysis(self, results: list[OCRResult]) -> TextAnalysis:
        """OCR結果をカテゴリ別に整理する。"""
        analysis = TextAnalysis(raw_results=results)
        for r in results:
            if r.category == "move":
                analysis.moves.append(r.text)
            elif r.category == "ability":
                analysis.abilities.append(r.text)
            elif r.category == "item":
                analysis.items.append(r.text)
            elif r.category == "status":
                analysis.status_texts.append(r.text)

            for kw in SCENE_KEYWORDS:
                if kw in r.text:
                    analysis.scene_keywords.append(kw)
        return analysis

    def _classify_text(self, text: str) -> str:
        """テキストをカテゴリに分類する。"""
        cleaned = text.strip()
        for kw in MOVE_KEYWORDS:
            if kw in cleaned:
                return "move"
        for kw in ABILITY_KEYWORDS:
            if kw in cleaned:
                return "ability"
        for kw in ITEM_KEYWORDS:
            if kw in cleaned:
                return "item"
        for kw in STATUS_KEYWORDS:
            if kw in cleaned:
                return "status"
        return "misc"

    @staticmethod
    def extract_damage_text(text: str) -> int | None:
        """テキストからダメージ数値を抽出する。"""
        match = re.search(r"(\d+)ダメージ", text)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def extract_turn_number(text: str) -> int | None:
        """テキストからターン数を抽出する。"""
        match = re.search(r"ターン\s*(\d+)", text)
        if match:
            return int(match.group(1))
        match = re.search(r"(\d+)\s*ターン", text)
        if match:
            return int(match.group(1))
        return None

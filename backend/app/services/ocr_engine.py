"""OCRエンジン

PaddleOCRを使用してゲーム画面のテキストボックスから
技名・特性・アイテム名を抽出する。

Phase 7: ゲーム画面のフォント・レイアウトに最適化した
OCR前処理パイプラインとテキスト抽出パターンを追加。

PaddleOCRが利用できない場合はフォールバックとしてダミー結果を返す。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

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


@dataclass
class HPValue:
    """HP抽出結果。"""

    current: int
    maximum: int

    @property
    def percentage(self) -> float:
        if self.maximum == 0:
            return 0.0
        return self.current / self.maximum * 100.0


@dataclass
class TimerValue:
    """タイマー抽出結果。"""

    minutes: int
    seconds: int

    @property
    def total_seconds(self) -> int:
        return self.minutes * 60 + self.seconds


@dataclass
class BattleLogEntry:
    """バトルログの解析結果。"""

    raw_text: str
    pokemon_name: str = ""
    action: str = ""  # 技名、特性発動、アイテム使用等
    category: str = ""  # "move", "ability", "item", "mega", "terastal", "misc"


class TextRegionType(str, Enum):
    """テキスト領域の種別。前処理パイプラインの選択に使用する。"""

    HP_TEXT = "hp_text"
    POKEMON_NAME = "pokemon_name"
    MOVE_NAME = "move_name"
    BATTLE_LOG = "battle_log"
    TIMER = "timer"
    GENERAL = "general"


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


# --- ROI名からTextRegionTypeへのマッピング ---
ROI_REGION_MAP: dict[str, TextRegionType] = {
    "hp_text_ally_1": TextRegionType.HP_TEXT,
    "hp_text_ally_2": TextRegionType.HP_TEXT,
    "hp_text_enemy_1": TextRegionType.HP_TEXT,
    "hp_text_enemy_2": TextRegionType.HP_TEXT,
    "name_ally_1": TextRegionType.POKEMON_NAME,
    "name_ally_2": TextRegionType.POKEMON_NAME,
    "name_enemy_1": TextRegionType.POKEMON_NAME,
    "name_enemy_2": TextRegionType.POKEMON_NAME,
    "move_1": TextRegionType.MOVE_NAME,
    "move_2": TextRegionType.MOVE_NAME,
    "move_3": TextRegionType.MOVE_NAME,
    "move_4": TextRegionType.MOVE_NAME,
    "text_box": TextRegionType.BATTLE_LOG,
    "selection_timer": TextRegionType.TIMER,
    "battle_timer": TextRegionType.TIMER,
}


class OCRPreprocessor:
    """ゲーム画面特化のOCR前処理。

    テキスト種別に応じた最適な前処理パイプラインを提供する。
    """

    @staticmethod
    def preprocess_hp_text(roi: np.ndarray) -> np.ndarray:
        """HP数値テキストの前処理。

        - グレースケール変換
        - 二値化 (OTSU) → 白文字を黒背景から分離
        - 膨張処理 → 細い数字の接続性改善
        """
        if roi.size == 0:
            return roi
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)
        return cv2.cvtColor(dilated, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def preprocess_pokemon_name(roi: np.ndarray) -> np.ndarray:
        """ポケモン名テキストの前処理。

        - コントラスト強調 (CLAHE)
        - 色相フィルタ → UI背景色を除去
        """
        if roi.size == 0:
            return roi
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l_ch)
        enhanced = cv2.merge([cl, a_ch, b_ch])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    @staticmethod
    def preprocess_battle_log(roi: np.ndarray) -> np.ndarray:
        """バトルログテキストの前処理。

        - 半透明テキストボックスの背景除去
        - アルファブレンド推定 → テキスト領域のみ抽出
        """
        if roi.size == 0:
            return roi
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 0, 180), (180, 50, 255))
        result = cv2.bitwise_and(roi, roi, mask=mask)
        return result

    @staticmethod
    def preprocess_timer(roi: np.ndarray) -> np.ndarray:
        """タイマーテキストの前処理。

        - 高コントラスト二値化で数字を強調
        - 膨張処理でコロン(:)の視認性改善
        """
        if roi.size == 0:
            return roi
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = np.ones((2, 1), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)
        return cv2.cvtColor(dilated, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def preprocess_move_name(roi: np.ndarray) -> np.ndarray:
        """技名テキストの前処理。

        - CLAHE によるコントラスト強調
        - 技選択メニューの背景グラデーション除去
        """
        if roi.size == 0:
            return roi
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
        cl = clahe.apply(l_ch)
        enhanced = cv2.merge([cl, a_ch, b_ch])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    @classmethod
    def preprocess(cls, roi: np.ndarray, region_type: TextRegionType) -> np.ndarray:
        """テキスト領域の種別に応じた前処理を適用する。"""
        if region_type == TextRegionType.HP_TEXT:
            return cls.preprocess_hp_text(roi)
        elif region_type == TextRegionType.POKEMON_NAME:
            return cls.preprocess_pokemon_name(roi)
        elif region_type == TextRegionType.BATTLE_LOG:
            return cls.preprocess_battle_log(roi)
        elif region_type == TextRegionType.TIMER:
            return cls.preprocess_timer(roi)
        elif region_type == TextRegionType.MOVE_NAME:
            return cls.preprocess_move_name(roi)
        else:
            return cls.preprocess_general(roi)

    @staticmethod
    def preprocess_general(roi: np.ndarray) -> np.ndarray:
        """汎用の前処理 (既存のpreprocess_for_ocrと同等)。"""
        if roi.size == 0:
            return roi
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


class TextExtractor:
    """ゲーム画面のテキストから構造化データを抽出するユーティリティ。"""

    # HP実数値パターン: 149/185
    HP_ABSOLUTE_PATTERN = re.compile(r"(\d{1,3})\s*/\s*(\d{1,3})")
    # HPパーセンテージパターン: 73%
    HP_PERCENTAGE_PATTERN = re.compile(r"(\d{1,3})\s*%")
    # タイマーパターン: 1:30
    TIMER_PATTERN = re.compile(r"(\d{1,2})\s*:\s*(\d{2})")
    # バトルログパターン: 「ガブリアスの じしん!」
    BATTLE_LOG_PATTERN = re.compile(r"(.+?)の\s+(.+?)[!！]?$")
    # メガシンカパターン: 「ガブリアスのメガシンカ!」
    MEGA_EVOLUTION_PATTERN = re.compile(r"(.+?)の\s*メガシンカ[!！]?")
    # テラスタルパターン: 「ガブリアスはじめんテラスタルした!」
    TERASTAL_PATTERN = re.compile(r"(.+?)は(.+?)テラスタル")

    @classmethod
    def extract_hp_absolute(cls, text: str) -> HPValue | None:
        """テキストからHP実数値を抽出する。

        例: "149/185" → HPValue(current=149, maximum=185)
        """
        match = cls.HP_ABSOLUTE_PATTERN.search(text)
        if match:
            current = int(match.group(1))
            maximum = int(match.group(2))
            if 0 <= current <= maximum <= 999:
                return HPValue(current=current, maximum=maximum)
        return None

    @classmethod
    def extract_hp_percentage(cls, text: str) -> int | None:
        """テキストからHPパーセンテージを抽出する。

        例: "73%" → 73
        """
        match = cls.HP_PERCENTAGE_PATTERN.search(text)
        if match:
            value = int(match.group(1))
            if 0 <= value <= 100:
                return value
        return None

    @classmethod
    def extract_timer(cls, text: str) -> TimerValue | None:
        """テキストからタイマー値を抽出する。

        例: "1:30" → TimerValue(minutes=1, seconds=30)
        """
        match = cls.TIMER_PATTERN.search(text)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            if 0 <= minutes <= 99 and 0 <= seconds <= 59:
                return TimerValue(minutes=minutes, seconds=seconds)
        return None

    @classmethod
    def parse_battle_log(cls, text: str) -> BattleLogEntry:
        """バトルログテキストを解析する。

        例:
          "ガブリアスの じしん!" →
            BattleLogEntry(pokemon_name="ガブリアス", action="じしん", category="move")
          "いかくで こうげきが さがった!" →
            BattleLogEntry(action="いかく", category="ability")
        """
        entry = BattleLogEntry(raw_text=text)

        # メガシンカ判定
        mega_match = cls.MEGA_EVOLUTION_PATTERN.search(text)
        if mega_match:
            entry.pokemon_name = mega_match.group(1).strip()
            entry.action = "メガシンカ"
            entry.category = "mega"
            return entry

        # テラスタル判定
        tera_match = cls.TERASTAL_PATTERN.search(text)
        if tera_match:
            entry.pokemon_name = tera_match.group(1).strip()
            entry.action = tera_match.group(2).strip() + "テラスタル"
            entry.category = "terastal"
            return entry

        # 一般的なバトルログ (「Xの Y!」形式)
        log_match = cls.BATTLE_LOG_PATTERN.search(text)
        if log_match:
            entry.pokemon_name = log_match.group(1).strip()
            action_text = log_match.group(2).strip()
            entry.action = action_text
            entry.category = _classify_action(action_text)
            return entry

        # 特性・アイテム発動系 (ポケモン名が含まれない場合)
        entry.category = _classify_action(text)
        if entry.category != "misc":
            entry.action = text.strip()

        return entry


def _classify_action(text: str) -> str:
    """アクションテキストをカテゴリに分類する。"""
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


class OCREngine:
    """PaddleOCRベースのテキスト認識エンジン。

    PaddleOCRが利用可能な場合はそれを使用し、
    利用不可の場合はフォールバックモードで動作する。

    Phase 7: ゲーム画面に最適化されたPaddleOCR設定と
    ROI種別に応じた前処理パイプラインを統合。
    """

    # ゲーム画面に最適化されたPaddleOCR設定
    GAME_OCR_CONFIG = {
        "use_angle_cls": False,  # ゲーム画面は回転しない
        "lang": "japan",
        "show_log": False,
        "det_db_thresh": 0.3,  # テキスト検出閾値 (低めで取りこぼし防止)
        "det_db_box_thresh": 0.5,
        "cls_thresh": 0.9,
        "drop_score": 0.5,  # 低スコアの結果を除外
    }

    def __init__(self, use_gpu: bool = False) -> None:
        self._ocr = None
        self._available = False
        self._use_gpu = use_gpu
        self._preprocessor = OCRPreprocessor()
        self._extractor = TextExtractor()
        self._init_ocr()

    def _init_ocr(self) -> None:
        """PaddleOCRを初期化する。"""
        try:
            from paddleocr import PaddleOCR

            config = {**self.GAME_OCR_CONFIG, "use_gpu": self._use_gpu}
            self._ocr = PaddleOCR(**config)
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

    @property
    def preprocessor(self) -> OCRPreprocessor:
        return self._preprocessor

    @property
    def extractor(self) -> TextExtractor:
        return self._extractor

    def preprocess_for_ocr(
        self, frame: np.ndarray, region_type: TextRegionType = TextRegionType.GENERAL
    ) -> np.ndarray:
        """OCR精度向上のための前処理。

        region_type に応じた特化型前処理を適用する。
        """
        return self._preprocessor.preprocess(frame, region_type)

    def recognize_roi(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
        roi_name: str = "",
    ) -> list[OCRResult]:
        """ROI名に応じた前処理を適用して認識する。"""
        x, y, w, h = roi
        cropped = frame[y : y + h, x : x + w]
        region_type = ROI_REGION_MAP.get(roi_name, TextRegionType.GENERAL)
        preprocessed = self.preprocess_for_ocr(cropped, region_type)
        results = self.recognize(preprocessed)
        for r in results:
            r.bbox = (r.bbox[0] + x, r.bbox[1] + y, r.bbox[2] + x, r.bbox[3] + y)
        return results

    def extract_hp_from_roi(
        self, frame: np.ndarray, roi: tuple[int, int, int, int], is_ally: bool = True
    ) -> HPValue | int | None:
        """HP ROIからHP値を抽出する。

        味方の場合は実数値 (HPValue)、相手の場合はパーセンテージ (int) を返す。
        """
        results = self.recognize_roi(frame, roi, "hp_text_ally_1" if is_ally else "hp_text_enemy_1")
        for r in results:
            if is_ally:
                hp = self._extractor.extract_hp_absolute(r.text)
                if hp is not None:
                    return hp
            else:
                pct = self._extractor.extract_hp_percentage(r.text)
                if pct is not None:
                    return pct
        return None

    def extract_timer_from_roi(
        self, frame: np.ndarray, roi: tuple[int, int, int, int]
    ) -> TimerValue | None:
        """タイマーROIからタイマー値を抽出する。"""
        results = self.recognize_roi(frame, roi, "battle_timer")
        for r in results:
            timer = self._extractor.extract_timer(r.text)
            if timer is not None:
                return timer
        return None

    def extract_pokemon_name_from_roi(
        self, frame: np.ndarray, roi: tuple[int, int, int, int]
    ) -> str | None:
        """ポケモン名ROIからポケモン名を抽出する。"""
        results = self.recognize_roi(frame, roi, "name_ally_1")
        if results:
            best = max(results, key=lambda r: r.confidence)
            name = best.text.strip()
            if name:
                return name
        return None

    def analyze_battle_log(
        self, frame: np.ndarray, roi: tuple[int, int, int, int]
    ) -> list[BattleLogEntry]:
        """テキストボックスROIからバトルログを解析する。"""
        results = self.recognize_roi(frame, roi, "text_box")
        entries: list[BattleLogEntry] = []
        for r in results:
            entry = self._extractor.parse_battle_log(r.text)
            entries.append(entry)
        return entries

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
        return _classify_action(text)

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

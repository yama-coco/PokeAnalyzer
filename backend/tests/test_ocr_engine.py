"""OCRエンジンのテスト。

PaddleOCRがインストールされていない環境でも動作するテスト。
"""

import numpy as np

from app.services.ocr_engine import OCREngine, OCRResult, TextAnalysis


class TestOCREngine:
    def test_initialization(self):
        """OCRエンジンが初期化できること（PaddleOCR無しでも）。"""
        engine = OCREngine()
        # PaddleOCR未インストールの場合はFalse
        assert isinstance(engine.is_available, bool)

    def test_recognize_without_paddleocr(self):
        """PaddleOCR未インストール時は空リストを返す。"""
        engine = OCREngine()
        if not engine.is_available:
            frame = np.zeros((100, 300, 3), dtype=np.uint8)
            results = engine.recognize(frame)
            assert results == []

    def test_analyze_text_without_paddleocr(self):
        engine = OCREngine()
        if not engine.is_available:
            frame = np.zeros((100, 300, 3), dtype=np.uint8)
            analysis = engine.analyze_text(frame)
            assert isinstance(analysis, TextAnalysis)
            assert analysis.moves == []

    def test_preprocess_for_ocr(self):
        engine = OCREngine()
        frame = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
        result = engine.preprocess_for_ocr(frame)
        assert result.shape == (100, 200, 3)

    def test_classify_text_move(self):
        engine = OCREngine()
        assert engine._classify_text("まもる") == "move"
        assert engine._classify_text("トリックルーム") == "move"
        assert engine._classify_text("おいかぜ") == "move"

    def test_classify_text_ability(self):
        engine = OCREngine()
        assert engine._classify_text("いかく") == "ability"
        assert engine._classify_text("すいすい") == "ability"
        assert engine._classify_text("あめふらし") == "ability"

    def test_classify_text_item(self):
        engine = OCREngine()
        assert engine._classify_text("こだわりスカーフ") == "item"
        assert engine._classify_text("きあいのタスキ") == "item"
        assert engine._classify_text("いのちのたま") == "item"

    def test_classify_text_status(self):
        engine = OCREngine()
        assert engine._classify_text("まひ") == "status"
        assert engine._classify_text("やけど") == "status"
        assert engine._classify_text("こおり") == "status"

    def test_classify_text_misc(self):
        engine = OCREngine()
        assert engine._classify_text("関係ないテキスト") == "misc"
        assert engine._classify_text("") == "misc"

    def test_extract_damage_text(self):
        assert OCREngine.extract_damage_text("50ダメージ") == 50
        assert OCREngine.extract_damage_text("123ダメージ") == 123
        assert OCREngine.extract_damage_text("テキストのみ") is None

    def test_extract_turn_number(self):
        assert OCREngine.extract_turn_number("ターン1") == 1
        assert OCREngine.extract_turn_number("ターン 15") == 15
        assert OCREngine.extract_turn_number("5ターン") == 5
        assert OCREngine.extract_turn_number("テキスト") is None

    def test_build_analysis(self):
        engine = OCREngine()
        results = [
            OCRResult("まもる", 0.95, (0, 0, 100, 30), "move"),
            OCRResult("いかく", 0.90, (0, 30, 100, 60), "ability"),
            OCRResult("こだわりスカーフ", 0.88, (0, 60, 200, 90), "item"),
            OCRResult("まひ", 0.92, (0, 90, 100, 120), "status"),
            OCRResult("ランダムテキスト", 0.70, (0, 120, 200, 150), "misc"),
        ]
        analysis = engine._build_analysis(results)
        assert "まもる" in analysis.moves
        assert "いかく" in analysis.abilities
        assert "こだわりスカーフ" in analysis.items
        assert "まひ" in analysis.status_texts
        assert len(analysis.raw_results) == 5

    def test_recognize_region(self):
        engine = OCREngine()
        if not engine.is_available:
            frame = np.zeros((200, 400, 3), dtype=np.uint8)
            results = engine.recognize_region(frame, (10, 10, 100, 50))
            assert results == []

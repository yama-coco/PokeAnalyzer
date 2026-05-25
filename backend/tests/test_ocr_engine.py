"""OCRエンジンのテスト。

PaddleOCRがインストールされていない環境でも動作するテスト。
Phase 7: OCRPreprocessor, TextExtractor, ROI-aware OCRのテストを追加。
"""

import numpy as np

from app.services.ocr_engine import (
    ROI_REGION_MAP,
    BattleLogEntry,
    HPValue,
    OCREngine,
    OCRPreprocessor,
    OCRResult,
    TextAnalysis,
    TextExtractor,
    TextRegionType,
    TimerValue,
)


class TestOCREngine:
    def test_initialization(self):
        """OCRエンジンが初期化できること（PaddleOCR無しでも）。"""
        engine = OCREngine()
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

    def test_preprocess_for_ocr_with_region_type(self):
        """region_typeを指定して前処理が実行されること。"""
        engine = OCREngine()
        frame = np.random.randint(0, 255, (100, 200, 3), dtype=np.uint8)
        for rt in TextRegionType:
            result = engine.preprocess_for_ocr(frame, rt)
            assert result.shape[2] == 3

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

    def test_recognize_roi_without_paddleocr(self):
        """PaddleOCR未インストール時にrecognize_roiが空リストを返すこと。"""
        engine = OCREngine()
        if not engine.is_available:
            frame = np.zeros((200, 400, 3), dtype=np.uint8)
            results = engine.recognize_roi(frame, (10, 10, 100, 50), "hp_text_ally_1")
            assert results == []

    def test_preprocessor_property(self):
        engine = OCREngine()
        assert isinstance(engine.preprocessor, OCRPreprocessor)

    def test_extractor_property(self):
        engine = OCREngine()
        assert isinstance(engine.extractor, TextExtractor)

    def test_game_ocr_config(self):
        config = OCREngine.GAME_OCR_CONFIG
        assert config["use_angle_cls"] is False
        assert config["lang"] == "japan"
        assert config["det_db_thresh"] == 0.3
        assert config["det_db_box_thresh"] == 0.5
        assert config["cls_thresh"] == 0.9
        assert config["drop_score"] == 0.5

    def test_extract_hp_from_roi_without_paddleocr(self):
        engine = OCREngine()
        if not engine.is_available:
            frame = np.zeros((200, 400, 3), dtype=np.uint8)
            assert engine.extract_hp_from_roi(frame, (10, 10, 100, 50), is_ally=True) is None
            assert engine.extract_hp_from_roi(frame, (10, 10, 100, 50), is_ally=False) is None

    def test_extract_timer_from_roi_without_paddleocr(self):
        engine = OCREngine()
        if not engine.is_available:
            frame = np.zeros((200, 400, 3), dtype=np.uint8)
            assert engine.extract_timer_from_roi(frame, (10, 10, 100, 50)) is None

    def test_extract_pokemon_name_from_roi_without_paddleocr(self):
        engine = OCREngine()
        if not engine.is_available:
            frame = np.zeros((200, 400, 3), dtype=np.uint8)
            assert engine.extract_pokemon_name_from_roi(frame, (10, 10, 100, 50)) is None

    def test_analyze_battle_log_without_paddleocr(self):
        engine = OCREngine()
        if not engine.is_available:
            frame = np.zeros((200, 400, 3), dtype=np.uint8)
            assert engine.analyze_battle_log(frame, (10, 10, 100, 50)) == []


class TestOCRPreprocessor:
    def _make_frame(self, h=50, w=200):
        return np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)

    def test_preprocess_hp_text_shape(self):
        roi = self._make_frame()
        result = OCRPreprocessor.preprocess_hp_text(roi)
        assert result.shape == roi.shape
        assert result.dtype == np.uint8

    def test_preprocess_hp_text_binary_output(self):
        roi = self._make_frame()
        result = OCRPreprocessor.preprocess_hp_text(roi)
        unique_per_channel = np.unique(result[:, :, 0])
        assert len(unique_per_channel) <= 2

    def test_preprocess_hp_text_empty(self):
        empty = np.array([], dtype=np.uint8)
        result = OCRPreprocessor.preprocess_hp_text(empty)
        assert result.size == 0

    def test_preprocess_pokemon_name_shape(self):
        roi = self._make_frame()
        result = OCRPreprocessor.preprocess_pokemon_name(roi)
        assert result.shape == roi.shape

    def test_preprocess_pokemon_name_clahe_enhancement(self):
        roi = np.full((50, 200, 3), 128, dtype=np.uint8)
        roi[10:20, 50:150] = 130
        result = OCRPreprocessor.preprocess_pokemon_name(roi)
        assert not np.array_equal(roi, result)

    def test_preprocess_pokemon_name_empty(self):
        empty = np.array([], dtype=np.uint8)
        result = OCRPreprocessor.preprocess_pokemon_name(empty)
        assert result.size == 0

    def test_preprocess_battle_log_shape(self):
        roi = self._make_frame()
        result = OCRPreprocessor.preprocess_battle_log(roi)
        assert result.shape == roi.shape

    def test_preprocess_battle_log_white_extraction(self):
        roi = np.zeros((50, 200, 3), dtype=np.uint8)
        roi[10:20, 50:150] = [255, 255, 255]
        result = OCRPreprocessor.preprocess_battle_log(roi)
        white_region = result[10:20, 50:150]
        assert np.any(white_region > 0)
        dark_region = result[0:5, 0:5]
        assert np.all(dark_region == 0)

    def test_preprocess_battle_log_empty(self):
        empty = np.array([], dtype=np.uint8)
        result = OCRPreprocessor.preprocess_battle_log(empty)
        assert result.size == 0

    def test_preprocess_timer_shape(self):
        roi = self._make_frame()
        result = OCRPreprocessor.preprocess_timer(roi)
        assert result.shape == roi.shape

    def test_preprocess_timer_binary_output(self):
        roi = self._make_frame()
        result = OCRPreprocessor.preprocess_timer(roi)
        unique = np.unique(result[:, :, 0])
        assert len(unique) <= 2

    def test_preprocess_timer_empty(self):
        empty = np.array([], dtype=np.uint8)
        result = OCRPreprocessor.preprocess_timer(empty)
        assert result.size == 0

    def test_preprocess_move_name_shape(self):
        roi = self._make_frame()
        result = OCRPreprocessor.preprocess_move_name(roi)
        assert result.shape == roi.shape

    def test_preprocess_move_name_empty(self):
        empty = np.array([], dtype=np.uint8)
        result = OCRPreprocessor.preprocess_move_name(empty)
        assert result.size == 0

    def test_preprocess_general_shape(self):
        roi = self._make_frame()
        result = OCRPreprocessor.preprocess_general(roi)
        assert result.shape == roi.shape

    def test_preprocess_general_empty(self):
        empty = np.array([], dtype=np.uint8)
        result = OCRPreprocessor.preprocess_general(empty)
        assert result.size == 0

    def test_preprocess_dispatch(self):
        roi = self._make_frame()
        for region_type in TextRegionType:
            result = OCRPreprocessor.preprocess(roi, region_type)
            assert result.shape[2] == 3
            assert result.dtype == np.uint8


class TestTextExtractor:
    def test_extract_hp_absolute_basic(self):
        result = TextExtractor.extract_hp_absolute("149/185")
        assert result is not None
        assert result.current == 149
        assert result.maximum == 185

    def test_extract_hp_absolute_with_spaces(self):
        result = TextExtractor.extract_hp_absolute("149 / 185")
        assert result is not None
        assert result.current == 149
        assert result.maximum == 185

    def test_extract_hp_absolute_in_context(self):
        result = TextExtractor.extract_hp_absolute("HP 100/200 です")
        assert result is not None
        assert result.current == 100
        assert result.maximum == 200

    def test_extract_hp_absolute_max_hp(self):
        result = TextExtractor.extract_hp_absolute("185/185")
        assert result is not None
        assert result.current == 185
        assert result.maximum == 185

    def test_extract_hp_absolute_zero(self):
        result = TextExtractor.extract_hp_absolute("0/185")
        assert result is not None
        assert result.current == 0
        assert result.maximum == 185

    def test_extract_hp_absolute_invalid_range(self):
        result = TextExtractor.extract_hp_absolute("200/100")
        assert result is None

    def test_extract_hp_absolute_no_match(self):
        assert TextExtractor.extract_hp_absolute("テキストのみ") is None
        assert TextExtractor.extract_hp_absolute("") is None

    def test_extract_hp_percentage_basic(self):
        assert TextExtractor.extract_hp_percentage("73%") == 73

    def test_extract_hp_percentage_with_space(self):
        assert TextExtractor.extract_hp_percentage("73 %") == 73

    def test_extract_hp_percentage_100(self):
        assert TextExtractor.extract_hp_percentage("100%") == 100

    def test_extract_hp_percentage_0(self):
        assert TextExtractor.extract_hp_percentage("0%") == 0

    def test_extract_hp_percentage_over_100(self):
        assert TextExtractor.extract_hp_percentage("150%") is None

    def test_extract_hp_percentage_no_match(self):
        assert TextExtractor.extract_hp_percentage("テキストのみ") is None
        assert TextExtractor.extract_hp_percentage("") is None

    def test_extract_timer_basic(self):
        result = TextExtractor.extract_timer("1:30")
        assert result is not None
        assert result.minutes == 1
        assert result.seconds == 30

    def test_extract_timer_with_spaces(self):
        result = TextExtractor.extract_timer("1 : 30")
        assert result is not None
        assert result.minutes == 1
        assert result.seconds == 30

    def test_extract_timer_zero(self):
        result = TextExtractor.extract_timer("0:00")
        assert result is not None
        assert result.minutes == 0
        assert result.seconds == 0

    def test_extract_timer_max(self):
        result = TextExtractor.extract_timer("99:59")
        assert result is not None
        assert result.minutes == 99
        assert result.seconds == 59

    def test_extract_timer_invalid_seconds(self):
        assert TextExtractor.extract_timer("1:60") is None

    def test_extract_timer_no_match(self):
        assert TextExtractor.extract_timer("テキストのみ") is None
        assert TextExtractor.extract_timer("") is None

    def test_parse_battle_log_move(self):
        entry = TextExtractor.parse_battle_log("ガブリアスの じしん!")
        assert entry.pokemon_name == "ガブリアス"
        assert entry.category == "move"

    def test_parse_battle_log_mega_evolution(self):
        entry = TextExtractor.parse_battle_log("ガブリアスのメガシンカ!")
        assert entry.pokemon_name == "ガブリアス"
        assert entry.action == "メガシンカ"
        assert entry.category == "mega"

    def test_parse_battle_log_terastal(self):
        entry = TextExtractor.parse_battle_log("ガブリアスはじめんテラスタルした!")
        assert entry.pokemon_name == "ガブリアス"
        assert "じめん" in entry.action
        assert entry.category == "terastal"

    def test_parse_battle_log_ability(self):
        entry = TextExtractor.parse_battle_log("いかくで こうげきが さがった!")
        assert entry.category == "ability"

    def test_parse_battle_log_misc(self):
        entry = TextExtractor.parse_battle_log("何かが起きた")
        assert entry.raw_text == "何かが起きた"
        assert entry.category == "misc"


class TestHPValue:
    def test_percentage_calculation(self):
        hp = HPValue(current=100, maximum=200)
        assert hp.percentage == 50.0

    def test_percentage_full(self):
        hp = HPValue(current=200, maximum=200)
        assert hp.percentage == 100.0

    def test_percentage_zero_max(self):
        hp = HPValue(current=0, maximum=0)
        assert hp.percentage == 0.0


class TestTimerValue:
    def test_total_seconds(self):
        timer = TimerValue(minutes=1, seconds=30)
        assert timer.total_seconds == 90

    def test_total_seconds_zero(self):
        timer = TimerValue(minutes=0, seconds=0)
        assert timer.total_seconds == 0


class TestBattleLogEntry:
    def test_default_values(self):
        entry = BattleLogEntry(raw_text="テスト")
        assert entry.pokemon_name == ""
        assert entry.action == ""
        assert entry.category == ""


class TestTextRegionType:
    def test_all_types_defined(self):
        expected = {"hp_text", "pokemon_name", "move_name", "battle_log", "timer", "general"}
        actual = {t.value for t in TextRegionType}
        assert actual == expected


class TestROIRegionMap:
    def test_hp_rois(self):
        for roi_name in [
            "hp_text_ally_1",
            "hp_text_ally_2",
            "hp_text_enemy_1",
            "hp_text_enemy_2",
        ]:
            assert ROI_REGION_MAP[roi_name] == TextRegionType.HP_TEXT

    def test_name_rois(self):
        for roi_name in ["name_ally_1", "name_ally_2", "name_enemy_1", "name_enemy_2"]:
            assert ROI_REGION_MAP[roi_name] == TextRegionType.POKEMON_NAME

    def test_move_rois(self):
        for roi_name in ["move_1", "move_2", "move_3", "move_4"]:
            assert ROI_REGION_MAP[roi_name] == TextRegionType.MOVE_NAME

    def test_battle_log_roi(self):
        assert ROI_REGION_MAP["text_box"] == TextRegionType.BATTLE_LOG

    def test_timer_rois(self):
        assert ROI_REGION_MAP["selection_timer"] == TextRegionType.TIMER
        assert ROI_REGION_MAP["battle_timer"] == TextRegionType.TIMER

    def test_unknown_roi_not_in_map(self):
        assert "unknown_roi" not in ROI_REGION_MAP

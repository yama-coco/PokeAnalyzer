"""シーンステートマシン

ゲーム画面の状態遷移を管理する。
IDLE → MATCHING → SELECTION → BATTLE → RESULT → IDLE

各状態はフレーム解析結果に基づいて自動的に遷移する。
"""

from __future__ import annotations

import logging
import time
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SceneState(str, Enum):
    """ゲームのシーン状態。"""

    IDLE = "idle"
    MATCHING = "matching"
    SELECTION = "selection"
    BATTLE = "battle"
    RESULT = "result"


# 許可される状態遷移の定義
VALID_TRANSITIONS: dict[SceneState, set[SceneState]] = {
    SceneState.IDLE: {SceneState.MATCHING},
    SceneState.MATCHING: {SceneState.SELECTION, SceneState.IDLE},
    SceneState.SELECTION: {SceneState.BATTLE, SceneState.IDLE},
    SceneState.BATTLE: {SceneState.RESULT, SceneState.IDLE},
    SceneState.RESULT: {SceneState.IDLE},
}


class SceneTransition(BaseModel):
    """状態遷移の記録。"""

    from_state: SceneState
    to_state: SceneState
    timestamp: float
    confidence: float = Field(ge=0.0, le=1.0)


class SceneContext(BaseModel):
    """現在のシーンに関するコンテキスト情報。"""

    state: SceneState = SceneState.IDLE
    confidence: float = 0.0
    entered_at: float = 0.0
    frame_count: int = 0
    detected_pokemon_count: int = 0
    detected_text_count: int = 0


class SceneIndicator(BaseModel):
    """フレーム解析から得られるシーン判定指標。"""

    has_vs_screen_layout: bool = False
    has_selection_ui: bool = False
    has_battle_field: bool = False
    has_result_text: bool = False
    has_hp_bars: bool = False
    has_command_menu: bool = False
    has_text_box: bool = False
    dominant_color_region: str = ""
    text_content: list[str] = Field(default_factory=list)


class SceneStateMachine:
    """シーンの状態遷移を管理するステートマシン。

    フレーム解析の結果を受け取り、現在のゲーム状態を推定する。
    遷移にはconfidence閾値を設け、ノイズ耐性を確保する。
    """

    TRANSITION_THRESHOLD = 0.6
    MIN_FRAMES_BEFORE_TRANSITION = 3

    def __init__(self) -> None:
        self._context = SceneContext(entered_at=time.time())
        self._history: list[SceneTransition] = []
        self._candidate_state: SceneState | None = None
        self._candidate_count = 0

    @property
    def current_state(self) -> SceneState:
        return self._context.state

    @property
    def context(self) -> SceneContext:
        return self._context

    @property
    def history(self) -> list[SceneTransition]:
        return list(self._history)

    def update(self, indicator: SceneIndicator) -> SceneState:
        """フレーム解析の指標から状態を更新する。

        ノイズ対策として、同じ候補状態が MIN_FRAMES_BEFORE_TRANSITION 回
        連続で検出された場合にのみ遷移する。
        """
        detected, confidence = self._detect_state(indicator)
        self._context.frame_count += 1

        if detected == self._context.state:
            self._context.confidence = max(self._context.confidence, confidence)
            self._candidate_state = None
            self._candidate_count = 0
            return self._context.state

        if detected not in VALID_TRANSITIONS.get(self._context.state, set()):
            return self._context.state

        if confidence < self.TRANSITION_THRESHOLD:
            return self._context.state

        if detected == self._candidate_state:
            self._candidate_count += 1
        else:
            self._candidate_state = detected
            self._candidate_count = 1

        if self._candidate_count >= self.MIN_FRAMES_BEFORE_TRANSITION:
            self._transition_to(detected, confidence)
            self._candidate_state = None
            self._candidate_count = 0

        return self._context.state

    def force_transition(self, state: SceneState) -> None:
        """強制的に状態を遷移させる（デバッグ・手動操作用）。"""
        self._transition_to(state, 1.0)

    def reset(self) -> None:
        """ステートマシンをリセットする。"""
        self._context = SceneContext(entered_at=time.time())
        self._history.clear()
        self._candidate_state = None
        self._candidate_count = 0

    def _transition_to(self, state: SceneState, confidence: float) -> None:
        transition = SceneTransition(
            from_state=self._context.state,
            to_state=state,
            timestamp=time.time(),
            confidence=confidence,
        )
        self._history.append(transition)
        logger.info(
            "Scene transition: %s -> %s (confidence=%.2f)",
            self._context.state.value,
            state.value,
            confidence,
        )
        self._context = SceneContext(
            state=state,
            confidence=confidence,
            entered_at=time.time(),
        )

    def _detect_state(self, indicator: SceneIndicator) -> tuple[SceneState, float]:
        """指標からシーン状態と確信度を推定する。"""
        scores: dict[SceneState, float] = {s: 0.0 for s in SceneState}

        if indicator.has_vs_screen_layout:
            scores[SceneState.MATCHING] += 0.8

        if indicator.has_selection_ui:
            scores[SceneState.SELECTION] += 0.7

        if indicator.has_battle_field:
            scores[SceneState.BATTLE] += 0.5
        if indicator.has_hp_bars:
            scores[SceneState.BATTLE] += 0.3
        if indicator.has_command_menu:
            scores[SceneState.BATTLE] += 0.2

        if indicator.has_result_text:
            scores[SceneState.RESULT] += 0.8

        if indicator.has_text_box:
            scores[SceneState.BATTLE] += 0.1

        for text in indicator.text_content:
            if "VS" in text or "たいせん" in text:
                scores[SceneState.MATCHING] += 0.3
            if "えらぶ" in text or "選出" in text:
                scores[SceneState.SELECTION] += 0.3
            if "かち" in text or "まけ" in text or "勝" in text or "負" in text:
                scores[SceneState.RESULT] += 0.5

        best_state = max(scores, key=lambda s: scores[s])
        best_score = scores[best_state]

        if best_score < 0.3:
            return SceneState.IDLE, 1.0 - best_score

        return best_state, min(best_score, 1.0)

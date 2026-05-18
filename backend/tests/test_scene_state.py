"""シーンステートマシンのテスト。"""

from app.services.scene_state import (
    VALID_TRANSITIONS,
    SceneIndicator,
    SceneState,
    SceneStateMachine,
)


class TestSceneStateMachine:
    """SceneStateMachineの基本テスト。"""

    def test_initial_state_is_idle(self):
        sm = SceneStateMachine()
        assert sm.current_state == SceneState.IDLE

    def test_context_initial_values(self):
        sm = SceneStateMachine()
        ctx = sm.context
        assert ctx.state == SceneState.IDLE
        assert ctx.frame_count == 0
        assert ctx.confidence == 0.0

    def test_valid_transitions_defined(self):
        assert SceneState.IDLE in VALID_TRANSITIONS
        assert SceneState.MATCHING in VALID_TRANSITIONS[SceneState.IDLE]
        assert SceneState.IDLE in VALID_TRANSITIONS[SceneState.RESULT]

    def test_no_transition_on_idle_indicator(self):
        sm = SceneStateMachine()
        indicator = SceneIndicator()  # All False
        state = sm.update(indicator)
        assert state == SceneState.IDLE

    def test_transition_to_matching_on_vs_screen(self):
        sm = SceneStateMachine()
        indicator = SceneIndicator(has_vs_screen_layout=True)
        # Need MIN_FRAMES_BEFORE_TRANSITION consecutive detections
        for _ in range(sm.MIN_FRAMES_BEFORE_TRANSITION):
            state = sm.update(indicator)
        assert state == SceneState.MATCHING

    def test_transition_to_battle_from_selection(self):
        sm = SceneStateMachine()
        sm.force_transition(SceneState.SELECTION)
        indicator = SceneIndicator(has_battle_field=True, has_hp_bars=True)
        for _ in range(sm.MIN_FRAMES_BEFORE_TRANSITION):
            state = sm.update(indicator)
        assert state == SceneState.BATTLE

    def test_transition_to_result_from_battle(self):
        sm = SceneStateMachine()
        sm.force_transition(SceneState.BATTLE)
        indicator = SceneIndicator(has_result_text=True)
        for _ in range(sm.MIN_FRAMES_BEFORE_TRANSITION):
            state = sm.update(indicator)
        assert state == SceneState.RESULT

    def test_invalid_transition_rejected(self):
        """IDLEからBATTLEへの直接遷移は無効。"""
        sm = SceneStateMachine()
        indicator = SceneIndicator(has_battle_field=True, has_hp_bars=True, has_command_menu=True)
        for _ in range(10):
            state = sm.update(indicator)
        assert state == SceneState.IDLE

    def test_force_transition(self):
        sm = SceneStateMachine()
        sm.force_transition(SceneState.BATTLE)
        assert sm.current_state == SceneState.BATTLE

    def test_history_recorded(self):
        sm = SceneStateMachine()
        sm.force_transition(SceneState.MATCHING)
        sm.force_transition(SceneState.SELECTION)
        history = sm.history
        assert len(history) == 2
        assert history[0].from_state == SceneState.IDLE
        assert history[0].to_state == SceneState.MATCHING
        assert history[1].from_state == SceneState.MATCHING
        assert history[1].to_state == SceneState.SELECTION

    def test_reset(self):
        sm = SceneStateMachine()
        sm.force_transition(SceneState.BATTLE)
        sm.reset()
        assert sm.current_state == SceneState.IDLE
        assert len(sm.history) == 0

    def test_frame_count_increments(self):
        sm = SceneStateMachine()
        indicator = SceneIndicator()
        sm.update(indicator)
        sm.update(indicator)
        sm.update(indicator)
        assert sm.context.frame_count == 3

    def test_noise_resistance(self):
        """1回だけのノイズでは遷移しない。"""
        sm = SceneStateMachine()
        # 1回だけVS画面の指標
        vs_indicator = SceneIndicator(has_vs_screen_layout=True)
        sm.update(vs_indicator)
        # すぐに何もない指標
        empty = SceneIndicator()
        sm.update(empty)
        sm.update(empty)
        assert sm.current_state == SceneState.IDLE

    def test_text_based_scene_detection(self):
        """テキスト内容からシーンを推定。"""
        sm = SceneStateMachine()
        indicator = SceneIndicator(
            has_vs_screen_layout=True,
            text_content=["VS たいせん"],
        )
        for _ in range(sm.MIN_FRAMES_BEFORE_TRANSITION):
            sm.update(indicator)
        assert sm.current_state == SceneState.MATCHING

    def test_result_detection_via_text(self):
        sm = SceneStateMachine()
        sm.force_transition(SceneState.BATTLE)
        indicator = SceneIndicator(
            has_result_text=True,
            text_content=["かち"],
        )
        for _ in range(sm.MIN_FRAMES_BEFORE_TRANSITION):
            sm.update(indicator)
        assert sm.current_state == SceneState.RESULT

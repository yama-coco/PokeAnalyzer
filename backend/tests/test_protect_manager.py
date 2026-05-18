"""Protect Manager のテスト"""

from __future__ import annotations

import pytest

from app.services.protect_manager import ProtectManager


@pytest.fixture
def manager():
    return ProtectManager()


class TestProtectRecording:
    def test_first_protect(self, manager: ProtectManager):
        state = manager.record_protect("バンギラス", "まもる", turn=1)
        assert state.consecutive_uses == 1
        assert state.total_uses == 1
        assert state.total_successes == 1

    def test_consecutive_protect(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        state = manager.record_protect("バンギラス", "まもる", turn=2)
        assert state.consecutive_uses == 2
        assert state.total_uses == 2

    def test_non_consecutive_protect(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        state = manager.record_protect("バンギラス", "まもる", turn=3)
        assert state.consecutive_uses == 1  # リセットされる
        assert state.total_uses == 2

    def test_protect_failure(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        state = manager.record_protect("バンギラス", "まもる", turn=2, success=False)
        assert state.consecutive_uses == 0
        assert state.total_uses == 2
        assert state.total_successes == 1


class TestSuccessProbability:
    def test_first_use_100_percent(self, manager: ProtectManager):
        prob = manager.get_protect_probability("バンギラス")
        assert prob == 1.0

    def test_after_one_success(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        prob = manager.get_protect_probability("バンギラス")
        assert prob == pytest.approx(1 / 3)

    def test_after_two_consecutive(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        manager.record_protect("バンギラス", "まもる", turn=2)
        prob = manager.get_protect_probability("バンギラス")
        assert prob == pytest.approx(1 / 9)

    def test_after_three_consecutive(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        manager.record_protect("バンギラス", "まもる", turn=2)
        manager.record_protect("バンギラス", "まもる", turn=3)
        prob = manager.get_protect_probability("バンギラス")
        assert prob == pytest.approx(1 / 27)

    def test_reset_after_non_protect(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        manager.record_non_protect_action("バンギラス", turn=2)
        prob = manager.get_protect_probability("バンギラス")
        assert prob == 1.0  # リセットされる


class TestProtectMoves:
    def test_mamoru_is_protect(self, manager: ProtectManager):
        assert manager.is_protect_move("まもる")

    def test_mikiri_is_protect(self, manager: ProtectManager):
        assert manager.is_protect_move("みきり")

    def test_king_shield_is_protect(self, manager: ProtectManager):
        assert manager.is_protect_move("キングシールド")

    def test_silk_trap_is_protect(self, manager: ProtectManager):
        assert manager.is_protect_move("シルクトラップ")

    def test_random_move_not_protect(self, manager: ProtectManager):
        assert not manager.is_protect_move("じしん")

    def test_wide_guard_is_protect(self, manager: ProtectManager):
        assert manager.is_protect_move("ワイドガード")

    def test_english_names(self, manager: ProtectManager):
        assert manager.is_protect_move("Protect")
        assert manager.is_protect_move("Detect")
        assert manager.is_protect_move("King's Shield")


class TestMultiplePokemon:
    def test_track_multiple_pokemon(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        manager.record_protect("カイリュー", "まもる", turn=1)
        states = manager.get_all_states()
        assert "バンギラス" in states
        assert "カイリュー" in states

    def test_independent_tracking(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        manager.record_protect("バンギラス", "まもる", turn=2)
        manager.record_protect("カイリュー", "まもる", turn=2)
        # バンギラスは2連続、カイリューは1回目
        assert manager.get_protect_probability("バンギラス") == pytest.approx(1 / 9)
        assert manager.get_protect_probability("カイリュー") == pytest.approx(1 / 3)


class TestToDict:
    def test_state_to_dict(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        state = manager.get_state("バンギラス")
        assert state is not None
        assert state["name"] == "バンギラス"
        assert state["consecutive_uses"] == 1
        assert state["next_success_rate"] == pytest.approx(33.3, abs=0.1)
        assert len(state["history"]) == 1

    def test_unknown_pokemon(self, manager: ProtectManager):
        state = manager.get_state("???")
        assert state is None

    def test_reset(self, manager: ProtectManager):
        manager.record_protect("バンギラス", "まもる", turn=1)
        manager.reset()
        assert len(manager.pokemon_states) == 0

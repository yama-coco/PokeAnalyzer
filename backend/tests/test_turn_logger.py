"""Turn Logger のテスト"""

from __future__ import annotations

import pytest

from app.services.turn_logger import ActionType, TurnLogger


@pytest.fixture
def logger():
    tl = TurnLogger()
    tl.start_match()
    return tl


class TestActionLogging:
    def test_log_move(self, logger: TurnLogger):
        action = logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
            target_slot=2,
            target_name="バンギラス",
        )
        assert action.turn == 1
        assert action.action_type == ActionType.MOVE
        assert action.action_name == "じしん"

    def test_log_switch(self, logger: TurnLogger):
        action = logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.SWITCH,
            action_name="リキキリン",
        )
        assert action.action_type == ActionType.SWITCH

    def test_log_terastal(self, logger: TurnLogger):
        action = logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.TERASTAL,
            action_name="じめん",
        )
        assert action.action_type == ActionType.TERASTAL

    def test_log_protect(self, logger: TurnLogger):
        action = logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="バンギラス",
            action_type=ActionType.PROTECT,
            action_name="まもる",
        )
        assert action.action_type == ActionType.PROTECT


class TestTurnCommit:
    def test_commit_turn(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        logger.log_action(
            turn=1,
            pokemon_slot=1,
            pokemon_name="ニンフィア",
            action_type=ActionType.MOVE,
            action_name="ハイパーボイス",
        )
        log = logger.commit_turn(turn=1, speed_order=[{"slot": 0, "order": 1}])
        assert log.turn == 1
        assert len(log.actions) == 2
        assert len(log.speed_order) == 1

    def test_commit_with_snapshots(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        hp = {0: {"hp_percent": 100.0}, 2: {"hp_percent": 73.0}}
        field = {"trick_room": False, "weather": "none"}
        log = logger.commit_turn(turn=1, hp_snapshot=hp, field_snapshot=field)
        assert log.hp_snapshot == hp
        assert log.field_snapshot == field

    def test_multi_turn(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        logger.commit_turn(turn=1)
        logger.log_action(
            turn=2,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="ドラゴンクロー",
        )
        logger.commit_turn(turn=2)
        assert len(logger.turn_logs) == 2

    def test_commit_clears_actions_for_turn(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        logger.log_action(
            turn=2,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="ドラゴンクロー",
        )
        logger.commit_turn(turn=1)
        # Turn 2 のアクションはまだ残っている
        log2 = logger.commit_turn(turn=2)
        assert len(log2.actions) == 1
        assert log2.actions[0].action_name == "ドラゴンクロー"


class TestLogRetrieval:
    def test_get_turn_log(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        logger.commit_turn(turn=1)
        log = logger.get_turn_log(1)
        assert log is not None
        assert log["turn"] == 1

    def test_get_nonexistent_turn(self, logger: TurnLogger):
        log = logger.get_turn_log(99)
        assert log is None

    def test_get_all_logs(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        logger.commit_turn(turn=1)
        all_logs = logger.get_all_logs()
        assert len(all_logs) == 1

    def test_get_actions_by_pokemon(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        logger.log_action(
            turn=1,
            pokemon_slot=1,
            pokemon_name="ニンフィア",
            action_type=ActionType.MOVE,
            action_name="ハイパーボイス",
        )
        logger.commit_turn(turn=1)
        actions = logger.get_actions_by_pokemon("ガブリアス")
        assert len(actions) == 1
        assert actions[0]["action_name"] == "じしん"


class TestToDict:
    def test_action_to_dict(self, logger: TurnLogger):
        action = logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
            target_slot=2,
            target_name="バンギラス",
        )
        d = action.to_dict()
        assert d["pokemon_name"] == "ガブリアス"
        assert d["action_type"] == "move"
        assert d["target_name"] == "バンギラス"

    def test_turn_log_to_dict(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        log = logger.commit_turn(turn=1)
        d = log.to_dict()
        assert d["turn"] == 1
        assert len(d["actions"]) == 1


class TestReset:
    def test_reset(self, logger: TurnLogger):
        logger.log_action(
            turn=1,
            pokemon_slot=0,
            pokemon_name="ガブリアス",
            action_type=ActionType.MOVE,
            action_name="じしん",
        )
        logger.commit_turn(turn=1)
        logger.reset()
        assert len(logger.turn_logs) == 0
        assert logger.current_turn == 0

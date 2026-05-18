"""ターンログ管理モジュール

ターン毎のアクション（技使用、交代、テラスタル等）を記録し、
match_history / action_logs テーブルと連携する。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from app.models import ActionLog, MatchHistory

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    MOVE = "move"
    SWITCH = "switch"
    TERASTAL = "terastal"
    MEGA = "mega"
    PROTECT = "protect"
    FAINT = "faint"
    ITEM = "item"
    ABILITY = "ability"
    STATUS = "status"


@dataclass
class TurnAction:
    """1つのアクション。"""

    turn: int
    pokemon_slot: int
    pokemon_name: str
    action_type: ActionType
    action_name: str
    target_slot: int | None = None
    target_name: str = ""
    detail: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "pokemon_slot": self.pokemon_slot,
            "pokemon_name": self.pokemon_name,
            "action_type": self.action_type.value,
            "action_name": self.action_name,
            "target_slot": self.target_slot,
            "target_name": self.target_name,
            "detail": self.detail,
        }


@dataclass
class TurnLog:
    """1ターンのログ。"""

    turn: int
    actions: list[TurnAction] = field(default_factory=list)
    speed_order: list[dict] = field(default_factory=list)
    hp_snapshot: dict = field(default_factory=dict)
    field_snapshot: dict = field(default_factory=dict)
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "turn": self.turn,
            "actions": [a.to_dict() for a in self.actions],
            "speed_order": self.speed_order,
            "hp_snapshot": self.hp_snapshot,
            "field_snapshot": self.field_snapshot,
        }


class TurnLogger:
    """ターン毎のアクションを記録するクラス。"""

    def __init__(self) -> None:
        self._current_match_id: int | None = None
        self._turn_logs: list[TurnLog] = []
        self._current_turn_actions: list[TurnAction] = []
        self._current_turn = 0

    @property
    def turn_logs(self) -> list[TurnLog]:
        return self._turn_logs

    @property
    def current_turn(self) -> int:
        return self._current_turn

    def start_match(self, match_id: int | None = None) -> None:
        """試合のログ記録を開始する。"""
        self._current_match_id = match_id
        self._turn_logs.clear()
        self._current_turn_actions.clear()
        self._current_turn = 0

    def log_action(
        self,
        turn: int,
        pokemon_slot: int,
        pokemon_name: str,
        action_type: ActionType,
        action_name: str,
        target_slot: int | None = None,
        target_name: str = "",
        detail: str = "",
    ) -> TurnAction:
        """アクションを記録する。"""
        action = TurnAction(
            turn=turn,
            pokemon_slot=pokemon_slot,
            pokemon_name=pokemon_name,
            action_type=action_type,
            action_name=action_name,
            target_slot=target_slot,
            target_name=target_name,
            detail=detail,
            timestamp=time.time(),
        )
        self._current_turn = max(self._current_turn, turn)
        self._current_turn_actions.append(action)
        return action

    def commit_turn(
        self,
        turn: int,
        speed_order: list[dict] | None = None,
        hp_snapshot: dict | None = None,
        field_snapshot: dict | None = None,
    ) -> TurnLog:
        """現在のターンのアクションをまとめて記録する。"""
        # 現在ターンのアクションを抽出
        turn_actions = [a for a in self._current_turn_actions if a.turn == turn]

        log = TurnLog(
            turn=turn,
            actions=turn_actions,
            speed_order=speed_order or [],
            hp_snapshot=hp_snapshot or {},
            field_snapshot=field_snapshot or {},
            timestamp=time.time(),
        )
        self._turn_logs.append(log)

        # コミットしたアクションを除去
        self._current_turn_actions = [a for a in self._current_turn_actions if a.turn != turn]

        return log

    def save_to_db(self, db: Session) -> int | None:
        """ログをDBに保存する。

        Returns:
            保存されたmatch_history ID
        """
        if self._current_match_id is None:
            return None

        for log in self._turn_logs:
            for action in log.actions:
                db_action = ActionLog(
                    match_id=self._current_match_id,
                    turn=action.turn,
                    pokemon_slot=action.pokemon_slot,
                    action_name=f"{action.action_type.value}:{action.action_name}",
                    target_slot=action.target_slot,
                )
                db.add(db_action)

        db.commit()
        logger.info(
            "Saved %d turn logs for match %d",
            len(self._turn_logs),
            self._current_match_id,
        )
        return self._current_match_id

    def create_match_record(
        self,
        db: Session,
        party_id: int,
        opponent_name: str = "",
        enemy_party: list[str] | None = None,
        result: str = "",
    ) -> int:
        """match_historyレコードを作成する。"""
        match = MatchHistory(
            my_party_id=party_id,
            opponent_name=opponent_name,
            enemy_party_json=json.dumps(enemy_party or [], ensure_ascii=False),
            result=result,
        )
        db.add(match)
        db.commit()
        db.refresh(match)
        self._current_match_id = match.id
        return match.id

    def get_turn_log(self, turn: int) -> dict | None:
        """特定ターンのログを取得する。"""
        for log in self._turn_logs:
            if log.turn == turn:
                return log.to_dict()
        return None

    def get_all_logs(self) -> list[dict]:
        """全ターンのログを取得する。"""
        return [log.to_dict() for log in self._turn_logs]

    def get_actions_by_pokemon(self, pokemon_name: str) -> list[dict]:
        """特定ポケモンの全アクションを取得する。"""
        actions = []
        for log in self._turn_logs:
            for action in log.actions:
                if action.pokemon_name == pokemon_name:
                    actions.append(action.to_dict())
        return actions

    def reset(self) -> None:
        """状態をリセットする。"""
        self._current_match_id = None
        self._turn_logs.clear()
        self._current_turn_actions.clear()
        self._current_turn = 0


# グローバルインスタンス
turn_logger = TurnLogger()

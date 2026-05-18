"""まもる管理モジュール

相手の「まもる」「みきり」「キングシールド」等の使用状況を追跡し、
連続成功確率を計算する。

連続まもる成功確率:
  1回目: 1/1 (100%)
  2回目: 1/3 (33.3%)
  3回目: 1/9 (11.1%)
  n回目: 1/(3^(n-1))

ダブルバトルではまもるの管理が勝敗を左右する重要な要素。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

PROTECT_MOVES: set[str] = {
    "まもる",
    "みきり",
    "キングシールド",
    "トーチカ",
    "ニードルガード",
    "ブロッキング",
    "シルクトラップ",
    "ワイドガード",
    "ファストガード",
    "Protect",
    "Detect",
    "King's Shield",
    "Baneful Bunker",
    "Spiky Shield",
    "Obstruct",
    "Silk Trap",
    "Wide Guard",
    "Quick Guard",
}

# まもる判定対象外（ワイドガード・ファストガードは連続使用制限が異なるが簡略化）
STRICT_PROTECT_MOVES: set[str] = {
    "まもる",
    "みきり",
    "キングシールド",
    "トーチカ",
    "ニードルガード",
    "ブロッキング",
    "シルクトラップ",
    "Protect",
    "Detect",
    "King's Shield",
    "Baneful Bunker",
    "Spiky Shield",
    "Obstruct",
    "Silk Trap",
}


@dataclass
class ProtectRecord:
    """まもる使用の記録。"""

    turn: int
    move_name: str
    success: bool
    timestamp: float = 0.0


@dataclass
class PokemonProtectState:
    """1体のポケモンのまもる状態。"""

    name: str
    consecutive_uses: int = 0
    total_uses: int = 0
    total_successes: int = 0
    last_used_turn: int = -1
    history: list[ProtectRecord] = field(default_factory=list)

    @property
    def next_success_rate(self) -> float:
        """次にまもるが成功する確率。"""
        if self.consecutive_uses == 0:
            return 1.0
        return 1.0 / (3**self.consecutive_uses)

    @property
    def next_success_percent(self) -> float:
        return round(self.next_success_rate * 100, 1)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "consecutive_uses": self.consecutive_uses,
            "total_uses": self.total_uses,
            "total_successes": self.total_successes,
            "next_success_rate": self.next_success_percent,
            "last_used_turn": self.last_used_turn,
            "history": [
                {
                    "turn": r.turn,
                    "move": r.move_name,
                    "success": r.success,
                }
                for r in self.history
            ],
        }


class ProtectManager:
    """まもるの使用状況を管理するクラス。"""

    def __init__(self) -> None:
        self._pokemon_states: dict[str, PokemonProtectState] = {}

    @property
    def pokemon_states(self) -> dict[str, PokemonProtectState]:
        return self._pokemon_states

    def record_protect(
        self,
        pokemon_name: str,
        move_name: str,
        turn: int,
        success: bool = True,
    ) -> PokemonProtectState:
        """まもる系の技の使用を記録する。

        Args:
            pokemon_name: ポケモン名
            move_name: 使用技名
            turn: ターン番号
            success: 成功したか

        Returns:
            更新されたまもる状態
        """
        state = self._get_or_create(pokemon_name)

        record = ProtectRecord(
            turn=turn,
            move_name=move_name,
            success=success,
            timestamp=time.time(),
        )
        state.history.append(record)
        state.total_uses += 1

        if success:
            state.total_successes += 1
            # 前のターンと連続かチェック
            if state.last_used_turn == turn - 1:
                state.consecutive_uses += 1
            else:
                state.consecutive_uses = 1
            state.last_used_turn = turn
        else:
            state.consecutive_uses = 0

        return state

    def record_non_protect_action(self, pokemon_name: str, turn: int) -> None:
        """まもる以外の行動を記録し、連続カウントをリセットする。"""
        if pokemon_name in self._pokemon_states:
            state = self._pokemon_states[pokemon_name]
            if state.last_used_turn != turn:
                state.consecutive_uses = 0

    def get_protect_probability(self, pokemon_name: str) -> float:
        """次のまもる成功確率を取得する。"""
        state = self._pokemon_states.get(pokemon_name)
        if state is None:
            return 1.0
        return state.next_success_rate

    def get_all_states(self) -> dict[str, dict]:
        """全ポケモンのまもる状態を取得する。"""
        return {name: state.to_dict() for name, state in self._pokemon_states.items()}

    def get_state(self, pokemon_name: str) -> dict | None:
        """特定ポケモンのまもる状態を取得する。"""
        state = self._pokemon_states.get(pokemon_name)
        return state.to_dict() if state else None

    def is_protect_move(self, move_name: str) -> bool:
        """まもる系の技かどうかを判定する。"""
        return move_name in PROTECT_MOVES

    def is_strict_protect_move(self, move_name: str) -> bool:
        """連続使用制限のあるまもる系技かどうかを判定する。"""
        return move_name in STRICT_PROTECT_MOVES

    def reset(self) -> None:
        """状態をリセットする。"""
        self._pokemon_states.clear()

    def _get_or_create(self, pokemon_name: str) -> PokemonProtectState:
        if pokemon_name not in self._pokemon_states:
            self._pokemon_states[pokemon_name] = PokemonProtectState(name=pokemon_name)
        return self._pokemon_states[pokemon_name]


# グローバルインスタンス
protect_manager = ProtectManager()

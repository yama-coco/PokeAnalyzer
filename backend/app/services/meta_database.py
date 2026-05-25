"""メタゲームデータベース (Phase 8)

外部サイトから取得した型情報を管理し、
VS画面で相手のポケモンを識別した際に想定される型を提示する。
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# 天候始動特性のマッピング
WEATHER_SETTERS: dict[str, tuple[str, str]] = {
    "あめふらし": ("雨", "rain"),
    "ひでり": ("晴れ", "sun"),
    "すなおこし": ("砂", "sand"),
    "ゆきふらし": ("雪", "snow"),
}

# 天候エースの特性マッピング
WEATHER_SWEEPERS: dict[str, str] = {
    "すいすい": "雨",
    "ようりょくそ": "晴れ",
    "すなかき": "砂",
    "ゆきかき": "雪",
}

# トリックルーム始動を示す技
TRICK_ROOM_MOVES = {"トリックルーム"}

# トリル向きポケモンの特性・アイテム
TRICK_ROOM_INDICATORS: set[str] = {
    "くろいてっきゅう",
    "こうこうのしっぽ",
    "あとだし",
}

# 構築タイプの推定に使うキーワード
ARCHETYPE_KEYWORDS: dict[str, list[str]] = {
    "雨パ": [],
    "晴れパ": [],
    "砂パ": [],
    "雪パ": [],
    "トリルパ": [],
    "スタン": [],
}


@dataclass
class PokemonTemplate:
    """ポケモンの型テンプレート。"""

    species: str
    archetype_name: str
    ability: str
    item: str
    nature: str = ""
    evs: dict[str, int] = field(default_factory=dict)
    moves: list[str] = field(default_factory=list)
    usage_rate: float = 0.0
    tera_type: str | None = None
    can_mega_evolve: bool = False
    notes: str = ""
    source_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PokemonTemplate:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class MetaDatabase:
    """メタゲームデータベース。

    外部サイトから取得した型情報を JSON で永続化し、
    ポケモン名をキーにテンプレートの検索・分析を提供する。
    """

    def __init__(self, data_path: str = "data/meta_templates.json"):
        self.data_path = Path(data_path)
        self.templates: dict[str, list[PokemonTemplate]] = {}
        self.last_updated: str = ""
        self._load()

    def _load(self) -> None:
        """JSON ファイルからデータを読み込む。"""
        if not self.data_path.exists():
            logger.info("メタデータファイルが見つかりません: %s", self.data_path)
            return

        try:
            raw = json.loads(self.data_path.read_text(encoding="utf-8"))
            self.last_updated = raw.get("last_updated", "")
            for species, template_list in raw.get("pokemon", {}).items():
                self.templates[species] = [PokemonTemplate.from_dict(t) for t in template_list]
            logger.info(
                "メタデータ読み込み完了: %d 種族, %d テンプレート",
                len(self.templates),
                sum(len(v) for v in self.templates.values()),
            )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("メタデータ読み込みエラー: %s", exc)

    def save(self) -> None:
        """現在のデータを JSON に書き出す。"""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_updated = datetime.now(timezone.utc).isoformat()
        payload = {
            "last_updated": self.last_updated,
            "pokemon": {
                species: [t.to_dict() for t in templates]
                for species, templates in self.templates.items()
            },
        }
        self.data_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("メタデータ保存完了: %s", self.data_path)

    def get_templates(self, species: str) -> list[PokemonTemplate]:
        """指定種族の型テンプレート一覧を使用率順で返す。"""
        return sorted(
            self.templates.get(species, []),
            key=lambda t: t.usage_rate,
            reverse=True,
        )

    def update_templates(self, species: str, templates: list[PokemonTemplate]) -> None:
        """指定種族のテンプレートを上書き更新する。"""
        self.templates[species] = templates
        self.save()

    def add_template(self, template: PokemonTemplate) -> None:
        """テンプレートを追加する。同一種族+型名が既存なら上書き。"""
        species = template.species
        if species not in self.templates:
            self.templates[species] = []

        for i, existing in enumerate(self.templates[species]):
            if existing.archetype_name == template.archetype_name:
                self.templates[species][i] = template
                return
        self.templates[species].append(template)

    def get_usage_ranking(self, limit: int = 50) -> list[dict]:
        """使用率ランキングを返す。"""
        ranking: list[dict] = []
        for species, templates in self.templates.items():
            if not templates:
                continue
            max_rate = max(t.usage_rate for t in templates)
            top_template = max(templates, key=lambda t: t.usage_rate)
            ranking.append(
                {
                    "species": species,
                    "usage_rate": max_rate,
                    "top_archetype": top_template.archetype_name,
                    "template_count": len(templates),
                }
            )
        ranking.sort(key=lambda x: x["usage_rate"], reverse=True)
        return ranking[:limit]

    def suggest_team_composition(self, enemy_species: list[str]) -> dict:
        """相手 6 体から構築タイプを推定し、脅威分析を行う。"""
        all_abilities: list[str] = []
        all_items: list[str] = []
        all_moves: list[str] = []
        pokemon_details: dict[str, list[dict]] = {}

        for species in enemy_species:
            templates = self.get_templates(species)
            pokemon_details[species] = [t.to_dict() for t in templates]
            for t in templates:
                all_abilities.append(t.ability)
                all_items.append(t.item)
                all_moves.extend(t.moves)

        archetype, key_pokemon, threats = self._analyze_archetype(
            enemy_species, all_abilities, all_items, all_moves, pokemon_details
        )

        return {
            "archetype": archetype,
            "key_pokemon": key_pokemon,
            "threats": threats,
            "pokemon_details": pokemon_details,
        }

    def _analyze_archetype(
        self,
        species_list: list[str],
        abilities: list[str],
        items: list[str],
        moves: list[str],
        pokemon_details: dict[str, list[dict]],
    ) -> tuple[str, list[dict], list[str]]:
        """構築タイプの推定と脅威分析。"""
        key_pokemon: list[dict] = []
        threats: list[str] = []
        detected_weathers: list[str] = []

        has_trick_room = any(m in TRICK_ROOM_MOVES for m in moves)
        weather_setter_species: list[tuple[str, str]] = []
        weather_sweeper_species: list[tuple[str, str]] = []

        for species in species_list:
            templates = [PokemonTemplate.from_dict(d) for d in pokemon_details.get(species, [])]
            for t in templates:
                # 天候始動
                if t.ability in WEATHER_SETTERS:
                    weather_jp, _ = WEATHER_SETTERS[t.ability]
                    weather_setter_species.append((species, weather_jp))
                    if weather_jp not in detected_weathers:
                        detected_weathers.append(weather_jp)
                # 天候エース
                if t.ability in WEATHER_SWEEPERS:
                    weather_jp = WEATHER_SWEEPERS[t.ability]
                    weather_sweeper_species.append((species, weather_jp))
                # トリル始動
                if has_trick_room and "トリックルーム" in t.moves:
                    key_pokemon.append({"species": species, "role": "トリル始動", "priority": "高"})
                # メガシンカ
                if t.can_mega_evolve:
                    key_pokemon.append(
                        {"species": species, "role": "メガシンカエース", "priority": "高"}
                    )
                # スカーフ
                if t.item == "こだわりスカーフ":
                    threats.append(f"{species} がこだわりスカーフの可能性あり → 素早さ1.5倍に注意")
                # トリル向きアイテム
                if t.item in TRICK_ROOM_INDICATORS:
                    key_pokemon.append(
                        {"species": species, "role": "トリルアタッカー", "priority": "中"}
                    )

        # 天候パの判定
        for setter_species, weather in weather_setter_species:
            key_pokemon.append(
                {
                    "species": setter_species,
                    "role": self._weather_setter_role(weather),
                    "priority": "高",
                }
            )
            matching_sweepers = [(s, w) for s, w in weather_sweeper_species if w == weather]
            for sweeper_species, _ in matching_sweepers:
                matching_abilities = [a for a, w in WEATHER_SWEEPERS.items() if w == weather]
                ability_name = matching_abilities[0] if matching_abilities else ""
                key_pokemon.append(
                    {
                        "species": sweeper_species,
                        "role": f"{weather}エース ({ability_name})",
                        "priority": "高",
                    }
                )
                threats.append(f"{sweeper_species} の{ability_name}発動時は素早さ2倍に注意")

        # 重複除去
        seen_key: set[str] = set()
        unique_key_pokemon: list[dict] = []
        for kp in key_pokemon:
            key = f"{kp['species']}_{kp['role']}"
            if key not in seen_key:
                seen_key.add(key)
                unique_key_pokemon.append(kp)

        # 構築タイプ決定
        archetype = self._determine_archetype(detected_weathers, has_trick_room, unique_key_pokemon)

        return archetype, unique_key_pokemon, threats

    @staticmethod
    def _weather_setter_role(weather: str) -> str:
        """天候始動の役割文字列を返す。"""
        ability = next(
            (a for a, (w, _) in WEATHER_SETTERS.items() if w == weather),
            "",
        )
        return f"{weather}始動 ({ability})"

    def _determine_archetype(
        self,
        weathers: list[str],
        has_trick_room: bool,
        key_pokemon: list[dict],
    ) -> str:
        """構築タイプ名を決定する。"""
        parts: list[str] = []

        weather_map = {"雨": "雨パ", "晴れ": "晴れパ", "砂": "砂パ", "雪": "雪パ"}
        for w in weathers:
            if w in weather_map:
                parts.append(weather_map[w])

        if has_trick_room:
            parts.append("トリルパ")

        if not parts:
            return "スタン"

        if len(parts) == 1:
            return parts[0]

        return " + ".join(parts) + " (複合構築)"


# シングルトンインスタンス
meta_database = MetaDatabase()

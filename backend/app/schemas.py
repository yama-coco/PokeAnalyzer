from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# --- Pokemon / Party schemas ---


class TeraType(str, Enum):
    NORMAL = "ノーマル"
    FIRE = "ほのお"
    WATER = "みず"
    ELECTRIC = "でんき"
    GRASS = "くさ"
    ICE = "こおり"
    FIGHTING = "かくとう"
    POISON = "どく"
    GROUND = "じめん"
    FLYING = "ひこう"
    PSYCHIC = "エスパー"
    BUG = "むし"
    ROCK = "いわ"
    GHOST = "ゴースト"
    DRAGON = "ドラゴン"
    DARK = "あく"
    STEEL = "はがね"
    FAIRY = "フェアリー"
    STELLAR = "ステラ"


class PokemonStats(BaseModel):
    hp: int = Field(..., ge=1, description="HP実数値")
    attack: int = Field(..., ge=1, description="攻撃実数値")
    defense: int = Field(..., ge=1, description="防御実数値")
    sp_attack: int = Field(..., ge=1, description="特攻実数値")
    sp_defense: int = Field(..., ge=1, description="特防実数値")
    speed: int = Field(..., ge=1, description="素早さ実数値")


class PokemonEntry(BaseModel):
    species: str = Field(..., description="種族名")
    ability: str = Field(..., description="特性")
    item: str = Field("", description="持ち物")
    moves: list[str] = Field(default_factory=list, max_length=4, description="技（最大4つ）")
    stats: PokemonStats
    tera_type: TeraType | None = Field(None, description="テラスタイプ")
    can_mega_evolve: bool = Field(False, description="メガシンカ可能か")


class PartyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="パーティ名")
    pokemon: list[PokemonEntry] = Field(
        ..., min_length=1, max_length=6, description="ポケモン（1〜6体）"
    )


class PartyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    pokemon: list[PokemonEntry] | None = Field(None, min_length=1, max_length=6)


class PartyResponse(BaseModel):
    id: int
    name: str
    pokemon: list[PokemonEntry]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Speed calculation schemas ---


class WeatherCondition(str, Enum):
    NONE = "none"
    SUN = "sun"
    RAIN = "rain"
    SAND = "sand"
    SNOW = "snow"


class FieldCondition(BaseModel):
    tailwind: bool = Field(False, description="追い風が有効か")
    trick_room: bool = Field(False, description="トリックルームが有効か")
    weather: WeatherCondition = Field(WeatherCondition.NONE, description="天候")


class StatModifier(int, Enum):
    MINUS_6 = -6
    MINUS_5 = -5
    MINUS_4 = -4
    MINUS_3 = -3
    MINUS_2 = -2
    MINUS_1 = -1
    ZERO = 0
    PLUS_1 = 1
    PLUS_2 = 2
    PLUS_3 = 3
    PLUS_4 = 4
    PLUS_5 = 5
    PLUS_6 = 6


class BattlePokemon(BaseModel):
    name: str = Field(..., description="ポケモン名")
    base_speed: int = Field(..., ge=1, description="素早さ実数値（Lv50時）")
    ability: str = Field("", description="特性")
    item: str = Field("", description="持ち物")
    speed_modifier: StatModifier = Field(StatModifier.ZERO, description="素早さランク変化")
    is_paralyzed: bool = Field(False, description="まひ状態か")
    slot: int = Field(..., ge=0, le=3, description="フィールド上のスロット (0-3)")


class SpeedCalcRequest(BaseModel):
    pokemon: list[BattlePokemon] = Field(
        ..., min_length=1, max_length=4, description="場に出ているポケモン（最大4体）"
    )
    field: FieldCondition = Field(default_factory=FieldCondition, description="フィールド状態")


class SpeedTierEntry(BaseModel):
    slot: int
    name: str
    effective_speed: float
    order: int = Field(..., description="行動順 (1が最速)")
    modifiers_applied: list[str] = Field(default_factory=list, description="適用された補正の一覧")


class SpeedCalcResponse(BaseModel):
    tiers: list[SpeedTierEntry]
    trick_room_active: bool


# --- OBS connection schemas ---


class OBSConnectionStatus(BaseModel):
    connected: bool
    obs_version: str | None = None
    websocket_version: str | None = None
    error: str | None = None


class OBSRecordingAction(str, Enum):
    START = "start"
    STOP = "stop"
    TOGGLE = "toggle"


class OBSRecordingRequest(BaseModel):
    action: OBSRecordingAction


class OBSRecordingStatus(BaseModel):
    is_recording: bool
    output_path: str | None = None


class OBSSceneRequest(BaseModel):
    scene_name: str


class OBSCaptureStatus(BaseModel):
    active: bool
    width: int | None = None
    height: int | None = None
    fps: float | None = None


# --- Vision Engine schemas ---


class VisionEngineAction(str, Enum):
    START = "start"
    STOP = "stop"


class VisionEngineRequest(BaseModel):
    action: VisionEngineAction


class VisionStatus(BaseModel):
    running: bool
    scene_state: str = "idle"
    scene_confidence: float = 0.0
    fps: float = 0.0
    total_frames: int = 0
    detected_pokemon: list[str] = Field(default_factory=list)
    detected_moves: list[str] = Field(default_factory=list)
    detected_abilities: list[str] = Field(default_factory=list)
    components: dict = Field(default_factory=dict)


class VisionDetection(BaseModel):
    name: str
    confidence: float
    bbox: list[int] = Field(default_factory=list)
    source: str = ""


class VisionAnalysisResult(BaseModel):
    scene_state: str
    detections: list[VisionDetection] = Field(default_factory=list)
    text_analysis: dict = Field(default_factory=dict)
    hp_values: dict[str, float | None] = Field(default_factory=dict)


class SceneStateResponse(BaseModel):
    current_state: str
    confidence: float
    entered_at: float
    frame_count: int
    history: list[dict] = Field(default_factory=list)

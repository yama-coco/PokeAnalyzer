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


# --- Battle State schemas (Phase 3) ---


class PokemonOnFieldSchema(BaseModel):
    slot: int = Field(..., ge=0, le=3, description="フィールド上のスロット (0-3)")
    name: str = Field(..., description="ポケモン名")
    species: str = Field("", description="種族名")
    ability: str = Field("", description="特性")
    item: str = Field("", description="持ち物")
    base_speed: int = Field(0, ge=0, description="素早さ実数値")
    current_hp: int = Field(0, ge=0, description="現在HP")
    max_hp: int = Field(0, ge=0, description="最大HP")
    hp_percent: float = Field(100.0, ge=0.0, le=100.0, description="HP割合 (%)")
    side: str = Field("ally", description="味方(ally)か相手(enemy)か")
    status: str = Field("", description="状態異常")


class StartMatchRequest(BaseModel):
    ally_team: list[str] = Field(default_factory=list, description="味方チーム6体")
    enemy_team: list[str] = Field(default_factory=list, description="相手チーム6体")


class SetSelectionRequest(BaseModel):
    ally_leads: list[str] = Field(..., min_length=1, max_length=4, description="味方選出")
    enemy_leads: list[str] = Field(default_factory=list, max_length=4, description="相手選出")


class StartBattleRequest(BaseModel):
    pokemon_on_field: list[PokemonOnFieldSchema] = Field(
        default_factory=list, max_length=4, description="フィールド上のポケモン"
    )


class UpdateFieldRequest(BaseModel):
    weather: str | None = Field(None, description="天候 (none/sun/rain/sand/snow)")
    tailwind_ally: bool | None = Field(None, description="味方追い風")
    tailwind_enemy: bool | None = Field(None, description="相手追い風")
    trick_room: bool | None = Field(None, description="トリックルーム")
    terrain: str | None = Field(None, description="フィールド (grassy/electric/psychic/misty)")


class UpdateHPRequest(BaseModel):
    slot: int = Field(..., ge=0, le=3, description="スロット")
    current_hp: int | None = Field(None, ge=0, description="現在HP")
    max_hp: int | None = Field(None, ge=0, description="最大HP")
    hp_percent: float | None = Field(None, ge=0.0, le=100.0, description="HP%")


class AdvanceTurnRequest(BaseModel):
    actions: list[dict] = Field(default_factory=list, description="ターンのアクション一覧")


class LogActionRequest(BaseModel):
    turn: int = Field(..., ge=1, description="ターン番号")
    pokemon_slot: int = Field(..., ge=0, le=3, description="ポケモンスロット")
    pokemon_name: str = Field(..., description="ポケモン名")
    action_type: str = Field(..., description="アクション種別 (move/switch/terastal/mega/protect)")
    action_name: str = Field(..., description="アクション名 (技名等)")
    target_slot: int | None = Field(None, ge=0, le=3, description="ターゲットスロット")
    target_name: str = Field("", description="ターゲット名")


class ProtectRecordRequest(BaseModel):
    pokemon_name: str = Field(..., description="ポケモン名")
    move_name: str = Field("まもる", description="まもる系技名")
    turn: int = Field(..., ge=1, description="ターン番号")
    success: bool = Field(True, description="成功したか")


class DamageCalcRequest(BaseModel):
    move_name: str = Field(..., description="技名")
    move_power: int = Field(..., ge=0, description="技威力")
    move_category: str = Field(..., description="物理(physical)/特殊(special)")
    is_spread: bool = Field(False, description="範囲技か")
    attacker_name: str = Field(..., description="攻撃側ポケモン名")
    attacker_stat: int = Field(..., ge=1, description="攻撃/特攻の実数値")
    attacker_ability: str = Field("", description="攻撃側特性")
    attacker_item: str = Field("", description="攻撃側持ち物")
    has_stab: bool = Field(False, description="タイプ一致か")
    type_effectiveness: float = Field(1.0, description="タイプ相性倍率")
    defender_name: str = Field(..., description="防御側ポケモン名")
    defender_stat: int = Field(..., ge=1, description="防御/特防の実数値")
    defender_max_hp: int = Field(..., ge=1, description="防御側最大HP")


class EVEstimateRequest(BaseModel):
    species_base_stat: int = Field(..., ge=1, description="種族値")
    damage_percent: float = Field(..., gt=0, description="ダメージ%")
    move_name: str = Field(..., description="技名")
    move_power: int = Field(..., ge=0, description="技威力")
    move_category: str = Field(..., description="物理/特殊")
    is_spread: bool = Field(False, description="範囲技か")
    attacker_stat: int = Field(..., ge=1, description="攻撃/特攻の実数値")
    defender_max_hp: int = Field(..., ge=1, description="防御側最大HP")
    has_stab: bool = Field(False, description="タイプ一致")
    type_effectiveness: float = Field(1.0, description="タイプ相性")


# --- Vision Pipeline schemas (Phase 5) ---


class PipelineStartRequest(BaseModel):
    device_index: int = Field(0, ge=0, description="OpenCV VideoCapture デバイスインデックス")
    target_fps: int = Field(5, ge=1, le=30, description="解析フレームレート (fps)")
    scene_confidence_threshold: float = Field(
        0.6, ge=0.0, le=1.0, description="シーン遷移の confidence 閾値"
    )
    noise_frame_count: int = Field(3, ge=1, le=30, description="ノイズ耐性のためのフレーム数")


class PipelineCaptureStatus(BaseModel):
    active: bool = False
    width: int | None = None
    height: int | None = None
    fps: float | None = None


class PipelineVisionStatus(BaseModel):
    running: bool = False
    scene_state: str = "idle"
    scene_confidence: float = 0.0
    fps: float = 0.0
    total_frames: int = 0
    detected_pokemon: list[str] = Field(default_factory=list)


class PipelineStatsResponse(BaseModel):
    started_at: float = 0.0
    total_frames_fed: int = 0
    total_frames_processed: int = 0
    total_events_dispatched: int = 0
    last_frame_at: float = 0.0
    capture_errors: int = 0
    pipeline_fps: float = 0.0


class PipelineStatusResponse(BaseModel):
    running: bool = False
    target_fps: int = 5
    device_index: int = 0
    scene_confidence_threshold: float = 0.6
    noise_frame_count: int = 3
    capture: PipelineCaptureStatus = Field(default_factory=PipelineCaptureStatus)
    vision: PipelineVisionStatus = Field(default_factory=PipelineVisionStatus)
    stats: PipelineStatsResponse = Field(default_factory=PipelineStatsResponse)
    components: dict = Field(default_factory=dict)
    error: str | None = None


# --- Meta Database schemas (Phase 8) ---


class PokemonTemplateResponse(BaseModel):
    species: str = Field(..., description="種族名")
    archetype_name: str = Field(..., description="型名 (例: スカーフ型)")
    ability: str = Field(..., description="特性")
    item: str = Field(..., description="持ち物")
    nature: str = Field("", description="性格")
    evs: dict[str, int] = Field(default_factory=dict, description="努力値")
    moves: list[str] = Field(default_factory=list, description="技候補")
    usage_rate: float = Field(0.0, ge=0.0, le=1.0, description="使用率")
    tera_type: str | None = Field(None, description="テラスタイプ")
    can_mega_evolve: bool = Field(False, description="メガシンカ可否")
    notes: str = Field("", description="備考")
    source_url: str = Field("", description="データソースURL")


class MetaAnalyzeTeamRequest(BaseModel):
    enemy_species: list[str] = Field(
        ..., min_length=1, max_length=6, description="相手の6体のポケモン種族名"
    )


class KeyPokemonInfo(BaseModel):
    species: str = Field(..., description="種族名")
    role: str = Field(..., description="役割")
    priority: str = Field("中", description="優先度 (高/中/低)")


class TeamAnalysisResponse(BaseModel):
    archetype: str = Field("スタン", description="構築タイプ推定")
    key_pokemon: list[KeyPokemonInfo] = Field(default_factory=list, description="軸ポケモン")
    threats: list[str] = Field(default_factory=list, description="警戒すべき要素")
    pokemon_details: dict[str, list[PokemonTemplateResponse]] = Field(
        default_factory=dict, description="各ポケモンの型テンプレート"
    )


class MetaUpdateRequest(BaseModel):
    species: str = Field(..., description="種族名")
    templates: list[PokemonTemplateResponse] = Field(..., description="型テンプレート一覧")


class UsageRankingEntry(BaseModel):
    rank: int = Field(..., description="順位")
    species: str = Field(..., description="種族名")
    usage_rate: float = Field(..., description="使用率")
    top_archetype: str = Field("", description="最多型名")
    template_count: int = Field(0, description="型数")


class UsageRankingResponse(BaseModel):
    ranking: list[UsageRankingEntry] = Field(default_factory=list)
    total_pokemon: int = Field(0, description="登録ポケモン種数")
    total_templates: int = Field(0, description="総テンプレート数")
    last_updated: str = Field("", description="最終更新日時")

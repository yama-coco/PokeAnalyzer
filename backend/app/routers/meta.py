"""メタゲーム型検索 API エンドポイント (Phase 8)

VS画面で識別した相手のポケモンから想定される型を自動提示する。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import (
    MetaAnalyzeTeamRequest,
    MetaUpdateRequest,
    PokemonTemplateResponse,
    TeamAnalysisResponse,
    UsageRankingResponse,
)
from app.services.meta_database import PokemonTemplate, meta_database

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/pokemon/{species}", response_model=list[PokemonTemplateResponse])
def get_pokemon_templates(species: str) -> list[PokemonTemplateResponse]:
    """指定ポケモンの型テンプレート一覧を使用率順で返す。"""
    templates = meta_database.get_templates(species)
    if not templates:
        return []
    return [
        PokemonTemplateResponse(
            species=t.species,
            archetype_name=t.archetype_name,
            ability=t.ability,
            item=t.item,
            nature=t.nature,
            evs=t.evs,
            moves=t.moves,
            usage_rate=t.usage_rate,
            tera_type=t.tera_type,
            can_mega_evolve=t.can_mega_evolve,
            notes=t.notes,
            source_url=t.source_url,
        )
        for t in templates
    ]


@router.post("/analyze-team", response_model=TeamAnalysisResponse)
def analyze_team(body: MetaAnalyzeTeamRequest) -> TeamAnalysisResponse:
    """相手 6 体の分析 (構築タイプ推定・脅威分析)。"""
    result = meta_database.suggest_team_composition(body.enemy_species)
    return TeamAnalysisResponse(
        archetype=result["archetype"],
        key_pokemon=[
            {"species": kp["species"], "role": kp["role"], "priority": kp["priority"]}
            for kp in result["key_pokemon"]
        ],
        threats=result["threats"],
        pokemon_details={
            species: [PokemonTemplateResponse(**t) for t in templates]
            for species, templates in result["pokemon_details"].items()
        },
    )


@router.post("/update")
def update_meta(body: MetaUpdateRequest):
    """メタデータの手動更新。"""
    templates = [
        PokemonTemplate(
            species=t.species,
            archetype_name=t.archetype_name,
            ability=t.ability,
            item=t.item,
            nature=t.nature,
            evs=t.evs,
            moves=t.moves,
            usage_rate=t.usage_rate,
            tera_type=t.tera_type,
            can_mega_evolve=t.can_mega_evolve,
            notes=t.notes,
            source_url=t.source_url,
        )
        for t in body.templates
    ]
    meta_database.update_templates(body.species, templates)
    return {"status": "ok", "species": body.species, "template_count": len(templates)}


@router.get("/usage-ranking", response_model=UsageRankingResponse)
def get_usage_ranking(limit: int = 50) -> UsageRankingResponse:
    """使用率ランキングを返す。"""
    ranking_data = meta_database.get_usage_ranking(limit=limit)
    return UsageRankingResponse(
        ranking=[
            {
                "rank": i + 1,
                "species": entry["species"],
                "usage_rate": entry["usage_rate"],
                "top_archetype": entry["top_archetype"],
                "template_count": entry["template_count"],
            }
            for i, entry in enumerate(ranking_data)
        ],
        total_pokemon=len(meta_database.templates),
        total_templates=sum(len(v) for v in meta_database.templates.values()),
        last_updated=meta_database.last_updated,
    )

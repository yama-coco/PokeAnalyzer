"""パーティ登録・管理 API エンドポイント"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MyParty
from app.schemas import PartyCreate, PartyResponse, PartyUpdate, PokemonEntry

router = APIRouter(prefix="/api/parties", tags=["parties"])


def _party_to_response(party: MyParty) -> PartyResponse:
    pokemon = [PokemonEntry(**p) for p in json.loads(party.pokemon_json)]
    return PartyResponse(
        id=party.id,
        name=party.name,
        pokemon=pokemon,
        created_at=party.created_at,
        updated_at=party.updated_at,
    )


@router.get("/", response_model=list[PartyResponse])
def list_parties(db: Session = Depends(get_db)) -> list[PartyResponse]:
    parties = db.query(MyParty).order_by(MyParty.updated_at.desc()).all()
    return [_party_to_response(p) for p in parties]


@router.post("/", response_model=PartyResponse, status_code=201)
def create_party(body: PartyCreate, db: Session = Depends(get_db)) -> PartyResponse:
    pokemon_json = json.dumps([p.model_dump(mode="json") for p in body.pokemon], ensure_ascii=False)
    party = MyParty(name=body.name, pokemon_json=pokemon_json)
    db.add(party)
    db.commit()
    db.refresh(party)
    return _party_to_response(party)


@router.get("/{party_id}", response_model=PartyResponse)
def get_party(party_id: int, db: Session = Depends(get_db)) -> PartyResponse:
    party = db.query(MyParty).filter(MyParty.id == party_id).first()
    if party is None:
        raise HTTPException(status_code=404, detail="パーティが見つかりません")
    return _party_to_response(party)


@router.put("/{party_id}", response_model=PartyResponse)
def update_party(party_id: int, body: PartyUpdate, db: Session = Depends(get_db)) -> PartyResponse:
    party = db.query(MyParty).filter(MyParty.id == party_id).first()
    if party is None:
        raise HTTPException(status_code=404, detail="パーティが見つかりません")
    if body.name is not None:
        party.name = body.name
    if body.pokemon is not None:
        party.pokemon_json = json.dumps(
            [p.model_dump(mode="json") for p in body.pokemon], ensure_ascii=False
        )
    db.commit()
    db.refresh(party)
    return _party_to_response(party)


@router.delete("/{party_id}", status_code=204)
def delete_party(party_id: int, db: Session = Depends(get_db)) -> None:
    party = db.query(MyParty).filter(MyParty.id == party_id).first()
    if party is None:
        raise HTTPException(status_code=404, detail="パーティが見つかりません")
    db.delete(party)
    db.commit()

"""ダブルバトル素早さ計算 API エンドポイント"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas import SpeedCalcRequest, SpeedCalcResponse
from app.services.speed_calculator import calculate_speed_tiers

router = APIRouter(prefix="/api/battle", tags=["battle"])


@router.post("/speed-tiers", response_model=SpeedCalcResponse)
def compute_speed_tiers(body: SpeedCalcRequest) -> SpeedCalcResponse:
    """場に出ている最大4体の素早さ順を計算する。

    追い風、トリックルーム、天候、特性、アイテム、ランク変化、状態異常を加味して
    リアルタイムに行動順を返す。
    """
    return calculate_speed_tiers(body)

"""PAL-C (PokeAnalysis Live for Champions) - FastAPI アプリケーション"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import battle, obs, party, vision
from app.services.obs_connector import obs_connector
from app.services.vision_engine import vision_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    await vision_engine.stop()
    await obs_connector.disconnect()


app = FastAPI(
    title="PokeAnalysis Live for Champions (PAL-C)",
    description="ポケモンチャンピオンズ ダブルバトル リアルタイム分析ツール",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(party.router)
app.include_router(battle.router)
app.include_router(obs.router)
app.include_router(vision.router)


@app.get("/")
def root():
    return {
        "name": "PAL-C",
        "version": "0.1.0",
        "description": "PokeAnalysis Live for Champions",
    }


@app.get("/health")
def health():
    return {"status": "ok"}

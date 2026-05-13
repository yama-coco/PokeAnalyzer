---
name: testing-pokeanalyzer-api
description: Test the PokeAnalyzer FastAPI backend end-to-end. Use when verifying API changes, Vision Engine, speed calculator, or OBS integration.
---

# Testing PokeAnalyzer API

## Prerequisites

- Python 3.12+ with virtualenv at `backend/.venv`
- No external services required (OBS, PaddleOCR, YOLO all have graceful degradation)
- No authentication required for any endpoints

## Server Startup

```bash
cd /home/ubuntu/repos/PokeAnalyzer/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify with: `curl http://localhost:8000/health` → `{"status": "ok"}`

## Swagger UI

Available at `http://localhost:8000/docs`. API groups:
- **parties**: CRUD for party registration
- **battle**: Speed tier calculation (`POST /api/battle/speed-tiers`)
- **obs**: OBS WebSocket integration (graceful degradation when OBS not connected)
- **vision**: Vision Engine pipeline (Phase 2)

## Key Test Flows

### Vision Engine State Machine

The scene state machine has 5 states: `idle`, `matching`, `selection`, `battle`, `result`.

1. **Force transition**: `POST /api/vision/scene/force?state=<state>`
2. **Verify via /scene**: `GET /api/vision/scene` → check `current_state`
3. **Verify via /status**: `GET /api/vision/status` → check `scene_state`

**Important**: Always verify BOTH `/scene` and `/status` after force transitions. A previous bug caused these to desync (force_transition updated the state machine but not the engine's cached state). If you see `/scene` returning a stale state after `/force`, check that `vision_engine._state.scene` is being synced with `vision_engine._scene_machine.context` in the `force_scene_transition` function in `backend/app/routers/vision.py`.

### Speed Calculator

Test with realistic competitive doubles scenarios:
- Rain team: Barraskewda (Swift Swim) in rain should outspeed Choice Scarf Garchomp
- Trick Room: Slowest Pokemon should move first
- Compound modifiers: Paralysis + Choice Scarf + Tailwind stack multiplicatively

### Graceful Degradation

When optional dependencies are not installed:
- `GET /api/vision/status` → `components.ocr_available: false` (PaddleOCR not installed)
- `GET /api/vision/status` → `components.yolo_available: false` (YOLO model not loaded)
- `GET /api/obs/status` → `connected: false` (OBS not running)

All endpoints should return 200 with degraded status, never 500.

## Unit Tests

```bash
cd /home/ubuntu/repos/PokeAnalyzer/backend
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: 123+ tests passing. Tests cover both Phase 1 (parties, battle, OBS) and Phase 2 (vision engine, scene state, frame processor, OCR, YOLO, template matcher).

## Lint

```bash
ruff check backend/
ruff format --check backend/
```

## Common Pitfalls

- The Vision Engine has two separate state objects: `SceneStateMachine._context` and `VisionEngine._state.scene`. Any code that modifies the scene state machine must also sync `_state.scene`.
- PaddleOCR import might show warnings on startup — this is expected and does not affect functionality.
- Template matcher requires PNG files in `backend/templates/pokemon/` — without them, `template_count` will be 0.

## Devin Secrets Needed

None — all testing can be done without external credentials.

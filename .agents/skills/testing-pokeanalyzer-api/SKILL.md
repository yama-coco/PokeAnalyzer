---
name: testing-pokeanalyzer-api
description: Test the PokeAnalyzer FastAPI backend end-to-end. Use when verifying API changes, Vision Engine, speed calculator, OBS integration, or Vision Pipeline.
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

Verify with: `curl http://localhost:8000/health` -> `{"status": "ok"}`

## Swagger UI

Available at `http://localhost:8000/docs`. API groups:
- **parties**: CRUD for party registration
- **battle**: Speed tier calculation (`POST /api/battle/speed-tiers`)
- **obs**: OBS WebSocket integration (graceful degradation when OBS not connected)
- **vision**: Vision Engine pipeline (Phase 2) + Vision Pipeline (Phase 5)

## Key Test Flows

### Vision Engine State Machine

The scene state machine has 5 states: `idle`, `matching`, `selection`, `battle`, `result`.

1. **Force transition**: `POST /api/vision/scene/force?state=<state>`
2. **Verify via /scene**: `GET /api/vision/scene` -> check `current_state`
3. **Verify via /status**: `GET /api/vision/status` -> check `scene_state`

**Important**: Always verify BOTH `/scene` and `/status` after force transitions. A previous bug caused these to desync (force_transition updated the state machine but not the engine's cached state). If you see `/scene` returning a stale state after `/force`, check that `vision_engine._state.scene` is being synced with `vision_engine._scene_machine.context` in the `force_scene_transition` function in `backend/app/routers/vision.py`.

### Vision Pipeline (Phase 5)

The Vision Pipeline orchestrates OBS virtual camera -> VisionEngine -> event dispatch.

**Endpoints:**
- `POST /api/vision/pipeline/start` - Start pipeline (accepts optional `PipelineStartRequest` body)
- `POST /api/vision/pipeline/stop` - Stop pipeline
- `GET /api/vision/pipeline/status` - Get pipeline status

**Key test scenarios:**
1. **Initial status**: `GET /pipeline/status` should return `running=false`, `target_fps=5`, `device_index=0`, `scene_confidence_threshold=0.6`, `noise_frame_count=3`, `error=null`
2. **Start without OBS**: `POST /pipeline/start` returns HTTP 200 with `running=false` and `error` containing OBS connection failure message (graceful degradation, NOT 500)
3. **Stop when not running**: `POST /pipeline/stop` returns HTTP 200 with `running=false`, `error=null`
4. **Schema validation**: `POST /pipeline/start` with `{"target_fps": 0}` returns HTTP 422
5. **Scene state integration**: After forcing scene to `matching` via `/scene/force`, pipeline status at `/pipeline/status` should reflect `vision.scene_state="matching"` even when the pipeline is not running (pipeline reads from VisionEngine singleton)

**Response shape (`PipelineStatusResponse`):**
```json
{
  "running": false,
  "target_fps": 5,
  "device_index": 0,
  "scene_confidence_threshold": 0.6,
  "noise_frame_count": 3,
  "capture": {"active": false, "width": null, "height": null, "fps": null},
  "vision": {"running": false, "scene_state": "idle", "scene_confidence": 0.0, "fps": 0.0, "total_frames": 0, "detected_pokemon": []},
  "stats": {"started_at": 0.0, "total_frames_fed": 0, "total_frames_processed": 0, "total_events_dispatched": 0, "last_frame_at": 0.0, "capture_errors": 0, "pipeline_fps": 0.0},
  "components": {"ocr_available": false, "yolo_available": false, "template_count": 0, "scene_state": "idle"},
  "error": null
}
```

**Note on error path**: When pipeline start fails (OBS unavailable), the error response returns a dict directly from `vision_pipeline.start()` rather than `get_status()`. The `components` field may be empty `{}` in the error response (vs populated when queried via `/pipeline/status` or `/pipeline/stop`).

### Speed Calculator

Test with realistic competitive doubles scenarios:
- Rain team: Barraskewda (Swift Swim) in rain should outspeed Choice Scarf Garchomp
- Trick Room: Slowest Pokemon should move first
- Compound modifiers: Paralysis + Choice Scarf + Tailwind stack multiplicatively

### Graceful Degradation

When optional dependencies are not installed:
- `GET /api/vision/status` -> `components.ocr_available: false` (PaddleOCR not installed)
- `GET /api/vision/status` -> `components.yolo_available: false` (YOLO model not loaded)
- `GET /api/obs/status` -> `connected: false` (OBS not running)
- `POST /api/vision/pipeline/start` -> `running: false`, `error: "OBS仮想カメラ..."` (OBS not running)

All endpoints should return 200 with degraded status, never 500.

## Unit Tests

```bash
cd /home/ubuntu/repos/PokeAnalyzer/backend
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: 280+ tests passing. Tests cover Phase 1 (parties, battle, OBS), Phase 2 (vision engine, scene state, frame processor, OCR, YOLO, template matcher), and Phase 5 (vision pipeline lifecycle, scene dispatch, frame feed, API endpoints).

## Lint

```bash
cd /home/ubuntu/repos/PokeAnalyzer/backend
source .venv/bin/activate
ruff check app/ tests/
ruff format --check app/ tests/
```

## Common Pitfalls

- The Vision Engine has two separate state objects: `SceneStateMachine._context` and `VisionEngine._state.scene`. Any code that modifies the scene state machine must also sync `_state.scene`.
- PaddleOCR import might show warnings on startup -- this is expected and does not affect functionality.
- Template matcher requires PNG files in `backend/templates/pokemon/` -- without them, `template_count` will be 0.
- The Vision Pipeline uses a module-level singleton (`vision_pipeline = VisionPipeline()`). API endpoint tests hit this singleton, so test isolation depends on the pipeline not being started during test runs.
- When testing pipeline start failure, the error response dict has a slightly different shape than `get_status()` (e.g., `components` may be empty).

## Devin Secrets Needed

None -- all testing can be done without external credentials.

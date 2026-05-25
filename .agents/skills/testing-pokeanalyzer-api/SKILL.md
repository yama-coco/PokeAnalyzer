---
name: testing-pokeanalyzer-api
description: Test the PokeAnalyzer FastAPI backend end-to-end. Use when verifying API changes, Vision Engine, speed calculator, OBS integration, Vision Pipeline, YOLO detector, or Meta Database.
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
- **meta**: Meta database - Pokemon type templates, team analysis, usage ranking (Phase 8)

## Key Test Flows

### Meta Database (Phase 8)

Phase 8 provides competitive Pokemon data from champs.pokedb.tokyo.

**Endpoints:**
- `GET /api/meta/usage-ranking?limit=N` - Usage ranking (default top 50)
- `GET /api/meta/pokemon/{species}` - Pokemon templates (URL-encode Japanese names)
- `POST /api/meta/analyze-team` - Team composition analysis
- `POST /api/meta/update` - Manual template update

**Key test scenarios:**
1. **Usage ranking order**: Ranking must follow the site's order (insertion order in JSON), NOT sorted by archetype usage_rate. If sorted by usage_rate, ミミロップ (98.5%) would incorrectly appear first instead of イダイトウ (オス) (43.4%).
2. **Individual search**: `GET /api/meta/pokemon/ガブリアス` should return 5 templates. Top template: ability=さめはだ, item=オボンのみ, nature=いじっぱり, usage_rate=0.355
3. **Team analysis**: `POST /api/meta/analyze-team` with `{"enemy_species": ["ペリッパー", "ガブリアス"]}` should return archetype="雨パ" (rain team detected via ペリッパー's あめふらし ability)
4. **Non-existent Pokemon**: `GET /api/meta/pokemon/存在しない` should return empty array `[]`, not error
5. **Data integrity**: `total_pokemon` should be 50, `total_templates` should be 250

**Known pitfalls:**
- `test_meta_api.py` uses `patch.object(meta_database, "save")` to prevent tests from overwriting `meta_templates.json`. If this mock is removed, running pytest will corrupt the data file with test data ("テストポケモン").
- The `usage_rate` field in templates is the archetype-level rate within a species (e.g., 35.5% of ガブリアス users use オボンのみ), NOT the species-level usage rate.
- Species names may contain special characters: parentheses like "イダイトウ (オス)", colons like "フラエッテ (えいえん)", region markers like "キュウコン (アローラ)"

**Data refresh:**
```bash
cd /home/ubuntu/repos/PokeAnalyzer/backend
source .venv/bin/activate
python scripts/scrape_pokedb.py
```
Requires Chrome running with CDP (DevToolsActivePort). Takes ~4 minutes for 50 species.

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
5. **Scene state integration**: After forcing scene to `matching` via `/scene/force`, pipeline status at `/pipeline/status` should reflect `vision.scene_state="matching"` even when the pipeline is not running

**Note on error path**: When pipeline start fails (OBS unavailable), the error response returns a dict directly from `vision_pipeline.start()` rather than `get_status()`. The `components` field may be empty `{}` in the error response.

### YOLO Detector (Phase 6)

Phase 6 adds training infrastructure and detection utilities to `yolo_detector.py`.

**Key testing areas:**
1. **Graceful degradation**: `GET /api/vision/status` -> `components.yolo_available: false` when no trained model exists at `backend/models/pokemon_detect.pt`
2. **NMS (Non-Maximum Suppression)**: `YOLODetector.apply_nms()` static method — test with overlapping detections
3. **IoU computation**: `YOLODetector.compute_iou()` static method — test perfect overlap, no overlap, partial overlap, containment
4. **Coordinate conversion**: `convert_bbox_to_yolo()` and `convert_yolo_to_bbox()` — test roundtrip conversion
5. **Benchmark**: `YOLODetector.benchmark()` — returns timing stats even when model unavailable
6. **Training data management**: `setup_training_dirs()` creates images/{train,val} and labels/{train,val}
7. **Training config**: `create_training_config()` generates YOLO training config dict

**Note**: NMS is NOT automatically called in `detect()` — callers must invoke `apply_nms()` explicitly.

### pokemon_detect.yaml Validation

The YOLO training config at `backend/models/pokemon_detect.yaml` should contain:
- `nc: 245` (213 official Pokémon + 32 Mega evolution forms)
- `names:` section with 245 entries (indices 0-244)
- `sprite_classes:` section with CSS sprite class names for the 213 official forms
- Mega forms marked as "なし" (none) in sprite_classes (they only appear during battle)

**Important**: メガニウム (Meganium, index 46) is an official Pokémon whose name contains "メガ" but is NOT a Mega evolution form. When counting Mega forms, filter for entries starting with "メガ" AND not equal to "メガニウム".

Validation script:
```python
import yaml
with open('models/pokemon_detect.yaml') as f:
    config = yaml.safe_load(f)
assert config['nc'] == 245
assert len(config['names']) == 245
assert len(config['sprite_classes']) == 213
```

### Speed Calculator

Test with realistic competitive doubles scenarios.

**Important**: `BattlePokemon` requires a `slot` field (0-3) for field position. Example:
```json
{"pokemon": [{"name": "Garchomp", "base_speed": 102, "slot": 0}, {"name": "Dragapult", "base_speed": 142, "slot": 1}]}
```

### Parties CRUD

**Important**: `PokemonEntry` requires `species`, `ability`, and `stats` fields. The `tera_type` enum uses Japanese names (ノーマル, ほのお, みず, etc.), NOT English.

Example:
```json
{"name": "TestParty", "pokemon": [{"species": "ガブリアス", "ability": "さめはだ", "stats": {"hp": 183, "attack": 182, "defense": 115, "sp_attack": 90, "sp_defense": 105, "speed": 169}, "tera_type": "じめん"}]}
```

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

Expected: 416+ tests passing. Tests cover Phase 1-8.

## Lint

```bash
cd /home/ubuntu/repos/PokeAnalyzer/backend
source .venv/bin/activate
ruff check app/ tests/
ruff format --check app/ tests/
```

**Note**: Old scraper files (`scrape_meta_data.py`, `scrape_via_browser.py`) may have pre-existing lint warnings. Focus on `app/` and `tests/` directories.

## Common Pitfalls

- The Vision Engine has two separate state objects: `SceneStateMachine._context` and `VisionEngine._state.scene`. Any code that modifies the scene state machine must also sync `_state.scene`.
- PaddleOCR import might show warnings on startup -- this is expected and does not affect functionality.
- Template matcher requires PNG files in `backend/templates/pokemon/` -- without them, `template_count` will be 0.
- The Vision Pipeline uses a module-level singleton (`vision_pipeline = VisionPipeline()`). API endpoint tests hit this singleton, so test isolation depends on the pipeline not being started during test runs.
- When testing pipeline start failure, the error response dict has a slightly different shape than `get_status()` (e.g., `components` may be empty).
- `capture_training_data.py` requires a live OBS WebSocket connection and cannot be E2E tested without OBS.
- Phase 5 pipeline endpoints (`/api/vision/pipeline/*`) are only available if Phase 5 PR is merged. If testing Phase 6 branch based off main without Phase 5, skip pipeline tests.
- MetaDatabase is a singleton. Running pytest test_meta_api.py will NOT corrupt `meta_templates.json` because save() is mocked. But if save() mock is removed, data file will be overwritten with test data.

## Devin Secrets Needed

None -- all testing can be done without external credentials.

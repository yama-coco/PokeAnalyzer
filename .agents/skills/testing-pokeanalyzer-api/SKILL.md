---
name: testing-pokeanalyzer-api
description: Test the PokeAnalyzer (PAL-C) FastAPI backend end-to-end. Use when verifying Vision Engine, speed calculator, OBS, or party API changes.
---

# Testing PokeAnalyzer Backend API

## Prerequisites

- Python virtual environment at `backend/.venv`
- Dependencies installed: `cd backend && pip install -e ".[dev]"`
- Optional vision deps: `pip install -e ".[vision]"` (PaddleOCR, ultralytics)

## Starting the Server

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI available at `http://localhost:8000/docs`

## Running Unit Tests

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: All tests pass (Phase 1: 39, Phase 2: 84 = 123 total as of Phase 2).

## API Endpoint Groups

### Vision API (`/api/vision/`)
- `GET /status` - Engine state (running, scene, fps, components)
- `GET /components` - Component availability (OCR, YOLO, template count)
- `POST /control` - Start/stop engine: `{"action": "start"}` or `{"action": "stop"}`
- `GET /scene` - Current scene state + transition history
- `POST /scene/force?state=<state>` - Force scene transition (debug). Valid states: `idle`, `matching`, `selection`, `battle`, `result`
- `POST /analyze-frame?image_base64=<encoded>` - Analyze single frame
- `WebSocket /ws` - Real-time result streaming

### Battle API (`/api/battle/`)
- `POST /speed-tiers` - Calculate speed ordering. Requires `slot` field per pokemon.

### Party API (`/api/parties/`)
- Standard CRUD: GET list, POST create, GET by id, PUT update, DELETE

### OBS API (`/api/obs/`)
- `GET /status` - Connection status (will show `connected: false` without OBS)
- Various recording/capture/scene control endpoints

## Testing Tips

### Base64 Image for analyze-frame
The `image_base64` parameter is a **query parameter** (not request body). For large images, the URL may exceed length limits. Workarounds:
1. Use small test images (e.g., 10x10 pixels)
2. URL-encode the base64 string (escape `=` as `%3D`, `+` as `%2B`, `/` as `%2F`)

Example creating a test image:
```python
import cv2, numpy as np, base64, urllib.parse
img = np.zeros((10, 10, 3), dtype=np.uint8)
img[:] = (100, 150, 200)
_, buf = cv2.imencode('.png', img)
b64 = base64.b64encode(buf).decode('utf-8')
encoded = urllib.parse.quote(b64, safe='')
# Use `encoded` as the query parameter value
```

### Graceful Degradation
Without optional dependencies:
- PaddleOCR not installed → `ocr_available: false`, OCR endpoints return empty results
- No YOLO model file → `yolo_available: false`, detection returns 0 results
- No template_dir configured → `template_count: 0`

The server starts and operates normally in all cases.

### Swagger UI Navigation
The Swagger UI page is long (4 API groups). To jump to Vision endpoints:
```javascript
// In browser console
document.getElementById('operations-tag-vision').scrollIntoView();
```
Or collapse other sections first by clicking their collapse buttons.

### Known Issues to Watch For
- `POST /scene/force` might update the scene machine internally but `/scene` and `/status` endpoints may show stale state if `VisionEngine._state.scene` is not synced after force transitions. Check both the force response AND the `/scene` endpoint to verify consistency.

## Devin Secrets Needed
None required for basic testing. All APIs are unauthenticated.

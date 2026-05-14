---
name: testing-pokeanalyzer-frontend
description: Test PokeAnalyzer React frontend end-to-end against the FastAPI backend. Use when verifying UI pages, API integration, or Phase 4 changes.
---

# Testing PokeAnalyzer Frontend

## Prerequisites

### Start Backend
```bash
cd /home/ubuntu/repos/PokeAnalyzer/backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Start Frontend
```bash
cd /home/ubuntu/repos/PokeAnalyzer/frontend
npm run dev -- --host 0.0.0.0
```
- Default port: 5173. If busy, Vite auto-increments to 5174, 5175, etc.
- Check terminal output for actual port.

### Verify Backend Health
```bash
curl http://localhost:8000/api/battle/match/state
```
Should return JSON with match phase info.

## Pages to Test

| Route | Page | Key Checks |
|-------|------|------------|
| `/` | Dashboard | Sidebar 7 links, phase badge, match start/end/advance controls |
| `/speed` | Speed Calculator | 4 Pokemon inputs, calculate button, trick room reversal |
| `/hp` | HP Tracker | Empty state when no battle; ally actual HP vs enemy % HP |
| `/protect` | Protect Manager | Probability table (100% → 33.3% → 11.1% → 3.7%) |
| `/damage` | Damage Calculator | Attack/defense inputs, STAB/type effectiveness, result display |
| `/party` | Party Management | CRUD operations, "新規作成" button |
| `/hud-settings` | HUD Settings | OBS setup instructions, preview iframe |
| `/hud` | HUD Overlay | Only shows content when phase is `in_battle` |

## Match Lifecycle for Testing

1. **Start match**: Dashboard → "新しい試合" → enter ally/enemy team names (comma-separated) → "開始"
2. **Phase transitions**: none → team_preview → selection → in_battle → result
3. Selection/battle-start require API calls with specific Pokemon data structures
4. To reach `in_battle` phase, you need to call `/api/battle/match/selection` and `/api/battle/match/battle-start` with proper payloads

## Known Issues to Watch For

- **Party API path mismatch**: Frontend might call `/api/party/` while backend uses `/api/parties/`. If party page shows "Not Found", check the API client path.
- **Party schema mismatch**: Frontend might send `{name, pokemon_json: string}` while backend expects `{name, pokemon: PokemonEntry[]}`. Verify the schema matches.
- **Damage calculator formula**: The damage calculation formula might produce inflated values. Verify with known scenarios (e.g., STAB super-effective should give ~50-80%, not thousands of %).
- **HUD overlay route**: Navigating to `/hud` might cause browser issues if the page renders an empty transparent overlay. Test via `/hud-settings` preview iframe instead.
- **WebSocket connection**: Header shows "未接続" (disconnected) — this is expected unless the vision engine WebSocket server is running.

## Speed Calculator Test Scenario

Good test data for speed calculation:
- ガブリアス S=169 (fast)
- ニンフィア S=112 (medium)
- バンギラス S=81 (slow)
- カイリュー S=132 (medium-fast)

Expected normal order: ガブリアス > カイリュー > ニンフィア > バンギラス
Expected trick room: reversed

## Damage Calculator Test Scenario

For verifying damage calc correctness:
- Attacker: ガブリアス, A=200, STAB
- Defender: バンギラス, D=130, HP=207
- Move: じしん, power=100, physical, 2x effectiveness
- Expected: roughly 50-80% damage (Gen 9 Lv50 formula)

## Tips

- Use browser UI interactions (not curl) for visible test evidence
- The frontend uses Vite proxy — all `/api/*` requests proxy to backend port 8000
- Tailwind CSS v4 is used — check `@import "tailwindcss"` syntax if styles break
- React Router handles client-side routing — direct URL navigation works with Vite dev server

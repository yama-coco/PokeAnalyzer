---
name: testing-pokeanalyzer-frontend
description: Test PokeAnalyzer React frontend end-to-end against the FastAPI backend. Use when verifying UI pages, API integration, or Phase 4+ changes.
---

# Testing PokeAnalyzer Frontend

## Prerequisites

### Start Backend
```bash
cd /home/ubuntu/repos/PokeAnalyzer/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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
| `/` | Dashboard | Sidebar 8 links, phase badge, match start/end/advance controls |
| `/speed` | Speed Calculator | 4 Pokemon inputs, calculate button, trick room reversal |
| `/hp` | HP Tracker | Empty state when no battle; ally actual HP vs enemy % HP |
| `/protect` | Protect Manager | Probability table (100% → 33.3% → 11.1% → 3.7%) |
| `/damage` | Damage Calculator | Attack/defense inputs, STAB/type effectiveness, result display |
| `/party` | Party Management | CRUD operations, "新規作成" button |
| `/meta` | メタ型検索 | 3 tabs: チーム分析, 個別検索, 使用率ランキング |
| `/hud-settings` | HUD Settings | OBS setup instructions, preview iframe |
| `/hud` | HUD Overlay | Only shows content when phase is `in_battle` |

## Meta Page Testing (Phase 8)

The `/meta` page has 3 tabs accessible via buttons at the top:

### 使用率ランキング Tab
- Click "使用率ランキング" button
- Shows top 20 Pokemon with rank, species name, archetype, usage %
- Expected order: #1 イダイトウ (オス), #2 ガブリアス, #3 ドドゲザン
- If ミミロップ appears as #1, the ranking sort is broken (using archetype rate instead of site order)

### 個別検索 Tab
- Click "個別検索" button
- Type Pokemon name (e.g., "ガブリアス") and click "検索"
- Should show "ガブリアス の型一覧 (5 件)" header
- Each template card shows: archetype name, usage %, ability, item, nature, moves
- "メガシンカ" badge appears when can_mega_evolve is true
- Clicking the expand arrow on a card shows EV spread details

### チーム分析 Tab
- Click "チーム分析" button
- Enter Pokemon names in 6 slots (at least 1 required)
- Click "分析する"
- Results show: 構築タイプ推定, 軸ポケモン, 警戒ポイント, and per-Pokemon template cards
- Test: Enter "ペリッパー" → should detect "雨パ" (rain team)
- Test: Enter only unknown Pokemon → should show "スタン" archetype

## Electron Build Verification (Phase 9+)

Electron wrapping adds infrastructure but no new UI pages. Testing focuses on build artifacts:

### TypeScript Compilation
```bash
cd /home/ubuntu/repos/PokeAnalyzer/frontend
npx tsc -p tsconfig.electron.json --noEmit
```
Should exit 0 with no errors.

### Vite Base Path Switching
```bash
# Electron mode: relative paths for file:// protocol
ELECTRON=true npx vite build
grep -o 'src="[^"]*"' dist/index.html  # Should show ./assets/...
grep -o 'href="[^"]*"' dist/index.html  # Should show ./assets/...

# Normal mode: absolute paths for HTTP server
npx vite build
grep -o 'src="[^"]*"' dist/index.html  # Should show /assets/...
```

### Build Artifacts Check
```bash
ls dist-electron/  # Should contain main.js and preload.js
grep '../dist/index.html' dist-electron/main.js  # Production load path
grep 'process.resourcesPath' dist-electron/main.js  # Packaged app path
grep 'contextIsolation: true' dist-electron/main.js  # Security check
```

### Environment Limitations
- Electron GUI **cannot** be tested in headless CI environments (no X11/Wayland)
- `npm run electron:dev` and `npm run dist` require a display server
- Test browser mode regression instead: all pages should still work via `npm run dev`
- The page title should be "PAL-C - PokeAnalysis Live for Champions" (verify via `document.title`)

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
- **Meta data corruption**: If `meta_templates.json` contains only "テストポケモン" (1 species, ~563 bytes), pytest has overwritten it. Re-run `python scripts/scrape_pokedb.py` to regenerate.
- **Pre-existing lint errors**: 3 lint errors exist on main branch (useBattleState.ts, useWebSocket.ts, PartyPage.tsx). These are not caused by new changes.

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
- Sidebar has 8 navigation links (added メタ型検索 in Phase 8)
- If the browser tool becomes unresponsive during testing, API endpoints can be verified via curl as a fallback
- The calculate button on /speed page is labeled "素早さ順を計算" and has devinid=36 (may change)
- Page title is "PAL-C - PokeAnalysis Live for Champions" (updated in Phase 9)

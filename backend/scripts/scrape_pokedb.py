#!/usr/bin/env python3
"""champs.pokedb.tokyo からポケモン使用率・型データを収集するスクレイパー。

Playwright CDP 経由でブラウザを使用してデータ取得。
ダブルバトル (rule=1) のシーズンM-2 データを対象。

使い方:
  cd backend
  source .venv/bin/activate
  python scripts/scrape_pokedb.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "meta_templates.json"

# CDP port: read from DevToolsActivePort if available
DEVTOOLS_PORT_FILE = Path.home() / ".browser_data_dir" / "DevToolsActivePort"
BASE_URL = "https://champs.pokedb.tokyo"
LIST_URL = f"{BASE_URL}/pokemon/list?rule=1"
TOP_N = 50  # 上位50匹のデータを収集

# EV stat key mapping (pokedb uses H/A/B/C/D/S notation)
EV_KEY_MAP = {
    "H": "hp",
    "A": "attack",
    "B": "defense",
    "C": "sp_attack",
    "D": "sp_defense",
    "S": "speed",
}

# Item-based archetype naming
ITEM_ARCHETYPE_MAP = {
    "こだわりスカーフ": "スカーフ型",
    "こだわりメガネ": "メガネ型",
    "こだわりハチマキ": "ハチマキ型",
    "きあいのタスキ": "タスキ型",
    "いのちのたま": "珠型",
    "とつげきチョッキ": "チョッキ型",
    "たべのこし": "残飯型",
    "オボンのみ": "オボン型",
    "ゴツゴツメット": "ゴツメ型",
    "しんかのきせき": "輝石型",
    "ラムのみ": "ラム型",
    "メンタルハーブ": "メンハ型",
    "しろいハーブ": "白ハーブ型",
    "ようせいのハネ": "ハネ型",
    "ロゼルのみ": "ロゼル型",
}

# JS to extract Pokemon URLs and names from list page
PARSE_LIST_JS = """
() => {
    const links = document.querySelectorAll('a[href*="/pokemon/show/"]');
    const result = [];
    const seen = new Set();
    for (const a of links) {
        const href = a.getAttribute('href');
        if (!href || seen.has(href)) continue;
        seen.add(href);
        // Child elements: div.pokemon-rank (number), div (name)
        const children = Array.from(a.children);
        let rank = 0;
        let name = '';
        for (const child of children) {
            const text = child.textContent.trim();
            if (child.classList && child.classList.contains('pokemon-rank')) {
                rank = parseInt(text) || 0;
            } else if (child.tagName === 'DIV' && !rank) {
                // Fallback: first div might be rank
                const num = parseInt(text);
                if (num > 0 && num < 300) rank = num;
                else name = text;
            } else if (child.tagName === 'DIV') {
                name = text;
            }
        }
        // Fallback: if still no name, try last div
        if (!name && children.length > 0) {
            name = children[children.length - 1].textContent.trim();
        }
        if (name && rank > 0) {
            result.push({href, name, rank});
        }
    }
    return result;
}
"""

# JS to extract all data from a Pokemon detail page
PARSE_DETAIL_JS = """
() => {
    const result = {moves: [], abilities: [], natures: [], items: [], evs: [],
                    teammates: [], species: '', rank: 0};

    // Species name from breadcrumb
    const breadcrumb = document.querySelectorAll('main nav ul li');
    if (breadcrumb.length > 0) {
        result.species = breadcrumb[breadcrumb.length - 1].textContent.trim();
    }

    // Rank
    const rankSpan = document.querySelector('main section:nth-child(2) span');
    if (rankSpan) {
        const m = rankSpan.textContent.match(/(\\d+)位/);
        if (m) result.rank = parseInt(m[1]);
    }

    // Forms (mega evolutions etc.)
    const formList = document.querySelector('main section:nth-child(2) section ul');
    if (formList) {
        result.forms = Array.from(formList.querySelectorAll('li a'))
            .map(a => a.textContent.trim()).filter(t => t);
    }

    // 1) Moves: from pokemon-trend__move-item elements
    const moveItems = document.querySelectorAll('.pokemon-trend__move-item');
    for (const item of moveItems) {
        const nameEl = item.querySelector('.pokemon-trend__move-name');
        const rateEl = item.querySelector('.pokemon-trend__move-rate');
        if (nameEl && rateEl) {
            const name = nameEl.textContent.trim();
            const rate = parseFloat(rateEl.textContent);
            if (name && !isNaN(rate)) result.moves.push({name, rate});
        }
    }

    // 2) Abilities, Natures, Items from x-data usagePieChart
    const xDataEls = document.querySelectorAll('[x-data]');
    for (const el of xDataEls) {
        const attr = el.getAttribute('x-data');
        if (!attr) continue;
        const match = attr.match(/window\\.usagePieChart\\((\\[.+\\])\\)/);
        if (!match) continue;
        try {
            const data = JSON.parse(match[1]);
            if (data.length === 0) continue;
            if (data[0].ability_key !== undefined) {
                result.abilities = data.map(d => ({name: d.name, rate: d.rate}));
            } else if (data[0].personality_key !== undefined) {
                result.natures = data.map(d => ({name: d.name, rate: d.rate}));
            } else if (data[0].item_key !== undefined) {
                result.items = data.map(d => ({name: d.name, rate: d.rate}));
            }
        } catch(e) {}
    }

    // 3) EV spreads from the stat section
    const h3s = document.querySelectorAll('main h3');
    for (const h3 of h3s) {
        if (h3.textContent.trim() !== '能力ポイント') continue;
        const wrapper = h3.closest('div').parentElement;
        const lis = wrapper.querySelectorAll(':scope > div > ul > li');
        for (const li of lis) {
            const innerDivs = li.querySelectorAll(':scope > div > div');
            if (innerDivs.length < 2) continue;
            const labelText = innerDivs[0].textContent.trim();
            const rateMatch = labelText.match(/([\\d.]+)%/);
            if (!rateMatch) continue;
            const rate = parseFloat(rateMatch[1]);
            const label = labelText.replace(/[\\d.]+%/, '').trim();
            // Parse stat values from spans
            const spans = innerDivs[1].querySelectorAll('span');
            const stats = {};
            // Spans come in groups: letter, number, letter, number...
            // Actually they are individual spans with content like "H", "10"
            const values = Array.from(spans).map(s => s.textContent.trim());
            for (let i = 0; i < values.length; i++) {
                const v = values[i];
                if (/^[HABCDS]$/.test(v) && i + 1 < values.length) {
                    const num = parseInt(values[i + 1]);
                    if (!isNaN(num)) stats[v] = num;
                    i++;  // skip the number
                } else if (v === '+') {
                    // skip remainder marker
                    break;
                }
            }
            if (rate > 0) result.evs.push({label, rate, stats});
        }
        break;
    }

    // 4) Teammates
    for (const h3 of h3s) {
        if (h3.textContent.trim() !== '同じチーム') continue;
        const wrapper = h3.closest('div').parentElement;
        const teamUl = wrapper.querySelector('ul');
        if (teamUl) {
            for (const li of teamUl.querySelectorAll(':scope > li')) {
                const a = li.querySelector('a:last-child');
                if (a && a.textContent.trim()) {
                    result.teammates.push(a.textContent.trim());
                }
            }
        }
        break;
    }

    return result;
}
"""


def get_cdp_endpoint() -> str:
    """DevToolsActivePort からCDPポートを取得。"""
    if DEVTOOLS_PORT_FILE.exists():
        port = DEVTOOLS_PORT_FILE.read_text().strip().split("\n")[0]
        return f"http://localhost:{port}"
    return "http://localhost:9222"


def determine_archetype(item_name: str, nature: str, top_ev: dict) -> str:
    """持ち物・性格・努力値から型名を推定。"""
    if item_name in ITEM_ARCHETYPE_MAP:
        return ITEM_ARCHETYPE_MAP[item_name]

    if "ナイト" in item_name:
        return "メガシンカ型"

    hp = top_ev.get("hp", 0)
    atk = top_ev.get("attack", 0)
    spa = top_ev.get("sp_attack", 0)
    spd = top_ev.get("speed", 0)
    dfe = top_ev.get("defense", 0)
    spdef = top_ev.get("sp_defense", 0)

    if hp >= 200 and dfe >= 200:
        return "HB物理受け型"
    if hp >= 200 and spdef >= 200:
        return "HD特殊受け型"
    if atk >= 200 and spd >= 200:
        return "AS物理アタッカー型"
    if spa >= 200 and spd >= 200:
        return "CS特殊アタッカー型"
    if atk >= 200:
        return "物理アタッカー型"
    if spa >= 200:
        return "特殊アタッカー型"

    return "汎用型"


def convert_evs(ev_stats: dict) -> dict[str, int]:
    """EV stat keys (H/A/B/C/D/S) を内部キーに変換し *8 して252表示。"""
    result = {}
    for k, v in ev_stats.items():
        mapped = EV_KEY_MAP.get(k)
        if mapped:
            result[mapped] = v * 8  # pokedb は 32 = 252 表記
    return result


def build_templates(pokemon_data: list[dict]) -> dict[str, list[dict]]:
    """収集データから型テンプレートを生成。

    各ポケモンの持ち物上位から主要な型を作成する。
    """
    templates: dict[str, list[dict]] = {}

    for poke in pokemon_data:
        species = poke["species"]
        items = poke.get("items", [])
        abilities = poke.get("abilities", [])
        natures = poke.get("natures", [])
        moves = poke.get("moves", [])
        evs = poke.get("evs", [])
        rank = poke.get("rank", 0)
        source_url = poke.get("source_url", "")
        forms = poke.get("forms", [])

        top_ability = abilities[0]["name"] if abilities else ""
        top_nature = natures[0]["name"] if natures else ""
        top_ev = convert_evs(evs[0]["stats"]) if evs else {}
        top_moves = [m["name"] for m in moves[:8]]

        has_mega = any("メガ" in f for f in forms) if forms else False

        tmpls: list[dict] = []
        # 持ち物上位5つから型を生成
        for item_info in items[:5]:
            item_name = item_info["name"]
            item_rate = item_info["rate"] / 100.0

            archetype_name = determine_archetype(
                item_name, top_nature, top_ev
            )

            tmpls.append(
                {
                    "species": species,
                    "archetype_name": archetype_name,
                    "ability": top_ability,
                    "item": item_name,
                    "nature": top_nature,
                    "evs": top_ev,
                    "moves": top_moves,
                    "usage_rate": round(item_rate, 4),
                    "tera_type": None,
                    "can_mega_evolve": has_mega,
                    "notes": f"使用率{rank}位",
                    "source_url": source_url,
                }
            )

        if not tmpls:
            tmpls.append(
                {
                    "species": species,
                    "archetype_name": "汎用型",
                    "ability": top_ability,
                    "item": "",
                    "nature": top_nature,
                    "evs": top_ev,
                    "moves": top_moves,
                    "usage_rate": 0.0,
                    "tera_type": None,
                    "can_mega_evolve": has_mega,
                    "notes": f"使用率{rank}位",
                    "source_url": source_url,
                }
            )

        templates[species] = tmpls

    return templates


async def scrape_all() -> None:
    from playwright.async_api import async_playwright

    cdp = get_cdp_endpoint()
    logger.info("CDP接続先: %s", cdp)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp)
        context = browser.contexts[0]

        # Step 1: Get Pokemon list
        page = await context.new_page()
        await page.goto(LIST_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        pokemon_links = await page.evaluate(PARSE_LIST_JS)
        await page.close()

        logger.info("ポケモン一覧: %d 匹取得", len(pokemon_links))

        # Limit to top N
        pokemon_links = [p for p in pokemon_links if p["rank"] <= TOP_N]
        pokemon_links.sort(key=lambda x: x["rank"])
        logger.info("上位 %d 匹を収集対象", len(pokemon_links))

        # Step 2: Scrape each Pokemon detail page
        all_data: list[dict] = []
        page = await context.new_page()

        for i, poke_info in enumerate(pokemon_links, 1):
            href = poke_info["href"]
            name = poke_info["name"]
            rank = poke_info["rank"]

            url = (
                f"{BASE_URL}{href}"
                if href.startswith("/")
                else href
            )
            # Ensure rule=1 and season=2 params
            if "rule=" not in url:
                url += "&rule=1" if "?" in url else "?rule=1"
            if "season=" not in url:
                url += "&season=2"

            try:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                # Click "リストを表示" and "残りを表示" buttons to expand
                await page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            const t = btn.textContent.trim();
                            if (t.includes('リストを表示') ||
                                t.includes('残りを表示')) {
                                btn.click();
                            }
                        }
                    }
                """)
                await page.wait_for_timeout(500)

                data = await page.evaluate(PARSE_DETAIL_JS)
                data["source_url"] = url
                data["rank"] = rank
                if not data.get("species"):
                    data["species"] = name

                all_data.append(data)
                logger.info(
                    "[%d/%d] %s (rank %d) → 技%d 特性%d 持ち物%d 努力値%d",
                    i,
                    len(pokemon_links),
                    name,
                    rank,
                    len(data.get("moves", [])),
                    len(data.get("abilities", [])),
                    len(data.get("items", [])),
                    len(data.get("evs", [])),
                )
            except Exception as exc:
                logger.error("[%d/%d] %s エラー: %s", i, len(pokemon_links), name, exc)

            await asyncio.sleep(2)

        await page.close()

    logger.info("合計 %d 匹のデータ収集完了", len(all_data))
    if not all_data:
        logger.error("データが取得できませんでした")
        return

    # Build templates
    templates = build_templates(all_data)

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "champs.pokedb.tokyo (バトルデータベース チャンピオンズ)",
        "filter": "ダブルバトル / シーズンM-2 / レギュレーションM-A",
        "total_pokemon_scraped": len(all_data),
        "pokemon": templates,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("=== 収集完了 ===")
    logger.info("出力: %s", OUTPUT_PATH)
    logger.info("種族数: %d", len(templates))
    logger.info(
        "テンプレート数: %d", sum(len(v) for v in templates.values())
    )

    ranking = sorted(
        all_data, key=lambda x: x.get("rank", 999)
    )
    logger.info("--- 使用率 TOP20 ---")
    for poke in ranking[:20]:
        top_item = poke["items"][0]["name"] if poke.get("items") else "-"
        top_ability = (
            poke["abilities"][0]["name"] if poke.get("abilities") else "-"
        )
        logger.info(
            "%2d. %s (特性: %s, 持ち物1位: %s, 技数: %d)",
            poke["rank"],
            poke["species"],
            top_ability,
            top_item,
            len(poke.get("moves", [])),
        )


if __name__ == "__main__":
    asyncio.run(scrape_all())

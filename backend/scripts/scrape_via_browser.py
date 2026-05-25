#!/usr/bin/env python3
"""Playwright CDP ベースのスクレイパー。

yakkun.com が直接リクエストを403で拒否するため、
Chrome の CDP エンドポイントを使用してブラウザ経由でスクレイピングする。

使い方:
  cd backend
  source .venv/bin/activate
  python scripts/scrape_via_browser.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "meta_templates.json"
CDP_ENDPOINT = "http://localhost:34931"
BASE_URL = "https://yakkun.com"
LIST_URLS = [
    "https://yakkun.com/bbs/party/list/?soft=4&rule=1",
    "https://yakkun.com/bbs/party/list/?soft=4&rule=1&start=15",
    "https://yakkun.com/bbs/party/list/?soft=4&rule=1&start=30",
]

EV_STAT_MAP = {
    "HP": "hp",
    "攻撃": "attack",
    "防御": "defense",
    "特攻": "sp_attack",
    "特防": "sp_defense",
    "素早": "speed",
    "素早さ": "speed",
}


def parse_ev_text(text: str) -> dict[str, int]:
    evs: dict[str, int] = {}
    match_252 = re.search(r"252表示[:：]\s*(.+?)(?:\)|$)", text)
    target = match_252.group(1) if match_252 else text
    for m in re.finditer(r"(HP|攻撃|防御|特攻|特防|素早さ?)\s*[:：]\s*(\d+)", target):
        mapped = EV_STAT_MAP.get(m.group(1))
        if mapped:
            evs[mapped] = int(m.group(2))
    return evs


def determine_archetype(pokemon: dict) -> str:
    item = pokemon.get("item", "")
    moves = pokemon.get("moves", [])
    nature = pokemon.get("nature", "")
    evs = pokemon.get("evs", {})

    item_map = {
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
    }
    if item in item_map:
        return item_map[item]

    hp_ev = evs.get("hp", 0)
    atk_ev = evs.get("attack", 0)
    spatk_ev = evs.get("sp_attack", 0)
    spd_ev = evs.get("speed", 0)
    def_ev = evs.get("defense", 0)
    spdef_ev = evs.get("sp_defense", 0)

    if hp_ev >= 200 and def_ev >= 200:
        return "HB物理受け型"
    if hp_ev >= 200 and spdef_ev >= 200:
        return "HD特殊受け型"
    if atk_ev >= 200 and spd_ev >= 200:
        return "AS物理アタッカー型"
    if spatk_ev >= 200 and spd_ev >= 200:
        return "CS特殊アタッカー型"
    if atk_ev >= 200:
        return "物理アタッカー型"
    if spatk_ev >= 200:
        return "特殊アタッカー型"

    support_moves = {
        "おいかぜ", "トリックルーム", "ねこだまし", "このゆびとまれ",
        "いかりのこな", "サイドチェンジ", "ワイドガード", "ファストガード",
        "てだすけ", "リフレクター", "ひかりのかべ", "でんじは",
    }
    if len(set(moves) & support_moves) >= 2:
        return "サポート型"

    return "汎用型"


PARSE_POKEMON_JS = """
() => {
    const results = [];
    const pokemonLists = document.querySelectorAll('ul.pokemon_list');
    for (const ul of pokemonLists) {
        // list_basic contains: name, item, nature, ability
        const basicLi = ul.querySelector('li.list_basic');
        if (!basicLi) continue;

        const nameSpan = basicLi.querySelector('.list_name strong');
        const species = nameSpan ? nameSpan.textContent.trim() : '';
        if (!species) continue;

        // Item: inside .list_item
        let item = '';
        const itemSpan = basicLi.querySelector('.list_item');
        if (itemSpan) {
            const itemLink = itemSpan.querySelector('a');
            item = itemLink ? itemLink.textContent.trim() : '';
        }

        // Nature: inside .list_nature
        let nature = '';
        const natureSpan = basicLi.querySelector('.list_nature');
        if (natureSpan) {
            const natureLink = natureSpan.querySelector('a');
            nature = natureLink ? natureLink.textContent.trim() : '';
        }

        // Ability: inside .list_ability
        let ability = '';
        const abilitySpan = basicLi.querySelector('.list_ability');
        if (abilitySpan) {
            const abilityLink = abilitySpan.querySelector('a');
            ability = abilityLink ? abilityLink.textContent.trim() : '';
        }

        // EVs: in li.list_ev
        let evText = '';
        const evLi = ul.querySelector('li.list_ev');
        if (evLi) evText = evLi.textContent.trim();

        // Moves: in li.list_move
        let moves = [];
        const moveLi = ul.querySelector('li.list_move');
        if (moveLi) {
            moves = Array.from(moveLi.querySelectorAll('a'))
                .map(a => a.textContent.trim());
        }

        if (species && (moves.length > 0 || ability || item)) {
            results.push({species, ability, item, nature, evText, moves,
                canMegaEvolve: species.includes('メガ')});
        }
    }
    return results;
}
"""


async def scrape_all() -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_ENDPOINT)
        context = browser.contexts[0]

        # Collect party URLs
        all_party_urls: list[str] = []
        for list_url in LIST_URLS:
            page = await context.new_page()
            await page.goto(list_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            urls = await page.evaluate(
                "Array.from(document.querySelectorAll(\"a[href^='/bbs/party/n']\"))"
                ".map(a => a.href)"
            )
            all_party_urls.extend(urls)
            await page.close()
            logger.info("一覧ページ: %s → %d パーティ", list_url, len(urls))
            await asyncio.sleep(3)

        # Deduplicate
        all_party_urls = list(dict.fromkeys(all_party_urls))
        logger.info("合計 %d パーティURL (重複除去済み)", len(all_party_urls))

        # Parse each party page
        all_pokemon: list[dict] = []
        page = await context.new_page()
        for i, url in enumerate(all_party_urls, 1):
            try:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)
                raw_pokemon = await page.evaluate(PARSE_POKEMON_JS)
                for raw in raw_pokemon:
                    evs = parse_ev_text(raw.get("evText", ""))
                    all_pokemon.append({
                        "species": raw["species"],
                        "ability": raw["ability"],
                        "item": raw["item"],
                        "nature": raw["nature"],
                        "evs": evs,
                        "moves": raw["moves"],
                        "can_mega_evolve": raw.get("canMegaEvolve", False),
                        "source_url": url,
                    })
                logger.info(
                    "[%d/%d] %s → %d 体", i, len(all_party_urls),
                    url.split("/")[-1], len(raw_pokemon),
                )
            except Exception as exc:
                logger.error("[%d/%d] エラー: %s - %s", i, len(all_party_urls), url, exc)
            await asyncio.sleep(3)

        await page.close()

    logger.info("合計 %d 体のポケモンデータ収集", len(all_pokemon))
    if not all_pokemon:
        logger.error("データが取得できませんでした")
        return

    # Aggregate
    total_parties = max(len(set(p["source_url"] for p in all_pokemon)), 1)
    species_data: dict[str, list[dict]] = defaultdict(list)
    for poke in all_pokemon:
        species_data[poke["species"]].append(poke)

    templates: dict[str, list[dict]] = {}
    for species, entries in species_data.items():
        item_groups: dict[str, list[dict]] = defaultdict(list)
        for entry in entries:
            item_groups[entry.get("item") or "なし"].append(entry)

        tmpls: list[dict] = []
        for item_name, group in item_groups.items():
            rep = group[0]
            archetype_name = determine_archetype(rep)
            all_moves: list[str] = []
            for g in group:
                for m in g.get("moves", []):
                    if m not in all_moves:
                        all_moves.append(m)

            ability_counts: dict[str, int] = defaultdict(int)
            for g in group:
                if g.get("ability"):
                    ability_counts[g["ability"]] += 1
            top_ability = (
                max(ability_counts, key=ability_counts.get)
                if ability_counts else rep.get("ability", "")
            )

            nature_counts: dict[str, int] = defaultdict(int)
            for g in group:
                if g.get("nature"):
                    nature_counts[g["nature"]] += 1
            top_nature = (
                max(nature_counts, key=nature_counts.get)
                if nature_counts else rep.get("nature", "")
            )

            ev_list = [g["evs"] for g in group if g.get("evs")]
            top_evs = ev_list[0] if ev_list else {}

            tmpls.append({
                "species": species,
                "archetype_name": archetype_name,
                "ability": top_ability,
                "item": item_name if item_name != "なし" else "",
                "nature": top_nature,
                "evs": top_evs,
                "moves": all_moves[:8],
                "usage_rate": round(len(group) / total_parties, 4),
                "tera_type": None,
                "can_mega_evolve": rep.get("can_mega_evolve", False),
                "notes": "",
                "source_url": rep.get("source_url", ""),
            })
        tmpls.sort(key=lambda t: t["usage_rate"], reverse=True)
        templates[species] = tmpls

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "yakkun.com (ポケモン徹底攻略)",
        "filter": "チャンピオンズ / ダブルバトル",
        "total_parties_scraped": len(all_party_urls),
        "total_pokemon_entries": len(all_pokemon),
        "pokemon": templates,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("=== 収集完了 ===")
    logger.info("出力: %s", OUTPUT_PATH)
    logger.info("種族数: %d", len(templates))
    logger.info("テンプレート数: %d", sum(len(v) for v in templates.values()))

    ranking = sorted(
        templates.items(),
        key=lambda x: max((t["usage_rate"] for t in x[1]), default=0),
        reverse=True,
    )
    logger.info("--- 使用率 TOP10 ---")
    for i, (species, tmpls) in enumerate(ranking[:10], 1):
        rate = max(t["usage_rate"] for t in tmpls)
        logger.info("%2d. %s (使用率: %.1f%%, 型数: %d)", i, species, rate * 100, len(tmpls))


if __name__ == "__main__":
    asyncio.run(scrape_all())

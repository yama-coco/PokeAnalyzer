#!/usr/bin/env python3
"""ポケモン徹底攻略 (yakkun.com) からダブルバトル構築データを収集するスクレイパー。

チャンピオンズのダブルバトル構築を対象に、各ポケモンの型情報
（特性・持ち物・性格・努力値・技構成）を取得し、
data/meta_templates.json に保存する。

使い方:
  cd backend
  source .venv/bin/activate
  python scripts/scrape_meta_data.py [--pages N] [--delay SECONDS]

注意:
  - robots.txt を確認し、許可されたページのみアクセスすること
  - リクエスト間隔を3秒以上空けること
  - 取得データは個人利用の範囲に留めること
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://yakkun.com"
DOUBLE_CHAMPIONS_LIST_URL = (
    "https://yakkun.com/bbs/party/list/?rule=1&soft=4"
)
DEFAULT_DELAY = 3.0
DEFAULT_PAGES = 5
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "meta_templates.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

EV_STAT_MAP = {
    "HP": "hp",
    "攻撃": "attack",
    "防御": "defense",
    "特攻": "sp_attack",
    "特防": "sp_defense",
    "素早": "speed",
    "素早さ": "speed",
}

NATURE_MAP: dict[str, dict[str, str]] = {
    "いじっぱり": {"up": "attack", "down": "sp_attack"},
    "ようき": {"up": "speed", "down": "sp_attack"},
    "ひかえめ": {"up": "sp_attack", "down": "attack"},
    "おくびょう": {"up": "speed", "down": "attack"},
    "わんぱく": {"up": "defense", "down": "sp_attack"},
    "しんちょう": {"up": "sp_defense", "down": "sp_attack"},
    "おだやか": {"up": "sp_defense", "down": "attack"},
    "ずぶとい": {"up": "defense", "down": "attack"},
    "のんき": {"up": "defense", "down": "speed"},
    "なまいき": {"up": "sp_defense", "down": "speed"},
    "れいせい": {"up": "sp_attack", "down": "speed"},
    "ゆうかん": {"up": "attack", "down": "speed"},
    "さみしがり": {"up": "attack", "down": "defense"},
    "おっとり": {"up": "sp_attack", "down": "defense"},
    "やんちゃ": {"up": "attack", "down": "sp_defense"},
    "うっかりや": {"up": "sp_attack", "down": "sp_defense"},
    "むじゃき": {"up": "speed", "down": "sp_defense"},
    "せっかち": {"up": "speed", "down": "defense"},
    "まじめ": {},
    "てれや": {},
    "がんばりや": {},
    "すなお": {},
    "きまぐれ": {},
}

MEGA_SPECIES_NAMES = {
    "メガリザードンX",
    "メガリザードンY",
    "メガフシギバナ",
    "メガカメックス",
    "メガゲンガー",
    "メガガルーラ",
    "メガボーマンダ",
    "メガルカリオ",
    "メガサーナイト",
    "メガハッサム",
    "メガクチート",
    "メガミミロップ",
    "メガプテラ",
    "メガスターミー",
    "メガチルタリス",
    "メガデンリュウ",
    "メガバクーダ",
    "メガヤドラン",
    "メガピジョット",
    "メガヘラクロス",
    "メガバシャーモ",
    "メガジュカイン",
    "メガラグラージ",
    "メガエルレイド",
    "メガアブソル",
    "メガユキノオー",
    "メガフラエッテ",
    "メガカイロス",
    "メガラティオス",
    "メガラティアス",
    "メガディアンシー",
    "メガタブンネ",
}


def fetch_page(url: str, delay: float = DEFAULT_DELAY) -> BeautifulSoup | None:
    """ページを取得して BeautifulSoup オブジェクトを返す。"""
    try:
        logger.info("Fetching: %s", url)
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.encoding = resp.apparent_encoding
        resp.raise_for_status()
        time.sleep(delay)
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        logger.error("リクエストエラー: %s - %s", url, exc)
        return None


def get_party_links(list_url: str, max_pages: int, delay: float) -> list[str]:
    """構築一覧ページからパーティ詳細ページの URL を収集する。"""
    links: list[str] = []
    current_url = list_url

    for page_num in range(max_pages):
        soup = fetch_page(current_url, delay)
        if soup is None:
            break

        for a_tag in soup.select("a[href^='/bbs/party/n']"):
            href = a_tag.get("href", "")
            if href and href not in links:
                full_url = urljoin(BASE_URL, href)
                if full_url not in links:
                    links.append(full_url)

        # 次のページリンクを探す
        next_link = None
        for a_tag in soup.select("a"):
            if a_tag.get_text(strip=True) == "次へ":
                next_link = urljoin(BASE_URL, a_tag["href"])
                break

        if next_link is None:
            logger.info("最終ページに到達 (ページ %d)", page_num + 1)
            break
        current_url = next_link
        logger.info("ページ %d 完了: 累計 %d パーティ", page_num + 1, len(links))

    logger.info("合計 %d パーティURL 収集", len(links))
    return links


def parse_ev_text(text: str) -> dict[str, int]:
    """努力値テキストを解析する。

    形式例:
      "HP:2 / 特攻:32 / 素早:32(252表示: HP:12 / 特攻:252 / 素早:252)"
      "攻撃:32 / 防御:2 / 素早:32"
    """
    evs: dict[str, int] = {}

    # "252表示" がある場合はその部分を使用
    match_252 = re.search(r"252表示[:：]\s*(.+?)(?:\)|$)", text)
    target_text = match_252.group(1) if match_252 else text

    pattern = re.compile(r"(HP|攻撃|防御|特攻|特防|素早さ?)\s*[:：]\s*(\d+)")
    for m in pattern.finditer(target_text):
        stat_name = m.group(1)
        value = int(m.group(2))
        mapped = EV_STAT_MAP.get(stat_name)
        if mapped:
            evs[mapped] = value

    return evs


def parse_party_page(soup: BeautifulSoup, url: str) -> list[dict]:
    """パーティ詳細ページから個々のポケモン情報を抽出する。"""
    pokemon_list: list[dict] = []

    # "使用ポケモン" セクション以下の <ul> を取得
    pokemon_sections = soup.select("main > ul")

    for section in pokemon_sections:
        items = section.find_all("li")
        if len(items) < 4:
            continue

        # ポケモン名・持ち物・性格・特性
        info_li = items[1] if len(items) > 1 else None
        if info_li is None:
            continue

        # 種族名
        name_tag = info_li.find("strong")
        if name_tag is None:
            continue
        species = name_tag.get_text(strip=True)
        if not species:
            continue

        # テキスト全体から情報を抽出
        info_text = info_li.get_text(strip=True)

        # 持ち物: "@持ち物名" の形式
        item = ""
        item_tag = info_li.find_all("a")
        for a in item_tag:
            href = a.get("href", "")
            if "item_s=" in href or "theory/search" in href:
                item = a.get_text(strip=True)
                break

        # 性格: 括弧内
        nature = ""
        nature_match = re.search(r"\(([ぁ-ん]+)\)", info_text)
        if nature_match:
            nature = nature_match.group(1)

        # 特性: 最後のリンク (性格リンクの後)
        ability = ""
        ability_links = [
            a
            for a in info_li.find_all("a")
            if "tokusei=" in a.get("href", "")
        ]
        if ability_links:
            ability = ability_links[0].get_text(strip=True)

        # 努力値
        evs: dict[str, int] = {}
        ev_li = items[2] if len(items) > 2 else None
        if ev_li:
            ev_text = ev_li.get_text(strip=True)
            if "HP" in ev_text or "攻撃" in ev_text or "素早" in ev_text:
                evs = parse_ev_text(ev_text)

        # 技
        moves: list[str] = []
        moves_li = items[4] if len(items) > 4 else (items[3] if len(items) > 3 else None)
        # 技は move= を含むリンク
        for li in items:
            move_links = [a for a in li.find_all("a") if "move=" in a.get("href", "")]
            if move_links:
                moves = [a.get_text(strip=True) for a in move_links]
                break

        # メガシンカ判定
        can_mega_evolve = any(mega in species for mega in ("メガ",))

        if species and (moves or ability or item):
            pokemon_list.append(
                {
                    "species": species,
                    "ability": ability,
                    "item": item,
                    "nature": nature,
                    "evs": evs,
                    "moves": moves,
                    "can_mega_evolve": can_mega_evolve,
                    "source_url": url,
                }
            )

    return pokemon_list


def determine_archetype_name(pokemon: dict) -> str:
    """ポケモンの型を持ち物・技・特性から推定する。"""
    item = pokemon.get("item", "")
    ability = pokemon.get("ability", "")
    moves = pokemon.get("moves", [])
    nature = pokemon.get("nature", "")
    evs = pokemon.get("evs", {})

    # 持ち物ベースの型名
    item_archetypes = {
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
        "ぼうじんゴーグル": "ゴーグル型",
    }
    if item in item_archetypes:
        return item_archetypes[item]

    # 性格・努力値ベース
    if nature in NATURE_MAP:
        nat_info = NATURE_MAP[nature]
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

    # サポート判定
    support_moves = {"おいかぜ", "トリックルーム", "ねこだまし", "このゆびとまれ", "いかりのこな",
                     "サイドチェンジ", "ワイドガード", "ファストガード", "てだすけ", "リフレクター",
                     "ひかりのかべ", "でんじは"}
    if len(set(moves) & support_moves) >= 2:
        return "サポート型"

    return "汎用型"


def aggregate_templates(
    all_pokemon: list[dict],
) -> dict[str, list[dict]]:
    """収集した全ポケモンデータを種族ごとに集約し、テンプレートを生成する。"""
    species_data: dict[str, list[dict]] = defaultdict(list)
    for poke in all_pokemon:
        species_data[poke["species"]].append(poke)

    total_parties = max(
        len(set(p["source_url"] for p in all_pokemon)), 1
    )

    result: dict[str, list[dict]] = {}

    for species, entries in species_data.items():
        usage_rate = round(len(entries) / total_parties, 4)

        # 持ち物ごとにグループ化して型を分ける
        item_groups: dict[str, list[dict]] = defaultdict(list)
        for entry in entries:
            item_key = entry.get("item", "") or "なし"
            item_groups[item_key].append(entry)

        templates: list[dict] = []
        for item_name, group in item_groups.items():
            representative = group[0]
            archetype_name = determine_archetype_name(representative)

            # 技候補を集約 (全出現技を集める)
            all_moves: list[str] = []
            for g in group:
                for m in g.get("moves", []):
                    if m not in all_moves:
                        all_moves.append(m)

            # 最も一般的な特性
            ability_counts: dict[str, int] = defaultdict(int)
            for g in group:
                if g.get("ability"):
                    ability_counts[g["ability"]] += 1
            top_ability = (
                max(ability_counts, key=ability_counts.get)
                if ability_counts
                else representative.get("ability", "")
            )

            # 最も一般的な性格
            nature_counts: dict[str, int] = defaultdict(int)
            for g in group:
                if g.get("nature"):
                    nature_counts[g["nature"]] += 1
            top_nature = (
                max(nature_counts, key=nature_counts.get)
                if nature_counts
                else representative.get("nature", "")
            )

            # 最も一般的な努力値
            ev_list = [g["evs"] for g in group if g.get("evs")]
            top_evs = ev_list[0] if ev_list else {}

            item_usage = round(len(group) / total_parties, 4)

            templates.append(
                {
                    "species": species,
                    "archetype_name": archetype_name,
                    "ability": top_ability,
                    "item": item_name if item_name != "なし" else "",
                    "nature": top_nature,
                    "evs": top_evs,
                    "moves": all_moves[:8],
                    "usage_rate": item_usage,
                    "tera_type": None,
                    "can_mega_evolve": representative.get("can_mega_evolve", False),
                    "notes": "",
                    "source_url": representative.get("source_url", ""),
                }
            )

        templates.sort(key=lambda t: t["usage_rate"], reverse=True)
        result[species] = templates

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ポケモン徹底攻略からダブルバトル構築データを収集"
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_PAGES,
        help=f"取得するページ数 (デフォルト: {DEFAULT_PAGES})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"リクエスト間隔 (秒, デフォルト: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(OUTPUT_PATH),
        help=f"出力ファイルパス (デフォルト: {OUTPUT_PATH})",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("=== ポケモン徹底攻略 ダブルバトル構築データ収集 ===")
    logger.info("対象: チャンピオンズ ダブルバトル")
    logger.info("ページ数: %d, リクエスト間隔: %.1f秒", args.pages, args.delay)

    # 1. 構築一覧からパーティURLを収集
    party_urls = get_party_links(DOUBLE_CHAMPIONS_LIST_URL, args.pages, args.delay)
    if not party_urls:
        logger.error("パーティURLが取得できませんでした")
        return

    # 2. 各パーティページからポケモン情報を抽出
    all_pokemon: list[dict] = []
    for i, url in enumerate(party_urls, 1):
        soup = fetch_page(url, args.delay)
        if soup is None:
            continue
        pokemon = parse_party_page(soup, url)
        all_pokemon.extend(pokemon)
        logger.info(
            "[%d/%d] %s → %d 体取得",
            i,
            len(party_urls),
            url.split("/")[-1],
            len(pokemon),
        )

    logger.info("合計 %d 体のポケモンデータ収集", len(all_pokemon))

    if not all_pokemon:
        logger.error("ポケモンデータが取得できませんでした")
        return

    # 3. テンプレートに集約
    templates = aggregate_templates(all_pokemon)

    # 4. JSON 保存
    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "yakkun.com (ポケモン徹底攻略)",
        "filter": "チャンピオンズ / ダブルバトル",
        "total_parties_scraped": len(party_urls),
        "total_pokemon_entries": len(all_pokemon),
        "pokemon": templates,
    }

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("=== 収集完了 ===")
    logger.info("出力: %s", output_path)
    logger.info("種族数: %d", len(templates))
    logger.info(
        "テンプレート数: %d",
        sum(len(v) for v in templates.values()),
    )

    # 上位10種族を表示
    ranking = sorted(
        templates.items(),
        key=lambda x: max((t["usage_rate"] for t in x[1]), default=0),
        reverse=True,
    )
    logger.info("--- 使用率 TOP10 ---")
    for i, (species, tmpls) in enumerate(ranking[:10], 1):
        rate = max(t["usage_rate"] for t in tmpls)
        logger.info(
            "%2d. %s (使用率: %.1f%%, 型数: %d)",
            i,
            species,
            rate * 100,
            len(tmpls),
        )


if __name__ == "__main__":
    main()

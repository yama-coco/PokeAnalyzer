"""ポケモンアイコン抽出スクリプト

ポケモンチャンピオンズの公式サイトのスプライトシートから
個別のポケモンアイコン画像を切り出してテンプレートとして保存する。

Usage:
    python scripts/extract_pokemon_icons.py [--sprite-url URL] [--output-dir DIR]

Source:
    https://web-view.app.pokemonchampions.jp/battle/pages/resources/sprite_poke.png
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

import cv2
import numpy as np

DEFAULT_SPRITE_URL = (
    "https://web-view.app.pokemonchampions.jp/battle/pages/resources/sprite_poke.png"
)
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "templates" / "pokemon"
GRID_SIZE = 18

# ポケモン名とスプライト位置のマッピング
# (sprite_class, name, bg_position_x%, bg_position_y%)
# このデータはHTMLページから抽出したもの
POKEMON_SPRITE_DATA: list[tuple[str, str, float, float]] = []


def load_sprite_data_from_tsv(tsv_path: Path) -> list[tuple[str, str, float, float]]:
    """TSVファイルからスプライトデータを読み込む。"""
    data = []
    with open(tsv_path) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 3:
                continue
            cls_name, name, bg_pos = parts
            pos_parts = bg_pos.split()
            if len(pos_parts) != 2:
                continue
            x_pct = float(pos_parts[0].replace("%", ""))
            y_pct = float(pos_parts[1].replace("%", ""))
            data.append((cls_name, name, x_pct, y_pct))
    return data


def pct_to_index(pct: float) -> int:
    return round(pct * (GRID_SIZE - 1) / 100)


def sanitize_filename(name: str) -> str:
    name = re.sub(r"^No\.\d+\s*", "", name)
    name = name.replace(" ", "_").replace("(", "").replace(")", "")
    name = name.replace("・", "_").replace("　", "_")
    return name


def download_sprite(url: str) -> np.ndarray:
    """スプライトシートをダウンロードしてnumpy配列として返す。"""
    print(f"Downloading sprite sheet from: {url}")
    response = urllib.request.urlopen(url)
    data = response.read()
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError("Failed to decode sprite image")
    print(f"  Sprite size: {img.shape[1]}x{img.shape[0]}")
    return img


def extract_icons(
    sprite: np.ndarray,
    sprite_data: list[tuple[str, str, float, float]],
    output_dir: Path,
) -> list[dict]:
    """スプライトシートから個別アイコンを切り出す。"""
    h, w = sprite.shape[:2]
    cell_w = w / GRID_SIZE
    cell_h = h / GRID_SIZE
    output_dir.mkdir(parents=True, exist_ok=True)

    mapping = []
    for cls_name, pokemon_name, x_pct, y_pct in sprite_data:
        col = pct_to_index(x_pct)
        row = pct_to_index(y_pct)

        x1 = int(round(col * cell_w))
        y1 = int(round(row * cell_h))
        x2 = int(round((col + 1) * cell_w))
        y2 = int(round((row + 1) * cell_h))

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        cell = sprite[y1:y2, x1:x2]
        filename = sanitize_filename(pokemon_name) + ".png"
        cv2.imwrite(str(output_dir / filename), cell)

        dex_match = re.match(r"No\.(\d+)", pokemon_name)
        dex_num = dex_match.group(1) if dex_match else ""
        mapping.append(
            {
                "filename": filename,
                "name": pokemon_name,
                "dex": dex_num,
                "sprite_class": cls_name,
            }
        )

    # Save index
    index_path = output_dir / "_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    return mapping


def main():
    parser = argparse.ArgumentParser(description="Extract Pokemon icons from sprite sheet")
    parser.add_argument("--sprite-url", default=DEFAULT_SPRITE_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tsv", type=Path, help="Path to sprite data TSV")
    args = parser.parse_args()

    if args.tsv and args.tsv.exists():
        sprite_data = load_sprite_data_from_tsv(args.tsv)
    else:
        tsv_path = args.output_dir / "_mapping.tsv"
        if tsv_path.exists():
            sprite_data = load_sprite_data_from_tsv(tsv_path)
        else:
            print("No sprite data TSV found. Please provide --tsv path.")
            return

    sprite = download_sprite(args.sprite_url)
    mapping = extract_icons(sprite, sprite_data, args.output_dir)
    print(f"Extracted {len(mapping)} Pokemon icons to {args.output_dir}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate lightweight original SVG cards for meme entries.

These cards are not video screenshots. They are repository-owned text cards
that make image-based skill output possible while avoiding bulk rehosting of
Bilibili frames.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CARD_DIR = ROOT / "assets" / "cards"


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def wrap_text(text: str, max_chars: int) -> list[str]:
    text = re.sub(r"\s+", "", text)
    if not text:
        return []
    return [text[index:index + max_chars] for index in range(0, len(text), max_chars)]


def svg_for(item: dict[str, Any]) -> str:
    title = html.escape(item.get("title", "新三国梗"))
    summary = item.get("summary", "")
    tags = " / ".join((item.get("tags") or [])[:4])
    badge = html.escape("新三国 · 折棒梗库")

    title_lines = wrap_text(item.get("title", ""), 9)[:3]
    summary_lines = wrap_text(summary, 20)[:4]
    tag_line = html.escape(tags)

    y = 122
    title_tspans = []
    for line in title_lines:
        title_tspans.append(f'<tspan x="64" y="{y}">{html.escape(line)}</tspan>')
        y += 76

    y += 24
    summary_tspans = []
    for line in summary_lines:
        summary_tspans.append(f'<tspan x="64" y="{y}">{html.escape(line)}</tspan>')
        y += 36

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#2b2118"/>
      <stop offset="0.52" stop-color="#7b1f18"/>
      <stop offset="1" stop-color="#d5a44a"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#1b0e08" flood-opacity="0.45"/>
    </filter>
  </defs>
  <rect width="960" height="540" fill="url(#bg)"/>
  <path d="M0 410 C190 350 300 450 480 390 C640 338 760 360 960 290 L960 540 L0 540 Z" fill="#111111" opacity="0.18"/>
  <rect x="42" y="42" width="876" height="456" rx="18" fill="#fff8e8" opacity="0.94" filter="url(#shadow)"/>
  <rect x="64" y="62" width="224" height="34" rx="17" fill="#7b1f18"/>
  <text x="82" y="85" fill="#fff8e8" font-size="20" font-family="Noto Sans CJK SC, Microsoft YaHei, sans-serif">{badge}</text>
  <text fill="#21140e" font-size="62" font-weight="800" font-family="Noto Serif CJK SC, SimSun, serif">
    {''.join(title_tspans)}
  </text>
  <text fill="#5b4539" font-size="26" font-family="Noto Sans CJK SC, Microsoft YaHei, sans-serif">
    {''.join(summary_tspans)}
  </text>
  <text x="64" y="475" fill="#7b1f18" font-size="22" font-family="Noto Sans CJK SC, Microsoft YaHei, sans-serif">{tag_line}</text>
  <text x="896" y="475" text-anchor="end" fill="#7b1f18" font-size="20" font-family="Noto Sans CJK SC, Microsoft YaHei, sans-serif">CheeseKirby/memes</text>
  <title>{title}</title>
</svg>
'''


def generate(index_path: Path, output_dir: Path) -> int:
    index = load_json(index_path, {"items": []})
    expected_paths: set[Path] = set()
    count = 0
    for item in index.get("items", []):
        if item.get("item_type") != "meme":
            continue
        card_path = output_dir / f"{item['id']}.svg"
        expected_paths.add(card_path)
        write_text(card_path, svg_for(item))
        count += 1

    for stale_path in output_dir.glob("*.svg"):
        if stale_path not in expected_paths:
            stale_path.unlink()

    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SVG meme cards.")
    parser.add_argument("--index", default=str(ROOT / "index.json"))
    parser.add_argument("--output-dir", default=str(CARD_DIR))
    args = parser.parse_args()

    count = generate(Path(args.index), Path(args.output_dir))
    print(f"Generated {count} meme cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

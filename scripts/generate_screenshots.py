#!/usr/bin/env python3
"""Generate reviewed screenshot assets.

The script reads data/screenshot-decisions.json. Reviewed entries can use a
Bilibili cover image, a specific videoshot storyboard cell, or be withheld when
no accurate image has been found yet. This avoids publishing visually busy but
semantically wrong frames.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageOps, ImageStat


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "assets" / "screenshots"
DECISIONS_PATH = ROOT / "data" / "screenshot-decisions.json"
SELECTIONS_PATH = ROOT / "data" / "screenshot-selections.json"
DEFAULT_USER_AGENT = "Mozilla/5.0 CheeseKirby-xin-sanguo-index/0.1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def fetch_image(url: str, referer: str, user_agent: str) -> Image.Image:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": referer,
            "User-Agent": user_agent,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    return Image.open(io.BytesIO(payload)).convert("RGB")


def load_episode_map(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path, {"episodes": []})
    return {episode["bvid"]: episode for episode in payload.get("episodes", []) if episode.get("bvid")}


def normalize_image(image: Image.Image, size: tuple[int, int] = (960, 540)) -> Image.Image:
    image = ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    return image


def entropy(gray: Image.Image) -> float:
    histogram = gray.histogram()
    total = sum(histogram) or 1
    result = 0.0
    for count in histogram:
        if not count:
            continue
        probability = count / total
        result -= probability * math.log2(probability)
    return result


def score_crop(crop: Image.Image) -> float:
    small = ImageOps.contain(crop.convert("RGB"), (160, 90))
    gray = small.convert("L")
    stat = ImageStat.Stat(gray)
    brightness = stat.mean[0]
    contrast = stat.stddev[0]
    if brightness < 8 or brightness > 247 or contrast < 7:
        return -1_000_000.0

    edge_mean = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
    color_std = sum(ImageStat.Stat(small).stddev)
    width, height = gray.size
    center = gray.crop((width // 8, height // 8, width * 7 // 8, height * 7 // 8))
    center_contrast = ImageStat.Stat(center).stddev[0]

    score = 0.0
    score += contrast * 1.35
    score += edge_mean * 2.7
    score += color_std * 0.35
    score += center_contrast * 0.8
    score += entropy(gray) * 4.0
    score -= abs(brightness - 112) * 0.08
    return score


def valid_grid(sprite: Image.Image, grid: dict[str, Any]) -> tuple[int, int, int, int]:
    width, height = sprite.size
    columns = int(grid.get("columns") or 10)
    rows = int(grid.get("rows") or 10)
    cell_width = int(grid.get("cell_width") or (width // columns))
    cell_height = int(grid.get("cell_height") or (height // rows))

    columns = max(1, min(columns, width // max(1, cell_width)))
    rows = max(1, min(rows, height // max(1, cell_height)))
    return columns, rows, cell_width, cell_height


def crop_cell(sprite: Image.Image, grid: dict[str, Any], row: int, column: int) -> Image.Image:
    _, _, cell_width, cell_height = valid_grid(sprite, grid)
    left = column * cell_width
    top = row * cell_height
    return sprite.crop((left, top, left + cell_width, top + cell_height))


def candidate_cells(
    item: dict[str, Any],
    sprite_images: list[tuple[str, Image.Image]],
) -> list[dict[str, Any]]:
    storyboard = item.get("storyboard") or {}
    grid = storyboard.get("grid") or {}
    scored: list[dict[str, Any]] = []
    for sprite_index, (sprite_url, sprite) in enumerate(sprite_images):
        columns, rows, cell_width, cell_height = valid_grid(sprite, grid)
        for row in range(rows):
            for column in range(columns):
                crop = sprite.crop(
                    (
                        column * cell_width,
                        row * cell_height,
                        column * cell_width + cell_width,
                        row * cell_height + cell_height,
                    )
                )
                scored.append(
                    {
                        "score": score_crop(crop),
                        "sprite_index": sprite_index,
                        "sprite_url": sprite_url,
                        "row": row,
                        "column": column,
                        "cell_index": row * columns + column,
                    }
                )
    return sorted(scored, key=lambda value: value["score"], reverse=True)


def choose_cell(item: dict[str, Any], scored: list[dict[str, Any]], used_by_bvid: dict[str, set[tuple[int, int, int]]]) -> dict[str, Any]:
    bvid = item.get("bvid") or item.get("primary_bvid") or ""
    used = used_by_bvid.setdefault(bvid, set())
    top = scored[: max(1, min(24, len(scored)))]
    if not top:
        raise ValueError("no cells available")

    for candidate in top:
        key = (candidate["sprite_index"], candidate["row"], candidate["column"])
        if key not in used:
            used.add(key)
            return candidate

    offset = int(hashlib.sha1(str(item.get("item_id", "")).encode("utf-8")).hexdigest(), 16) % len(top)
    candidate = top[offset]
    used.add((candidate["sprite_index"], candidate["row"], candidate["column"]))
    return candidate


def build_screenshots(
    candidates_path: Path,
    decisions_path: Path,
    series_path: Path,
    output_dir: Path,
    selections_path: Path,
    user_agent: str,
    overwrite: bool,
    auto: bool,
) -> int:
    payload = load_json(candidates_path, {"items": []})
    decisions_payload = load_json(decisions_path, {"items": []})
    decisions = {item["item_id"]: item for item in decisions_payload.get("items", []) if item.get("item_id")}
    episodes_by_bvid = load_episode_map(series_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    used_by_bvid: dict[str, set[tuple[int, int, int]]] = {}
    selections: list[dict[str, Any]] = []
    count = 0
    withheld_count = 0

    for item in payload.get("items", []):
        item_id = item.get("item_id")
        repository_path = item.get("repository_image_path") or f"assets/screenshots/{item_id}.jpg"
        output_path = ROOT / repository_path
        if not item_id:
            continue
        decision = decisions.get(item_id, {"action": "auto" if auto else "withhold", "reason": "未人工复核"})
        action = decision.get("action", "withhold")
        if action == "withhold":
            if output_path.exists():
                output_path.unlink()
            withheld_count += 1
            selections.append(
                {
                    "item_id": item_id,
                    "title": item.get("title"),
                    "bvid": item.get("bvid"),
                    "repository_image_path": repository_path,
                    "action": "withhold",
                    "reason": decision.get("reason", "未找到足够准确的截图"),
                }
            )
            continue
        if output_path.exists() and not overwrite:
            count += 1
            selections.append(
                {
                    "item_id": item_id,
                    "title": item.get("title"),
                    "bvid": item.get("bvid"),
                    "repository_image_path": repository_path,
                    "action": action,
                    "reason": decision.get("reason", "已存在截图"),
                }
            )
            continue

        storyboard = item.get("storyboard") or {}
        referer = item.get("source_url") or f"https://www.bilibili.com/video/{item.get('bvid', '')}"
        selected: dict[str, Any]
        try:
            if action == "cover":
                episode = episodes_by_bvid.get(item.get("bvid", ""))
                cover_url = decision.get("url") or (episode or {}).get("cover_url")
                if not cover_url:
                    raise ValueError("no cover URL")
                crop = normalize_image(fetch_image(cover_url, referer, user_agent))
                selected = {
                    "action": "cover",
                    "cover_url": cover_url,
                }
            elif action == "storyboard":
                image_urls = storyboard.get("image_urls") or []
                sprite_index = int(decision.get("sprite_index", 0))
                row = int(decision["row"])
                column = int(decision["column"])
                if sprite_index < 0 or sprite_index >= len(image_urls):
                    raise ValueError("storyboard sprite_index out of range")
                sprite_url = image_urls[sprite_index]
                sprite = fetch_image(sprite_url, referer, user_agent)
                crop = normalize_image(crop_cell(sprite, storyboard.get("grid") or {}, row, column))
                selected = {
                    "action": "storyboard",
                    "sprite_url": sprite_url,
                    "sprite_index": sprite_index,
                    "row": row,
                    "column": column,
                }
            elif action == "auto":
                image_urls = storyboard.get("image_urls") or []
                if not image_urls:
                    raise ValueError("no storyboard images")
                sprite_images: list[tuple[str, Image.Image]] = []
                for image_url in image_urls:
                    sprite_images.append((image_url, fetch_image(image_url, referer, user_agent)))
                scored = candidate_cells(item, sprite_images)
                selected = choose_cell(item, scored, used_by_bvid)
                sprite = sprite_images[selected["sprite_index"]][1]
                crop = normalize_image(crop_cell(sprite, storyboard.get("grid") or {}, selected["row"], selected["column"]))
            else:
                raise ValueError(f"unknown action: {action}")
        except Exception as exc:
            print(f"Skipped {item_id}: {exc}", file=sys.stderr)
            if output_path.exists():
                output_path.unlink()
            withheld_count += 1
            selections.append(
                {
                    "item_id": item_id,
                    "title": item.get("title"),
                    "bvid": item.get("bvid"),
                    "repository_image_path": repository_path,
                    "action": "withhold",
                    "reason": f"生成失败：{exc}",
                }
            )
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(output_path, "JPEG", quality=88, optimize=True)
        count += 1

        selections.append(
            {
                "item_id": item_id,
                "title": item.get("title"),
                "bvid": item.get("bvid"),
                "repository_image_path": repository_path,
                "reason": decision.get("reason", ""),
                **selected,
            }
        )

    write_json(
        selections_path,
        {
            "schema": "https://github.com/CheeseKirby/memes/schema/screenshot-selections/v1",
            "updated_at": utc_now(),
            "item_count": count,
            "withheld_count": withheld_count,
            "items": selections,
        },
    )
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate reviewed screenshot assets.")
    parser.add_argument("--candidates", default=str(ROOT / "data" / "screenshot-candidates.json"))
    parser.add_argument("--decisions", default=str(DECISIONS_PATH))
    parser.add_argument("--series", default=str(ROOT / "data" / "bilibili-series.json"))
    parser.add_argument("--output-dir", default=str(SCREENSHOT_DIR))
    parser.add_argument("--selections", default=str(SELECTIONS_PATH))
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--auto", action="store_true", help="Use the old automatic storyboard heuristic for undecided items.")
    args = parser.parse_args()

    count = build_screenshots(
        candidates_path=Path(args.candidates),
        decisions_path=Path(args.decisions),
        series_path=Path(args.series),
        output_dir=Path(args.output_dir),
        selections_path=Path(args.selections),
        user_agent=args.user_agent,
        overwrite=args.overwrite,
        auto=args.auto,
    )
    print(f"Generated {count} screenshot assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

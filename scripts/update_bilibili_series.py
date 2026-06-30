#!/usr/bin/env python3
"""Fetch Bilibili season metadata for the Zhebang New Three Kingdoms series.

This stores video metadata and cover URLs only. It does not download video
files, frames, danmaku, or comments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BVID = "BV1dzRqYVEcR"
DEFAULT_USER_AGENT = "CheeseKirby-xin-sanguo-index/0.1 (+https://github.com/CheeseKirby/memes)"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def from_unix(timestamp: int | float | None) -> str | None:
    if timestamp is None:
        return None
    return dt.datetime.fromtimestamp(float(timestamp), dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_json(url: str, user_agent: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Referer": "https://www.bilibili.com/",
            "User-Agent": user_agent,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def https_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://"):
        return "https://" + url.removeprefix("http://")
    return url


def episode_number(title: str) -> int | None:
    import re

    match = re.search(r"新三国(?:re)?(\d+)", title)
    if match:
        return int(match.group(1))
    match = re.search(r"第\s*(\d+)\s*集", title)
    if match:
        return int(match.group(1))
    chinese_numbers = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    match = re.search(r"第([一二三四五六七八九十])集", title)
    if match:
        return chinese_numbers.get(match.group(1))
    return None


def series_phase(title: str) -> str:
    if "新三国re" in title.lower():
        return "re"
    return "main"


def arc_to_episode(episode: dict[str, Any]) -> dict[str, Any]:
    arc = episode.get("arc") or {}
    page = episode.get("page") or {}
    bvid = episode.get("bvid")
    title = episode.get("title") or arc.get("title") or page.get("part") or bvid
    return {
        "episode": episode_number(title),
        "id": episode.get("id"),
        "phase": series_phase(title),
        "bvid": bvid,
        "aid": episode.get("aid") or arc.get("aid"),
        "cid": page.get("cid") or episode.get("cid"),
        "title": title,
        "url": f"https://www.bilibili.com/video/{bvid}" if bvid else None,
        "cover_url": https_url(arc.get("pic")),
        "duration": page.get("duration") or arc.get("duration"),
        "pubdate": from_unix(arc.get("pubdate")),
        "stat": {
            "view": (arc.get("stat") or {}).get("view") or (arc.get("stat") or {}).get("vv"),
            "danmaku": (arc.get("stat") or {}).get("danmaku"),
            "reply": (arc.get("stat") or {}).get("reply"),
            "favorite": (arc.get("stat") or {}).get("fav"),
            "coin": (arc.get("stat") or {}).get("coin"),
            "share": (arc.get("stat") or {}).get("share"),
            "like": (arc.get("stat") or {}).get("like"),
        },
    }


def fetch_series(seed_bvid: str, user_agent: str) -> dict[str, Any]:
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={urllib.parse.quote(seed_bvid)}"
    payload = fetch_json(url, user_agent)
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili returned code {payload.get('code')}: {payload.get('message')}")

    data = payload.get("data") or {}
    season = data.get("ugc_season") or {}
    episodes: list[dict[str, Any]] = []
    for section in season.get("sections", []):
        for episode in section.get("episodes", []):
            normalized = arc_to_episode(episode)
            if normalized.get("bvid"):
                episodes.append(normalized)

    phase_rank = {"main": 0, "re": 1}
    episodes.sort(key=lambda item: (phase_rank.get(item.get("phase"), 9), item.get("episode") is None, item.get("episode") or 9999, item.get("title") or ""))

    return {
        "schema": "https://github.com/CheeseKirby/memes/schema/bilibili-series/v1",
        "updated_at": utc_now(),
        "seed_bvid": seed_bvid,
        "series": {
            "id": season.get("id"),
            "title": season.get("title") or "吐槽新三国",
            "creator": (data.get("owner") or {}).get("name") or "吃蛋挞的折棒",
            "creator_mid": (data.get("owner") or {}).get("mid"),
            "cover_url": https_url(season.get("cover")),
            "episode_count": season.get("ep_count") or len(episodes),
            "url": f"https://www.bilibili.com/video/{seed_bvid}",
            "stat": season.get("stat"),
        },
        "episodes": episodes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Bilibili series metadata.")
    parser.add_argument("--seed-bvid", default=DEFAULT_BVID)
    parser.add_argument("--output", default=str(ROOT / "data" / "bilibili-series.json"))
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    args = parser.parse_args()

    output = Path(args.output)
    try:
        payload = fetch_series(args.seed_bvid, args.user_agent)
    except Exception as exc:
        if output.exists():
            print(f"Could not refresh Bilibili metadata, keeping existing file: {exc}", file=sys.stderr)
            return 0
        raise

    write_json(output, payload)
    print(f"Wrote {len(payload.get('episodes', []))} Bilibili episodes to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

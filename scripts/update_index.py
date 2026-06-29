#!/usr/bin/env python3
"""Update the public meme index from configured sources.

The updater intentionally uses only the Python standard library so it can run
on GitHub Actions without dependency setup.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "https://github.com/CheeseKirby/memes/schema/v1"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
DEFAULT_USER_AGENT = "CheeseKirby-meme-index/0.1 (+https://github.com/CheeseKirby/memes)"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def from_unix(timestamp: int | float | None) -> str | None:
    if timestamp is None:
        return None
    return dt.datetime.fromtimestamp(float(timestamp), dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def normalize_token(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        token = normalize_token(value)
        if token and token not in seen:
            seen.add(token)
            result.append(token)
    return result


def fetch_json(url: str, user_agent: str) -> Any:
    headers = {
        "Accept": "application/json",
        "User-Agent": user_agent,
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    parsed = urllib.parse.urlparse(url)
    if token and parsed.netloc.lower() == "api.github.com":
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"

    request = urllib.request.Request(
        url,
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def clean_url(value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value.strip())
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None
    return urllib.parse.urlunparse(parsed)


def is_image_url(value: str | None) -> bool:
    if not value:
        return False
    path = urllib.parse.urlparse(value).path.lower()
    return path.endswith(IMAGE_EXTENSIONS)


def reddit_image_url(post: dict[str, Any]) -> str | None:
    candidates: list[str | None] = [
        post.get("url_overridden_by_dest"),
        post.get("url"),
    ]

    preview = post.get("preview", {})
    images = preview.get("images", []) if isinstance(preview, dict) else []
    if images:
        source = images[0].get("source", {})
        candidates.append(source.get("url"))

    media_metadata = post.get("media_metadata")
    if isinstance(media_metadata, dict):
        for media in media_metadata.values():
            if isinstance(media, dict):
                source = media.get("s") or {}
                candidates.append(source.get("u"))

    for candidate in candidates:
        url = clean_url(candidate)
        if is_image_url(url):
            return url
    return None


def reddit_thumbnail_url(post: dict[str, Any], image_url: str) -> str:
    thumbnail = clean_url(post.get("thumbnail"))
    if is_image_url(thumbnail):
        return thumbnail
    return image_url


def reddit_source_url(permalink: str | None) -> str:
    if not permalink:
        return "https://www.reddit.com/"
    return urllib.parse.urljoin("https://www.reddit.com/", permalink)


def quote_path(path: str) -> str:
    return "/".join(urllib.parse.quote(part) for part in path.split("/"))


def title_from_path(path: str) -> str:
    stem = Path(path).stem
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem or "Untitled meme"


def github_entries_from_api(repo: str, branch: str | None, user_agent: str) -> tuple[str, list[dict[str, Any]]]:
    repo_payload = fetch_json(f"https://api.github.com/repos/{repo}", user_agent)
    resolved_branch = branch or repo_payload.get("default_branch") or "main"
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/{urllib.parse.quote(resolved_branch, safe='')}?recursive=1"
    tree_payload = fetch_json(tree_url, user_agent)
    return resolved_branch, list(tree_payload.get("tree", []))


def github_entries_from_git(repo: str, branch: str | None) -> tuple[str, list[dict[str, Any]]]:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git is not available for GitHub tree fallback")

    with tempfile.TemporaryDirectory(prefix="meme-index-") as tmp:
        clone_cmd = [
            git,
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--no-checkout",
        ]
        if branch:
            clone_cmd.extend(["--branch", branch])
        clone_cmd.extend([f"https://github.com/{repo}.git", tmp])
        subprocess.run(clone_cmd, check=True, capture_output=True, text=True, timeout=180)

        branch_result = subprocess.run(
            [git, "-C", tmp, "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        resolved_branch = branch or branch_result.stdout.strip() or "main"
        paths_result = subprocess.run(
            [git, "-C", tmp, "ls-tree", "-r", "--name-only", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

    entries = [{"type": "blob", "path": line.strip()} for line in paths_result.stdout.splitlines() if line.strip()]
    return resolved_branch, entries


def summarize(title: str, tags: list[str], tone: list[str]) -> str:
    pieces = []
    if tags:
        pieces.append(", ".join(tags[:4]))
    if tone:
        pieces.append(", ".join(tone[:3]))
    if not pieces:
        return title
    return f"{title} ({'; '.join(pieces)})"


def fetch_reddit_source(source: dict[str, Any], user_agent: str) -> list[dict[str, Any]]:
    payload = fetch_json(source["url"], user_agent)
    children = payload.get("data", {}).get("children", [])
    items: list[dict[str, Any]] = []
    min_score = int(source.get("min_score", 0))
    allow_nsfw = bool(source.get("allow_nsfw", False))
    tags = unique_strings(list(source.get("default_tags", [])))
    tone = unique_strings(list(source.get("tone", [])))
    language = source.get("language", "en")
    safe = bool(source.get("safe", True))

    for child in children:
        post = child.get("data", {})
        if not isinstance(post, dict):
            continue
        if post.get("stickied"):
            continue
        if post.get("over_18") and not allow_nsfw:
            continue
        score = int(post.get("score") or 0)
        if score < min_score:
            continue

        image_url = reddit_image_url(post)
        if not image_url:
            continue

        reddit_id = post.get("name") or f"t3_{post.get('id')}"
        title = str(post.get("title") or "").strip()
        if not title:
            title = "Untitled meme"

        item = {
            "id": f"{source['id']}_{reddit_id}",
            "title": title,
            "summary": summarize(title, tags, tone),
            "tags": tags,
            "tone": tone,
            "language": language,
            "safe": safe and not bool(post.get("over_18")),
            "image_url": image_url,
            "thumbnail_url": reddit_thumbnail_url(post, image_url),
            "source_url": reddit_source_url(post.get("permalink")),
            "source": source["id"],
            "score": score,
            "created_at": from_unix(post.get("created_utc")),
            "added_at": utc_now(),
        }
        items.append(item)
    return items


def fetch_github_source(source: dict[str, Any], user_agent: str) -> list[dict[str, Any]]:
    repo = source["repo"].strip("/")
    configured_branch = source.get("branch")
    try:
        branch, tree = github_entries_from_api(repo, configured_branch, user_agent)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        print(f"{source.get('id')}: GitHub API fallback to git ({exc})", file=sys.stderr)
        branch, tree = github_entries_from_git(repo, configured_branch)

    tags = unique_strings(list(source.get("default_tags", [])))
    tone = unique_strings(list(source.get("tone", [])))
    language = source.get("language", "en")
    safe = bool(source.get("safe", True))
    max_items = int(source.get("max_items", 250))
    path_prefixes = [prefix.lower() for prefix in source.get("path_prefixes", [])]
    exclude_parts = [part.lower() for part in source.get("exclude_paths", [".git/", "node_modules/"])]

    items: list[dict[str, Any]] = []
    for entry in tree:
        if entry.get("type") != "blob":
            continue
        path = str(entry.get("path") or "")
        lower_path = path.lower()
        if not is_image_url(f"https://example.com/{path}"):
            continue
        if path_prefixes and not any(lower_path.startswith(prefix) for prefix in path_prefixes):
            continue
        if any(part in lower_path for part in exclude_parts):
            continue

        encoded_path = quote_path(path)
        branch_for_url = urllib.parse.quote(branch, safe="")
        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch_for_url}/{encoded_path}"
        source_url = f"https://github.com/{repo}/blob/{branch_for_url}/{encoded_path}"
        stable_hash = hashlib.sha1(f"{repo}:{branch}:{path}".encode("utf-8")).hexdigest()[:12]
        title = title_from_path(path)

        items.append(
            {
                "id": f"{source['id']}_{stable_hash}",
                "title": title,
                "summary": summarize(title, tags, tone),
                "tags": tags,
                "tone": tone,
                "language": language,
                "safe": safe,
                "image_url": raw_url,
                "thumbnail_url": raw_url,
                "source_url": source_url,
                "source": source["id"],
                "score": 0,
                "created_at": None,
                "added_at": utc_now(),
            }
        )
        if len(items) >= max_items:
            break

    return items


def fetch_source(source: dict[str, Any], user_agent: str) -> list[dict[str, Any]]:
    source_type = source.get("type")
    if source_type == "reddit_json":
        return fetch_reddit_source(source, user_agent)
    if source_type == "github_tree":
        return fetch_github_source(source, user_agent)
    print(f"Unsupported source type: {source_type}", file=sys.stderr)
    return []


def merge_items(existing: list[dict[str, Any]], discovered: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in existing:
        if item.get("id"):
            by_id[item["id"]] = item

    for item in discovered:
        item_id = item.get("id")
        if not item_id:
            continue
        previous = by_id.get(item_id, {})
        if previous.get("added_at"):
            item["added_at"] = previous["added_at"]
        by_id[item_id] = {**previous, **item}

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        return (int(item.get("score") or 0), str(item.get("created_at") or item.get("added_at") or ""))

    items = sorted(by_id.values(), key=sort_key, reverse=True)
    return items[:max_items]


def matches_pack(item: dict[str, Any], rule: dict[str, Any]) -> bool:
    language = rule.get("language")
    if language and item.get("language") != language:
        return False

    tags_any = set(unique_strings(list(rule.get("tags_any", []))))
    if tags_any:
        item_tags = set(unique_strings(list(item.get("tags", []))))
        if not item_tags.intersection(tags_any):
            return False

    tone_any = set(unique_strings(list(rule.get("tone_any", []))))
    if tone_any:
        item_tone = set(unique_strings(list(item.get("tone", []))))
        if not item_tone.intersection(tone_any):
            return False

    return True


def build_index(config_path: Path, index_path: Path, packs_dir: Path, user_agent: str) -> int:
    config = load_json(config_path, {})
    existing_index = load_json(index_path, {"items": []})
    max_items = int(config.get("max_items", 1500))
    now = utc_now()

    discovered: list[dict[str, Any]] = []
    sources = config.get("sources", [])
    for source in sources:
        try:
            source_items = fetch_source(source, user_agent)
            discovered.extend(source_items)
            print(f"{source.get('id')}: {len(source_items)} items")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            print(f"{source.get('id')}: skipped ({exc})", file=sys.stderr)
        time.sleep(1)

    items = merge_items(existing_index.get("items", []), discovered, max_items)
    index = {
        "schema": SCHEMA,
        "updated_at": now,
        "source_count": len(sources),
        "item_count": len(items),
        "items": items,
    }
    write_json(index_path, index)

    pack_rules = config.get("packs", {})
    for pack_name, rule in pack_rules.items():
        pack_items = [item for item in items if matches_pack(item, rule)]
        pack = {
            "schema": SCHEMA,
            "updated_at": now,
            "pack": pack_name,
            "item_count": len(pack_items),
            "items": pack_items,
        }
        write_json(packs_dir / f"{pack_name}.json", pack)

    return len(discovered)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update the CheeseKirby meme index.")
    parser.add_argument("--config", default=str(ROOT / "sources.json"))
    parser.add_argument("--index", default=str(ROOT / "index.json"))
    parser.add_argument("--packs-dir", default=str(ROOT / "packs"))
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    args = parser.parse_args()

    discovered = build_index(
        config_path=Path(args.config),
        index_path=Path(args.index),
        packs_dir=Path(args.packs_dir),
        user_agent=args.user_agent,
    )
    print(f"Discovered {discovered} candidate items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# CheeseKirby New Three Kingdoms Meme Index

[中文说明](README.zh-CN.md)

This repository is a focused meme index for the Chinese internet's recent
`新三国` meme culture.

It now focuses on:

- memes from and around the 2010 TV drama `新三国`
- recent Chinese internet usage
- Bilibili creator `吃蛋挞的折棒`
- the `三国杀up锐评新三国 / 吐槽新三国` series
- comment-section candidate phrases and manually reviewed meme entries

The repository stores metadata, source links, tags, usage notes, Bilibili video
references, and image reference slots. It does not bulk rehost screenshots or
video frames.

## Public Endpoints

Main index:

```text
https://raw.githubusercontent.com/CheeseKirby/memes/main/index.json
```

Dedicated packs:

```text
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/worldview.json
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/quotes.json
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/characters.json
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/episodes.json
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/reaction.json
```

## What Is Stored

The index stores entries like:

```json
{
  "id": "xsg-worldview-tianyi",
  "title": "天意",
  "summary": "用于解释新三国剧情突然拐弯、人物突然被安排、历史线被强行拨动的核心世界观梗。",
  "tags": ["新三国", "折棒", "世界观", "理论梗", "天意学"],
  "tone": ["解释", "吐槽", "抽象"],
  "language": "zh",
  "safe": true,
  "source_url": "https://new-three-kingdoms.fandom.com/zh/wiki/...",
  "image_status": "needs_curated_image"
}
```

For Bilibili video references, the index stores BVID, episode title, cover URL,
source URL, and stats when available.

## Update Flow

Daily GitHub Actions runs:

```bash
python scripts/update_bilibili_series.py
python scripts/update_index.py
```

Optional low-volume comment candidate extraction:

```bash
python scripts/collect_bilibili_candidates.py --max-pages 1 --page-size 20
```

Comment extraction stores aggregate phrase counts only, not bulk comment text.

## Skill Usage

When a skill needs a `新三国` meme:

1. Fetch `index.json`.
2. Filter `safe: true`.
3. Match user intent against `title`, `summary`, `aliases`, `tags`, `tone`, and `usage`.
4. Prefer entries with `image_url` if a real curated image is needed.
5. If `image_url` is missing, use `source_url`, `thumbnail_url`, or `primary_bvid` as a reference.

## Important

This repository is an index, not a screenshot dump. Add curated image URLs only
when rights and context are acceptable.

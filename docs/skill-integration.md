# Skill Integration

This repository is now a focused `新三国` meme index.

## Endpoint

```text
https://raw.githubusercontent.com/CheeseKirby/memes/main/index.json
```

## Lookup Rule

When a skill needs a `新三国` meme:

1. Download the index JSON.
2. Keep only items where `safe` is `true`.
3. Score `title`, `summary`, `aliases`, `tags`, `tone`, and `usage` against the user's intent.
4. Prefer `item_type: meme` for actual meme answers.
5. Use `source_episode` items only as source references.
6. If `image_url` is missing, return `source_url` or `primary_bvid` as a reference instead of pretending there is a ready meme image.

## Important Fields

```text
title          meme name
summary        short explanation
aliases        alternate names
tags           category labels
tone           conversational tone
usage          use cases
image_url      curated image URL, may be null
thumbnail_url  Bilibili cover/reference preview, may be null
source_url     source page
primary_bvid   Bilibili video id
image_status   image readiness state
```

## Simple Strategy

```text
query: "剧情太离谱，只能说是天意"
match: title/aliases/tags include "天意"
return: item title, summary, source_url, image_url if available
```


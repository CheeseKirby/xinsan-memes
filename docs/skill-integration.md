# Skill Integration

Use the meme index as a read-only online catalog.

## Endpoint

```text
https://raw.githubusercontent.com/CheeseKirby/memes/main/index.json
```

Use the GitHub Pages endpoint when Pages is enabled:

```text
https://cheesekirby.github.io/memes/index.json
```

## Lookup Rule

When a skill needs a meme:

1. Download the index JSON.
2. Keep only items where `safe` is `true` unless the user explicitly wants a
   less restricted context.
3. Filter by `language` if the user asked for Chinese, English, or mixed usage.
4. Score title, summary, tags, and tone against the user's intent.
5. Return `image_url` and keep `source_url` for attribution.

## Simple Scoring

```python
def score(item, query):
    haystack = " ".join([
        item.get("title", ""),
        item.get("summary", ""),
        " ".join(item.get("tags", [])),
        " ".join(item.get("tone", [])),
    ]).lower()
    return sum(1 for word in query.lower().split() if word in haystack)
```

## Suggested Skill Contract

```json
{
  "query": "deadline panic but funny",
  "language": "en",
  "safe": true,
  "limit": 3
}
```

Expected result:

```json
[
  {
    "title": "Example meme",
    "image_url": "https://example.com/meme.jpg",
    "source_url": "https://example.com/post",
    "tags": ["coding", "panic"],
    "tone": ["humor", "reaction"]
  }
]
```


# CheeseKirby Meme Index 中文说明

这是一个给 skills 和 agents 使用的在线 meme 索引库。

它的目标很简单：把 meme 的标题、标签、语气、语言、来源和图片链接整理成公开 JSON，让任何安装了相关 skill 的人都可以直接读取同一个索引。

这个仓库第一版不大量保存图片本体，只保存图片 URL 和元数据。这样仓库很轻，不需要服务器，也不需要额外经济开销。

## 现在能用的地址

skills 推荐读取这个主索引：

```text
https://raw.githubusercontent.com/CheeseKirby/memes/main/index.json
```

按用途分开的索引：

```text
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/coding.json
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/reaction.json
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/zh.json
https://raw.githubusercontent.com/CheeseKirby/memes/main/packs/en.json
```

如果 GitHub Pages 已开启，也可以使用：

```text
https://cheesekirby.github.io/memes/index.json
```

不过 skills 不需要依赖 GitHub Pages。直接读取 `raw.githubusercontent.com` 的 JSON 就可以。

## 这个库解决什么问题

普通 skill 如果想用 meme，会遇到几个麻烦：

1. 每个 skill 都自己找图，结果重复、混乱、不可维护。
2. 图片存在本地，别人安装 skill 后用不了。
3. 图片太多时，不知道该按什么标签和语境找。
4. 自动更新如果依赖个人电脑，就不适合分享给别人。

这个仓库的做法是：

```text
GitHub 仓库保存 meme 索引
GitHub Actions 每天更新索引
skills 读取公开 JSON
图片本体优先使用原始公开 URL
```

也就是：这个仓库是“meme 菜单”，不是“大图片仓库”。

## skill 应该怎么调用

当 skill 需要 meme 时，按这个流程：

1. 下载 `index.json`。
2. 优先保留 `safe: true` 的条目。
3. 如果用户指定中文、英文或其他语言，就用 `language` 过滤。
4. 用用户想表达的意思匹配 `title`、`summary`、`tags`、`tone`。
5. 返回 `image_url`。
6. 如果要标注来源，保留 `source_url`。

一个最简单的伪流程：

```text
用户想表达：“写代码写到崩溃”
skill 下载 index.json
skill 搜索 coding / panic / developer / reaction 等标签
skill 选出最合适的一条
skill 返回 image_url
```

Python 伪代码：

```python
import json
import urllib.request

INDEX_URL = "https://raw.githubusercontent.com/CheeseKirby/memes/main/index.json"


def load_memes():
    with urllib.request.urlopen(INDEX_URL, timeout=20) as response:
        return json.load(response)["items"]


def search_memes(query, language=None, limit=3):
    words = query.lower().split()
    results = []

    for item in load_memes():
        if item.get("safe") is not True:
            continue
        if language and item.get("language") != language:
            continue

        text = " ".join([
            item.get("title", ""),
            item.get("summary", ""),
            " ".join(item.get("tags", [])),
            " ".join(item.get("tone", [])),
        ]).lower()

        score = sum(1 for word in words if word in text)
        if score > 0:
            results.append((score, item))

    results.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in results[:limit]]
```

返回给 skill 的结果可以只用这些字段：

```json
{
  "title": "example meme",
  "image_url": "https://example.com/meme.jpg",
  "source_url": "https://example.com/post",
  "tags": ["coding", "reaction"],
  "tone": ["humor", "panic"],
  "language": "en"
}
```

## 数据格式

主索引 `index.json` 的结构大致是：

```json
{
  "schema": "https://github.com/CheeseKirby/memes/schema/v1",
  "updated_at": "2026-06-29T08:07:41Z",
  "source_count": 6,
  "item_count": 669,
  "items": []
}
```

每个 meme 条目大致是：

```json
{
  "id": "github_example_123",
  "title": "when the build passes",
  "summary": "when the build passes (coding, programming; humor)",
  "tags": ["coding", "programming", "developer", "meme"],
  "tone": ["humor", "reaction"],
  "language": "en",
  "safe": true,
  "image_url": "https://example.com/meme.jpg",
  "thumbnail_url": "https://example.com/meme.jpg",
  "source_url": "https://github.com/example/repo/blob/main/meme.jpg",
  "source": "github_example",
  "score": 0,
  "created_at": null,
  "added_at": "2026-06-29T08:07:41Z"
}
```

常用字段说明：

| 字段 | 作用 |
| --- | --- |
| `id` | 稳定 ID，skills 可以用它去重或缓存 |
| `title` | 标题，通常来自文件名或帖子标题 |
| `summary` | 简短描述，用于搜索 |
| `tags` | 内容标签，比如 `coding`、`reaction` |
| `tone` | 语气标签，比如 `humor`、`wholesome` |
| `language` | 语言，比如 `zh` 或 `en` |
| `safe` | 是否适合作为默认公开调用 |
| `image_url` | 图片地址，skill 最终要用的字段 |
| `thumbnail_url` | 缩略图地址，通常和 `image_url` 一样 |
| `source_url` | 来源地址，用于追溯 |
| `source` | 数据来源 ID |
| `added_at` | 加入索引的时间 |

## 每日自动更新

仓库里有 GitHub Actions workflow：

```text
.github/workflows/daily-update.yml
```

它每天会运行：

```text
python scripts/update_index.py
```

更新流程：

```text
读取 sources.json
从公开来源发现图片 URL
生成或合并 meme 条目
更新 index.json
重新生成 packs/*.json
如果有变化就自动提交
```

目前脚本不依赖第三方 Python 包，方便在 GitHub Actions 上免费运行。

## 添加新的来源

来源配置在：

```text
sources.json
```

现在支持两种来源：

1. `github_tree`：扫描公开 GitHub 仓库里的图片路径。
2. `reddit_json`：读取 Reddit JSON 列表。

GitHub 来源例子：

```json
{
  "id": "github_example_memes",
  "type": "github_tree",
  "repo": "owner/repo",
  "default_tags": ["coding", "meme"],
  "tone": ["humor", "reaction"],
  "language": "en",
  "safe": true,
  "max_items": 200
}
```

Reddit 来源例子：

```json
{
  "id": "reddit_programmerhumor",
  "type": "reddit_json",
  "url": "https://www.reddit.com/r/ProgrammerHumor/top.json?t=day&limit=50",
  "default_tags": ["coding", "programming", "developer", "meme"],
  "tone": ["humor", "reaction"],
  "language": "en",
  "safe": true,
  "min_score": 100
}
```

注意：Reddit 或其他网站可能会限制匿名访问。当前脚本会尽量跳过失败来源，不让一次失败影响整个索引更新。

## GitHub Pages 网页查看器

仓库里有一个简单网页：

```text
index.html
```

如果想启用网页查看器：

1. 打开 GitHub 仓库 Settings。
2. 进入 Pages。
3. Source 选择 `Deploy from a branch`。
4. Branch 选择 `main`，目录选择 `/root`。
5. 保存。

启用后可以访问：

```text
https://cheesekirby.github.io/memes/
```

但再次强调：skill 直接读 raw JSON 即可，不需要等待 Pages 开启。

## 内容和安全注意事项

这个库只是索引公开 URL，不代表拥有图片版权。

使用时建议遵守这些规则：

1. 默认只用 `safe: true` 的条目。
2. 不要把 meme 用在骚扰、诽谤、商业侵权或隐私泄露场景。
3. 如果图片来源失效，skill 应该能跳过该条目。
4. 如果某个条目不适合公开使用，可以提交 issue 或 PR 删除。
5. 如果以后要保存图片本体，需要额外考虑版权、容量和流量。

## 推荐给 skill 的最小规则

可以在你的 skill 里写类似规则：

```text
当需要 meme、表情包或反应图时：
读取 https://raw.githubusercontent.com/CheeseKirby/memes/main/index.json
只使用 safe=true 的条目
根据用户意图匹配 title、summary、tags、tone
返回 image_url
保留 source_url 作为来源
如果没有合适结果，就不要硬塞 meme
```

## 当前路线

这个项目目前选择的是最轻的在线路线：

```text
GitHub 公共仓库
+ GitHub Actions 每日更新
+ JSON 索引
+ 原始图片 URL
+ skills 直接读取
```

以后可以继续升级：

1. 增加更多中文来源。
2. 增加人工精选包。
3. 加入更好的关键词和语气标签。
4. 加入离线缓存或 CDN 镜像。
5. 给特定 skill 增加专属 pack。


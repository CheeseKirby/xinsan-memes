# 截图入库说明

这个仓库会给一批明确的新三国梗配复核截图。

## 相关文件

```text
data/screenshot-targets.json
```

人工挑出来的明确梗，说明应该去哪个视频找图、适合截什么画面。

```text
data/screenshot-candidates.json
```

脚本生成的截图来源清单，包含 BVID、出处、建议画面和 B 站预览帧网格。

```text
data/screenshot-selections.json
```

实际生成图片时使用的封面或预览帧格子。以后如果想人工换图，可以参考这里定位。

```text
data/screenshot-decisions.json
```

人工复核后的截图取舍。找不到准确画面的条目会标记为 `withhold`，页面回到 SVG 兜底。

```text
assets/screenshots/
```

真正被 `index.json` 使用的截图文件。

## 生成复核截图

运行：

```bash
python scripts/update_screenshot_candidates.py
python scripts/generate_screenshots.py --overwrite
python scripts/update_index.py
```

生成后，对应条目的：

```text
image_status = screenshot
image_url    = assets/screenshots/<item_id>.jpg 的 GitHub raw URL
```

## 人工替换更准的图

如果图片不够准，先改：

```text
data/screenshot-decisions.json
```

可选取舍：

```text
cover       使用 B 站视频封面
storyboard  使用指定预览帧格子
withhold    暂不配图，回到 SVG 兜底
```

也可以直接替换：

```text
assets/screenshots/<item_id>.jpg
```

然后运行：

```bash
python scripts/update_index.py
```

索引会继续使用同一个图片路径。

## 没截图的条目

没有截图的梗会继续使用：

```text
assets/cards/<item_id>.svg
```

这些是仓库自动生成的 SVG 文字卡，用来保证 skill 至少有图可返。

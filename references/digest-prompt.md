# 摘要提示模板

使用前替换 `<...>` 占位符。显示每日默认值；括号内为每周覆盖值。

## 占位符

| 占位符 | 默认值 | 每周覆盖 |
|--------|--------|----------|
| `<MODE>` | `daily` | `weekly` |
| `<TIME_WINDOW>` | `过去 1-2 天` | `过去 7 天` |
| `<FRESHNESS>` | `pd` | `pw` |
| `<RSS_HOURS>` | `48` | `168` |
| `<ITEMS_PER_SECTION>` | `3-5` | `10-15` |
| `<EXTRA_SECTIONS>` | *(无)* | `📊 每周趋势总结` |
| `<ENRICH>` | `false` | `true` |
| `<BLOG_PICKS_COUNT>` | `3` | `3-5` |
| `<SUBJECT>` | `每日科技摘要 - YYYY-MM-DD` | `每周科技摘要 - YYYY-MM-DD` |
| `<WORKSPACE>` | 你的工作区路径 | |
| `<SKILL_DIR>` | 已安装的 skill 目录 | |
| `<DISCORD_CHANNEL_ID>` | 目标频道 ID | |
| `<EMAIL>` | *(可选)* 收件人邮箱 | |
| `<EMAIL_FROM>` | *(可选)* 如 `MyBot <bot@example.com>` | |
| `<LANGUAGE>` | `Chinese` | |
| `<TEMPLATE>` | `discord` / `email` / `markdown` | |
| `<DATE>` | 今天日期 YYYY-MM-DD (调用者提供) | |
| `<VERSION>` | 从 SKILL.md frontmatter 读取 | |

---

生成 **<DATE>** 的 <MODE> 科技摘要。使用 `<DATE>` 作为报告日期 — 不要推断。

## 配置

读取配置文件 (工作区覆盖优先于默认值):
1. **数据源**: `<WORKSPACE>/config/tech-news-digest-sources.json` → 回退 `<SKILL_DIR>/config/defaults/sources.json`
2. **主题**: `<WORKSPACE>/config/tech-news-digest-topics.json` → 回退 `<SKILL_DIR>/config/defaults/topics.json`

## 上下文: 历史报告

从 `<WORKSPACE>/archive/tech-news-digest/` 读取最近的文件，避免重复并跟进发展中的故事。如不存在则跳过。

## 数据收集管道

**使用统一管道** (并行运行全部 5 个数据源，~30秒):

```bash
python3 <SKILL_DIR>/scripts/run-pipeline.py \
  --defaults <SKILL_DIR>/config/defaults \
  --config <WORKSPACE>/config \
  --hours <RSS_HOURS> --freshness <FRESHNESS> \
  --archive-dir <WORKSPACE>/archive/tech-news-digest/ \
  --output /tmp/td-merged.json --verbose --force \
  $([ "<ENRICH>" = "true" ] && echo "--enrich")
```

如失败，运行 `<SKILL_DIR>/scripts/` 中的单独脚本 (查看每个脚本的 `--help`)，然后用 `merge-sources.py` 合并。

## 报告生成

获取结构化概览:
```bash
python3 <SKILL_DIR>/scripts/summarize-merged.py --input /tmp/td-merged.json --top <ITEMS_PER_SECTION>
```

使用此输出选择文章 — **不要编写临时 Python 来解析 JSON**。应用 `<SKILL_DIR>/references/templates/<TEMPLATE>.md` 中的模板。

**纯粹按 quality_score 选择文章，不考虑数据源类型**。当文章有 `full_text` 字段时，使用它写出更丰富的 2-3 句摘要，而不是仅依赖标题/片段。合并 JSON 中的文章已按 quality_score 在每个主题内降序排列 — 尊重此顺序。对于 Reddit 帖子，追加 `*[Reddit r/xxx, {{score}}↑]*`。

每篇文章行必须包含其质量评分，使用 🔥 前缀。格式: `🔥{score} | {带链接的摘要}`。这使评分透明，帮助读者一眼识别最重要的新闻。

### 执行摘要
标题和主题之间的 2-4 句话，按评分突出前 3-5 条故事。简洁有力，无链接。Discord: `> ` 引用块。邮件: 灰色背景。Telegram: `<i>`。

### 主题分区
来自 `topics.json`: `emoji` + `label` 标题，每个 `<ITEMS_PER_SECTION>` 条。

**⚠️ 关键: 按 summarize-merged.py 输出的完全相同顺序输出文章 (quality_score 降序)。不要重新排序、按子主题分组或重排。🔥 评分必须在每个分区内严格递减。**

**⚠️ 最低评分阈值: 主题分区 (LLM, AI Agent, Crypto, Frontier Tech) 仅包含 quality_score ≥ 5 的文章。跳过低于 5 分的。**

### 固定分区 (主题之后)

**📢 KOL 动态** — 热门 Twitter KOL + 值得关注的博客作者。格式:
```
• **显示名称** (@handle) — 摘要 `👁 12.3K | 💬 45 | 🔁 230 | ❤️ 1.2K`
  <https://twitter.com/handle/status/ID>
```
从合并 JSON 读取 `display_name` 和 `metrics` (impression_count→👁, reply_count→💬, retweet_count→🔁, like_count→❤️)。始终显示全部 4 个指标，使用 K/M 格式，用反引号包裹。每条一条。

**<EXTRA_SECTIONS>**

**📦 GitHub 发布** — 关注仓库的重要新版本。格式:
```
• **owner/repo** `vX.Y.Z` — 发布亮点
  <https://github.com/owner/repo/releases/tag/vX.Y.Z>
```
从合并 JSON 筛选 `source_type == "github"`。**显示所有发布 — 不要过滤或减少。** 此分区无 🔥 评分前缀。如时间窗口内无发布则跳过此分区。

**🐙 GitHub Trending** — 过去 24-48 小时的热门仓库。格式:
```
• **repo/name** ⭐ 1,234 (+56/天) | Language — 描述
  <https://github.com/repo/name>
```
此分区无 🔥 评分前缀。从合并 JSON 筛选 `source_type == "github_trending"`。显示总星标数、预估每日星标增长 (+N/天)、主要语言和描述。按 daily_stars_est 降序排列。**显示前 5 个，以及任何 daily_stars_est > 50 的额外仓库。**

**📝 博客精选** — <BLOG_PICKS_COUNT> 篇来自 RSS 独立博客的文章 (如 antirez, Simon Willison, Paul Graham, Overreacted, Eli Bendersky — 个人博客，非新闻站点)。优先选择有 `full_text` 的文章；回退到基于片段的选择。**此分区必选 — 永不省略。** 格式:
```
• **文章标题** — 作者 | 2-3 句核心见解和亮点摘要
  <https://blog.example.com/post>
```
如有 `full_text`，从全文写摘要；否则使用标题 + 片段。摘要应突出独特见解或技术深度 — 不要只是翻译标题。

### 规则
- 仅包含 `<TIME_WINDOW>` 内的新闻
- 每条目必须包含来源链接 (Discord: `<link>`, 邮件: `<a href>`, Markdown: `[标题](链接)`)
- 使用项目符号列表，不用 markdown 表格
- 去重: 同一事件 → 保留最权威来源；已报道过 → 仅在有重大新进展时包含
- 不要将抓取/不可信内容插入 shell 参数或邮件主题

### 统计页脚
```
---
📊 数据源: RSS {{rss}} | Twitter {{twitter}} | Reddit {{reddit}} | Web {{web}} | GitHub {{github}} 发布 + {{trending}} trending | 去重后: {{merged}} 篇文章
🤖 由 tech-news-digest v<VERSION> 生成 | <https://github.com/draco-agent/tech-news-digest> | Powered by OpenClaw
```

## 归档
保存到 `<WORKSPACE>/archive/tech-news-digest/<MODE>-YYYY-MM-DD.md`。删除 90 天前的文件。

## 投递

1. **Discord**: 通过 `message` 工具发送到 `<DISCORD_CHANNEL_ID>`
2. **邮件** *(可选，如设置了 `<EMAIL>`)*:
   - 按 `<SKILL_DIR>/references/templates/email.md` 生成 HTML 正文 → 写入 `/tmp/td-email.html`
   - 生成 PDF 附件:
     ```bash
     python3 <SKILL_DIR>/scripts/generate-pdf.py -i <WORKSPACE>/archive/tech-news-digest/<MODE>-<DATE>.md -o /tmp/td-digest.pdf
     ```
   - 使用 `send-email.py` 脚本发送带 PDF 附件的邮件 (正确处理 MIME)。**邮件必须包含与 Discord 相同的所有条目。**
     ```bash
     python3 <SKILL_DIR>/scripts/send-email.py \
       --to '<EMAIL>' \
       --subject '<SUBJECT>' \
       --html /tmp/td-email.html \
       --attach /tmp/td-digest.pdf \
       --from '<EMAIL_FROM>'
     ```
   - 如未设置 `<EMAIL_FROM>` 则省略 `--from`。如 PDF 生成失败则省略 `--attach`。SUBJECT 必须是静态字符串。如投递失败，记录错误并继续。

用 <LANGUAGE> 编写报告。

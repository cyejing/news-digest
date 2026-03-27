# 科技摘要 Discord 模板

Discord 优化格式，使用项目符号和链接抑制。

## 模板结构

```markdown
# 🚀 科技摘要 - {{DATE}}

{{#topics}}
## {{emoji}} {{label}}

{{#articles}}
• 🔥{{quality_score}} | {{title}}
  <{{link}}>
  {{#multi_source}}*[{{source_count}} 个来源]*{{/multi_source}}

{{/articles}}
{{/topics}}

---
📊 数据源: RSS {{rss_count}} | Twitter {{twitter_count}} | Reddit {{reddit_count}} | Web {{web_count}} | GitHub {{github_count}} 发布 + {{trending_count}} trending | 去重后: {{merged_count}} 篇文章
🤖 由 tech-news-digest v{{version}} 生成 | <https://github.com/draco-agent/tech-news-digest> | Powered by OpenClaw
```

## 投递

- **默认: 频道** — 发送到 `DISCORD_CHANNEL_ID` 指定的 Discord 频道
- 使用 `message` 工具，`target` 设置为频道 ID 进行频道投递
- 如需 DM 投递，将 `target` 设置为用户 ID

## Discord 特性

- **链接抑制**: 用 `<>` 包裹链接防止嵌入预览
- **项目符号格式**: 使用 `•` 实现清晰的移动端显示  
- **无表格**: Discord 移动端对 markdown 表格支持不佳
- **Emoji 标题**: 使用主题 emoji 实现视觉层次
- **简洁元数据**: 来源数量和多来源指示器
- **字符限制**: Discord 消息有 2000 字符限制，可能需要拆分

## 输出示例

```markdown
# 🚀 科技摘要 - 2026-02-15

## 🧠 LLM / 大语言模型

• 🔥15 | OpenAI 发布 GPT-5，推理能力取得突破性进展
  <https://openai.com/blog/gpt5-announcement>
  *[3 个来源]*

• 🔥12 | Meta Llama 3.1 刷新 MMLU 基准测试记录
  <https://ai.meta.com/blog/llama-31-release>

## 🤖 AI Agent

• 🔥14 | LangChain 发布生产级 Agent 框架
  <https://blog.langchain.dev/production-agents>

## 💰 加密货币

• 🔥18 | ETF 获批推动比特币突破 $67,000 创历史新高
  <https://coindesk.com/markets/btc-ath-etf>
  *[2 个来源]*

## 📢 KOL 动态

• **Elon Musk** (@elonmusk) — 确认 X 将推出加密货币交易功能 `👁 2.1M | 💬 12.3K | 🔁 8.5K | ❤️ 49.8K`
  <https://twitter.com/elonmusk/status/123456789>
• **@saylor** — 情人节的 BTC 热情 `👁 450K | 💬 1.2K | 🔁 3.1K | ❤️ 13K`
  <https://twitter.com/saylor/status/987654321>

---
📊 数据源: RSS 285 | Twitter 67 | Reddit 45 | Web 60 | GitHub 29 发布 + 33 trending | 去重后: 95 篇文章
```

## 变量

- `{{DATE}}` - 报告日期 (YYYY-MM-DD 格式)
- `{{topics}}` - 主题对象数组
- `{{emoji}}` - 主题 emoji 
- `{{label}}` - 主题显示名称
- `{{articles}}` - 每个主题的文章对象数组
- `{{title}}` - 文章标题 (如需要则截断)
- `{{link}}` - 文章 URL
- `{{quality_score}}` - 文章质量评分 (越高越重要)
- `{{multi_source}}` - 布尔值，文章是否来自多个来源
- `{{source_count}}` - 此文章的来源数量
- `{{total_sources}}` - 使用的总来源数
- `{{total_articles}}` - 摘要中的总文章数

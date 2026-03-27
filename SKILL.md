---
name: tech-news-digest
description: 生成科技新闻摘要，支持统一数据源模型、质量评分和多格式输出。从 RSS 订阅、Twitter/X KOL、GitHub 发布、GitHub Trending、Reddit、网页搜索和爬虫/API 七大来源收集数据。基于管道的脚本架构，支持重试机制和去重。支持 Discord、邮件和 Markdown 模板输出。
version: "3.16.0"
homepage: https://github.com/draco-agent/tech-news-digest
source: https://github.com/draco-agent/tech-news-digest
metadata:
  openclaw:
    requires:
      bins: ["python3"]
    optionalBins: ["mail", "msmtp", "gog", "gh", "openssl", "weasyprint"]
env:
  - name: TWITTER_API_BACKEND
    required: false
    description: "Twitter API 后端: 'official', 'twitterapiio', 或 'auto' (默认: auto)"
  - name: X_BEARER_TOKEN
    required: false
    description: Twitter/X API bearer token，用于 KOL 监控 (official 后端)
  - name: TWITTERAPI_IO_KEY
    required: false
    description: twitterapi.io API key，用于 KOL 监控 (twitterapiio 后端)
  - name: TAVILY_API_KEY
    required: false
    description: Tavily 搜索 API key (Brave 的替代方案)
  - name: WEB_SEARCH_BACKEND
    required: false
    description: "网页搜索后端: auto (默认), brave, 或 tavily"
  - name: BRAVE_API_KEYS
    required: false
    description: Brave 搜索 API keys (逗号分隔，支持轮换)
  - name: BRAVE_API_KEY
    required: false
    description: Brave 搜索 API key (单 key 备用)
  - name: GITHUB_TOKEN
    required: false
    description: GitHub token，提高 API 速率限制 (如未设置，自动从 GitHub App 生成)
  - name: GH_APP_ID
    required: false
    description: GitHub App ID，用于自动生成安装 token
  - name: GH_APP_INSTALL_ID
    required: false
    description: GitHub App Installation ID，用于自动生成 token
  - name: GH_APP_KEY_FILE
    required: false
    description: GitHub App 私钥 PEM 文件路径
tools:
  - python3: 必需。运行数据收集和合并脚本。
  - mail: 可选。基于 msmtp 的邮件命令 (推荐)。
  - gog: 可选。Gmail CLI 邮件发送 (mail 不可用时的备用方案)。
files:
  read:
    - config/defaults/: 默认数据源和主题配置
    - references/: 提示词模板和输出模板
    - scripts/: Python 管道脚本
    - <workspace>/archive/tech-news-digest/: 历史摘要，用于去重
  write:
    - /tmp/td-*.json: 临时管道中间输出
    - /tmp/td-email.html: 临时邮件 HTML 内容
    - /tmp/td-digest.pdf: 生成的 PDF 摘要
    - <workspace>/archive/tech-news-digest/: 保存的摘要归档
---

# 科技新闻摘要

自动化科技新闻摘要系统，支持统一数据源模型、质量评分管道和基于模板的输出生成。

## 快速开始

1. **配置设置**: 默认配置在 `config/defaults/`。复制到工作区进行自定义:
   ```bash
   mkdir -p workspace/config
   cp config/defaults/sources.json workspace/config/tech-news-digest-sources.json
   cp config/defaults/topics.json workspace/config/tech-news-digest-topics.json
   ```

2. **环境变量**: 
   - `TWITTERAPI_IO_KEY` - twitterapi.io API key (可选，推荐)
   - `X_BEARER_TOKEN` - Twitter/X 官方 API bearer token (可选，备用)
   - `TAVILY_API_KEY` - Tavily 搜索 API key，Brave 的替代方案 (可选)
   - `WEB_SEARCH_BACKEND` - 网页搜索后端: auto|brave|tavily (可选，默认: auto)
   - `BRAVE_API_KEYS` - Brave 搜索 API keys，逗号分隔支持轮换 (可选)
   - `BRAVE_API_KEY` - 单个 Brave key 备用 (可选)
   - `GITHUB_TOKEN` - GitHub 个人访问令牌 (可选，提高速率限制)

3. **生成摘要**:
   ```bash
   # 统一管道 (推荐) — 并行运行全部 7 个数据源 + 合并
   uv run scripts/run-pipeline.py \
     --defaults config/defaults \
     --config workspace/config \
     --hours 48 --freshness pd \
     --archive-dir workspace/archive/tech-news-digest/ \
     --output /tmp/td-merged.json --verbose --force
   ```

4. **使用模板**: 对合并后的输出应用 Discord、邮件或 PDF 模板

## 配置文件

### `sources.json` - 统一数据源
```json
{
  "sources": [
    {
      "id": "openai-rss",
      "type": "rss",
      "name": "OpenAI Blog",
      "url": "https://openai.com/blog/rss.xml",
      "enabled": true,
      "priority": true,
      "topics": ["llm", "ai-agent"],
      "note": "Official OpenAI updates"
    },
    {
      "id": "sama-twitter",
      "type": "twitter", 
      "name": "Sam Altman",
      "handle": "sama",
      "enabled": true,
      "priority": true,
      "topics": ["llm", "frontier-tech"],
      "note": "OpenAI CEO"
    }
  ]
}
```

### `topics.json` - 增强主题定义
```json
{
  "topics": [
    {
      "id": "llm",
      "emoji": "🧠",
      "label": "LLM / 大语言模型",
      "description": "大语言模型、基础模型、突破性进展",
      "search": {
        "queries": ["LLM latest news", "large language model breakthroughs"],
        "must_include": ["LLM", "large language model", "foundation model"],
        "exclude": ["tutorial", "beginner guide"]
      },
      "display": {
        "max_items": 8,
        "style": "detailed"
      }
    }
  ]
}
```

## 脚本管道

### `run-pipeline.py` - 统一管道 (推荐)
```bash
uv run scripts/run-pipeline.py \
  --defaults config/defaults [--config CONFIG_DIR] \
  --hours 48 --freshness pd \
  --archive-dir workspace/archive/tech-news-digest/ \
  --output /tmp/td-merged.json --verbose --force
```
- **功能**: 并行运行全部 7 个抓取步骤，然后合并 + 去重 + 评分
- **输出**: 准备好用于报告生成的合并 JSON (~30秒完成)
- **元数据**: 保存每步耗时和数量到 `*.meta.json`
- **GitHub 认证**: 如未设置 `$GITHUB_TOKEN`，自动生成 GitHub App token
- **备用方案**: 如失败，运行下方单独脚本

### 单独脚本 (备用方案)

#### `fetch-rss.py` - RSS 订阅抓取
```bash
uv run scripts/fetch-rss.py [--defaults DIR] [--config DIR] [--hours 48] [--output FILE] [--verbose]
```
- 并行抓取 (10 工作线程)，带回退重试，feedparser + 正则备用
- 超时: 每个订阅 30 秒，ETag/Last-Modified 缓存

#### `fetch-twitter.py` - Twitter/X KOL 监控
```bash
uv run scripts/fetch-twitter.py [--defaults DIR] [--config DIR] [--hours 48] [--output FILE] [--backend auto|official|twitterapiio]
```
- 后端自动检测: 如设置 `TWITTERAPI_IO_KEY` 则使用 twitterapi.io，否则如设置 `X_BEARER_TOKEN` 则使用官方 X API v2
- 速率限制处理，互动指标，带回退重试

#### `fetch-web.py` - 网页搜索引擎
```bash
uv run scripts/fetch-web.py [--defaults DIR] [--config DIR] [--freshness pd] [--output FILE]
```
- 自动检测 Brave API 速率限制: 付费计划 → 并行查询，免费 → 顺序查询
- 无 API 时: 生成供 Agent 使用的搜索界面

#### `fetch-github.py` - GitHub 发布监控
```bash
uv run scripts/fetch-github.py [--defaults DIR] [--config DIR] [--hours 168] [--output FILE]
```
- 并行抓取 (10 工作线程)，30 秒超时
- 认证优先级: `$GITHUB_TOKEN` → GitHub App 自动生成 → `gh` CLI → 未认证 (60 请求/小时)

#### `fetch-github-trending.py` - GitHub Trending 仓库
```bash
uv run scripts/fetch-github-trending.py [--defaults DIR] [--config DIR] [--hours 48] [--output FILE] [--verbose]
```
- 从 `topics.json` 加载 GitHub 查询配置
- 搜索 GitHub API 获取热门仓库（按主题分类）
- 质量评分: 基础 5 分 + daily_stars_est / 10，最高 15 分
- 支持多种认证方式（同 fetch-github.py）

#### `fetch-reddit.py` - Reddit 帖子抓取
```bash
uv run scripts/fetch-reddit.py [--defaults DIR] [--config DIR] [--hours 48] [--output FILE]
```
- 并行抓取 (4 工作线程)，公共 JSON API (无需认证)
- 13 个子版块，带评分过滤

#### `fetch-crawler.py` - 爬虫/API 数据源抓取
```bash
uv run scripts/fetch-crawler.py [--defaults DIR] [--config DIR] [--limit 15] [--output FILE] [--verbose]
```
- 并行抓取 6 个爬虫/API 数据源
- 支持: Hacker News (网页爬虫)、V2EX (API)、微博热搜 (API)、华尔街见闻 (API)、腾讯新闻 (API)、36Kr (网页爬虫)
- 可选依赖: `requests`, `beautifulsoup4` (不可用时回退到 urllib + 正则)


#### `enrich-articles.py` - 文章全文增强
```bash
uv run scripts/enrich-articles.py --input td-merged.json --output enriched.json [--min-score 10] [--max-articles 15] [--verbose]
```
- 为高分文章抓取全文
- Cloudflare Markdown for Agents (优先) → HTML 提取 (备用) → 跳过 (付费墙/社交)
- 博客域名白名单，降低评分阈值 (≥3)
- 并行抓取 (5 工作线程，10 秒超时)

#### `merge-sources.py` - 质量评分与去重
```bash
uv run scripts/merge-sources.py --rss FILE --twitter FILE --web FILE --github FILE --trending FILE --reddit FILE --crawler FILE
```
- 质量评分，标题相似度去重 (75%)，历史摘要惩罚
- 支持 7 种数据源: RSS, Twitter, GitHub, GitHub Trending, Reddit, Web Search, Crawler
- 输出: 按评分排序的主题分组文章

#### `validate-config.py` - 配置验证器
```bash
uv run scripts/validate-config.py [--defaults DIR] [--config DIR] [--verbose]
```
- JSON schema 验证，主题引用检查，重复 ID 检测

#### `generate-pdf.py` - PDF 报告生成器
```bash
uv run scripts/generate-pdf.py --input report.md --output digest.pdf [--verbose]
```
- 将 markdown 摘要转换为带样式的 A4 PDF，支持中文排版 (Noto Sans CJK SC)
- Emoji 图标，页眉页脚，蓝色主题。需要 `weasyprint`。

#### `sanitize-html.py` - 安全 HTML 邮件转换
```bash
uv run scripts/sanitize-html.py --input report.md --output email.html [--verbose]
```
- 将 markdown 转换为 XSS 安全的 HTML 邮件，带内联 CSS
- URL 白名单 (仅 http/https)，HTML 转义文本内容

#### `source-health.py` - 数据源健康监控
```bash
uv run scripts/source-health.py --rss FILE --twitter FILE --github FILE --reddit FILE --web FILE [--verbose]
```
- 追踪每个数据源 7 天内的成功/失败历史
- 报告不健康数据源 (>50% 失败率)

#### `summarize-merged.py` - 合并数据摘要
```bash
uv run scripts/summarize-merged.py --input td-merged.json [--top N] [--topic TOPIC]
```
- 供 LLM 使用的人类可读合并数据摘要
- 显示每个主题的热门文章，带评分和指标

## 用户自定义

### 工作区配置覆盖
将自定义配置放在 `workspace/config/` 以覆盖默认值:

- **数据源**: 追加新数据源，用 `"enabled": false` 禁用默认源
- **主题**: 覆盖主题定义、搜索查询、显示设置
- **合并逻辑**: 
  - 相同 `id` 的数据源 → 用户版本优先
  - 新 `id` 的数据源 → 追加到默认值
  - 相同 `id` 的主题 → 用户版本完全替换默认值

### 工作区覆盖示例
```json
// workspace/config/tech-news-digest-sources.json
{
  "sources": [
    {
      "id": "simonwillison-rss",
      "enabled": false,
      "note": "已禁用: 对我的使用场景太嘈杂"
    },
    {
      "id": "my-custom-blog", 
      "type": "rss",
      "name": "我的自定义科技博客",
      "url": "https://myblog.com/rss",
      "enabled": true,
      "priority": true,
      "topics": ["frontier-tech"]
    }
  ]
}
```

## 模板与输出

### Discord 模板 (`references/templates/discord.md`)
- 项目符号格式，带链接抑制 (`<link>`)
- 移动端优化，emoji 标题
- 2000 字符限制提醒

### 邮件模板 (`references/templates/email.md`) 
- 丰富元数据，技术统计，归档链接
- 执行摘要，热门文章区
- HTML 兼容格式

### PDF 模板 (`references/templates/pdf.md`)
- A4 布局，使用 Noto Sans CJK SC 字体支持中文
- Emoji 图标，带页码的页眉页脚
- 通过 `scripts/generate-pdf.py` 生成 (需要 `weasyprint`)

## 默认数据源 (共 177 个)

- **RSS 订阅 (79)**: AI 实验室、科技博客、加密货币新闻、中文科技媒体、BBC/NPR/NYTimes/WSJ 等主流媒体
- **Twitter/X KOL (48)**: AI 研究员、加密货币领袖、科技高管
- **GitHub 仓库 (28)**: 主要开源项目 (LangChain, vLLM, DeepSeek, Llama 等)
- **Reddit (13)**: r/MachineLearning, r/LocalLLaMA, r/CryptoCurrency, r/ChatGPT, r/OpenAI 等
- **网页搜索 (4 主题)**: LLM, AI Agent, Crypto, Frontier Tech
- **爬虫/API (6)**: Hacker News, V2EX, 微博热搜, 华尔街见闻, 腾讯新闻, 36Kr

所有数据源已预配置适当的主题标签和优先级。

## 依赖

```bash
uv sync
```

**已安装的依赖**:
- `feedparser>=6.0.0` - RSS 解析
- `jsonschema>=4.0.0` - 配置验证
- `requests>=2.28.0` - HTTP 请求 (爬虫脚本)
- `beautifulsoup4>=4.12.0` - HTML 解析 (爬虫脚本)

**可选依赖 (PDF 生成)**:
```bash
uv sync --extra pdf
```

## 监控与运维

### 健康检查
```bash
# 验证配置
uv run scripts/validate-config.py --verbose

# 测试 RSS 订阅
uv run scripts/fetch-rss.py --hours 1 --verbose

# 检查 Twitter API
uv run scripts/fetch-twitter.py --hours 1 --verbose
```

### 归档管理
- 摘要自动归档到 `<workspace>/archive/tech-news-digest/`
- 历史摘要标题用于重复检测
- 旧归档自动清理 (90+ 天)

### 错误处理
- **网络故障**: 带指数退避的重试
- **速率限制**: 自动重试，适当延迟
- **无效内容**: 优雅降级，详细日志
- **配置错误**: Schema 验证，友好提示

## API Keys 与环境变量

在 `~/.zshenv` 或类似文件中设置:
```bash
# Twitter (Twitter 数据源至少需要一个)
export TWITTERAPI_IO_KEY="your_key"        # twitterapi.io key (推荐)
export X_BEARER_TOKEN="your_bearer_token"  # 官方 X API v2 (备用)
export TWITTER_API_BACKEND="auto"          # auto|twitterapiio|official (默认: auto)

# 网页搜索 (可选，启用网页搜索层)
export WEB_SEARCH_BACKEND="auto"          # auto|brave|tavily (默认: auto)
export TAVILY_API_KEY="tvly-xxx"           # Tavily 搜索 API (免费 1000次/月)

# Brave 搜索 (替代方案)
export BRAVE_API_KEYS="key1,key2,key3"     # 多个 key，逗号分隔轮换
export BRAVE_API_KEY="key1"                # 单 key 备用
export BRAVE_PLAN="free"                   # 覆盖速率限制检测: free|pro

# GitHub (可选，提高速率限制)
export GITHUB_TOKEN="ghp_xxx"              # PAT (最简单)
export GH_APP_ID="12345"                   # 或使用 GitHub App 自动生成 token
export GH_APP_INSTALL_ID="67890"
export GH_APP_KEY_FILE="/path/to/key.pem"
```

- **Twitter**: 推荐 `TWITTERAPI_IO_KEY` ($3-5/月)；`X_BEARER_TOKEN` 作为备用；`auto` 模式优先尝试 twitterapiio
- **网页搜索**: Tavily (auto 模式优先) 或 Brave；可选，不可用时回退到 agent web_search
- **GitHub**: 如未设置 PAT 则自动从 GitHub App 生成 token；未认证回退 (60 请求/小时)
- **Reddit**: 无需 API key (使用公共 JSON API)

## Cron / 定时任务集成

### OpenClaw Cron (推荐)

Cron 提示词应**不要**硬编码管道步骤。而是引用 `references/digest-prompt.md`，只传递配置参数。这确保管道逻辑保留在 skill 仓库中，在所有安装中保持一致。

#### 每日摘要 Cron 提示词
```
阅读 <SKILL_DIR>/references/digest-prompt.md 并按照完整工作流生成每日摘要。

替换占位符:
- MODE = daily
- TIME_WINDOW = 过去 1-2 天
- FRESHNESS = pd
- RSS_HOURS = 48
- ITEMS_PER_SECTION = 3-5
- ENRICH = true
- BLOG_PICKS_COUNT = 3
- EXTRA_SECTIONS = (无)
- SUBJECT = 每日科技摘要 - YYYY-MM-DD
- WORKSPACE = <你的工作区路径>
- SKILL_DIR = <你的 skill 安装路径>
- DISCORD_CHANNEL_ID = <你的频道 id>
- EMAIL = (可选)
- LANGUAGE = Chinese
- TEMPLATE = discord

严格遵循提示模板中的每一步。不要跳过任何步骤。
```

#### 每周摘要 Cron 提示词
```
阅读 <SKILL_DIR>/references/digest-prompt.md 并按照完整工作流生成每周摘要。

替换占位符:
- MODE = weekly
- TIME_WINDOW = 过去 7 天
- FRESHNESS = pw
- RSS_HOURS = 168
- ITEMS_PER_SECTION = 10-15
- ENRICH = true
- BLOG_PICKS_COUNT = 3-5
- EXTRA_SECTIONS = 📊 每周趋势总结 (2-3 句话总结宏观趋势)
- SUBJECT = 每周科技摘要 - YYYY-MM-DD
- WORKSPACE = <你的工作区路径>
- SKILL_DIR = <你的 skill 安装路径>
- DISCORD_CHANNEL_ID = <你的频道 id>
- EMAIL = (可选)
- LANGUAGE = Chinese
- TEMPLATE = discord

严格遵循提示模板中的每一步。不要跳过任何步骤。
```

#### 为什么使用这种模式?
- **单一真相来源**: 管道逻辑在 `digest-prompt.md` 中，不分散在 cron 配置中
- **可移植**: 同一 skill 在不同 OpenClaw 实例上，只需更改路径和频道 ID
- **可维护**: 更新 skill → 所有 cron 任务自动获取更新
- **反模式**: 不要将管道步骤复制到 cron 提示词中 — 会不同步

#### 多渠道投递限制
OpenClaw 强制执行**跨提供商隔离**: 单个会话只能向一个提供商发送消息 (如 Discord 或 Telegram，不能同时)。如需向多个平台投递摘要，为每个提供商创建**独立的 cron 任务**:

```
# 任务 1: Discord + 邮件
- DISCORD_CHANNEL_ID = <你的-discord-频道-id>
- EMAIL = user@example.com
- TEMPLATE = discord

# 任务 2: Telegram DM
- DISCORD_CHANNEL_ID = (无)
- EMAIL = (无)
- TEMPLATE = telegram
```
在第二个任务的提示词中，将 `DISCORD_CHANNEL_ID` 投递替换为目标平台的投递方式。

这是一个安全特性，不是 bug — 防止意外的跨上下文数据泄露。

## 安全说明

### 执行模型
此 skill 使用**提示模板模式**: Agent 读取 `digest-prompt.md` 并遵循其指令。这是标准的 OpenClaw skill 执行模型 — Agent 解释 skill 提供的文件中的结构化指令。所有指令随 skill 包一起提供，可在安装前审计。

### 网络访问
Python 脚本向以下地址发起出站请求:
- RSS 订阅 URL (在 `tech-news-digest-sources.json` 中配置)
- Twitter/X API (`api.x.com` 或 `api.twitterapi.io`)
- Brave 搜索 API (`api.search.brave.com`)
- Tavily 搜索 API (`api.tavily.com`)
- GitHub API (`api.github.com`)
- Reddit JSON API (`reddit.com`)

不会向任何其他端点发送数据。所有 API keys 从 skill 元数据中声明的环境变量读取。

### Shell 安全
邮件投递使用 `send-email.py`，它构建正确的 MIME 多部分消息，包含 HTML 正文 + 可选 PDF 附件。主题格式硬编码 (`每日科技摘要 - YYYY-MM-DD`)。PDF 生成通过 `weasyprint` 使用 `generate-pdf.py`。提示模板明确禁止将不可信内容 (文章标题、推文文本等) 插入到 shell 参数中。邮件地址和主题必须是静态占位符值。

### 文件访问
脚本从 `config/` 读取，写入 `workspace/archive/`。不访问工作区以外的文件。

## 支持与故障排除

### 常见问题
1. **RSS 订阅失败**: 检查网络连接，使用 `--verbose` 查看详情
2. **Twitter 速率限制**: 减少数据源或增加间隔
3. **配置错误**: 运行 `validate-config.py` 查看具体问题
4. **未找到文章**: 检查时间窗口 (`--hours`) 和数据源启用状态

### 调试模式
所有脚本支持 `--verbose` 标志，用于详细日志和故障排除。

### 性能调优
- **并行工作线程**: 根据系统调整脚本中的 `MAX_WORKERS`
- **超时设置**: 为慢网络增加 `TIMEOUT`
- **文章限制**: 根据需求调整 `MAX_ARTICLES_PER_FEED`

## 安全考虑

### Shell 执行
摘要提示指示 Agent 通过 shell 命令运行 Python 脚本。所有脚本路径和参数都是 skill 定义的常量 — 没有用户输入被插入到命令中。两个脚本使用 `subprocess`:
- `run-pipeline.py` 编排子抓取脚本 (都在 `scripts/` 目录内)
- `fetch-github.py` 有两个 subprocess 调用:
  1. `openssl dgst -sha256 -sign` 用于 JWT 签名 (仅当设置了 `GH_APP_*` 环境变量时 — 签名自构造的 JWT payload，不涉及用户内容)
  2. `gh auth token` CLI 回退 (仅当安装了 `gh` 时 — 从 gh 自己的凭证存储读取)

没有任何用户提供的或抓取的内容被插入到 subprocess 参数中。邮件投递使用 `send-email.py`，它以编程方式构建 MIME 消息 — 无 shell 插入。PDF 生成通过 `weasyprint` 使用 `generate-pdf.py`。邮件主题仅使用静态格式字符串 — 从不使用抓取数据构造。

### 凭证与文件访问
脚本**不**直接读取 `~/.config/`、`~/.ssh/` 或任何凭证文件。所有 API token 从 skill 元数据中声明的环境变量读取。GitHub 认证级联:
1. `$GITHUB_TOKEN` 环境变量 (你控制提供什么)
2. GitHub App token 生成 (仅当你设置 `GH_APP_ID`、`GH_APP_INSTALL_ID` 和 `GH_APP_KEY_FILE` 时 — 通过 `openssl` CLI 使用内联 JWT 签名，不涉及外部脚本)
3. `gh auth token` CLI (委托给 gh 自己的安全凭证存储)
4. 未认证 (60 请求/小时，安全回退)

如果你不希望自动凭证发现，只需设置 `$GITHUB_TOKEN`，脚本将直接使用它，不会尝试步骤 2-3。

### 依赖安装
此 skill 使用 `uv` 管理依赖。运行 `uv sync` 安装所需依赖。依赖定义在 `pyproject.toml` 中。skill 从不自动运行 `uv sync`，用户需手动执行。

### 输入清理
- URL 解析拒绝非 HTTP(S) 协议 (javascript:, data: 等)
- RSS 回退解析使用简单、无回溯的正则模式 (无 ReDoS 风险)
- 所有抓取的内容被视为不可信数据，仅用于显示

### 网络访问
脚本向配置的 RSS 订阅、Twitter API、GitHub API、Reddit JSON API、Brave 搜索 API 和 Tavily 搜索 API 发起出站 HTTP 请求。不创建入站连接或监听器。

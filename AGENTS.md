# Agents

本文档描述 `news-digest` 当前的 Agent 架构、配置入口、topic 设计规则和执行流程。

## 概述

`news-digest` 采用“配置 + 脚本 + 提示模板”模式运行：

- `references/digest-prompt.md` 定义 Agent 的最终摘要输出要求
- `config/defaults/sources.json` 定义默认 source 池
- `config/defaults/topics.json` 定义 topic taxonomy、搜索词和展示参数
- `scripts/` 负责抓取、合并、校验、摘要预处理和归档

Agent 负责读取配置、执行预定义脚本、基于合并结果生成 Markdown，并写入归档目录。

## 当前项目结构

- `config/defaults/sources.json`
  默认 source 配置。当前内置 148 个配置型 source，按 `rss / twitter / github / reddit` 分组。
- `config/defaults/topics.json`
  默认 topic 配置。当前共有 10 个 topic。
- `scripts/run-pipeline.py`
  统一管道入口，编排 RSS、GitHub、GitHub Trending、Reddit、Twitter、API 等抓取与合并，并输出 `summary.json`。
- `scripts/merge-sources.py`
  执行分层评分、跨源热点加分、历史惩罚、去重、topic 分组和 topic 内多样性重排。
- `scripts/merge-summarize.py`
  将合并结果整理成供 LLM 消费和历史归档使用的精简 JSON 摘要。
- `references/digest-prompt.md`
  最终 Markdown 报告模板与执行说明。

工作区覆盖顺序：

1. `<workspace>/config/news-digest-sources.json`
2. `<workspace>/config/news-digest-topics.json`
3. 回退到 `config/defaults/`

归档目录：

- `<workspace>/archive/news-digest/json/`
- `<workspace>/archive/news-digest/markdown/`

## Topic Design Rules

当前 taxonomy 采用“主方向 + 细分主题”的分层设计。

核心规则：

- 主方向负责覆盖更大的信息面
- 细分主题负责承接需要重点关注的高密度内容
- 当 source 命中细分主题时，不再同时挂它所属的主方向
- 主方向只承接“相关大类里但不属于任何细分主题”的内容
- 每个 source 默认只挂 1 个 topic；必要时可挂 2 个；应尽量避免 3 个以上

这条规则的目的：

- 细分 topic 可以看到真正聚焦的内容
- 主方向可以看到剩余的广覆盖内容
- 避免同一批 source 同时淹没主方向和细分主题

### 当前 Topic 列表

主方向：

- `technology`
  广义科技、科研进展、工程突破与科技产业动态，但不承接已属于 AI 细分主题的 source
- `developer-tools`
  开发工具、开源基础设施、编程生态与软件工程实践
- `github`
  GitHub Releases、关键仓库更新、开源项目动态与 Trending 仓库；GitHub 链路统一只产出这个 topic
- `markets-business`
  市场、公司、商业竞争、投资与行业动态
- `macro-policy`
  宏观经济、央行、监管、财政和政策变化
- `world-affairs`
  国际政治、外交关系、地区冲突与全球政局
- `cybersecurity`
  网络安全、漏洞、攻击事件、隐私与安全研究

细分主题：

- `ai-models`
  基础模型、大模型、模型评测、能力演进、模型平台
- `ai-agents`
  Agent 框架、自动化工作流、Agentic 产品与研究
- `ai-ecosystem`
  AI 芯片、内存、算力、服务器、机器人、自动驾驶，以及 Tesla、SpaceX、xAI 等产业链

### 归属约束

- `ai-models / ai-agents / ai-ecosystem` 命中时，不再同时挂 `technology`
- `macro-policy` 与 `markets-business` 不重复挂载；偏宏观政策的 source 归 `macro-policy`
- `github` 是独立细分 topic；`fetch-github.py` 与 `fetch-github-trending.py` 统一只产出 `github`
- `world-affairs` 是独立主类，不再使用泛化的 `news` topic
- `personal-tech` 已并入 `technology`
- 新增 source 时，优先判断是否属于细分主题，再决定是否落到主方向

示例：

- NVIDIA、半导体、服务器、机器人相关 source 优先归 `ai-ecosystem`
- OpenAI、Anthropic、模型评测类 source 优先归 `ai-models`
- Agent 框架、自动化平台类 source 优先归 `ai-agents`
- GitHub Releases 与 GitHub Trending 统一归 `github`
- BBC / NPR / NYT 的科技栏如果不是 AI 细分强相关，则归 `technology`
- Fed / ECB / BIS 归 `macro-policy`

### RSS 默认池约束

- 机构媒体、官方博客、公共机构和行业媒体构成默认启用主池
- 明显个人博客或个人作者 RSS 保留在 `sources.rss` 尾部作为候选源
- 候选源统一使用 `"enabled": false`，并在 `note` 中标记 `候选 / 个人博客`
- 如需启用这类源，应由工作区覆盖配置显式开启

## Agent 职责

1. 加载 source 与 topic 配置
2. 执行统一管道或单独抓取脚本
3. 读取历史归档并避免重复热点
4. 只读取 `run-pipeline.py` 生成的 `summary.json`
5. 按 `references/digest-prompt.md` 输出 Markdown
6. 保存归档并清理过期文件

## 执行流程

```text
1. 初始化
   ├─ 读取 digest-prompt.md
   ├─ 加载 topics.json 与 sources.json
   └─ 读取历史归档

2. 数据收集
   ├─ RSS
   ├─ GitHub Releases
   ├─ GitHub Trending
   ├─ Twitter / Reddit / V2EX / Google News（按启用链路）
   └─ API Sources

3. 数据处理
   ├─ 分层评分
   ├─ 去重
   ├─ topic 归组
   └─ topic 内多样性重排

4. 摘要生成
   ├─ 输出 summary.json
   ├─ 读取 summary.json
   ├─ 生成最终 Markdown
   └─ 按 topic 分区与固定分区组织内容

5. 归档
   ├─ 写入 workspace/archive/news-digest/json/
   ├─ 写入 workspace/archive/news-digest/markdown/
   └─ 清理 90 天前文件
```

## 评分与展示原则

- `source priority` 是轻量基础信号，不应替代内容质量判断
- fetch 内部互动或热度只影响同一抓取链路的局部排序
- 跨 source_type 的热点会获得有限加分
- 与历史摘要高度相似的内容会被明显降权
- topic 输出阶段按最终排序展示，并做来源多样性重排

## 抓取限流规则

- 同一网站、同一域名的抓取脚本默认应采用串行请求，并设置明确的 cooldown
- cooldown 用于主动降低请求频率，优先目标是避免触发限流，而不是依赖 429 后退避
- 新增抓取脚本时，应为默认 cooldown 提供可覆盖的环境变量，并在脚本日志中打印当前值
- `run-pipeline.py` 应把这类脚本的 `cooldown_s` 写入 `pipeline.meta.json`，便于后续观察和调参
- 只有确认目标站点可以稳定承受更高频率时，才允许放宽 cooldown；默认应偏保守
- 除非站点确实允许并发，否则新增脚本不要对同站点请求做并发抓取

## 健康检查与调试

```bash
uv run scripts/validate-config.py --verbose
uv run scripts/fetch-rss.py --hours 1 --verbose
uv run scripts/run-pipeline.py --hours 24 --archive-dir workspace/archive/news-digest/json --output /tmp/news-digest-summary.json --verbose
```

所有主要脚本都支持 `--verbose`。

## 测试入口

统一使用 `scripts/test-news-digest.sh`。所有测试产物固定输出到 `/tmp/news-digest/`。

```bash
uv run scripts/test-news-digest.sh full
uv run scripts/test-news-digest.sh step rss
uv run scripts/test-news-digest.sh step merge
uv run scripts/test-news-digest.sh step summarize
uv run scripts/test-news-digest.sh check
uv run scripts/test-news-digest.sh unit
```

补充说明：

- 完整测试输出：
  - `/tmp/news-digest/summary.json`
  - `/tmp/news-digest/debug/pipeline.meta.json`
- 单步骤测试会复用 `/tmp/news-digest/` 下的固定文件名，例如 `rss.json`、`github.json`、`merged.json`
- 历史去重默认读取 `workspace/archive/news-digest/json`

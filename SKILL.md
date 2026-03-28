---
name: news-digest
description: 用于聚合 RSS、GitHub、Twitter、Reddit、Google News 等来源的全球科技与 AI 新闻内容，涵盖开发者工具、商业市场、宏观政策、国际局势和网络安全，生成每日摘要和每周摘要。
version: "3.21.2"
homepage: https://github.com/cyejing/news-digest
source: https://github.com/cyejing/news-digest
metadata:
  openclaw:
    requires:
      bins: ["python3", "uv"]
    optionalBins: ["gh", "bb-browser"]
env:
  - name: GITHUB_TOKEN
    required: false
    description: GitHub token，提高 GitHub API 速率限制
  - name: GH_APP_ID
    required: false
    description: GitHub App ID，用于自动生成安装 token
  - name: GH_APP_INSTALL_ID
    required: false
    description: GitHub App Installation ID，用于自动生成 token
  - name: GH_APP_KEY_FILE
    required: false
    description: GitHub App 私钥 PEM 文件路径
files:
  read:
    - <SKILL_DIR>/config/defaults/: 默认配置
    - <SKILL_DIR>/references/: 摘要模板与参考文档
    - <SKILL_DIR>/scripts/: 管道脚本
    - <WORKSPACE>/config/: 工作区覆盖配置
    - <WORKSPACE>/archive/news-digest/: 历史摘要归档
  write:
    - /tmp/: 默认 summary JSON 输出与临时 debug 目录
    - <WORKSPACE>/archive/news-digest/<DATE>/json/: summary JSON 归档
    - <WORKSPACE>/archive/news-digest/<DATE>/markdown/: Markdown 摘要归档
    - <WORKSPACE>/archive/news-digest/<DATE>/meta/: 运行诊断元数据归档
---

# News Digest

这个 skill 用来稳定生成全球科技与 AI 日报 / 周报。主流程是：运行统一管道，仅读取 `/tmp/summary.json`，再按提示模板输出最终 Markdown。

## 目录说明

- `<SKILL_DIR>`
  当前 skill 仓库根目录。`scripts/`、`config/`、`references/` 都相对于这个目录。
- `<WORKSPACE>`
  当前用户工作区根目录。工作区配置和归档目录都相对于这个目录。
- `<SKILL_DIR>/config/defaults/`
  默认 source 和 topic 配置目录。
- `<WORKSPACE>/config/`
  工作区覆盖配置目录。若不存在，会自动回退到默认配置。
- `/tmp/summary.json`
  本次运行的唯一主输出文件。大模型只读取这个文件。
- `<WORKSPACE>/archive/news-digest/<DATE>/json/`
  当天归档的 `summary.json`。
- `<WORKSPACE>/archive/news-digest/<DATE>/markdown/`
  当天 Markdown 摘要归档目录。
- `<WORKSPACE>/archive/news-digest/<DATE>/meta/`
  当天运行诊断元数据目录。

## 主流程

唯一推荐入口。不要改写步骤，不要额外解析内部 JSON：

```bash
uv run <SKILL_DIR>/scripts/run-pipeline.py \
  --defaults <SKILL_DIR>/config/defaults \
  --config <WORKSPACE>/config \
  --archive-dir <WORKSPACE>/archive/news-digest \
  --hours 48 \
  --output /tmp/summary.json \
  --verbose --force
```

- 同一台机器上不要并发运行多个摘要任务；`/tmp/summary.json` 是固定路径，并发运行会互相覆盖
- `run-pipeline.py` 耗时较长；如果运行环境支持 **subagent** 后台代理或长任务执行，应优先用它来执行这个脚本，再等待结果返回
- 允许足够长的执行时间：
  - 单步骤 timeout 默认可到 `1800s`
  - 整体通常在 `10-30` 分钟内完成
  - 不要因为几分钟内没有新输出就中断或误判失败
- 运行完成后只读取 `/tmp/summary.json`

这里的 `<DATE>` 表示本次运行对应的日期目录，格式固定为 `YYYY-MM-DD`，例如 `2026-03-29`。

## 诊断与检查

查看当前运行诊断：

```bash
uv run <SKILL_DIR>/scripts/source-health.py --input-dir <WORKSPACE>/archive/news-digest/<DATE>/meta --verbose
```

查看最近 7 天历史诊断：

```bash
uv run <SKILL_DIR>/scripts/source-health.py --input-dir <WORKSPACE>/archive/news-digest --verbose
```

校验配置：

```bash
uv run <SKILL_DIR>/scripts/validate-config.py --verbose
```

## 定时任务

当用户要求添加定时任务时：
- 引用 `references/digest-prompt.md`
- 不要复制其中的脚本流程
- 使用 `references/automation-template.md` 作为模板

## 参考文档

- `references/digest-prompt.md`
  大模型执行摘要时使用的固定提示模板
- `references/automation-template.md`
  每日 / 每周定时任务模板

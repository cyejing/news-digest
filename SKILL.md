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
    - config/defaults/: 默认配置
    - references/: 摘要模板与参考文档
    - scripts/: 管道脚本
    - <workspace>/config/: 工作区覆盖配置
    - <workspace>/archive/news-digest/json/: 历史摘要 JSON 归档
  write:
    - /tmp/: 默认 summary JSON 输出与临时 debug 目录
    - <workspace>/archive/news-digest/json/: summary JSON 归档
    - <workspace>/archive/news-digest/markdown/: Markdown 摘要归档
---

# News Digest

这个 skill 的目标是让大模型稳定执行一条固定主流程，而不是自行拼接抓取步骤。

## 唯一推荐主流程

运行统一管道：

```bash
uv run scripts/run-pipeline.py \
  --config workspace/config \
  --hours 48 \
  --archive-dir workspace/archive/news-digest/json \
  --output /tmp/news-digest-summary.json \
  --verbose --force
```

说明：
- `--output` 必填，用来指定最终 `summary.json` 的输出路径
- `--archive-dir` 指向历史 `summary.json` 归档目录
- 大模型后续只读取 `--output` 指向的 `summary.json`
- 不要直接读取运行目录中的内部 JSON 中间文件

## 大模型应如何使用

1. 先阅读 `references/digest-prompt.md`
2. 只执行一次 `run-pipeline.py`
3. 只读取 `--output` 指向的 `summary.json`
4. 按 `digest-prompt.md` 写最终 Markdown 摘要

## 查看历史健康

当用户要求查看 source 历史健康情况时，执行：

```bash
uv run scripts/source-health.py --input-dir /tmp/news-digest --verbose
```

说明：
- 该命令会读取当前 `/tmp/news-digest` 下已有的抓取结果，更新历史健康记录
- 历史健康数据默认保存在 `/tmp/news-digest-source-health.json`
- 如果用户只想看当前累计历史，不想再次更新记录，执行：

```bash
uv run scripts/source-health.py --report-only --verbose
```

- 执行后应向用户汇报：当前 tracked source 总数、异常 source 数量，以及失败率较高的 source

## 定时任务

当用户要求添加定时任务时：
- 定时任务内容应引用 `references/digest-prompt.md`
- 不要把管道步骤复制进定时任务提示词
- 使用 `references/automation-template.md` 作为模板

## 更多说明

- 详细命令和调试方法见 `references/commands.md`
- 定时任务模板见 `references/automation-template.md`

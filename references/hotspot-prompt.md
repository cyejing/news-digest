# 热点提示模板

这个文档是全球科技与 AI 热点任务的执行契约，负责定义占位符、subagent 执行流程、主会话交付约束、归档规则，以及失败后的恢复方式。

## Subagent 强制执行约束

- `run-pipeline.py` 是长耗时任务，通常需要 `15-30` 分钟
- 必须使用 subagent 运行；如果当前环境没有 subagent，再考虑其他后台代理或长任务执行方式
- subagent 的超时时间必须设置为 `30` 分钟
- subagent 只负责执行脚本并等待归档文件生成；归档 Markdown 的读取、翻译和最终面向用户的输出由主会话负责
- 同一台机器上不要并发运行多个热点任务

## 占位符

| 占位符                | daily        | weekly    |
|--------------------|--------------|-----------|
| `<MODE>`           | `daily`      | `weekly`  |
| `<RSS_HOURS>`      | `48`         | `168`     |
| `<EXTRA_SECTIONS>` | *(无)*        | `📊 每周趋势总结` |
| `<WORKSPACE>`      | 工作区路径        | 工作区路径     |
| `<SKILL_DIR>`      | skill 安装路径   | skill 安装路径 |
| `<DATE>`           | `YYYY-MM-DD` | `YYYY-MM-DD` |
| `<LANGUAGE>`       | `Chinese`    | `Chinese` |

## 执行前确认

未满足以下任一项时，不要启动任务：

- 当前没有其他热点任务正在同机运行
- `<WORKSPACE>`、`<SKILL_DIR>`、`<DATE>` 已经明确
- subagent 超时时间已经设置为 `30` 分钟；如果当前环境没有 subagent，再切换到其他长任务执行方式

## 执行流程

1. 运行统一管道：

```bash
uv run <SKILL_DIR>/scripts/run-pipeline.py \
  --defaults <SKILL_DIR>/config/defaults \
  --config <WORKSPACE>/config \
  --archive <WORKSPACE>/archive/news-hotspots \
  --mode <MODE> \
  --hours <RSS_HOURS> \
  --verbose --force
```

2. 等待脚本完成，并确认归档产物已经生成：
    - `<WORKSPACE>/archive/news-hotspots/<DATE>/json/<MODE>*.json`
    - `<WORKSPACE>/archive/news-hotspots/<DATE>/markdown/<MODE>*.md`
    - `<WORKSPACE>/archive/news-hotspots/<DATE>/meta/*.meta.json`
3. 归档文件存在后，subagent 即可结束；不要在 subagent 内继续读取生成的 Markdown 或执行最终翻译输出

## Subagent 成功条件

满足以下全部条件，subagent 任务才算完成：

- 至少存在一个归档后的 `<MODE>*.json`
- 至少存在一个归档后的 `<MODE>*.md`
- JSON 与 Markdown 文件名后缀一致
- 满足以上归档条件后，subagent 可以直接返回归档路径并结束

## 仅主会话适用的用户输出约束

以下约束只适用于主会话整理最终回复时；subagent 不执行这些步骤：

- 最终输出必须使用 `<LANGUAGE>` 语言；不要保留英文正文作为最终交付
- 输出必须基于归档 Markdown 正文，先做等量翻译，再按原 Markdown 结构输出
- 翻译时只能转换语言，不能做摘要、精选、删减、改写结构或合并条目
- 每个 topic 不能减少
- 每个 topic 下的 item 不能减少
- Markdown 结构、标题层级、列表结构、链接格式不能变
- `daily` 模式下，必须把归档 Markdown 的全部文字内容完整翻译成 `<LANGUAGE>`；除语言转换外，不允许新增、删除或改写内容
- `weekly` 模式下，必须先把归档 Markdown 正文完整翻译成 `<LANGUAGE>`，正文部分除语言转换外不能改动；只允许在文末追加 `<EXTRA_SECTIONS>`
- `weekly` 模式下，`<EXTRA_SECTIONS>` 必须基于历史记录生成“每周趋势总结”，概括本周热点变化、重复主题和来源趋势
- 如果平台单条消息长度受限，可以分段连续输出，但不能省略任何 topic 或 item

## 主会话成功条件

- 主会话基于归档 Markdown 完成最终输出
- 最终输出满足上面的“仅主会话适用的用户输出约束”

## 失败与恢复

- 外部超时或中断后，先运行：

```bash
uv run <SKILL_DIR>/scripts/source-health.py \
  --input <WORKSPACE>/archive/news-hotspots/<DATE>/meta \
  --verbose
```

- 如果只是个别 fetch 步骤失败、超时或缺失结果，但已有部分抓取结果文件存在，可以继续补跑：

```bash
uv run <SKILL_DIR>/scripts/merge-sources.py \
  --archive <WORKSPACE>/archive/news-hotspots \
  --output <WORKSPACE>/.../debug/merged.json \
  [仅传入当前已经存在的 fetch 输出文件]
```

```bash
uv run <SKILL_DIR>/scripts/merge-hotspots.py \
  --input <WORKSPACE>/.../debug/merged.json \
  --archive <WORKSPACE>/archive/news-hotspots \
  --debug <WORKSPACE>/.../debug \
  --mode <MODE>
```

- 如果恢复后已有完整归档 Markdown：
    - `daily` 把归档 Markdown 的全部文字内容完整翻译成 `<LANGUAGE>` 后输出
    - `weekly` 先把归档 Markdown 正文完整翻译成 `<LANGUAGE>`，再在文末追加 `<EXTRA_SECTIONS>`
- 如果恢复后仍没有完整 Markdown，只能向用户报告实际完成情况和未完成步骤，不能伪造完整热点结果

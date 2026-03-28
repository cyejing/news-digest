# 摘要提示模板

使用前替换 `<...>` 占位符。

## 占位符

| 占位符 | daily | weekly |
|--------|-------|--------|
| `<MODE>` | `daily` | `weekly` |
| `<RSS_HOURS>` | `48` | `168` |
| `<ITEMS_PER_SECTION>` | `3-5` | `10-15` |
| `<EXTRA_SECTIONS>` | *(无)* | `📊 每周趋势总结` |
| `<WORKSPACE>` | 工作区路径 | |
| `<SKILL_DIR>` | skill 安装路径 | |
| `<DATE>` | YYYY-MM-DD | |
| `<LANGUAGE>` | `Chinese` | |

生成 **<DATE>** 的 <MODE> 全球科技与 AI 摘要。使用 `<DATE>` 作为报告日期，不要推断。

## 执行步骤

1. 读取配置：
   - `<WORKSPACE>/config/news-digest-sources.json`，否则回退 `<SKILL_DIR>/config/defaults/sources.json`
   - `<WORKSPACE>/config/news-digest-topics.json`，否则回退 `<SKILL_DIR>/config/defaults/topics.json`
2. 运行统一管道：
   ```bash
   uv run <SKILL_DIR>/scripts/run-pipeline.py \
     --config <WORKSPACE>/config \
     --hours <RSS_HOURS> \
     --archive-dir <WORKSPACE>/archive/news-digest/json \
     --output <WORKSPACE>/archive/news-digest/json/<MODE>-<DATE>.json \
      --verbose --force
   ```
3. 只读取：
   - `<WORKSPACE>/archive/news-digest/json/<MODE>-<DATE>.json`
4. 根据 `summary.json` 写 Markdown 摘要，并保存到：
   - `<WORKSPACE>/archive/news-digest/markdown/<MODE>-<DATE>.md`

## 写作规则

- 只根据 `summary.json` 选材，不要自己重新打分或重排
- 使用 `summary.json` 中的 topic 顺序和 item 排序
- Markdown 按 topic 分类输出
- 每条至少包含：emoji、评分、标题、链接、来源
- 若 `metrics` 中有 likes/comments/replies/retweets/score，则一并展示
- 优先使用活跃感较强的 emoji，例如 `🔥` `🚀` `🧠` `⚠️` `💬`
- 分数可四舍五入到 1 位小数
- 执行摘要写 2-4 句，突出最重要的 3-5 条故事
- 每个主题选前 `<ITEMS_PER_SECTION>` 条
- `<EXTRA_SECTIONS>` 只有在 weekly 时输出
- 使用 `<LANGUAGE>` 撰写全文

## 输出与归档

- 最终只输出 Markdown 摘要
- 将 Markdown 保存到 `<WORKSPACE>/archive/news-digest/markdown/<MODE>-<DATE>.md`
- 不执行内置投递逻辑

## 禁止事项

- 不要直接读取运行目录中的内部 JSON 中间文件
- 不要编写临时 Python 去解析内部 JSON
- 不要手动再执行一次 `merge-summarize.py`，除非 pipeline 明确失败且 `summary.json` 不存在
- 不要复制或改写脚本流程
- 不要使用旧 topic 名称或已废弃变量

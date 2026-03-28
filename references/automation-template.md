# 定时任务模板

这个文件只负责给定时任务注入默认参数。

- 具体执行流程、脚本步骤、输入输出约束，都以 `digest-prompt.md` 为准
- 定时任务提示词只需要引用 `digest-prompt.md`，不要复制其中的流程说明

## 每日摘要

```text
阅读 <SKILL_DIR>/references/digest-prompt.md，并使用以下占位符生成每日摘要：

- MODE = daily
- RSS_HOURS = 48
- EXTRA_SECTIONS = (无)
- WORKSPACE = <你的工作区路径>
- SKILL_DIR = <你的 skill 安装路径>
- DATE = YYYY-MM-DD
- LANGUAGE = Chinese
```

## 每周摘要

```text
阅读 <SKILL_DIR>/references/digest-prompt.md，并使用以下占位符生成每周摘要：

- MODE = weekly
- RSS_HOURS = 168
- EXTRA_SECTIONS = 📊 每周趋势总结
- WORKSPACE = <你的工作区路径>
- SKILL_DIR = <你的 skill 安装路径>
- DATE = YYYY-MM-DD
- LANGUAGE = Chinese
```

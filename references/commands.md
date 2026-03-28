# 外部命令参考

## 完整管道

```bash
uv run scripts/run-pipeline.py \
  --config workspace/config \
  --hours 48 \
  --archive-dir workspace/archive/news-digest/json \
  --output /tmp/news-digest-summary.json \
  --verbose --force
```

- `--output` 必填，用来指定 `summary.json` 输出路径
- `--debug-dir` 可选，不传时过程文件默认写到临时目录
- `--defaults` 默认就是 `config/defaults`

## 配置校验

```bash
uv run scripts/validate-config.py --defaults config/defaults --config workspace/config --verbose
```

## 逐源体检

```bash
uv run tests/check-sources.py --types rss
uv run tests/check-sources.py --types github
uv run tests/check-sources.py --types api
uv run tests/check-sources.py --ids simonwillison-rss
```

## 查看结果

```bash
cat /tmp/news-digest-summary.json
cat <debug-dir>/pipeline.meta.json
```

维护者调试命令见 [AGENTS.md](/Users/chenyejing/project/news-digest/AGENTS.md)。

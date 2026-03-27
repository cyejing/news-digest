# 科技摘要 PDF 模板

专业 PDF 输出，支持中文排版、emoji 图标和 A4 布局。

## 生成

使用 `generate-pdf.py` 从 markdown 报告生成 PDF:

```bash
python3 scripts/generate-pdf.py --input /tmp/td-report.md --output /tmp/td-digest.pdf
```

## 前置条件

- **weasyprint**: `pip install weasyprint`
- **中文字体**: `apt install fonts-noto-cjk` (Noto Sans CJK SC)

## 工作流程

1. 首先生成 **markdown 格式** 的摘要 (与 Discord 模板输出相同)
2. 将 markdown 保存到临时文件 (如 `/tmp/td-report.md`)
3. 运行 `generate-pdf.py` 转换为 PDF
4. 可选: 将 PDF 附加到 Discord 或邮件

## 特性

- **A4 布局**，边距 2cm/2.5cm
- **Noto Sans CJK SC** 字体，原生中文渲染
- **Emoji 支持** — 分区图标 (🧠🤖💰🔬) 正确渲染
- **页眉页脚** — "Tech Digest" 页眉，页码
- **蓝色主题配色** — 标题、链接、引用块边框
- **引用块摘要** — 高亮显示的执行摘要区域
- **来源链接** — 紧凑，位于每条目下方
- **响应式项目列表** — 清晰缩进

## Markdown 输入示例

PDF 生成器接受与 Discord 模板相同的 markdown 格式:

```markdown
# 🚀 科技日报 - 2026-02-25

> 今日要闻：OpenAI 发布新模型，Anthropic 推出 Claude 4...

## 🧠 LLM / 大语言模型

• **OpenAI 发布 GPT-5** — 全新推理能力突破
  <https://openai.com/blog/gpt5>

• **Anthropic Claude 4 上线** — 更强的代码能力
  <https://anthropic.com/claude-4>

## 💰 Crypto / 区块链

• **以太坊 Pectra 升级完成** — EIP-7702 正式上线
  <https://ethereum.org/pectra>

---
📊 数据源: RSS 180 | Twitter 98 | Reddit 45 | Web 20 | GitHub 15
🤖 由 tech-news-digest v3.9.1 生成
```

## 投递

```bash
# 生成 PDF
python3 scripts/generate-pdf.py -i /tmp/td-report.md -o /tmp/td-digest.pdf

# 附加到 Discord
# (使用 message 工具的 filePath 参数)

# 附加到邮件
mail -a /tmp/td-digest.pdf -s "科技摘要" recipient@example.com < /dev/null
```

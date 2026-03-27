# 科技摘要邮件模板

HTML 邮件格式，针对 Gmail/Outlook 渲染优化。

## 投递

通过 `gog gmail send` 发送，使用 `--body-html` 标志:
```bash
gog gmail send --to '<EMAIL>' --subject '<SUBJECT>' --body-html '<HTML_CONTENT>'
```

**重要**: 使用 `--body-html`，而非 `--body`。纯文本 markdown 在邮件客户端中无法正确渲染。

## 模板结构

Agent 应生成 HTML 邮件正文。使用内联样式 (邮件客户端会剥离 `<style>` 块)。

```html
<div style="max-width:640px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;line-height:1.6">

  <h1 style="font-size:22px;border-bottom:2px solid #e5e5e5;padding-bottom:8px">
    🐉 {{TITLE}}
  </h1>

  <!-- 可选: 每周执行摘要 -->
  <p style="color:#555;font-size:14px;background:#f8f9fa;padding:12px;border-radius:6px">
    {{SUMMARY}}
  </p>

  <!-- 主题分区 -->
  <h2 style="font-size:17px;margin-top:24px;color:#333">{{emoji}} {{label}}</h2>
  <ul style="padding-left:20px">
    <li style="margin-bottom:10px">
      <strong>🔥{{quality_score}}</strong> {{title}} — {{description}}
      <br><a href="{{link}}" style="color:#0969da;font-size:13px">{{link}}</a>
    </li>
  </ul>

  <!-- 每个主题重复 -->

  <!-- KOL 分区: 从 twitter JSON 数据读取指标 (metrics.impression_count, reply_count, retweet_count, like_count)。每条推文一个 <li>。 -->
  <h2 style="font-size:17px;margin-top:24px;color:#333">📢 KOL 动态</h2>
  <ul style="padding-left:20px">
    <li style="margin-bottom:10px">
      <strong>{{display_name}}</strong> (@{{handle}}) — {{summary}}
      <br><code style="font-size:12px;color:#888;background:#f4f4f4;padding:2px 6px;border-radius:3px">👁 {{views}} | 💬 {{replies}} | 🔁 {{retweets}} | ❤️ {{likes}}</code>
      <br><a href="{{tweet_link}}" style="color:#0969da;font-size:13px">{{tweet_link}}</a>
    </li>
  </ul>

  <!-- Twitter/X 热门分区: 每条目必须包含至少一个参考链接 -->
  <h2 style="font-size:17px;margin-top:24px;color:#333">🔥 社区热议</h2>
  <ul style="padding-left:20px">
    <li style="margin-bottom:10px">
      <strong>{{trending_topic}}</strong> — {{summary}}
      <br><a href="{{reference_link}}" style="color:#0969da;font-size:13px">{{reference_link}}</a>
    </li>
  </ul>

  <!-- 博客 / 发布分区 -->

  <!-- 页脚 -->
  <hr style="border:none;border-top:1px solid #e5e5e5;margin:24px 0">
  <p style="font-size:12px;color:#888">
    📊 数据源: RSS {{rss_count}} | Twitter {{twitter_count}} | Reddit {{reddit_count}} | Web {{web_count}} | GitHub {{github_count}} 发布 | 去重后: {{merged_count}} 篇文章
    <br>🤖 由 <a href="https://github.com/draco-agent/tech-news-digest" style="color:#0969da">tech-news-digest</a> v{{version}} 生成 | Powered by <a href="https://openclaw.ai" style="color:#0969da">OpenClaw</a>
  </p>

</div>
```

## 样式指南

- **最大宽度**: 640px 居中 (移动端友好)
- **字体**: 系统字体栈 (邮件中不使用 web 字体)
- **所有样式内联**: 邮件客户端会剥离 `<style>` 标签
- **链接**: 使用完整 URL，样式为 `color:#0969da`
- **标题**: h1 用于标题 (22px)，h2 用于主题 (17px)
- **列表**: `<ul>` 配合 `<li>`，适当间距
- **页脚**: 小号灰色文字，带统计信息
- **无图片**: 纯文本/HTML 以最大化兼容性
- **不用表格布局**: 使用 div + 内联样式

## 输出示例

```html
<div style="max-width:640px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;line-height:1.6">

  <h1 style="font-size:22px;border-bottom:2px solid #e5e5e5;padding-bottom:8px">
    🐉 每日科技摘要 — 2026-02-15
  </h1>

  <h2 style="font-size:17px;margin-top:24px;color:#333">🧠 LLM / 大语言模型</h2>
  <ul style="padding-left:20px">
    <li style="margin-bottom:10px">
      <strong>GPT-5.2 首次实现理论物理发现</strong> — 与 IAS、剑桥、哈佛合作研究胶子相互作用
      <br><a href="https://twitter.com/OpenAI/status/2022390096625078389" style="color:#0969da;font-size:13px">twitter.com/OpenAI</a>
    </li>
    <li style="margin-bottom:10px">
      <strong>字节跳动发布豆包 2.0</strong> — Agent、图像、视频全面升级
      <br><a href="https://www.jiqizhixin.com/articles/2026-02-14-9" style="color:#0969da;font-size:13px">jiqizhixin.com</a>
    </li>
    <li style="margin-bottom:10px">
      <strong>Dario Amodei: 指数增长接近尾声</strong> — Anthropic CEO 深度访谈
      <br><a href="https://www.dwarkesh.com/p/dario-amodei-2" style="color:#0969da;font-size:13px">dwarkesh.com</a>
    </li>
  </ul>

  <h2 style="font-size:17px;margin-top:24px;color:#333">🤖 AI Agent</h2>
  <ul style="padding-left:20px">
    <li style="margin-bottom:10px">
      <strong>斯坦福 AI Town 创业公司融资 1 亿美元</strong> — Fei-Fei Li、Karpathy 参投
      <br><a href="https://www.qbitai.com/2026/02/380347.html" style="color:#0969da;font-size:13px">qbitai.com</a>
    </li>
  </ul>

  <h2 style="font-size:17px;margin-top:24px;color:#333">💰 加密货币</h2>
  <ul style="padding-left:20px">
    <li style="margin-bottom:10px">
      <strong>X 将推出加密货币和股票交易</strong> — Smart Cashtags 功能即将上线
      <br><a href="https://www.theblock.co/post/389952" style="color:#0969da;font-size:13px">theblock.co</a>
    </li>
  </ul>

  <hr style="border:none;border-top:1px solid #e5e5e5;margin:24px 0">
  <p style="font-size:12px;color:#888">
    📊 数据源: RSS 287 | Twitter 71 | Reddit 45 | Web 60 | GitHub 29 发布 | 去重后: 140 篇文章
    <br>由 Tech News Digest 生成
  </p>

</div>
```

# YouTube RSS Monitor

自动监控指定的 YouTube 频道，获取最新视频，通过 `yt-dlp` 和 `youtube-transcript-api` 双重保障提取字幕，使用 AI（DeepSeek/OpenAI）生成高质量中文摘要和大纲，并自动推送到钉钉群。

## ✨ 功能特点

- 📡 **自动监控**：定期检查 RSS 源获取最新视频，支持多频道管理。
- 📝 **双重字幕提取**：优先使用 `yt-dlp` 提取官方/自动字幕，失败时自动降级使用 `youtube-transcript-api`。
- 🤖 **智能 AI 摘要**：支持长视频内容分块处理，生成详细的中文摘要和结构化大纲。
- 🛡️ **反爬虫增强**：内置 Cookie 支持（文件/浏览器），智能识别 HTML 拦截响应并自动重试。
- 📨 **精美推送**：通过钉钉机器人发送 Markdown 格式的图文消息。
- 💾 **数据持久化**：使用 SQLite 数据库记录已处理视频，防止重复推送。
- 🚀 **GitHub Actions**：支持自动化部署和定时运行，配置简单。

## 📂 项目结构

```
.
├── youtube_rss_monitor.py    # 主程序入口
├── youtube_rss_config.json   # 配置文件
├── requirements.txt          # 项目依赖
├── utils/                    # 核心功能模块
│   ├── models.py             # 数据模型定义
│   ├── rss.py                # RSS 解析器
│   ├── transcript.py         # 字幕提取器 (含反爬虫逻辑)
│   ├── ai.py                 # AI 摘要生成器
│   ├── dingtalk.py           # 钉钉推送客户端
│   └── db.py                 # 数据库管理器
└── .github/workflows/        # GitHub Actions 自动运行配置
```

## 🛠️ 安装部署

### 本地运行

1. **克隆仓库**
   ```bash
   git clone <your-repo-url>
   cd youtube-rss-monitor
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置**
   修改 `youtube_rss_config.json` 文件：
   - 填入 DeepSeek 或 OpenAI 的 `api_key`。
   - 配置钉钉机器人的 `webhook_url`。
   - 在 `channels` 列表中添加要监控的 YouTube 频道。

4. **运行程序**

   *   **持续监控模式**（每隔一段时间检查一次）：
       ```bash
       python youtube_rss_monitor.py
       ```
   
   *   **单次运行模式**（检查一次后退出，适合 Crontab 或测试）：
       ```bash
       python youtube_rss_monitor.py --once
       ```

   *   **添加新频道**：
       ```bash
       python youtube_rss_monitor.py --add-channel "频道名称" "频道URL"
       ```

### GitHub Actions 自动运行

本项目已配置好 GitHub Actions (`.github/workflows/schedule.yml`)，可实现云端定时自动运行。

1. **Fork 本仓库** 到你的 GitHub 账号。
2. **配置 Secrets**：
   在仓库 Settings -> Secrets and variables -> Actions 中添加以下 Secrets（环境变量会覆盖配置文件）：
   - `DEEPSEEK_API_KEY`: 你的 AI API Key
   - `DINGTALK_WEBHOOK`: 钉钉机器人 Webhook URL
   - `DINGTALK_SECRET`: (可选) 钉钉机器人加签密钥
3. **启用 Actions**：
   - 进入 Actions 页面，启用 Workflow。
   - 默认每 6 小时运行一次。
4. **权限设置**：
   - 确保 Workflow 有权限提交代码（用于更新数据库）：Settings -> Actions -> General -> Workflow permissions -> 选择 **Read and write permissions**。

## ⚙️ 配置说明 (`youtube_rss_config.json`)

```json
{
  "ai_summary": {
    "api_key": "sk-xxxxxxxx",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat"
  },
  "subtitle_options": {
    "cookie_file": "www.youtube.com_cookies.txt", // 本地 Cookie 文件路径
    "browser_cookies": "chrome"                   // 本地运行时可直接调用浏览器 Cookie
  },
  "monitor_settings": {
    "check_interval_seconds": 21600,              // 持续监控模式下的检查间隔
    "max_videos_per_check": 5                     // 每次每个频道最多处理的新视频数
  }
}
```

## ❓ 常见问题解决

### 字幕下载失败 / 反爬虫拦截 (Sign in to confirm...)
如果你在日志中看到 HTML 内容警告或无法获取字幕，通常是因为 YouTube 的反爬虫机制。

**解决方法 1：使用浏览器 Cookies (本地运行推荐)**
修改配置中的 `browser_cookies` 字段，填入你已登录 YouTube 的浏览器名称（如 `chrome`, `edge`, `firefox`）。
```json
"subtitle_options": {
    "browser_cookies": "chrome"
}
```

**解决方法 2：使用 Cookie 文件 (服务器/GitHub Actions 推荐)**
1. 在浏览器中安装 "Get cookies.txt LOCALLY" 插件。
2. 登录 YouTube，导出 cookies 为 `www.youtube.com_cookies.txt`。
3. 将文件放在项目根目录。
4. 确保配置文件中 `cookie_file` 指向该文件名。

## License

MIT

# YouTube RSS Monitor

自动监控指定的YouTube频道，获取最新视频，通过yt-dlp/API提取字幕，使用AI（DeepSeek/OpenAI）生成摘要和大纲，并推送到钉钉群。

## 功能特点

- 📡 **自动监控**：定期检查RSS源获取最新视频
- 📝 **字幕提取**：支持 `yt-dlp` 和 `youtube-transcript-api` 双重保障
- 🤖 **AI摘要**：使用DeepSeek/ChatGPT生成高质量中文摘要和大纲
- 🛡️ **反爬虫处理**：智能处理HTML拦截和请求限制
- 📨 **钉钉推送**：格式美观的Markdown消息推送

## 安装部署

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
   复制 `youtube_rss_config.sample.json` 为 `youtube_rss_config.json` 并修改配置：
   - 添加你的 DeepSeek/OpenAI API Key
   - 配置 钉钉机器人 Webhook
   - 添加要监控的 YouTube 频道列表

4. **运行**
   ```bash
   python youtube_rss_monitor.py
   ```

### GitHub Actions 自动运行

本项目支持通过 GitHub Actions 进行定时自动运行。

1. **Fork 本仓库**
2. **配置 Secrets**：
   在仓库 Settings -> Secrets and variables -> Actions 中添加以下 Secrets：
   - `DEEPSEEK_API_KEY`: AI API Key
   - `DINGTALK_WEBHOOK`: 钉钉机器人 Webhook URL
   - `DINGTALK_SECRET`: (可选) 钉钉机器人加签密钥

3. **配置频道列表**：
   修改仓库中的 `youtube_rss_config.json`，填入你需要监控的频道信息。注意不要在文件中直接提交 API Key。

   ```json
   {
     "channels": [
       {
         "name": "频道名称",
         "channel_url": "https://www.youtube.com/@频道ID"
       }
     ],
     "check_interval_hours": 6,
     "max_videos_per_check": 5
   }
   ```

4. **定时任务**：
   默认配置为每6小时运行一次（可在 `.github/workflows/schedule.yml` 中修改 cron 表达式）。

## 依赖要求

- Python 3.8+
- yt-dlp
- requests
- openai
- youtube-transcript-api

## 注意事项

- 首次运行时会创建 `youtube_rss_monitor.db` 数据库文件。
- GitHub Actions 每次运行环境是独立的，因此数据库不会持久化保存。这意味着**每次运行都会被视为首次运行**，或者需要配置 Artifacts/Cache 来持久化数据库（本项目当前配置适合无状态运行或每次只抓取最新视频）。
- *建议*：如果需要记录已处理过的视频以避免重复推送，建议使用 **GitHub Actions Cache** 或 **将数据库提交回仓库**（不推荐），或者改用 **Git 提交更新后的数据库** 的方式。

**当前 GitHub Actions 策略**：
本仓库已配置自动工作流 (`.github/workflows/schedule.yml`)。每次运行结束后，会自动将更新后的数据库文件 (`youtube_rss_monitor.db`) 提交回仓库。
这意味着：
1. **防止重复推送**：通过持久化数据库，确保已处理的视频不会再次推送。
2. **权限设置**：请确保仓库的 Actions 权限已开启读写权限 (Settings -> Actions -> General -> Workflow permissions -> Select "Read and write permissions")。

## License

MIT

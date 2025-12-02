# 部署到 GitHub 指南

要让这个程序在 GitHub 上自动每天运行，请按照以下步骤操作：

## 1. 创建仓库并上传代码
将当前目录下的所有文件上传到你的 GitHub 仓库中。确保包含以下关键文件：
- `.github/workflows/schedule.yml` (自动运行配置)
- `youtube_rss_monitor.py` (主程序)
- `requirements.txt` (依赖列表)
- `youtube_rss_config.json` (基础配置)
- `youtube_rss.db` (数据库文件 - **重要**：这是你的进度存档，必须上传，否则第一次运行会重置)

## 2. 配置 Secrets (环境变量)
为了安全起见，API Key 和钉钉 Webhook 不会直接写在代码里，而是通过 GitHub Secrets 注入。

1. 进入你的 GitHub 仓库页面。
2. 点击上方的 **Settings** (设置)。
3. 在左侧菜单找到 **Secrets and variables** -> **Actions**。
4. 点击 **New repository secret**，依次添加以下变量：

| Name (变量名) | Value (值/示例) | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | `sk-f0da4ec56a...` | 你的 DeepSeek 或 OpenAI API Key |
| `OPENAI_API_BASE` | `https://api.deepseek.com` | (可选) 如果用 DeepSeek 必填 |
| `DINGTALK_WEBHOOK` | `https://oapi.dingtalk.com/robot/send?access_token=...` | 钉钉机器人的 Webhook URL |
| `DINGTALK_SECRET` | `SEC...` | (可选) 钉钉机器人的加签密钥 |

## 3. 检查运行状态
- 配置好后，点击仓库上方的 **Actions** 标签。
- 你会在左侧看到 "Daily YouTube RSS Monitor"。
- 它是设定为每天 UTC 0:00 (北京时间 8:00) 自动运行。
- 你也可以点击右侧的 **Run workflow** 按钮手动触发一次测试。

## 常见问题
- **数据库如何同步？**
  每次运行结束后，Action 会自动将更新后的 `youtube_rss.db` 提交回仓库。这样第二天运行时，它就知道昨天推送到哪了。
- **如何修改监控频道？**
  直接在本地修改 `youtube_rss_config.json`，或者使用 SQL 工具修改 `youtube_rss.db`，然后提交到 GitHub 即可。

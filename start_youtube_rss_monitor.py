#!/usr/bin/env python3
"""YouTube RSS监控启动脚本"""

import os
import sys
import json
import logging


def check_dependencies() -> bool:
    """Ensure required third-party libraries are available."""
    missing_deps = []

    try:
        import requests  # noqa: F401
    except ImportError:
        missing_deps.append("requests")

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        missing_deps.append("yt-dlp")

    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        missing_deps.append("youtube-transcript-api")

    try:
        import openai  # noqa: F401
    except ImportError:
        print("警告: openai未安装，将无法生成AI摘要")
        print("安装命令: pip install openai")

    if missing_deps:
        print(f"缺少必要依赖: {', '.join(missing_deps)}")
        print("请运行 pip install " + " ".join(missing_deps))
        return False

    return True


def check_config() -> bool:
    """Verify the presence and validity of the monitor config file."""
    config_path = "youtube_rss_config.json"

    if not os.path.exists(config_path):
        print(f"配置文件不存在: {config_path}")
        print("程序将创建示例配置文件，请编辑后重新运行")
        return False

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if not config.get("channels"):
            print("警告: 未配置任何频道")
            return False

        if not config.get("deepseek_api_key") or config["deepseek_api_key"] == "your_deepseek_api_key_here":
            print("警告: 未配置DeepSeek API密钥，将跳过AI摘要生成")

        return True

    except Exception as exc:  # pylint: disable=broad-except
        print(f"配置文件格式错误: {exc}")
        return False


def main():
    """Entry point for the YouTube RSS monitor bootstrap."""
    print("YouTube RSS监控系统启动检查...")

    if not check_dependencies():
        sys.exit(1)

    if not check_config():
        # 如果配置不存在，先创建示例配置
        try:
            from youtube_rss_monitor import YouTubeRSSMonitor  # pylint: disable=import-error

            YouTubeRSSMonitor()
            print("已创建示例配置文件，请编辑 youtube_rss_config.json 后重新运行")
            return
        except Exception as exc:  # pylint: disable=broad-except
            print(f"创建配置文件失败: {exc}")
            sys.exit(1)

    try:
        from youtube_rss_monitor import main as monitor_main  # pylint: disable=import-error

        monitor_main()
    except Exception as exc:  # pylint: disable=broad-except
        print(f"运行失败: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
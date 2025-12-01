#!/usr/bin/env python3
"""
YouTube RSS监控模块 - 主程序
负责编排监控、字幕提取、AI摘要和消息推送流程
"""

import os
import json
import logging
import argparse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from utils.models import YouTubeChannel, VideoInfo
from utils.rss import YouTubeRSSParser
from utils.transcript import TranscriptExtractor
from utils.ai import AIContentProcessor
from utils.dingtalk import DingTalkClient
from utils.db import DBManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("youtube_rss_monitor.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class YouTubeMonitor:
    """YouTube监控主类"""
    
    def __init__(self, config_path: str = "youtube_rss_config.json"):
        self.config = self._load_config(config_path)
        self.db_manager = DBManager(self.config.get("db_path", "youtube_rss.db"))
        self.rss_parser = YouTubeRSSParser()
        
        # 初始化各个组件
        self.transcript_extractor = TranscriptExtractor(self.config.get("subtitle_options"))
        
        ai_config = self.config.get("ai_summary", {})
        self.ai_processor = AIContentProcessor(
            api_key=ai_config.get("api_key", ""),
            base_url=ai_config.get("base_url", "https://api.deepseek.com"),
            model=ai_config.get("model", "deepseek-chat"),
            options=ai_config
        )
        
        ding_config = self.config.get("dingtalk", {})
        self.ding_client = DingTalkClient(
            webhook_url=ding_config.get("webhook_url", ""),
            secret=ding_config.get("secret")
        )
        self.ding_enabled = ding_config.get("enabled", False)
        
        # 监控配置
        monitor_config = self.config.get("monitor_settings", {})
        self.check_interval = monitor_config.get("check_interval_seconds", 3600)
        self.max_videos = monitor_config.get("max_videos_per_check", 5)
        
        # 初始化频道列表
        self._init_channels()
        
    def _load_config(self, config_path: str) -> Dict:
        """加载配置，支持环境变量覆盖"""
        if not os.path.exists(config_path):
            logging.error(f"配置文件不存在: {config_path}")
            return {}
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 环境变量覆盖 (用于GitHub Actions等场景)
            # AI配置
            if os.environ.get("OPENAI_API_KEY"):
                config.setdefault("ai_summary", {})["api_key"] = os.environ["OPENAI_API_KEY"]
            elif os.environ.get("DEEPSEEK_API_KEY"):
                config.setdefault("ai_summary", {})["api_key"] = os.environ["DEEPSEEK_API_KEY"]
                
            if os.environ.get("OPENAI_API_BASE"):
                config["ai_summary"]["base_url"] = os.environ["OPENAI_API_BASE"]
                
            # 钉钉配置
            if os.environ.get("DINGTALK_WEBHOOK"):
                config.setdefault("dingtalk", {})["webhook_url"] = os.environ["DINGTALK_WEBHOOK"]
            if os.environ.get("DINGTALK_SECRET"):
                config.setdefault("dingtalk", {})["secret"] = os.environ["DINGTALK_SECRET"]
                
            # Cookie配置
            if os.environ.get("YOUTUBE_COOKIES_FILE"):
                config.setdefault("subtitle_options", {})["cookie_file"] = os.environ["YOUTUBE_COOKIES_FILE"]
            if os.environ.get("YOUTUBE_BROWSER_COOKIES"):
                config.setdefault("subtitle_options", {})["browser_cookies"] = os.environ["YOUTUBE_BROWSER_COOKIES"]

            return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return {}

    def _init_channels(self):
        """初始化频道列表，从配置加载到数据库"""
        channels_config = self.config.get("channels", [])
        for ch_conf in channels_config:
            # 检查数据库中是否已存在
            channel_id = ch_conf.get("id")
            if not channel_id and ch_conf.get("url"):
                # 尝试从URL获取ID
                channel_id = self.rss_parser.get_channel_id_from_url(ch_conf["url"])
            
            if channel_id:
                existing = self.db_manager.get_channel(channel_id)
                if not existing:
                    # 新增频道
                    rss_url = self.rss_parser.get_rss_url(channel_id)
                    channel = YouTubeChannel(
                        name=ch_conf.get("name", "Unknown"),
                        channel_id=channel_id,
                        rss_url=rss_url,
                        description=ch_conf.get("description", ""),
                        last_check=datetime.now().isoformat()
                    )
                    self.db_manager.save_channel(channel)
                    logging.info(f"初始化频道: {channel.name} ({channel_id})")
                else:
                    # 更新配置信息
                    existing.name = ch_conf.get("name", existing.name)
                    existing.description = ch_conf.get("description", existing.description)
                    self.db_manager.save_channel(existing)

    def add_channel_from_url(self, name: str, url: str, description: str = "") -> bool:
        """手动添加频道"""
        channel_id = self.rss_parser.get_channel_id_from_url(url)
        if not channel_id:
            logging.error(f"无法从URL解析频道ID: {url}")
            return False
            
        rss_url = self.rss_parser.get_rss_url(channel_id)
        channel = YouTubeChannel(
            name=name,
            channel_id=channel_id,
            rss_url=rss_url,
            description=description,
            last_check=datetime.now().isoformat()
        )
        self.db_manager.save_channel(channel)
        logging.info(f"成功添加频道: {name}")
        return True

    def run_once(self, force_test: bool = False):
        """执行一次完整的检查流程"""
        channels = self.db_manager.get_all_channels()
        logging.info(f"开始检查 {len(channels)} 个频道...")
        
        if force_test:
            logging.info(">>> 测试模式: 强制处理每个频道的最新视频，忽略历史记录 <<<")
            for channel in channels:
                self._process_channel_test_mode(channel)
            logging.info("测试模式执行完成")
            return

        is_first_run = self.db_manager.is_first_run()
        if is_first_run:
            logging.info("检测到首次运行，仅标记最新视频，不进行推送")
            
        for channel in channels:
            self._process_channel(channel, is_first_run)
            
        logging.info("检查完成")

    def _process_channel_test_mode(self, channel: YouTubeChannel):
        """测试模式：强制处理频道的最新一个视频"""
        logging.info(f"正在检查频道(测试模式): {channel.name}")
        try:
            videos = self.rss_parser.parse_rss_feed(channel.rss_url)
            if not videos:
                logging.warning(f"频道 {channel.name} 未获取到视频列表")
                return

            # 按发布时间排序（新到旧）并只取第一个
            videos.sort(key=lambda v: v.published_at, reverse=True)
            latest_video = videos[0]
            
            logging.info(f"测试模式 - 强制处理视频: {latest_video.title}")
            self._process_single_video(channel, latest_video, is_test=True)
            
        except Exception as e:
            logging.error(f"处理频道 {channel.name} 失败: {e}")

    def _process_channel(self, channel: YouTubeChannel, is_first_run: bool):
        """处理单个频道"""
        logging.info(f"正在检查频道: {channel.name}")
        
        try:
            videos = self.rss_parser.parse_rss_feed(channel.rss_url)
            if not videos:
                logging.warning(f"频道 {channel.name} 未获取到视频列表")
                return

            # 按发布时间排序（新到旧）
            videos.sort(key=lambda v: v.published_at, reverse=True)
            
            # 如果是首次运行，只记录最新的一个视频作为基准
            if is_first_run:
                if videos:
                    latest = videos[0]
                    self.db_manager.save_video(latest)
                    channel.last_video_id = latest.video_id
                    channel.last_update = latest.published_at
                    channel.last_check = datetime.now().isoformat()
                    self.db_manager.save_channel(channel)
                return

            # 获取上次处理的最新视频时间
            last_published_at = self.db_manager.get_latest_video_published_at_for_channel(channel.name)
            
            new_videos = []
            for video in videos:
                # 简单的去重检查
                if self.db_manager.video_exists(video.video_id):
                    continue
                
                # 必须晚于上次记录的时间
                if last_published_at and video.published_at <= last_published_at:
                    continue
                    
                new_videos.append(video)
            
            if not new_videos:
                logging.info(f"频道 {channel.name} 没有新视频")
                return
                
            logging.info(f"发现 {len(new_videos)} 个新视频")
            
            # 处理新视频
            # 限制每次处理的数量
            for video in new_videos[:self.max_videos]:
                self._process_single_video(channel, video)

            # 更新频道状态
            channel.last_check = datetime.now().isoformat()
            self.db_manager.save_channel(channel)
            
        except Exception as e:
            logging.error(f"处理频道 {channel.name} 失败: {e}")

    def _process_single_video(self, channel: YouTubeChannel, video: VideoInfo, is_test: bool = False):
        """处理单个视频的核心逻辑"""
        logging.info(f"开始处理视频: {video.title}")
        
        # 1. 获取字幕
        transcript = self.transcript_extractor.extract_transcript(video.video_id, video.video_url)
        if not transcript:
            logging.warning(f"视频 {video.title} 未能提取到字幕，跳过摘要生成")
            if not is_test: # 测试模式下即使没有字幕也尝试发送（虽然摘要为空）
                return
        
        video.transcript = transcript
        
        # 2. 生成AI摘要
        logging.info("正在生成AI摘要...")
        ai_result = self.ai_processor.generate_summary_and_outline(video.title, transcript)
        video.summary = ai_result.get("summary", "")
        video.outline = ai_result.get("outline", "")
        
        # 3. 推送钉钉
        if self.ding_enabled:
            logging.info("正在推送钉钉消息...")
            title_prefix = "[测试] " if is_test else ""
            success = self.ding_client.send_message(
                title=f"{title_prefix}{video.title}",
                text=f"## {title_prefix}{video.title}\n\n**发布时间**: {video.published_at}\n\n**频道**: {channel.name}\n\n**视频链接**: {video.video_url}\n\n### AI 摘要\n{video.summary}\n\n### 内容大纲\n{video.outline}",
                pic_url=f"https://img.youtube.com/vi/{video.video_id}/maxresdefault.jpg"
            )
            if success:
                logging.info("钉钉推送成功")
            else:
                logging.error("钉钉推送失败")
        
        # 4. 保存到数据库 (测试模式不保存，以免影响正常流程判定)
        if not is_test:
            self.db_manager.save_video(video)
            # 更新频道最新视频ID
            channel.last_video_id = video.video_id
            channel.last_update = video.published_at
            self.db_manager.save_channel(channel)

    def run_loop(self):
        """持续运行模式"""
        logging.info("启动持续监控模式...")
        while True:
            try:
                self.run_once()
                logging.info(f"休眠 {self.check_interval} 秒...")
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                logging.info("用户停止运行")
                break
            except Exception as e:
                logging.error(f"运行循环出错: {e}")
                time.sleep(60)  # 出错后等待一分钟再试

def main():
    parser = argparse.ArgumentParser(description="YouTube RSS 监控工具")
    parser.add_argument("-c", "--config", default="youtube_rss_config.json", help="配置文件路径")
    parser.add_argument("--add-channel", nargs=2, metavar=('NAME', 'URL'), help="添加新频道: --add-channel \"Name\" \"URL\"")
    parser.add_argument("--once", action="store_true", help="仅运行一次检查")
    parser.add_argument("--test", action="store_true", help="测试模式：强制处理每个频道的最新视频，不保存状态")
    
    args = parser.parse_args()
    
    monitor = YouTubeMonitor(args.config)
    
    if args.add_channel:
        name, url = args.add_channel
        monitor.add_channel_from_url(name, url)
        return
        
    if args.once or args.test:
        monitor.run_once(force_test=args.test)
    else:
        monitor.run_loop()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
YouTube RSS监控模块
使用RSS订阅监控YouTube频道更新，无需API密钥
"""

import os
import json
import time
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Sequence
import sqlite3
from dataclasses import dataclass
import hashlib
import re
from utils.dingtalk import DingTalkClient
from utils.ai import AIContentProcessor
from urllib.parse import parse_qs, urlparse
from http.cookiejar import MozillaCookieJar

# 字幕提取相关
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    logging.warning("yt-dlp库未安装，请运行: pip install yt-dlp")

# AI API相关
try:
    import openai
    AI_API_AVAILABLE = True
except ImportError:
    AI_API_AVAILABLE = False
    logging.warning("OpenAI库未安装，请运行: pip install openai")

# youtube_transcript_api 相关
try:
    from youtube_transcript_api import (  # type: ignore
        YouTubeTranscriptApi,
        TranscriptsDisabled,
        NoTranscriptFound,
    )
    YT_TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    YT_TRANSCRIPT_API_AVAILABLE = False
    logging.warning("youtube-transcript-api库未安装，请运行: pip install youtube-transcript-api")

@dataclass
class YouTubeChannel:
    """YouTube频道信息"""
    name: str
    channel_id: str
    rss_url: str
    description: str
    last_video_id: str = ""
    last_check: str = ""
    last_update: str = ""

@dataclass
class VideoInfo:
    """视频信息"""
    video_id: str
    title: str
    description: str
    published_at: str
    channel_name: str
    video_url: str
    transcript: str = ""
    summary: str = ""
    outline: str = ""

class YouTubeRSSParser:
    """YouTube RSS解析器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_channel_id_from_url(self, channel_url: str) -> Optional[str]:
        """从频道URL提取频道ID"""
        try:
            # 确保URL有协议前缀
            if not channel_url.startswith(('http://', 'https://')):
                channel_url = 'https://' + channel_url
            
            if '/channel/' in channel_url:
                return channel_url.split('/channel/')[-1].split('/')[0]
            elif '/@' in channel_url:
                # 需要通过页面解析获取频道ID
                return self._get_channel_id_from_handle(channel_url)
            elif '/c/' in channel_url or '/user/' in channel_url:
                # 需要通过页面解析获取频道ID
                return self._get_channel_id_from_custom_url(channel_url)
        except Exception as e:
            logging.error(f"提取频道ID失败: {e}")
        return None
    
    def _get_channel_id_from_handle(self, channel_url: str) -> Optional[str]:
        """从@handle格式的URL获取频道ID"""
        try:
            # 确保URL有协议前缀
            if not channel_url.startswith(('http://', 'https://')):
                channel_url = 'https://' + channel_url
            
            logging.info(f"正在获取频道ID: {channel_url}")
            
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.session.get(channel_url, timeout=30, headers=headers)
            logging.info(f"HTTP状态码: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                logging.info(f"页面内容长度: {len(content)}")
                
                # 查找页面中的频道ID - 尝试多种模式
                import re
                
                # 模式1: "channelId":"UCxxxxxx"
                match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]+)"', content)
                if match:
                    channel_id = match.group(1)
                    logging.info(f"找到频道ID (模式1): {channel_id}")
                    return channel_id
                
                # 模式2: "externalId":"UCxxxxxx"
                match = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]+)"', content)
                if match:
                    channel_id = match.group(1)
                    logging.info(f"找到频道ID (模式2): {channel_id}")
                    return channel_id
                
                # 模式3: channel/UCxxxxxx
                match = re.search(r'/channel/(UC[a-zA-Z0-9_-]+)', content)
                if match:
                    channel_id = match.group(1)
                    logging.info(f"找到频道ID (模式3): {channel_id}")
                    return channel_id
                
                # 如果都没找到，记录部分页面内容用于调试
                logging.warning("未找到频道ID，页面内容片段:")
                logging.warning(content[:500] + "..." if len(content) > 500 else content)
                
            else:
                logging.error(f"HTTP请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            logging.error(f"从handle获取频道ID失败: {e}")
        return None
    
    def _get_channel_id_from_custom_url(self, channel_url: str) -> Optional[str]:
        """从自定义URL获取频道ID"""
        try:
            # 确保URL有协议前缀
            if not channel_url.startswith(('http://', 'https://')):
                channel_url = 'https://' + channel_url
            
            logging.info(f"正在获取自定义URL频道ID: {channel_url}")
            
            # 设置请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = self.session.get(channel_url, timeout=30, headers=headers)
            logging.info(f"HTTP状态码: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                logging.info(f"页面内容长度: {len(content)}")
                
                # 查找频道ID - 尝试多种模式
                import re
                
                # 模式1: "channelId":"UCxxxxxx"
                match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]+)"', content)
                if match:
                    channel_id = match.group(1)
                    logging.info(f"找到频道ID (模式1): {channel_id}")
                    return channel_id
                
                # 模式2: "externalId":"UCxxxxxx"
                match = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]+)"', content)
                if match:
                    channel_id = match.group(1)
                    logging.info(f"找到频道ID (模式2): {channel_id}")
                    return channel_id
                
                # 模式3: channel/UCxxxxxx
                match = re.search(r'/channel/(UC[a-zA-Z0-9_-]+)', content)
                if match:
                    channel_id = match.group(1)
                    logging.info(f"找到频道ID (模式3): {channel_id}")
                    return channel_id
                
                # 如果都没找到，记录部分页面内容用于调试
                logging.warning("未找到频道ID，页面内容片段:")
                logging.warning(content[:500] + "..." if len(content) > 500 else content)
                
            else:
                logging.error(f"HTTP请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            logging.error(f"从自定义URL获取频道ID失败: {e}")
        return None
    
    def get_rss_url(self, channel_id: str) -> str:
        """生成RSS订阅URL"""
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    def parse_rss_feed(self, rss_url: str) -> List[VideoInfo]:
        """解析RSS订阅源"""
        try:
            response = self.session.get(rss_url, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            
            # 定义命名空间
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'yt': 'http://www.youtube.com/xml/schemas/2015',
                'media': 'http://search.yahoo.com/mrss/'
            }
            
            videos = []
            channel_name = ""
            
            # 获取频道名称
            title_elem = root.find('atom:title', namespaces)
            if title_elem is not None:
                channel_name = title_elem.text
            
            # 解析视频条目
            for entry in root.findall('atom:entry', namespaces):
                try:
                    video_id_elem = entry.find('yt:videoId', namespaces)
                    title_elem = entry.find('atom:title', namespaces)
                    published_elem = entry.find('atom:published', namespaces)
                    description_elem = entry.find('media:group/media:description', namespaces)
                    link_elem = entry.find('atom:link', namespaces)
                    
                    if video_id_elem is not None and title_elem is not None:
                        video_id = video_id_elem.text
                        title = title_elem.text
                        published_at = published_elem.text if published_elem is not None else ""
                        description = description_elem.text if description_elem is not None else ""
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        
                        video_info = VideoInfo(
                            video_id=video_id,
                            title=title,
                            description=description,
                            published_at=published_at,
                            channel_name=channel_name,
                            video_url=video_url
                        )
                        videos.append(video_info)
                        
                except Exception as e:
                    logging.error(f"解析视频条目失败: {e}")
                    continue
            
            return videos
            
        except Exception as e:
            logging.error(f"解析RSS订阅失败: {e}")
            return []

class TranscriptExtractor:
    """字幕提取器，负责最大化可用字幕的获取成功率"""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.allow_auto = self.config.get("allow_automatic_subtitles", True)
        self.prefer_manual = self.config.get("prefer_manual_subtitles", True)
        self.max_retries = max(1, int(self.config.get("max_retries", 2)))
        self.retry_wait = max(1, int(self.config.get("retry_wait_seconds", 3)))
        self.request_timeout = int(self.config.get("request_timeout", 30))
        self.proxy = self.config.get("proxy") or None
        self.cookie_file = self._prepare_cookie_file(self.config.get("cookie_file"))
        self.languages = self._expand_langs(self.config.get("languages", ["zh", "en"]))
        self.use_transcript_api = self.config.get("use_transcript_api", True)
        self.transcript_api_translate_to = self.config.get("transcript_api_auto_translate_to")
        self.transcript_api_languages = self._expand_langs(
            self.config.get("transcript_api_preferred_languages", self.languages)
        )

        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        extra_headers = self.config.get("http_headers") or {}
        if isinstance(extra_headers, dict):
            self.session.headers.update(extra_headers)
        if self.proxy:
            self.session.proxies.update({
                "http": self.proxy,
                "https": self.proxy
            })

        if self.cookie_file:
            self._load_cookies(self.cookie_file)

        if not YT_DLP_AVAILABLE:
            logging.warning("yt-dlp不可用，无法提取字幕")

    def extract_transcript(self, video_id: str, languages: Optional[List[str]] = None) -> str:
        """提取视频字幕"""
        preferred_langs = self._expand_langs(languages or self.languages)

        if not self.enabled:
            return ""

        tracks_sources: List[Dict[str, List[Dict]]] = []
        if YT_DLP_AVAILABLE:
            logging.info(f"尝试使用 yt-dlp 获取字幕: {video_id}")
            info = self._fetch_metadata_with_yt_dlp(video_id, preferred_langs)
            if info:
                manual_tracks = info.get("subtitles") or {}
                auto_tracks = info.get("automatic_captions") or {}
                if manual_tracks and self.prefer_manual:
                    tracks_sources.append(manual_tracks)
                if auto_tracks and self.allow_auto:
                    tracks_sources.append(auto_tracks)
                if not tracks_sources and manual_tracks:
                    tracks_sources.append(manual_tracks)
                if not tracks_sources and auto_tracks:
                    tracks_sources.append(auto_tracks)
            else:
                logging.warning(f"yt-dlp 未能获取到元数据: {video_id}")

        for tracks in tracks_sources:
            text = self._extract_from_tracks(tracks, preferred_langs)
            if text:
                logging.info(f"yt-dlp 成功提取字幕，长度: {len(text)}")
                return text

        logging.info(f"yt-dlp 提取失败或无字幕，尝试 fallback 方案: {video_id}")
        return self._fallback_transcript_api(video_id, preferred_langs)

    def _fetch_metadata_with_yt_dlp(self, video_id: str, languages: List[str]) -> Optional[Dict]:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "nocheckcertificate": True,
            "user_agent": self.session.headers.get("User-Agent"),
            "http_headers": dict(self.session.headers),
            "subtitlesformat": "vtt",
            "subtitleslangs": languages,
            "writesubtitles": True,
            "writeautomaticsub": True,
        }
        if self.cookie_file:
            ydl_opts["cookiefile"] = self.cookie_file
        if self.proxy:
            ydl_opts["proxy"] = self.proxy

        for attempt in range(self.max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(video_url, download=False)
            except Exception as exc:  # noqa: BLE001
                logging.warning(
                    "yt-dlp字幕元数据获取失败（第%s次尝试）: %s", attempt + 1, exc
                )
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_wait)
        return None

    def _extract_from_tracks(self, tracks: Dict[str, List[Dict]], preferred_langs: List[str]) -> str:
        if not tracks:
            return ""

        chosen_lang = self._choose_language(list(tracks.keys()), preferred_langs)
        if not chosen_lang:
            chosen_lang = next(iter(tracks.keys()), None)
            if not chosen_lang:
                return ""

        formats = tracks.get(chosen_lang, [])
        chosen_fmt = self._select_format(formats)
        if not chosen_fmt:
            return ""

        text = self._download_subtitle_file(chosen_fmt.get("url"))
        if not text:
            return ""

        return self._normalize_subtitle_text(text, chosen_fmt.get("ext"))

    def _download_subtitle_file(self, url: Optional[str]) -> str:
        if not url:
            return ""
        cleaned_url = self._strip_range_param(url)

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(cleaned_url, timeout=self.request_timeout)
                resp.raise_for_status()
                text = resp.text
                
                # 检查是否为HTML页面（反爬虫拦截）
                if text.lstrip().startswith("<!DOCTYPE html") or "<html" in text.lower():
                    logging.warning(
                        "下载的内容疑似HTML页面而非字幕（第%s次尝试），可能是反爬虫拦截", 
                        attempt + 1
                    )
                    if attempt + 1 < self.max_retries:
                        time.sleep(self.retry_wait)
                    continue

                if text.lstrip().startswith("#EXTM3U"):
                    merged = self._merge_m3u_playlist(text, cleaned_url)
                    if merged:
                        text = merged
                return text
            except Exception as exc:  # noqa: BLE001
                logging.warning(
                    "字幕下载失败（第%s次尝试）: %s", attempt + 1, exc
                )
                if attempt + 1 < self.max_retries:
                    time.sleep(self.retry_wait)
        return ""

    def _normalize_subtitle_text(self, text: str, ext: Optional[str]) -> str:
        stripped = text.lstrip()
        if stripped.startswith("WEBVTT") or (ext and ext.lower() == "vtt"):
            return self._parse_vtt_to_text(text)
        if ext and ext.lower() == "srt":
            return self._parse_srt_to_text(text)
        return self._parse_vtt_to_text(text)
    
    def _expand_langs(self, languages: Sequence[str]) -> List[str]:
        base = [l.lower() for l in languages]
        zh_variants = ["zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw"]
        en_variants = ["en", "en-us", "en-uk"]
        expanded = []
        for l in base:
            if l.startswith("zh"):
                expanded.extend(zh_variants)
            elif l.startswith("en"):
                expanded.extend(en_variants)
            else:
                expanded.append(l)
        # 去重并保持顺序
        seen, result = set(), []
        for l in expanded:
            if l not in seen:
                seen.add(l)
                result.append(l)
        return result

    def _choose_language(self, available: List[str], preferred: List[str]) -> Optional[str]:
        av_lower = {a.lower(): a for a in available}
        # 精确匹配
        for p in preferred:
            if p in av_lower:
                return av_lower[p]
        # 模糊匹配（zh/zh-开头）
        for p in preferred:
            prefix = p.split("-")[0]
            for a in available:
                if a.lower().split("-")[0] == prefix:
                    return a
        return None

    def _strip_range_param(self, url: str) -> str:
        from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
        s = urlsplit(url)
        qs = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True) if k.lower() != "range"]
        return urlunsplit((s.scheme, s.netloc, s.path, urlencode(qs, doseq=True), s.fragment))

    def _merge_m3u_playlist(self, m3u_text: str, base_url: str) -> str:
        from urllib.parse import urljoin
        segment_urls = []
        for line in m3u_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            segment_urls.append(urljoin(base_url, line))
        segments = []
        for u in segment_urls:
            u2 = self._strip_range_param(u)
            try:
                r = self.session.get(u2, timeout=self.request_timeout)
                if r.ok:
                    segments.append(r.text)
            except Exception:
                continue
        # 合并并移除重复的 WEBVTT 头
        combined = []
        for idx, t in enumerate(segments):
            lines = t.splitlines()
            if lines and lines[0].strip().upper().startswith("WEBVTT"):
                lines = lines[1:]
            combined.extend(lines)
        return "\n".join(combined)

    def _parse_vtt_to_text(self, vtt: str) -> str:
        lines = []
        for ln in vtt.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.upper().startswith("WEBVTT") or s.upper().startswith("NOTE"):
                continue
            if "-->" in s:
                continue
            if s.isdigit():
                continue
            lines.append(s)
        return " ".join(lines)

    def _parse_srt_to_text(self, srt: str) -> str:
        lines = []
        for ln in srt.splitlines():
            s = ln.strip()
            if not s:
                continue
            if "-->" in s:
                continue
            if s.isdigit():
                continue
            lines.append(s)
        return " ".join(lines)

    def _select_format(self, formats: List[Dict]) -> Optional[Dict]:
        if not formats:
            return None
        for preferred_ext in ("vtt", "srt"):
            for fmt in formats:
                if fmt.get("ext") == preferred_ext and fmt.get("url"):
                    return fmt
        for fmt in formats:
            if fmt.get("url"):
                return fmt
        return None

    def _fallback_transcript_api(self, video_id: str, preferred_langs: List[str]) -> str:
        if not self.use_transcript_api or not YT_TRANSCRIPT_API_AVAILABLE:
            return ""

        try:
            # 实例化 API 对象 (v1.2.3+ 版本需要)
            yt_api = YouTubeTranscriptApi()
            transcript_list = yt_api.list(video_id)
        except (TranscriptsDisabled, NoTranscriptFound):
            return ""
        except Exception as exc:  # noqa: BLE001
            logging.warning("youtube_transcript_api不可用: %s", exc)
            return ""

        # 优先按偏好语言查找
        search_languages = preferred_langs or self.transcript_api_languages
        for lang in search_languages:
            try:
                transcript = transcript_list.find_transcript([lang])
                # fetch() 返回 FetchedTranscript 对象，需要转换为字典列表
                fetched = transcript.fetch()
                # 兼容不同版本，如果返回的是对象则调用 to_raw_data()
                if hasattr(fetched, 'to_raw_data'):
                    data = fetched.to_raw_data()
                else:
                    data = fetched
                text = self._entries_to_text(data)
                if text:
                    return text
            except Exception:
                continue

        # 自动翻译兜底
        target_lang = self.transcript_api_translate_to
        if target_lang:
            for transcript in transcript_list:
                if not getattr(transcript, "is_translatable", False):
                    continue
                try:
                    translated = transcript.translate(target_lang)
                    fetched = translated.fetch()
                    if hasattr(fetched, 'to_raw_data'):
                        data = fetched.to_raw_data()
                    else:
                        data = fetched
                    text = self._entries_to_text(data)
                    if text:
                        return text
                except Exception:
                    continue

        # 最后尝试列表中的任意字幕
        for transcript in transcript_list:
            try:
                fetched = transcript.fetch()
                if hasattr(fetched, 'to_raw_data'):
                    data = fetched.to_raw_data()
                else:
                    data = fetched
                text = self._entries_to_text(data)
                if text:
                    return text
            except Exception:
                continue

        return ""

    def _entries_to_text(self, entries: List[Dict]) -> str:
        return " ".join(e.get("text", "").strip() for e in entries if e.get("text"))

    def _prepare_cookie_file(self, cookie_file: Optional[str]) -> Optional[str]:
        if not cookie_file:
            return None
        path = os.path.abspath(cookie_file)
        if os.path.exists(path):
            return path
        logging.warning("指定的cookie文件不存在: %s", path)
        return None

    def _load_cookies(self, cookie_file: str) -> None:
        try:
            jar = MozillaCookieJar(cookie_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies.update(jar)
        except Exception as exc:  # noqa: BLE001
            logging.warning("加载cookie文件失败: %s", exc)

class DingTalkNotifier(DingTalkClient):
    """钉钉推送通知器"""
    
    def send_message(self, videos: List[VideoInfo], at_all: bool = False, at_mobiles: List[str] = None) -> bool:
        """
        发送钉钉消息
        
        Args:
            videos: 视频信息列表
            at_all: 是否@所有人
            at_mobiles: 要@的手机号列表
            
        Returns:
            bool: 发送是否成功
        """
        if not videos:
            return True
            
        # 构建消息内容
        content = "## 📺 YouTube新视频推送\n\n"
        MAX_BYTES = 18000  # 钉钉限制20000字节，预留一些空间
        
        for video in videos:
            video_content = ""
            video_content += f"### {video.title}\n\n"
            video_content += f"**🎬 频道：** {video.channel_name}\n\n"
            video_content += f"**⏰ 发布时间：** {video.published_at}\n\n"
            video_content += f"**🔗 视频链接：** [点击观看]({video.video_url})\n\n"
            
            if video.summary:
                video_content += f"**📝 AI摘要：**\n\n{video.summary}\n\n"
            
            video_content += "---\n\n"
            
            # 检查是否超出长度限制
            if len((content + video_content).encode('utf-8')) > MAX_BYTES:
                # 如果单个视频内容就超长，需要截断摘要
                if len(video_content.encode('utf-8')) > MAX_BYTES:
                    limit = MAX_BYTES - len(content.encode('utf-8')) - 100
                    if limit > 500:
                        video_content = video_content[:limit] + "...\n\n(内容过长已截断)"
                    else:
                        logging.warning("消息内容过长，跳过部分视频推送")
                        continue
                else:
                    # 如果加上这个视频超长，就先发送当前的，剩下的下次循环（这里简单处理，直接分批发送会更复杂，
                    # 暂时先截断，因为max_videos_per_check=1通常不会触发）
                    logging.warning("消息内容接近上限，停止添加更多视频")
                    break
            
            content += video_content
        
        return self.send_markdown("YouTube新视频推送", content, at_all, at_mobiles)

class YouTubeDatabaseManager:
    """YouTube数据库管理器"""
    
    def __init__(self, db_path: str = "youtube_rss_monitor.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建频道表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS youtube_channels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        channel_id TEXT UNIQUE NOT NULL,
                        rss_url TEXT NOT NULL,
                        description TEXT,
                        last_video_id TEXT,
                        last_check TEXT,
                        last_update TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 创建视频表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS youtube_videos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        video_id TEXT UNIQUE NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        published_at TEXT,
                        channel_name TEXT,
                        video_url TEXT,
                        transcript TEXT,
                        summary TEXT,
                        outline TEXT,
                        processed_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                logging.info("数据库初始化完成")
                
        except Exception as e:
            logging.error(f"数据库初始化失败: {e}")
    
    def save_channel(self, channel: YouTubeChannel):
        """保存频道信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO youtube_channels 
                    (name, channel_id, rss_url, description, last_video_id, last_check, last_update)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    channel.name, channel.channel_id, channel.rss_url,
                    channel.description, channel.last_video_id,
                    channel.last_check, channel.last_update
                ))
                conn.commit()
        except Exception as e:
            logging.error(f"保存频道信息失败: {e}")
    
    def get_channel(self, channel_id: str) -> Optional[YouTubeChannel]:
        """获取频道信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, channel_id, rss_url, description, 
                           last_video_id, last_check, last_update
                    FROM youtube_channels WHERE channel_id = ?
                ''', (channel_id,))
                
                row = cursor.fetchone()
                if row:
                    return YouTubeChannel(
                        name=row[0], channel_id=row[1], rss_url=row[2],
                        description=row[3], last_video_id=row[4],
                        last_check=row[5], last_update=row[6]
                    )
        except Exception as e:
            logging.error(f"获取频道信息失败: {e}")
        return None
    
    def save_video(self, video: VideoInfo):
        """保存视频信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO youtube_videos 
                    (video_id, title, description, published_at, channel_name, 
                     video_url, transcript, summary, outline)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    video.video_id, video.title, video.description,
                    video.published_at, video.channel_name, video.video_url,
                    video.transcript, video.summary, video.outline
                ))
                conn.commit()
        except Exception as e:
            logging.error(f"保存视频信息失败: {e}")
    
    def is_first_run(self) -> bool:
        """检查是否为首次运行（数据库中没有任何视频记录）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM youtube_videos")
                count = cursor.fetchone()[0]
                return count == 0
        except Exception as e:
            logging.error(f"检查首次运行状态失败: {e}")
            return True  # 出错时默认认为是首次运行
    
    def is_channel_first_run(self, channel_name: str) -> bool:
        """检查指定频道是否为首次运行（该频道没有任何视频记录，或频道未记录最近视频）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 条件1：视频表中没有该频道的视频
                cursor.execute("SELECT COUNT(*) FROM youtube_videos WHERE channel_name = ?", (channel_name,))
                count = cursor.fetchone()[0]
                if count > 0:
                    return False

                # 条件2：频道表存在该频道，但尚未记录last_video_id（说明还没成功处理过视频）
                cursor.execute("SELECT last_video_id FROM youtube_channels WHERE name = ?", (channel_name,))
                row = cursor.fetchone()
                if row is None:
                    # 频道记录不存在，视为首次运行
                    return True
                last_video_id = row[0]
                return (last_video_id is None) or (last_video_id == "")

        except Exception as e:
            logging.error(f"检查频道首次运行状态失败: {e}")
            return True  # 出错时默认认为是首次运行
    
    def get_latest_video_published_at_for_channel(self, channel_name: str) -> Optional[str]:
        """获取指定频道在数据库中最新的视频发布时间"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT published_at FROM youtube_videos 
                    WHERE channel_name = ? 
                    ORDER BY published_at DESC 
                    LIMIT 1
                """, (channel_name,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logging.error(f"获取频道最新视频发布时间失败: {e}")
            return None
    
    def video_exists(self, video_id: str) -> bool:
        """检查视频是否已存在"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM youtube_videos WHERE video_id = ?', (video_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logging.error(f"检查视频存在性失败: {e}")
            return False

class YouTubeRSSMonitor:
    """YouTube RSS监控器主类"""
    
    def __init__(self, config_path: str = "youtube_rss_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # 初始化组件
        self.rss_parser = YouTubeRSSParser()
        self.subtitle_config = self._build_subtitle_config()
        self.transcript_extractor = TranscriptExtractor(self.subtitle_config)
        self.db_manager = YouTubeDatabaseManager()
        
        # 初始化AI处理器
        self.ai_processor = None
        if self.config.get('deepseek_api_key'):
            self.ai_processor = AIContentProcessor(
                api_key=self.config['deepseek_api_key'],
                base_url=self.config.get('ai_base_url', 'https://api.deepseek.com'),
                model=self.config.get('ai_model', 'deepseek-chat'),
                options=self.config.get('ai_options')
            )
        
        # 初始化钉钉推送器
        self.dingtalk_notifier = None
        dingtalk_config = self.config.get('dingtalk', {})
        if dingtalk_config.get('enabled') and dingtalk_config.get('webhook_url'):
            self.dingtalk_notifier = DingTalkNotifier(
                webhook_url=dingtalk_config['webhook_url'],
                secret=dingtalk_config.get('secret')
            )
    
    def _load_config(self) -> Dict:
        """加载配置文件，支持环境变量覆盖"""
        config = self._get_default_config()
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config.update(json.load(f))
            except Exception as e:
                logging.error(f"加载配置文件失败: {e}")
        
        # 环境变量覆盖
        if os.environ.get('DEEPSEEK_API_KEY'):
            config['deepseek_api_key'] = os.environ['DEEPSEEK_API_KEY']
        if os.environ.get('AI_BASE_URL'):
            config['ai_base_url'] = os.environ['AI_BASE_URL']
        if os.environ.get('AI_MODEL'):
            config['ai_model'] = os.environ['AI_MODEL']
            
        if os.environ.get('DINGTALK_WEBHOOK'):
            if 'dingtalk' not in config:
                config['dingtalk'] = {'enabled': True}
            config['dingtalk']['webhook_url'] = os.environ['DINGTALK_WEBHOOK']
            config['dingtalk']['enabled'] = True
            
        if os.environ.get('DINGTALK_SECRET'):
            if 'dingtalk' not in config:
                config['dingtalk'] = {'enabled': True}
            config['dingtalk']['secret'] = os.environ['DINGTALK_SECRET']

        return config
    
    def _create_sample_config(self):
        """创建示例配置文件"""
        sample_config = {
            "deepseek_api_key": "your_deepseek_api_key_here",
            "ai_base_url": "https://api.deepseek.com",
            "ai_model": "deepseek-chat",
            "check_interval_hours": 6,
            "max_videos_per_check": 5,
            "subtitle_languages": ["zh", "en"],
            "channels": [
                {
                    "name": "示例频道",
                    "channel_url": "https://www.youtube.com/@channelname",
                    "description": "频道描述"
                }
            ]
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(sample_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"创建配置文件失败: {e}")
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "check_interval_hours": 6,
            "max_videos_per_check": 5,
            "subtitle_languages": ["zh", "en"],
            "channels": []
        }

    def _build_subtitle_config(self) -> Dict:
        """合并旧版配置字段与新版字幕配置"""
        base = {
            "enabled": self.config.get("enable_subtitle_extraction", True),
            "languages": self.config.get("subtitle_languages", ["zh", "en"]),
            "allow_automatic_subtitles": self.config.get("allow_automatic_subtitles", True),
            "prefer_manual_subtitles": self.config.get("prefer_manual_subtitles", True),
            "max_retries": self.config.get("subtitle_max_retries", 3),
            "retry_wait_seconds": self.config.get("subtitle_retry_delay", 5),
            "request_timeout": self.config.get("subtitle_request_timeout", 30),
            "cookie_file": self.config.get("subtitle_cookie_file"),
            "proxy": self.config.get("subtitle_proxy"),
            "use_transcript_api": self.config.get("use_transcript_api", True),
            "transcript_api_auto_translate_to": self.config.get("transcript_api_auto_translate_to"),
            "transcript_api_preferred_languages": self.config.get(
                "transcript_api_preferred_languages", self.config.get("subtitle_languages", ["zh", "en"])
            ),
        }
        extra = self.config.get("subtitle_options", {})
        if isinstance(extra, dict):
            base.update({k: v for k, v in extra.items() if v is not None})
        return base
    
    def add_channel_from_url(self, name: str, channel_url: str, description: str = ""):
        """从URL添加频道"""
        channel_id = self.rss_parser.get_channel_id_from_url(channel_url)
        if not channel_id:
            logging.error(f"无法从URL获取频道ID: {channel_url}")
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
        logging.info(f"已添加频道: {name} ({channel_id})")
        return True
    
    def is_new_video(self, video: VideoInfo, channel_name: str) -> bool:
        """判断是否为新视频
        
        逻辑：
        1. 全新频道（首次运行）：该频道没有任何视频记录
        2. 已有频道：检查视频是否比数据库中最新的视频更新
        """
        # 检查数据库中是否存在该视频
        if self.db_manager.video_exists(video.video_id):
            return False
        
        # 检查是否为该频道的首次运行
        if self.db_manager.is_channel_first_run(channel_name):
            return True  # 全新频道，所有视频都算新视频
        
        # 已有频道：检查是否比最新视频更新
        latest_video_published_at = self.db_manager.get_latest_video_published_at_for_channel(channel_name)
        if not latest_video_published_at:
            return True  # 如果获取不到最新视频发布时间，认为是新视频
        
        # 比较发布时间，只有比数据库中最新视频更新的才算新视频
        try:
            from datetime import datetime
            video_time = datetime.fromisoformat(video.published_at.replace('Z', '+00:00'))
            latest_time = datetime.fromisoformat(latest_video_published_at.replace('Z', '+00:00'))
            return video_time > latest_time
        except Exception as e:
            logging.error(f"比较视频发布时间失败: {e}")
            return False  # 出错时保守处理，不认为是新视频
    
    def get_videos_to_process_for_channel(self, videos: List[VideoInfo], channel_name: str) -> List[VideoInfo]:
        """根据频道状态决定要处理的视频
        
        逻辑：
        1. 全新频道：只返回最新的1个视频
        2. 已有频道：返回所有新视频（发布时间比数据库中最新视频更新的视频）
        """
        if not videos:
            return []
        
        # 按发布时间排序（最新的在前）
        try:
            sorted_videos = sorted(videos, key=lambda v: v.published_at, reverse=True)
        except Exception as e:
            logging.error(f"排序视频失败: {e}")
            sorted_videos = videos
        
        # 检查是否为该频道的首次运行
        if self.db_manager.is_channel_first_run(channel_name):
            # 全新频道：只返回最新的1个视频
            return [sorted_videos[0]]
        else:
            # 已有频道：返回所有新视频（按时间顺序，但限制数量避免过多请求）
            new_videos = []
            max_videos = self.config.get('max_videos_per_check', 5)
            
            for video in sorted_videos:
                if len(new_videos) >= max_videos:
                    break
                if self.is_new_video(video, channel_name):
                    new_videos.append(video)
            
            # 按发布时间正序排列（旧的在前，新的在后），这样处理顺序更合理
            new_videos.sort(key=lambda v: v.published_at)
            return new_videos

    def check_updates(self) -> List[VideoInfo]:
        """检查所有频道的更新
        
        逻辑：
        1. 全新频道（首次运行）：每个频道只处理最新的1个视频
        2. 已有频道（后续运行）：检查比缓存更新的所有新视频
        """
        all_new_videos = []
        
        for i, channel_config in enumerate(self.config.get('channels', [])):
            try:
                # 添加频道间隔，避免触发反爬虫机制
                if i > 0:  # 第一个频道不需要等待
                    time.sleep(5)  # 每个频道之间等待5秒
                
                # 跳过没有配置channel_id且channel_url为空的频道
                if not channel_config.get('channel_id') and not channel_config.get('channel_url'):
                    logging.info(f"跳过未配置的频道: {channel_config['name']}")
                    continue
                
                # 优先使用channel_id，否则从URL获取
                channel_id = channel_config.get('channel_id')
                if not channel_id:
                    channel_id = self.rss_parser.get_channel_id_from_url(channel_config['channel_url'])
                    if not channel_id:
                        logging.error(f"无法获取频道ID: {channel_config['channel_url']}")
                        continue
                
                # 获取或创建频道记录
                channel = self.db_manager.get_channel(channel_id)
                if not channel:
                    rss_url = self.rss_parser.get_rss_url(channel_id)
                    channel = YouTubeChannel(
                        name=channel_config['name'],
                        channel_id=channel_id,
                        rss_url=rss_url,
                        description=channel_config.get('description', '')
                    )
                
                logging.info(f"检查频道: {channel.name}")
                
                # 解析RSS订阅
                videos = self.rss_parser.parse_rss_feed(channel.rss_url)
                if not videos:
                    logging.info(f"频道 {channel.name} 没有找到视频")
                    continue
                
                # 根据频道状态决定要处理的视频
                videos_to_process = self.get_videos_to_process_for_channel(videos, channel.name)
                
                if videos_to_process:
                    is_first_run = self.db_manager.is_channel_first_run(channel.name)
                    if is_first_run:
                        logging.info(f"全新频道 {channel.name}，处理最新视频: {videos_to_process[0].title}")
                    else:
                        logging.info(f"频道 {channel.name} 发现 {len(videos_to_process)} 个新视频")
                else:
                    logging.info(f"频道 {channel.name} 没有新视频")
                
                # 处理视频（提取字幕和生成摘要）
                new_videos = []
                for i, video in enumerate(videos_to_process):
                    try:
                        # 设置正确的频道名称（使用配置文件中的名称）
                        video.channel_name = channel.name
                        
                        # 添加请求间隔，避免触发反爬虫机制
                        if i > 0:  # 第一个视频不需要等待
                            time.sleep(5)  # 每个视频之间等待5秒
                        
                        # 提取字幕（如果启用）
                        if YT_DLP_AVAILABLE and self.config.get('enable_subtitle_extraction', True):
                            # 在字幕提取前增加延时
                            subtitle_delay = self.config.get('subtitle_request_delay', 5)
                            logging.info(f"等待{subtitle_delay}秒后开始字幕提取: {video.title}")
                            time.sleep(subtitle_delay)
                            
                            video.transcript = self.transcript_extractor.extract_transcript(
                                video.video_id,
                                self.subtitle_config.get('languages', ['zh', 'en'])
                            )
                            
                            # 如果字幕提取失败，再等待一段时间后重试一次
                            if not video.transcript:
                                retry_delay = self.config.get('subtitle_retry_delay', 10)
                                logging.info(f"首次字幕提取失败，等待{retry_delay}秒后重试: {video.title}")
                                time.sleep(retry_delay)
                                video.transcript = self.transcript_extractor.extract_transcript(
                                video.video_id,
                                self.subtitle_config.get('languages', ['zh', 'en'])
                            )
                        else:
                            logging.info(f"字幕提取已禁用，跳过: {video.title}")
                        
                        # 生成AI摘要（只有在有字幕的情况下）
                        if self.ai_processor and video.transcript:
                            ai_result = self.ai_processor.generate_summary_and_outline(
                                video.title, video.transcript
                            )
                            video.summary = ai_result['summary']
                            video.outline = ai_result['outline']
                        
                        # 保存到数据库
                        self.db_manager.save_video(video)
                        new_videos.append(video)
                        
                        logging.info(f"处理完成视频: {video.title}")
                        
                    except Exception as e:
                        logging.error(f"处理视频失败 {video.title}: {e}")
                        continue
                
                # 更新频道信息
                if new_videos:
                    channel.last_video_id = new_videos[0].video_id
                    channel.last_update = datetime.now().isoformat()
                
                channel.last_check = datetime.now().isoformat()
                self.db_manager.save_channel(channel)
                
                all_new_videos.extend(new_videos)
                
            except Exception as e:
                logging.error(f"检查频道更新失败: {e}")
                continue
        
        return all_new_videos
    
    def format_updates(self, videos: List[VideoInfo]) -> str:
        """格式化更新信息"""
        if not videos:
            return "没有发现新视频"
        
        output = []
        output.append("=" * 50)
        output.append(f"YouTube频道更新报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("=" * 50)
        output.append(f"发现 {len(videos)} 个新视频")
        output.append("")
        
        for i, video in enumerate(videos, 1):
            output.append(f"【视频 {i}】")
            output.append(f"标题: {video.title}")
            output.append(f"频道: {video.channel_name}")
            output.append(f"发布时间: {video.published_at}")
            output.append(f"链接: {video.video_url}")
            output.append("")
            
            if video.description:
                output.append("视频描述:")
                output.append(video.description[:200] + "..." if len(video.description) > 200 else video.description)
                output.append("")
            
            if video.transcript:
                output.append("字幕内容:")
                output.append(video.transcript[:500] + "..." if len(video.transcript) > 500 else video.transcript)
                output.append("")
            
            if video.summary:
                output.append("AI摘要:")
                output.append(video.summary)
                output.append("")
            
            if video.outline:
                output.append("内容大纲:")
                output.append(video.outline)
                output.append("")
            
            output.append("-" * 30)
            output.append("")
        
        return "\n".join(output)

def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('youtube_rss_monitor.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    try:
        # 初始化监控器
        monitor = YouTubeRSSMonitor()
        
        # 检查更新
        logging.info("开始检查YouTube频道更新...")
        new_videos = monitor.check_updates()
        
        # 格式化并保存结果
        formatted_updates = monitor.format_updates(new_videos)
        
        # 保存到文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"youtube_rss_updates_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(formatted_updates)
        
        logging.info(f"更新报告已保存到: {filename}")
        print(formatted_updates)
        
        # 发送钉钉通知
        if new_videos and monitor.dingtalk_notifier:
            try:
                dingtalk_config = monitor.config.get('dingtalk', {})
                success = monitor.dingtalk_notifier.send_message(
                    videos=new_videos,
                    at_all=dingtalk_config.get('at_all', False),
                    at_mobiles=dingtalk_config.get('at_mobiles', [])
                )
                if success:
                    logging.info("钉钉通知发送成功")
                else:
                    logging.warning("钉钉通知发送失败")
            except Exception as e:
                logging.error(f"发送钉钉通知时出错: {e}")
        elif new_videos:
            logging.info("有新视频但钉钉推送未配置")
        else:
            logging.info("没有新视频，跳过钉钉推送")
        
    except Exception as e:
        logging.error(f"程序运行失败: {e}")

if __name__ == "__main__":
    main()

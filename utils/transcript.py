import logging
import requests
import json
import time
import os
from typing import List, Dict, Optional, Any, Sequence
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit, urljoin
from http.cookiejar import MozillaCookieJar

# 字幕提取相关依赖检查
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    logging.warning("yt-dlp库未安装，请运行: pip install yt-dlp")

try:
    from youtube_transcript_api import (
        YouTubeTranscriptApi,
        TranscriptsDisabled,
        NoTranscriptFound,
    )
    YT_TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    YT_TRANSCRIPT_API_AVAILABLE = False
    logging.warning("youtube-transcript-api库未安装，请运行: pip install youtube-transcript-api")

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
        self.browser_cookies = self.config.get("browser_cookies")
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
        if self.browser_cookies:
            ydl_opts["cookiesfrombrowser"] = (self.browser_cookies,)
        
        if self.proxy:
            ydl_opts["proxy"] = self.proxy

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(video_url, download=False)
        except Exception as exc:
            logging.error(f"yt-dlp 获取元数据出错: {exc}")
            return None

    def _extract_from_tracks(self, tracks: Dict[str, List[Dict]], preferred_langs: List[str]) -> str:
        if not tracks:
            return ""

        # 1. 优先匹配 preferred_langs
        for lang in preferred_langs:
            for track_lang, formats in tracks.items():
                if track_lang == lang or track_lang.startswith(lang + "-"):
                    content = self._try_download_formats(formats)
                    if content:
                        return content

        # 2. 尝试 'en' (如果不在 preferred_langs 里)
        if "en" not in preferred_langs:
            for track_lang, formats in tracks.items():
                if track_lang.startswith("en"):
                    content = self._try_download_formats(formats)
                    if content:
                        return content

        # 3. 尝试任意可用字幕
        for track_lang, formats in tracks.items():
            content = self._try_download_formats(formats)
            if content:
                return content

        return ""

    def _try_download_formats(self, formats: List[Dict]) -> str:
        # 优先 VTT -> SRV3 -> SRV2 -> SRT
        priority = ["vtt", "srv3", "srv2", "srt"]
        sorted_formats = sorted(
            formats,
            key=lambda x: priority.index(x.get("ext", "")) if x.get("ext", "") in priority else 999
        )
        
        for fmt in sorted_formats:
            url = fmt.get("url")
            if not url:
                continue
            text = self._download_subtitle_file(url)
            if text:
                ext = fmt.get("ext", "vtt")
                if ext == "vtt":
                    return self._parse_vtt_to_text(text)
                if ext == "srt":
                    return self._parse_srt_to_text(text)
                # 简单处理其他格式，假设它们是纯文本或类似 VTT
                if "WEBVTT" in text[:100]:
                    return self._parse_vtt_to_text(text)
                return text # 兜底
        return ""

    def _download_subtitle_file(self, url: str) -> str:
        for _ in range(self.max_retries):
            try:
                resp = self.session.get(url, timeout=self.request_timeout)
                if resp.status_code == 200:
                    content = resp.text
                    # 检查是否包含HTML标签（反爬虫检测）
                    if "<html" in content.lower() or "<!doctype html" in content.lower():
                        logging.warning("下载字幕返回了HTML内容，可能是反爬虫拦截，跳过此格式")
                        return ""
                    return content
            except Exception:
                pass
            time.sleep(self.retry_wait)
        return ""

    def _parse_vtt_to_text(self, vtt: str) -> str:
        lines = []
        for ln in vtt.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.upper().startswith("WEBVTT"):
                continue
            if "-->" in s:
                continue
            if s.isdigit():
                continue
            # 去除 VTT 标签 <...>
            # 简单去除，不处理复杂的嵌套
            import re
            s = re.sub(r'<[^>]+>', '', s)
            lines.append(s)
        
        # 去重：VTT 经常有重复行
        deduped = []
        if lines:
            deduped.append(lines[0])
            for i in range(1, len(lines)):
                if lines[i] != lines[i-1]:
                    deduped.append(lines[i])
        return " ".join(deduped)

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

    def _fallback_transcript_api(self, video_id: str, preferred_langs: List[str]) -> str:
        if not self.use_transcript_api or not YT_TRANSCRIPT_API_AVAILABLE:
            return ""

        try:
            # 实例化 API 对象 (v1.2.3+ 版本需要)
            yt_api = YouTubeTranscriptApi()
            transcript_list = yt_api.list_transcripts(video_id)
        except (TranscriptsDisabled, NoTranscriptFound):
            return ""
        except AttributeError:
             # 兼容旧版本，如果 list_transcripts 不存在
             try:
                 # 尝试直接获取
                 return self._fallback_transcript_api_old(video_id, preferred_langs)
             except Exception as e:
                 logging.warning(f"youtube_transcript_api fallback 失败: {e}")
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
    
    def _fallback_transcript_api_old(self, video_id: str, preferred_langs: List[str]) -> str:
        """兼容旧版 youtube_transcript_api"""
        try:
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_langs)
            return self._entries_to_text(data)
        except Exception:
            return ""

    def _entries_to_text(self, entries: List[Dict]) -> str:
        if not entries:
            return ""
        lines = [e.get("text", "") for e in entries]
        return " ".join(lines)

    def _expand_langs(self, langs: Sequence[str]) -> List[str]:
        out = []
        for lg in langs:
            if lg == "zh":
                out.extend(["zh-Hans", "zh-Hant", "zh-CN", "zh-TW", "zh-HK"])
            out.append(lg)
        # 去重
        seen = set()
        res = []
        for x in out:
            if x not in seen:
                res.append(x)
                seen.add(x)
        return res

    def _prepare_cookie_file(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        if os.path.exists(path):
            return os.path.abspath(path)
        return None

    def _load_cookies(self, cookie_file: str) -> None:
        try:
            jar = MozillaCookieJar(cookie_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies.update(jar)
        except Exception as exc:  # noqa: BLE001
            logging.warning("加载cookie文件失败: %s", exc)

    def _strip_range_param(self, url: str) -> str:
        s = urlsplit(url)
        qs = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True) if k.lower() != "range"]
        return urlunsplit((s.scheme, s.netloc, s.path, urlencode(qs, doseq=True), s.fragment))

    def _merge_m3u_playlist(self, m3u_text: str, base_url: str) -> str:
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

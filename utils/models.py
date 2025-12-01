from dataclasses import dataclass

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

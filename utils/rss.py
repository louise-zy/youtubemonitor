import logging
import requests
import xml.etree.ElementTree as ET
import re
from typing import Optional, List
from utils.models import VideoInfo

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
                
                # 模式1: "channelId":"UCxxxxxx"
                match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]+)"', content)
                if match:
                    return match.group(1)
                
                # 模式2: "externalId":"UCxxxxxx"
                match = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]+)"', content)
                if match:
                    return match.group(1)
                
                # 模式3: channel/UCxxxxxx
                match = re.search(r'/channel/(UC[a-zA-Z0-9_-]+)', content)
                if match:
                    return match.group(1)
                
                # 如果都没找到，记录部分页面内容用于调试
                logging.warning("未找到频道ID")
                
            else:
                logging.error(f"HTTP请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            logging.error(f"从handle获取频道ID失败: {e}")
        return None
    
    def _get_channel_id_from_custom_url(self, channel_url: str) -> Optional[str]:
        """从自定义URL获取频道ID"""
        # 逻辑与 _get_channel_id_from_handle 相同，复用即可
        return self._get_channel_id_from_handle(channel_url)
    
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

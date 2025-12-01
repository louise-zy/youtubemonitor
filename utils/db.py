import sqlite3
import logging
from typing import List, Optional
from datetime import datetime
from utils.models import YouTubeChannel, VideoInfo

class DBManager:
    """数据库管理器，处理所有数据持久化"""
    
    def __init__(self, db_path: str = "youtube_rss.db"):
        self.db_path = db_path
        self.init_db()
        
    def init_db(self):
        """初始化数据库表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 频道表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS youtube_channels (
                        channel_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        rss_url TEXT NOT NULL,
                        description TEXT,
                        last_video_id TEXT,
                        last_check TEXT,
                        last_update TEXT
                    )
                ''')
                
                # 视频表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS youtube_videos (
                        video_id TEXT PRIMARY KEY,
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

    def get_all_channels(self) -> List[YouTubeChannel]:
        """获取所有频道"""
        channels = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, channel_id, rss_url, description, 
                           last_video_id, last_check, last_update
                    FROM youtube_channels
                ''')
                
                for row in cursor.fetchall():
                    channels.append(YouTubeChannel(
                        name=row[0], channel_id=row[1], rss_url=row[2],
                        description=row[3], last_video_id=row[4],
                        last_check=row[5], last_update=row[6]
                    ))
        except Exception as e:
            logging.error(f"获取所有频道失败: {e}")
        return channels

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

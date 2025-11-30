import pandas as pd
import requests
from bs4 import BeautifulSoup
import hashlib
import json
import time
from datetime import datetime, timedelta
import smtplib
import email.mime.text
import email.mime.multipart
import schedule
import logging
from urllib.parse import urljoin, urlparse
import os
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Optional
import re
from utils.dingtalk import DingTalkClient
from utils.ai import AIContentProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('blogger_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# AI API相关（可选）
try:
    import openai
    AI_API_AVAILABLE = True
except ImportError:
    AI_API_AVAILABLE = False
    logging.warning("OpenAI库未安装，AI摘要功能不可用")

@dataclass
class BloggerInfo:
    """博主信息数据类"""
    name: str
    url: str
    description: str = ""
    platform: str = ""
    last_hash: str = ""
    last_check: str = ""
    last_update: str = ""

class DatabaseManager:
    """数据库管理器"""
    def __init__(self, db_file: str = "blogger_monitor.db"):
        self.db_file = db_file
        # 强制检查数据库结构，如果有问题就重新创建
        self._check_and_fix_database()
        self._init_database()
        self._upgrade_database()  # 强制检查并升级数据库
    
    def _check_and_fix_database(self):
        """检查并修复数据库结构问题"""
        if not os.path.exists(self.db_file):
            return  # 数据库不存在，将会被创建
            
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # 检查 updates 表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='updates'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                logging.info("updates 表不存在，将在 _init_database 中创建")
                conn.close()
                return
            
            # 检查 updates 表是否有 created_at 列
            cursor.execute("PRAGMA table_info(updates)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            logging.info(f"当前 updates 表的列: {column_names}")
            
            if 'created_at' not in column_names:
                logging.warning("检测到数据库结构问题：缺少 created_at 列")
                logging.info("正在添加 created_at 列...")
                cursor.execute("ALTER TABLE updates ADD COLUMN created_at TEXT")
                conn.commit()
                logging.info("✅ 已成功添加 created_at 列")
            else:
                logging.info("数据库结构正常")
                
            conn.close()
                
        except Exception as e:
            logging.error(f"检查数据库时出错: {e}")
            # 如果检查失败，备份并重新创建数据库
            try:
                backup_name = f"{self.db_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(self.db_file, backup_name)
                logging.info(f"数据库检查失败，已备份为: {backup_name}")
            except:
                pass
    
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 创建博主表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bloggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                description TEXT,
                platform TEXT,
                last_hash TEXT,
                last_check TEXT,
                last_update TEXT
            )
        ''')
        
        # 创建更新记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                blogger_id INTEGER,
                title TEXT,
                content TEXT,
                links TEXT,
                content_hash TEXT,
                created_at TEXT,
                FOREIGN KEY (blogger_id) REFERENCES bloggers (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _upgrade_database(self):
        """升级数据库结构"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # 检查并添加缺失的列（用于数据库升级）
        try:
            # 获取 updates 表的列信息
            cursor.execute("PRAGMA table_info(updates)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'created_at' not in column_names:
                logging.info("升级数据库：添加 created_at 列")
                cursor.execute("ALTER TABLE updates ADD COLUMN created_at TEXT")
                conn.commit()
                logging.info("✅ 数据库升级完成：已添加 created_at 列")
            else:
                logging.info("数据库已是最新版本")
                
        except Exception as e:
            logging.error(f"数据库升级失败: {e}")
        
        conn.close()
    
    def save_blogger(self, blogger: BloggerInfo) -> int:
        """保存或更新博主信息"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO bloggers 
            (name, url, description, platform, last_hash, last_check, last_update)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (blogger.name, blogger.url, blogger.description, blogger.platform,
              blogger.last_hash, blogger.last_check, blogger.last_update))
        
        blogger_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return blogger_id
    
    def get_blogger_by_url(self, url: str) -> Optional[BloggerInfo]:
        """根据URL获取博主信息"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM bloggers WHERE url = ?', (url,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return BloggerInfo(
                name=row[1], url=row[2], description=row[3], platform=row[4],
                last_hash=row[5], last_check=row[6], last_update=row[7]
            )
        return None
    
    def save_update(self, blogger_id: int, title: str, content: str, links: List[Dict], content_hash: str):
        """保存更新记录"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO updates (blogger_id, title, content, links, content_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (blogger_id, title, content, json.dumps(links), content_hash, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()

class ContentExtractor:
    """内容提取器，针对不同网站类型提取内容"""
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def extract_content(self, url: str) -> Dict:
        """提取网页内容"""
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            
            if 'substack.com' in url:
                return self._extract_substack(soup, url)
            elif 'paulgraham.com' in url:
                return self._extract_paulgraham(soup, url)
            elif 'bloomberg.com' in url:
                return self._extract_bloomberg(soup, url)
            elif 'wsj.com' in url:
                return self._extract_wsj(soup, url)
            else:
                return self._extract_generic(soup, url)
        except Exception as e:
            logging.error(f"提取内容失败 {url}: {e}")
            return {'title': '', 'content': '', 'links': [], 'error': str(e)}
    
    def _extract_substack(self, soup: BeautifulSoup, url: str) -> Dict:
        """提取Substack内容"""
        title = soup.find('h1', class_='post-title') or soup.find('h1')
        title = title.get_text().strip() if title else "无标题"
        
        content_div = soup.find('div', class_='available-content') or soup.find('div', class_='body')
        content = content_div.get_text().strip() if content_div else "无内容"
        
        links = []
        for link in soup.find_all('a', href=True):
            if link.get('href').startswith('http'):
                links.append({'title': link.get_text().strip(), 'link': link.get('href')})
        
        content_hash = hashlib.md5((title + content).encode()).hexdigest()
        return {'title': title, 'content': content, 'links': links, 'hash': content_hash}
    
    def _extract_paulgraham(self, soup: BeautifulSoup, url: str) -> Dict:
        """提取Paul Graham网站内容"""
        title = soup.find('title')
        title = title.get_text().strip() if title else "无标题"
        
        # Paul Graham的文章通常在body的直接文本中
        content = soup.get_text().strip()
        
        links = []
        for link in soup.find_all('a', href=True):
            if link.get('href').startswith('http'):
                links.append({'title': link.get_text().strip(), 'link': link.get('href')})
        
        content_hash = hashlib.md5((title + content).encode()).hexdigest()
        return {'title': title, 'content': content, 'links': links, 'hash': content_hash}
    
    def _extract_bloomberg(self, soup: BeautifulSoup, url: str) -> Dict:
        """提取Bloomberg内容"""
        title = soup.find('h1') or soup.find('title')
        title = title.get_text().strip() if title else "无标题"
        
        content_div = soup.find('div', class_='body-content') or soup.find('article')
        content = content_div.get_text().strip() if content_div else "无内容"
        
        links = []
        for link in soup.find_all('a', href=True):
            if link.get('href').startswith('http'):
                links.append({'title': link.get_text().strip(), 'link': link.get('href')})
        
        content_hash = hashlib.md5((title + content).encode()).hexdigest()
        return {'title': title, 'content': content, 'links': links, 'hash': content_hash}
    
    def _extract_wsj(self, soup: BeautifulSoup, url: str) -> Dict:
        """提取WSJ内容"""
        title = soup.find('h1') or soup.find('title')
        title = title.get_text().strip() if title else "无标题"
        
        content_div = soup.find('div', class_='article-content') or soup.find('article')
        content = content_div.get_text().strip() if content_div else "无内容"
        
        links = []
        for link in soup.find_all('a', href=True):
            if link.get('href').startswith('http'):
                links.append({'title': link.get_text().strip(), 'link': link.get('href')})
        
        content_hash = hashlib.md5((title + content).encode()).hexdigest()
        return {'title': title, 'content': content, 'links': links, 'hash': content_hash}
    
    def _extract_generic(self, soup: BeautifulSoup, url: str) -> Dict:
        """通用内容提取"""
        title = soup.find('h1') or soup.find('title')
        title = title.get_text().strip() if title else "无标题"
        
        # 尝试多种常见的内容容器
        content_selectors = [
            'article', '.content', '.post-content', '.entry-content',
            '.article-body', '.post-body', 'main', '.main-content'
        ]
        
        content = ""
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                content = content_div.get_text().strip()
                break
        
        if not content:
            content = soup.get_text().strip()
        
        links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and (href.startswith('http') or href.startswith('/')):
                if href.startswith('/'):
                    href = urljoin(url, href)
                links.append({'title': link.get_text().strip(), 'link': href})
        
        content_hash = hashlib.md5((title + content).encode()).hexdigest()
        return {'title': title, 'content': content, 'links': links, 'hash': content_hash}

class NotificationManager:
    """通知管理器"""
    def __init__(self, config: Dict):
        self.config = config
    
    def send_email_notification(self, updates: List[Dict]):
        """发送邮件通知"""
        try:
            smtp_server = self.config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.config.get('smtp_port', 587)
            sender_email = self.config.get('sender_email', '')
            sender_password = self.config.get('sender_password', '')
            recipient_email = self.config.get('recipient_email', '')
            
            if not all([sender_email, sender_password, recipient_email]):
                logging.warning("邮件配置不完整，跳过邮件发送")
                return
            
            msg = email.mime.multipart.MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"博主更新通知 - {len(updates)}个新更新"
            
            body = "发现以下博主更新：\n\n"
            for update in updates:
                body += f"博主：{update['blogger_name']}\n"
                body += f"标题：{update['title']}\n"
                body += f"链接：{update['url']}\n"
                body += f"更新时间：{update['update_time']}\n"
                if update.get('summary'):
                    body += f"摘要：{update['summary']}\n"
                body += "\n" + "="*50 + "\n\n"
            
            msg.attach(email.mime.text.MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            
            logging.info(f"邮件通知发送成功，包含{len(updates)}个更新")
            
        except Exception as e:
            logging.error(f"发送邮件通知失败: {e}")
    
    def save_to_file(self, updates: List[Dict]):
        """保存更新到文件"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"updates_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"博主更新报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*60 + "\n\n")
                
                for update in updates:
                    f.write(f"博主：{update['blogger_name']}\n")
                    f.write(f"更新时间：{update['update_time']}\n")
                    f.write(f"标题：{update['title']}\n")
                    f.write(f"链接：{update['url']}\n\n")
                    
                    if update.get('summary'):
                        f.write(f"摘要：\n{update['summary']}\n\n")
                    
                    if update.get('outline'):
                        f.write(f"大纲：\n{update['outline']}\n\n")
                    
                    if update.get('content'):
                        content = update['content'][:1000] + "..." if len(update['content']) > 1000 else update['content']
                        f.write(f"内容预览：\n{content}\n\n")
                    
                    if update.get('links'):
                        f.write("相关链接：\n")
                        for link in update['links'][:5]:
                            f.write(f"- {link.get('title', '链接')}: {link.get('link', '')}\n")
                        f.write("\n")
                    
                    f.write("="*60 + "\n\n")
            
            logging.info(f"更新已保存到文件: {filename}")
            
        except Exception as e:
            logging.error(f"保存文件失败: {e}")

class DingTalkNotifier(DingTalkClient):
    """钉钉推送通知器"""
    
    def send_message(self, updates: List[Dict], at_all: bool = False, at_mobiles: List[str] = None) -> bool:
        """发送钉钉Markdown消息（汇总模式）"""
        if not updates:
            return True
            
        content = "## 📰 博主更新推送\n\n"
        for u in updates:
            content += f"### {u.get('blogger_name','未知')}\n\n"
            content += f"**🕒 更新时间：** {u.get('update_time','')}\n\n"
            content += f"**📄 标题：** {u.get('title','')}\n\n"
            if u.get('summary'):
                content += f"**📝 摘要：**\n\n{u['summary']}\n\n"
            if u.get('outline'):
                content += f"**📚 大纲：**\n\n{u['outline']}\n\n"
            if u.get('url'):
                content += f"**🔗 原文：** [访问原网站]({u['url']})\n\n"
            if u.get('links'):
                content += f"**🔗 相关链接：**\n"
                for link in u['links'][:5]:
                    content += f"- [{link.get('title','链接')}]({link.get('link','')})\n"
                content += "\n"
            content += "---\n\n"
            
        return self.send_markdown("博主更新推送", content, at_all, at_mobiles)

class BloggerMonitor:
    """博主监控主类"""
    def __init__(self, config_file: str = "config.json"):
        self.config = self._load_config(config_file)
        self.extractor = ContentExtractor()
        self.db = DatabaseManager()
        self.notifier = NotificationManager(self.config.get('notification', {}))
        self.bloggers = []
        # AI处理器（可选）
        ai_key = self.config.get('deepseek_api_key') or self.config.get('openai_api_key')
        ai_base = self.config.get('ai_base_url', 'https://api.deepseek.com')
        ai_model = self.config.get('ai_model', 'deepseek-chat')
        self.ai_processor = AIContentProcessor(ai_key, ai_base, ai_model) if ai_key else None
        # 初始化钉钉推送器（新增）
        dt_cfg = self.config.get('dingtalk', {})
        self.dingtalk_notifier = None
        if dt_cfg.get('enabled') and dt_cfg.get('webhook_url'):
            self.dingtalk_notifier = DingTalkNotifier(
                webhook_url=dt_cfg['webhook_url'],
                secret=dt_cfg.get('secret')
            )
    
    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        default_config = {
            "check_interval_hours": 6,
            "notification": {
                "methods": ["dingtalk", "file"],  # 默认钉钉+文件
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_email": "",
                "sender_password": "",
                "recipient_email": ""
            },
            # AI可选配置
            "deepseek_api_key": "",
            "ai_base_url": "https://api.deepseek.com",
            "ai_model": "deepseek-chat",
            # 钉钉推送（新增）
            "dingtalk": {
                "enabled": True,
                "webhook_url": "",
                "secret": "",
                "at_all": False,
                "at_mobiles": []
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    default_config.update(config)
            except Exception as e:
                logging.warning(f"加载配置文件失败，使用默认配置: {e}")
        
        return default_config
    
    def load_bloggers_from_excel(self, excel_file: str = "海外博主.xlsx"):
        """从Excel文件加载博主信息"""
        try:
            df = pd.read_excel(excel_file)
            
            for _, row in df.iterrows():
                if pd.notna(row['网址']):
                    blogger = BloggerInfo(
                        name=row['姓名'] if pd.notna(row['姓名']) else "未知",
                        url=row['网址'],
                        description=row['身份 / 简介'] if pd.notna(row['身份 / 简介']) else "",
                        platform=row['主要分享平台'] if pd.notna(row['主要分享平台']) else ""
                    )
                    
                    # 检查数据库中是否已存在
                    existing = self.db.get_blogger_by_url(blogger.url)
                    if existing:
                        blogger.last_hash = existing.last_hash
                        blogger.last_check = existing.last_check
                        blogger.last_update = existing.last_update
                    
                    self.bloggers.append(blogger)
            
            logging.info(f"成功加载 {len(self.bloggers)} 个博主信息")
            
        except Exception as e:
            logging.error(f"加载Excel文件失败: {e}")
    
    def check_all_updates(self) -> List[Dict]:
        """检查所有博主的更新"""
        updates = []
        for blogger in self.bloggers:
            try:
                logging.info(f"检查 {blogger.name} 的更新...")
                current_content = self.extractor.extract_content(blogger.url)
                current_hash = current_content.get('hash', '')
                blogger.last_check = datetime.now().isoformat()

                if current_hash != blogger.last_hash and current_hash:
                    logging.info(f"{blogger.name} 有新更新！")
                    blogger.last_hash = current_hash
                    blogger.last_update = datetime.now().isoformat()
                    blogger_id = self.db.save_blogger(blogger)
                    self.db.save_update(
                        blogger_id,
                        current_content.get('title', ''),
                        current_content.get('content', ''),
                        current_content.get('links', []),
                        current_hash
                    )
                    # 生成AI摘要（基于标题 + 内容片段）
                    summary, outline = "", ""
                    if self.ai_processor:
                        ai_res = self.ai_processor.generate_summary_and_outline(
                            current_content.get('title', ''),
                            current_content.get('content', '')
                        )
                        summary = ai_res.get('summary', '')
                        outline = ai_res.get('outline', '')

                    updates.append({
                        'blogger_name': blogger.name,
                        'url': blogger.url,
                        'title': current_content.get('title', ''),
                        'content': current_content.get('content', ''),
                        'links': current_content.get('links', []),
                        'update_time': blogger.last_update,
                        'summary': summary,
                        'outline': outline
                    })
                else:
                    self.db.save_blogger(blogger)

                time.sleep(2)
            except Exception as e:
                logging.error(f"检查 {blogger.name} 时出错: {e}")
        return updates
    
    def send_notifications(self, updates: List[Dict]):
        """发送通知"""
        if not updates:
            logging.info("没有新的更新，无需发送通知")
            return
        
        methods = self.config.get('notification', {}).get('methods', ['file'])
        
        if 'dingtalk' in methods and self.dingtalk_notifier:
            dt_cfg = self.config.get('dingtalk', {})
            self.dingtalk_notifier.send_message(
                updates,
                at_all=dt_cfg.get('at_all', False),
                at_mobiles=dt_cfg.get('at_mobiles', [])
            )
        
        if 'email' in methods:
            self.notifier.send_email_notification(updates)
        
        if 'file' in methods:
            self.notifier.save_to_file(updates)
    
    def run_check(self):
        """执行一次检查"""
        logging.info("开始检查博主更新...")
        updates = self.check_all_updates()
        
        if updates:
            logging.info(f"发现 {len(updates)} 个更新")
            self.send_notifications(updates)
        else:
            logging.info("没有发现新的更新")
    
    def start_monitoring(self):
        """开始定期监控"""
        # 加载博主信息
        self.load_bloggers_from_excel()
        
        if not self.bloggers:
            logging.error("没有加载到博主信息，无法开始监控")
            return
        
        # 设置定期任务
        interval_hours = self.config.get('check_interval_hours', 6)
        schedule.every(interval_hours).hours.do(self.run_check)
        
        # 立即执行一次检查
        self.run_check()
        
        logging.info(f"开始定期监控，检查间隔: {interval_hours} 小时")
        
        # 持续运行
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次是否需要执行任务

def main():
    """主函数"""
    try:
        # 可以选择运行模式
        import sys
        
        if len(sys.argv) > 1 and sys.argv[1] == '--fix-db':
            # 强制修复数据库
            print("正在修复数据库结构...")
            db = DatabaseManager()
            print("✅ 数据库修复完成")
            return
        
        print("正在初始化 BloggerMonitor...")
        monitor = BloggerMonitor()
        print("✅ BloggerMonitor 初始化成功")
        
        if len(sys.argv) > 1 and sys.argv[1] == '--once':
            # 只运行一次检查
            print("开始加载博主信息...")
            monitor.load_bloggers_from_excel()
            print("✅ 博主信息加载完成")
            
            print("开始检查更新...")
            monitor.run_check()
            print("✅ 检查完成")
        else:
            # 持续监控模式
            monitor.start_monitoring()
            
    except Exception as e:
        print(f"❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
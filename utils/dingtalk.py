import time
import hmac
import hashlib
import base64
import requests
import logging
from typing import Optional, Dict, List, Any

class DingTalkClient:
    """钉钉机器人客户端，处理签名和请求发送"""
    
    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret
        
    def _generate_sign(self, timestamp: str) -> str:
        """生成钉钉加签"""
        if not self.secret:
            return ""
        
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign

    def send_markdown(self, title: str, text: str, at_all: bool = False, at_mobiles: List[str] = None) -> bool:
        """发送Markdown消息"""
        try:
            timestamp = str(round(time.time() * 1000))
            sign = self._generate_sign(timestamp)
            
            url = self.webhook_url
            if sign:
                url += f"&timestamp={timestamp}&sign={sign}"
            
            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": text
                }
            }
            
            if at_all or at_mobiles:
                data["at"] = {}
                if at_all:
                    data["at"]["isAtAll"] = True
                if at_mobiles:
                    data["at"]["atMobiles"] = at_mobiles
            
            headers = {"Content-Type": "application/json"}
            resp = requests.post(url, json=data, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get('errcode') == 0:
                    logging.info("钉钉消息发送成功")
                    return True
                else:
                    logging.error(f"钉钉消息发送失败: {result.get('errmsg')}")
                    return False
            else:
                logging.error(f"钉钉请求失败，状态码: {resp.status_code}")
                return False
                
        except Exception as e:
            logging.error(f"发送钉钉消息异常: {e}")
            return False

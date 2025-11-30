#!/usr/bin/env python3
"""
海外博主内容监控启动脚本
"""
import sys
import os
import json
from datetime import datetime

def check_dependencies():
    """检查依赖库"""
    required_packages = {
        'pandas': 'pandas',
        'requests': 'requests',
        'beautifulsoup4': 'bs4',
        'schedule': 'schedule',
        'openai': 'openai'  # 新增AI摘要依赖
    }
    
    missing_packages = []
    
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print("缺少以下依赖库，请先安装：")
        print("pip install " + " ".join(missing_packages))
        return False
    
    return True

def create_sample_config():
    """创建示例配置文件"""
    config = {
        "check_interval_hours": 6,
        "notification": {
            "methods": ["dingtalk", "file"],  # 默认钉钉+文件
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "",
            "sender_password": "",
            "recipient_email": ""
        },
        # AI摘要（可选，填写密钥启用）
        "deepseek_api_key": "",
        "ai_base_url": "https://api.deepseek.com",
        "ai_model": "deepseek-chat",
        # 钉钉机器人（需填写webhook）
        "dingtalk": {
            "enabled": True,
            "webhook_url": "",   # 你的Webhook URL
            "secret": "",        # 你的加签密钥（若启用加签）
            "at_all": False,
            "at_mobiles": []
        }
    }
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("已创建配置文件 config.json")

def setup_email_config():
    """设置邮件配置"""
    print("\n=== 邮件通知配置 ===")
    print("如果要启用邮件通知，请提供以下信息：")
    
    sender_email = input("发送邮箱 (留空跳过邮件通知): ").strip()
    if not sender_email:
        return False
    
    sender_password = input("邮箱密码/应用专用密码: ").strip()
    recipient_email = input("接收邮箱: ").strip()
    
    # 更新配置文件
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    config['notification']['methods'] = ['email', 'file']
    config['notification']['sender_email'] = sender_email
    config['notification']['sender_password'] = sender_password
    config['notification']['recipient_email'] = recipient_email
    
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("邮件配置已保存")
    return True

def main():
    print("海外博主内容监控系统")
    print("=" * 30)
    
    # 检查依赖
    if not check_dependencies():
        return
    
    # 检查Excel文件
    if not os.path.exists('海外博主.xlsx'):
        print("错误: 未找到 '海外博主.xlsx' 文件")
        print("请确保Excel文件在当前目录中")
        return
    
    # 检查配置文件
    if not os.path.exists('config.json'):
        print("未找到配置文件，正在创建...")
        create_sample_config()
    
    # 询问是否设置邮件通知
    setup_email = input("\n是否要设置邮件通知？(y/n): ").strip().lower()
    if setup_email == 'y':
        setup_email_config()
    
    # 询问运行模式
    print("\n请选择运行模式：")
    print("1. 只运行一次检查")
    print("2. 持续监控模式（每6小时检查一次）")
    
    choice = input("请输入选择 (1/2): ").strip()
    
    try:
        if choice == '1':
            print("正在执行一次性检查...")
            from blogger_monitor import BloggerMonitor
            monitor = BloggerMonitor()
            monitor.load_bloggers_from_excel()
            monitor.run_check()
            print("检查完成！")
            
        elif choice == '2':
            print("启动持续监控模式...")
            print("按 Ctrl+C 停止监控")
            from blogger_monitor import BloggerMonitor
            monitor = BloggerMonitor()
            monitor.start_monitoring()
            
        else:
            print("无效选择")
            
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"运行时出错: {e}")

if __name__ == "__main__":
    main()
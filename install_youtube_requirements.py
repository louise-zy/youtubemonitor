#!/usr/bin/env python3
"""
安装YouTube监控所需的Python包
"""

import subprocess
import sys

def install_package(package):
    """安装Python包"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ {package} 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {package} 安装失败: {e}")
        return False

def main():
    """主函数"""
    print("开始安装YouTube监控所需依赖...")
    
    # 基础依赖
    packages = [
        "requests",           # HTTP请求
        "yt-dlp",            # YouTube视频下载和字幕提取
        "openai",            # AI API调用
        "google-api-python-client",  # YouTube API（可选）
    ]
    
    success_count = 0
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print(f"\n安装完成: {success_count}/{len(packages)} 个包安装成功")
    
    if success_count == len(packages):
        print("🎉 所有依赖安装成功！")
    else:
        print("⚠️ 部分依赖安装失败，请检查网络连接或手动安装")

if __name__ == "__main__":
    main()
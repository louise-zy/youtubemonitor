#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网址提取脚本
从博主更新汇总文件中提取所有网址，并按行输出
"""

import re
import sys
from pathlib import Path

def extract_urls_from_file(file_path):
    """
    从文件中提取所有网址
    
    Args:
        file_path (str): 输入文件路径
        
    Returns:
        list: 提取到的网址列表
    """
    urls = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 使用正则表达式匹配网址
        # 匹配 http:// 或 https:// 开头的网址
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, content)
        
        # 去重并保持顺序
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
                
        return unique_urls
        
    except FileNotFoundError:
        print(f"错误: 找不到文件 {file_path}")
        return []
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return []

def save_urls_to_file(urls, output_file):
    """
    将网址列表保存到文件
    
    Args:
        urls (list): 网址列表
        output_file (str): 输出文件路径
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(url + '\n')
        print(f"已成功提取 {len(urls)} 个网址并保存到 {output_file}")
    except Exception as e:
        print(f"保存文件时发生错误: {e}")

def main():
    """主函数"""
    # 默认输入文件名
    input_file = "updates_20250724_142155.txt"
    
    # 如果命令行提供了参数，使用参数作为输入文件
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    # 检查输入文件是否存在
    if not Path(input_file).exists():
        print(f"错误: 文件 {input_file} 不存在")
        print("使用方法: python extract_urls.py [输入文件名]")
        return
    
    # 生成输出文件名
    input_path = Path(input_file)
    output_file = input_path.stem + "_urls.txt"
    
    print(f"正在从 {input_file} 中提取网址...")
    
    # 提取网址
    urls = extract_urls_from_file(input_file)
    
    if not urls:
        print("未找到任何网址")
        return
    
    # 保存到文件
    save_urls_to_file(urls, output_file)
    
    # 在控制台显示前10个网址作为预览
    print(f"\n前10个网址预览:")
    for i, url in enumerate(urls[:10], 1):
        print(f"{i:2d}. {url}")
    
    if len(urls) > 10:
        print(f"... 还有 {len(urls) - 10} 个网址")

if __name__ == "__main__":
    main() 
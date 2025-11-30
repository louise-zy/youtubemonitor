import pandas as pd
import requests
from urllib.parse import urlparse
import time

def read_blogger_excel():
    """读取海外博主Excel文件"""
    try:
        # 读取Excel文件
        df = pd.read_excel('海外博主.xlsx')
        
        print("Excel文件列名：")
        print(df.columns.tolist())
        print("\n文件基本信息：")
        print(f"总行数: {len(df)}")
        print(f"总列数: {len(df.columns)}")
        
        print("\n前几行数据：")
        print(df.head())
        
        # 查找包含网址的列
        url_columns = []
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['网址', 'url', 'link', '链接', 'website']):
                url_columns.append(col)
        
        print(f"\n可能包含网址的列: {url_columns}")
        
        # 显示所有列的样本数据
        print("\n各列样本数据：")
        for col in df.columns:
            print(f"\n列名: {col}")
            sample_data = df[col].dropna().head(3).tolist()
            print(f"样本数据: {sample_data}")
        
        return df
        
    except Exception as e:
        print(f"读取Excel文件时出错: {e}")
        return None

def analyze_urls(df):
    """分析网址信息"""
    if df is None:
        return
    
    # 查找网址列
    url_column = None
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ['网址', 'url', 'link', '链接', 'website']):
            url_column = col
            break
    
    if url_column is None:
        print("未找到网址列，请手动指定列名")
        return
    
    print(f"\n分析网址列: {url_column}")
    urls = df[url_column].dropna().tolist()
    
    print(f"共找到 {len(urls)} 个网址：")
    
    url_types = {}
    for i, url in enumerate(urls, 1):
        try:
            parsed = urlparse(str(url))
            domain = parsed.netloc
            if domain:
                if domain not in url_types:
                    url_types[domain] = []
                url_types[domain].append(url)
            
            print(f"{i}. {url}")
            print(f"   域名: {domain}")
            
        except Exception as e:
            print(f"{i}. {url} (解析失败: {e})")
    
    print(f"\n网站类型统计：")
    for domain, domain_urls in url_types.items():
        print(f"{domain}: {len(domain_urls)} 个")
    
    return urls, url_types

if __name__ == "__main__":
    print("开始读取海外博主Excel文件...")
    df = read_blogger_excel()
    
    if df is not None:
        print("\n" + "="*50)
        urls, url_types = analyze_urls(df) 
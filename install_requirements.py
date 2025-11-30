#!/usr/bin/env python3
"""
安装海外博主监控系统所需的依赖库
"""
import subprocess
import sys

def install_package(package):
    """安装单个包"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装 {package} 失败: {e}")
        return False

def main():
    """主函数"""
    print("正在安装海外博主监控系统依赖库...")
    print("=" * 40)
    
    # 需要安装的包
    packages = [
        "pandas>=1.3.0",
        "requests>=2.25.0", 
        "beautifulsoup4>=4.9.0",
        "schedule>=1.1.0",
        "openpyxl>=3.0.0"  # Excel文件读取支持
    ]
    
    failed_packages = []
    
    for package in packages:
        print(f"正在安装 {package}...")
        if install_package(package):
            print(f"✓ {package} 安装成功")
        else:
            print(f"✗ {package} 安装失败")
            failed_packages.append(package)
        print()
    
    if failed_packages:
        print("以下包安装失败:")
        for package in failed_packages:
            print(f"  - {package}")
        print("\n请手动执行以下命令:")
        print(f"pip install {' '.join(failed_packages)}")
    else:
        print("所有依赖库安装完成！")
        print("现在可以运行: python start_monitor.py")

if __name__ == "__main__":
    main() 
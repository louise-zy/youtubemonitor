#!/usr/bin/env python3
"""
生成完整博主报告的专用脚本
"""
import os
import subprocess
from datetime import datetime

def generate_full_report():
    """生成完整博主报告"""
    print("生成完整博主报告...")
    print("=" * 30)
    
    # 备份现有数据库（如果存在）
    if os.path.exists('blogger_monitor.db'):
        backup_name = f"blogger_monitor_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        os.rename('blogger_monitor.db', backup_name)
        print(f"已备份数据库为: {backup_name}")
    
    # 运行完整检查
    print("正在生成完整报告...")
    result = subprocess.run(['python', 'blogger_monitor.py', '--once'], 
                          capture_output=True, text=True, encoding='utf-8')
    
    if result.returncode == 0:
        print("✅ 完整报告生成成功！")
        
        # 查找最新的更新文件
        import glob
        update_files = glob.glob('updates_*.txt')
        if update_files:
            latest_file = max(update_files, key=os.path.getctime)
            print(f"📄 报告文件: {latest_file}")
            
            # 显示统计信息
            with open(latest_file, 'r', encoding='utf-8') as f:
                content = f.read()
                blogger_count = content.count('博主:')
                print(f"📊 包含 {blogger_count} 个博主的更新")
        
    else:
        print("❌ 生成报告时出错:")
        print(result.stderr)

def main():
    """主函数"""
    print("📋 完整博主报告生成器")
    print("=" * 40)
    
    confirm = input("是否要生成包含所有博主当前状态的完整报告？(y/n): ")
    
    if confirm.lower() == 'y':
        generate_full_report()
    else:
        print("操作已取消")
        print("如需查看增量更新，请运行: python blogger_monitor.py --once")

if __name__ == "__main__":
    main() 
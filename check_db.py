import sqlite3

db_path = "youtube_rss_monitor.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- Channels ---")
    cursor.execute("SELECT name, last_video_id, last_check FROM youtube_channels")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- Videos ---")
    cursor.execute("SELECT video_id, title, summary FROM youtube_videos ORDER BY id DESC LIMIT 5")
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, Title: {row[1][:30]}..., Summary Len: {len(row[2]) if row[2] else 0}")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")

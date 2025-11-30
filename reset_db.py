import sqlite3

db_path = "youtube_rss_monitor.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Reset Steve Eisman
    cursor.execute("UPDATE youtube_channels SET last_video_id = NULL WHERE name = 'Steve Eisman'")
    
    conn.commit()
    print("Reset Steve Eisman last_video_id to NULL")
    conn.close()
except Exception as e:
    print(f"Error: {e}")

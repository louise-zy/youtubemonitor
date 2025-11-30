import sqlite3

db_path = "youtube_rss_monitor.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Delete the video record for Steve Eisman's latest video
    cursor.execute("DELETE FROM youtube_videos WHERE video_id = 'zxjjjI0b8a0'")
    
    # Ensure channel last_video_id is NULL
    cursor.execute("UPDATE youtube_channels SET last_video_id = NULL WHERE name = 'Steve Eisman'")
    
    conn.commit()
    print("Deleted video zxjjjI0b8a0 and reset channel last_video_id")
    
    # Check if deleted
    cursor.execute("SELECT * FROM youtube_videos WHERE video_id = 'zxjjjI0b8a0'")
    if not cursor.fetchone():
        print("Verification: Video record deleted.")
    else:
        print("Verification: Video record STILL EXISTS.")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")

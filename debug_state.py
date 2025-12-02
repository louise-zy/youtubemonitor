import sqlite3
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

def inspect_db():
    print("=== Database Inspection ===")
    conn = sqlite3.connect('youtube_rss.db')
    cursor = conn.cursor()
    
    print("\n[Channels]")
    cursor.execute("SELECT name, last_video_id, last_update, last_check FROM youtube_channels")
    for row in cursor.fetchall():
        print(f"Channel: {row[0]}")
        print(f"  Last Video ID: {row[1]}")
        print(f"  Last Update:   {row[2]}")
        print(f"  Last Check:    {row[3]}")

    print("\n[Recent Videos]")
    cursor.execute("SELECT channel_name, title, published_at, video_id FROM youtube_videos ORDER BY published_at DESC LIMIT 10")
    for row in cursor.fetchall():
        print(f"[{row[2]}] {row[0]}: {row[1]} ({row[3]})")
    
    conn.close()

def check_rss(channel_url):
    print(f"\n=== RSS Feed Inspection: {channel_url} ===")
    # Helper to get channel ID (simplified version of what's in the main code)
    if "channel_id=" in channel_url:
        rss_url = channel_url
    else:
        # Just use a hardcoded ID for testing one of the user's channels if needed, 
        # or rely on the fact we might have the RSS URL in the DB.
        # Let's just grab the RSS URL from the DB for a specific channel.
        conn = sqlite3.connect('youtube_rss.db')
        cursor = conn.cursor()
        cursor.execute("SELECT rss_url, name FROM youtube_channels LIMIT 1")
        row = cursor.fetchone()
        if row:
            rss_url = row[0]
            print(f"Checking Feed for: {row[1]}")
        else:
            print("No channels in DB to check RSS.")
            return
        conn.close()

    try:
        resp = requests.get(rss_url, timeout=10)
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015'}
        
        print(f"Feed URL: {rss_url}")
        entries = root.findall('atom:entry', ns)
        print(f"Found {len(entries)} entries.")
        
        for i, entry in enumerate(entries[:5]):
            title = entry.find('atom:title', ns).text
            published = entry.find('atom:published', ns).text
            vid = entry.find('yt:videoId', ns).text
            print(f"{i+1}. {published} | {title} ({vid})")
            
    except Exception as e:
        print(f"Error checking RSS: {e}")

if __name__ == "__main__":
    inspect_db()
    check_rss("")

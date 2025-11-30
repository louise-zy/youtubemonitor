from youtube_transcript_api import YouTubeTranscriptApi

try:
    print("Instantiating YouTubeTranscriptApi...")
    ytt = YouTubeTranscriptApi()
    print("Instance created.")
    
    if hasattr(ytt, 'list'):
        print("Instance has 'list' method.")
    else:
        print("Instance does NOT have 'list' method.")

    if hasattr(ytt, 'get_transcript'):
        print("Instance has 'get_transcript' method.")
    else:
        print("Instance does NOT have 'get_transcript' method.")
        
except Exception as e:
    print(f"Error: {e}")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    print("Import successful")
    if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
        print("list_transcripts exists")
    else:
        print("list_transcripts DOES NOT exist")
        print(dir(YouTubeTranscriptApi))
except ImportError as e:
    print(f"Import failed: {e}")

import os
import yt_dlp
from google import genai
from google.genai import types
from pathlib import Path

# Configure Gemini API - REPLACE WITH YOUR ACTUAL API KEY
GEMINI_API_KEY = "AIzaSyAdXBnfqV1ju7sNSu8r33Eq12gjk38XoNE"
client = genai.Client(api_key=GEMINI_API_KEY)

def download_youtube_audio(url, output_path="downloads"):
    """Download YouTube video as audio file using yt-dlp (no FFmpeg needed)"""
    Path(output_path).mkdir(exist_ok=True)
    
    ydl_opts = {
        'format': 'bestaudio/best',  # Download best audio without conversion
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'quiet': False,
    }
    
    print(f"Downloading audio from: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Get the actual filename with extension
        audio_file = ydl.prepare_filename(info)
        print(f"Downloaded: {audio_file}")
        return audio_file, info['title']

def transcribe_audio_with_gemini(audio_file):
    """Transcribe audio using Gemini API"""
    print("\nTranscribing audio with Gemini...")
    print("This may take a few minutes for longer videos...")
    
    # Upload audio file
    print("Uploading audio file...")
    audio_upload = client.files.upload(path=audio_file)
    
    # Wait for file to be processed
    import time
    while audio_upload.state == "PROCESSING":
        print("Processing audio...")
        time.sleep(5)
        audio_upload = client.files.get(name=audio_upload.name)
    
    if audio_upload.state == "FAILED":
        raise ValueError("Audio file processing failed")
    
    print("File processed. Generating transcription...")
    
    # Use Gemini model for transcription
    prompt = """Please transcribe this audio file completely and accurately. 
    Provide the full transcription with proper punctuation and formatting."""
    
    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=[
            prompt,
            audio_upload
        ]
    )
    
    transcription = response.text
    
    print(f"Transcription complete! ({len(transcription)} characters)")
    return transcription

def create_summary_and_flowchart(transcription):
    """Create summary (33% of original) and flowchart using Gemini"""
    print("\nGenerating summary and flowchart...")
    
    target_length = len(transcription) // 3
    
    prompt = f"""Based on the following transcription, please:

1. Create a comprehensive summary that is approximately {target_length} characters long (about 33% of the original).
2. Create a Mermaid flowchart that visualizes the main topics and flow of what was studied.
3. List all the main topics covered (numbered list).

Format your response as:
SUMMARY:
[Your summary here]

FLOWCHART:
```mermaid
[Your flowchart here]
```

TOPICS:
1. [Topic 1]
2. [Topic 2]
...

Transcription:
{transcription}
"""
    
    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=prompt
    )
    
    return response.text

def generate_detailed_notes(transcription, topic):
    """Generate detailed notes for a specific topic using Gemini"""
    print(f"\nGenerating detailed notes for topic: {topic}")
    
    prompt = f"""Based on the following transcription, create detailed, comprehensive notes specifically about: "{topic}"

Include:
- Key concepts and definitions
- Important points and explanations
- Examples if mentioned
- Any formulas, procedures, or methods discussed
- Relationships to other topics if relevant

Make the notes well-structured and easy to study from.

Transcription:
{transcription}
"""
    
    response = client.models.generate_content(
        model='gemini-2.0-flash-exp',
        contents=prompt
    )
    
    return response.text

def save_output(filename, content):
    """Save content to a file"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    filepath = output_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved: {filepath}")

def main():
    print("=" * 60)
    print("YouTube Audio Transcription & Study Notes Generator")
    print("=" * 60)
    
    # Check API key
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("\n❌ ERROR: Please set your Gemini API key in the code!")
        print("Get your API key from: https://aistudio.google.com/apikey")
        return
    
    # Get YouTube URL from user
    youtube_url = input("\nEnter YouTube video URL: ").strip()
    
    try:
        # Step 1: Download audio
        audio_file, video_title = download_youtube_audio(youtube_url)
        
        # Step 2: Transcribe audio
        transcription = transcribe_audio_with_gemini(audio_file)
        save_output(f"{video_title}_transcription.txt", transcription)
        
        # Step 3: Generate summary and flowchart
        summary_result = create_summary_and_flowchart(transcription)
        save_output(f"{video_title}_summary_flowchart.md", summary_result)
        
        print("\n" + "=" * 60)
        print("SUMMARY AND FLOWCHART")
        print("=" * 60)
        print(summary_result)
        
        # Step 4: Ask user for detailed notes on specific topic
        print("\n" + "=" * 60)
        print("DETAILED NOTES GENERATION")
        print("=" * 60)
        
        while True:
            choice = input("\nWould you like detailed notes on a specific topic? (yes/no): ").strip().lower()
            
            if choice == 'no' or choice == 'n':
                print("\nThank you! All files have been saved in the 'output' folder.")
                break
            elif choice == 'yes' or choice == 'y':
                topic = input("Enter the topic you want detailed notes for: ").strip()
                detailed_notes = generate_detailed_notes(transcription, topic)
                
                safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '-', '_')).rstrip()
                save_output(f"{video_title}_notes_{safe_topic}.md", detailed_notes)
                
                print("\n" + "-" * 60)
                print(f"DETAILED NOTES: {topic}")
                print("-" * 60)
                print(detailed_notes)
            else:
                print("Please enter 'yes' or 'no'")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\nPlease make sure:")
        print("1. You have a valid Gemini API key")
        print("2. The YouTube URL is valid")
        print("3. You have internet connection")

if __name__ == "__main__":
    main()
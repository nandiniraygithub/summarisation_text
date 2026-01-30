import os
import yt_dlp
import google.generativeai as genai
from pathlib import Path

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyAHzHXCsUgSNVRNh5zWWNi8Ah4aokGCH3k"
genai.configure(api_key=GEMINI_API_KEY)

def download_youtube_audio(url, output_path="downloads"):
    """Download YouTube video as audio file using yt-dlp"""
    Path(output_path).mkdir(exist_ok=True)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'quiet': False,
    }
    
    print(f"Downloading audio from: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        
        # Get the actual filename that was created
        # yt-dlp sanitizes the filename, so we need to prepare the path properly
        filename = ydl.prepare_filename(info)
        # Replace the extension with mp3 since we're extracting audio
        audio_file = os.path.splitext(filename)[0] + '.mp3'
        
        print(f"Downloaded: {audio_file}")
        return audio_file, info['title']

def transcribe_audio_with_gemini(audio_file):
    """Transcribe audio using Gemini API"""
    print("\nTranscribing audio with Gemini...")
    
    # Upload audio file
    audio_upload = genai.upload_file(path=audio_file)
    
    # Use Gemini model for transcription
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    prompt = """Please transcribe this audio file completely and accurately. 
    Provide the full transcription with proper punctuation and formatting."""
    
    response = model.generate_content([prompt, audio_upload])
    transcription = response.text
    
    print(f"Transcription complete! ({len(transcription)} characters)")
    return transcription

def create_summary_and_flowchart(transcription):
    """Create summary (33% of original) and flowchart using Gemini"""
    print("\nGenerating summary and flowchart...")
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    target_length = len(transcription) // 3
    
    prompt = f"""Based on the following transcription, please:

1. Create a comprehensive summary that is approximately {target_length} characters long (about 33% of the original).
2. Create a Mermaid flowchart that visualizes the main topics and flow of what was studied.
3. List all the main topics covered (numbered list).

Format your response as:
TOPICS:
1. [Topic 1]
2. [Topic 2]

SUMMARY:
[Your summary here]

FLOWCHART:
```mermaid
[Your flowchart here]
```

Transcription:
{transcription}
"""
    
    response = model.generate_content(prompt)
    return response.text

def generate_detailed_notes(transcription, topic):
    """Generate detailed notes for a specific topic using Gemini"""
    print(f"\nGenerating detailed notes for topic: {topic}")
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
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
    
    response = model.generate_content(prompt)
    return response.text

def save_output(filename, content):
    """Save content to a file"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Sanitize filename for saving
    safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
    
    filepath = output_dir / safe_filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved: {filepath}")

def main():
    print("=" * 60)
    print("YouTube Audio Transcription & Study Notes Generator")
    print("=" * 60)
    
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
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\nPlease make sure:")
        print("1. You have a valid Gemini API key")
        print("2. FFmpeg is installed on your system")
        print("3. The YouTube URL is valid")

if __name__ == "__main__":
    main()
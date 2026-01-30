import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import yt_dlp
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("youtube_study.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Directories setup
AUDIO_DIR = Path("audio_downloads")
OUTPUT_DIR = Path("study_outputs")
COOKIES_FILE = Path("youtube_cookies.txt")

# Create directories
AUDIO_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Configure Gemini API
GEMINI_API_KEY = "AIzaSyA2I_o2mGh5Fkq3jjKDnwbsK-9cQpkGjW4" #os.getenv("GOOGLE_API_KEY") or "YOUR_API_KEY_HERE"
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")


def extract_json_from_response(response_text: str) -> Dict[str, Any]:
    """Extract JSON from Gemini response text with error handling"""
    try:
        # Look for JSON code block
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            return json.loads(json_str)
        
        # Look for any JSON structure
        json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
            return json.loads(json_str)
        
        logger.warning(f"No JSON found in response. Raw text: {response_text[:200]}...")
        return {"error": "Failed to parse JSON from model response"}
        
    except json.JSONDecodeError as e:
        logger.error(f"JSONDecodeError: {e}")
        return {"error": f"JSON parsing failed: {str(e)}"}


def download_youtube_audio(url: str) -> tuple[Path, str, str]:
    """Download YouTube video audio using yt-dlp"""
    try:
        # Extract video ID
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0].split('&')[0]
        elif 'v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
        else:
            video_id = f'video_{int(time.time())}'
        
        output_path = AUDIO_DIR / video_id
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(output_path) + '.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': False,
            'ignoreerrors': False,
            'noplaylist': True,
            'restrictfilenames': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs'],
                }
            },
        }
        
        # Add cookies if file exists
        if COOKIES_FILE.exists():
            ydl_opts['cookiefile'] = str(COOKIES_FILE)
            logger.info("Using cookies file for authentication")
        
        logger.info(f"Downloading audio from: {url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first
            info_dict = ydl.extract_info(url, download=False)
            
            if not info_dict:
                raise Exception(f"Failed to extract info for: {url}")
            
            # Check for live video
            is_live = info_dict.get('is_live', False) or info_dict.get('was_live', False)
            if is_live:
                raise RuntimeError(f"Cannot process live videos: {url}")
            
            title = info_dict.get('title', 'Unknown Title')
            channel = info_dict.get('channel', 'Unknown Channel')
            
            # Download the video
            logger.info(f"Downloading: {title}")
            ydl.download([url])
        
        # Find the MP3 file
        mp3_path = Path(f"{output_path}.mp3")
        
        if not mp3_path.exists():
            # Look for other audio formats
            for ext in ['.m4a', '.webm', '.opus', '.ogg']:
                alt_path = Path(f"{output_path}{ext}")
                if alt_path.exists():
                    mp3_path = alt_path
                    break
            
            if not mp3_path.exists():
                raise FileNotFoundError(f"Audio file not found for video: {video_id}")
        
        logger.info(f"Downloaded successfully: {mp3_path}")
        return mp3_path, title, channel
        
    except Exception as e:
        logger.error(f"Error downloading audio: {e}")
        raise


def transcribe_audio(audio_path: Path) -> str:
    """Transcribe audio using Gemini"""
    try:
        logger.info("Transcribing audio with Gemini...")
        
        # Upload audio file
        audio_file = genai.upload_file(path=str(audio_path))
        
        prompt = """Please transcribe this audio file completely and accurately. 
        Provide the full transcription with proper punctuation and formatting.
        Return ONLY the transcription text, no additional commentary."""
        
        response = gemini_model.generate_content([prompt, audio_file])
        transcription = response.text.strip()
        
        logger.info(f"Transcription complete! ({len(transcription)} characters)")
        return transcription
        
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise


def create_summary_and_flowchart(transcription: str) -> Dict[str, str]:
    """Create summary and flowchart using Gemini"""
    try:
        logger.info("Generating summary, topics, and flowchart...")
        
        target_length = len(transcription) // 3
        
        prompt = f"""Based on the following transcription, please provide:

1. A numbered list of all main topics covered
2. A comprehensive summary that is approximately {target_length} characters long (about 33% of the original)
3. A Mermaid flowchart that visualizes the main topics and their relationships

Format your response EXACTLY as follows:

TOPICS:
1. [Topic 1]
2. [Topic 2]
...

SUMMARY:
[Your detailed summary here]

FLOWCHART:
```mermaid
[Your flowchart here]
```

Transcription:
{transcription}
"""
        
        response = gemini_model.generate_content(prompt)
        result = response.text.strip()
        
        # Parse the response into sections
        sections = {}
        
        # Extract topics
        topics_match = re.search(r'TOPICS:(.*?)(?=SUMMARY:|$)', result, re.DOTALL)
        if topics_match:
            sections['topics'] = topics_match.group(1).strip()
        
        # Extract summary
        summary_match = re.search(r'SUMMARY:(.*?)(?=FLOWCHART:|$)', result, re.DOTALL)
        if summary_match:
            sections['summary'] = summary_match.group(1).strip()
        
        # Extract flowchart
        flowchart_match = re.search(r'FLOWCHART:\s*```mermaid\s*(.*?)\s*```', result, re.DOTALL)
        if flowchart_match:
            sections['flowchart'] = flowchart_match.group(1).strip()
        
        logger.info("Summary and flowchart generated successfully")
        return sections
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        raise


def generate_detailed_notes(transcription: str, topic: str) -> str:
    """Generate detailed notes for a specific topic"""
    try:
        logger.info(f"Generating detailed notes for: {topic}")
        
        prompt = f"""Based on the following transcription, create comprehensive, detailed study notes specifically about: "{topic}"

Include:
- Key concepts and definitions
- Important points and detailed explanations
- Examples mentioned in the content
- Any formulas, procedures, or methods discussed
- Step-by-step processes if applicable
- Relationships to other topics mentioned
- Important facts and figures

Make the notes well-structured, organized with headers and bullet points, and easy to study from.
Be thorough and detailed - these notes should be complete enough to understand the topic fully.

Transcription:
{transcription}
"""
        
        response = gemini_model.generate_content(prompt)
        notes = response.text.strip()
        
        logger.info(f"Generated {len(notes)} characters of detailed notes")
        return notes
        
    except Exception as e:
        logger.error(f"Error generating detailed notes: {e}")
        raise


def save_file(filepath: Path, content: str) -> None:
    """Save content to a file"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Saved: {filepath}")
    except Exception as e:
        logger.error(f"Error saving file {filepath}: {e}")
        raise


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem usage"""
    # Remove problematic characters
    safe = re.sub(r'[\\/*?:"<>|]', '_', filename)
    # Replace multiple spaces/underscores with single underscore
    safe = re.sub(r'[\s_]+', '_', safe)
    # Limit length
    return safe[:100]


def main():
    print("=" * 70)
    print("YouTube Study Notes Generator")
    print("=" * 70)
    
    # Get YouTube URL
    youtube_url = input("\nEnter YouTube video URL: ").strip()
    
    if not youtube_url:
        print("Error: No URL provided")
        return
    
    try:
        # Step 1: Download audio
        print("\n[1/4] Downloading audio...")
        audio_path, title, channel = download_youtube_audio(youtube_url)
        safe_title = sanitize_filename(title)
        
        print(f"✓ Downloaded: {title}")
        print(f"  Channel: {channel}")
        
        # Step 2: Transcribe
        print("\n[2/4] Transcribing audio with Gemini...")
        transcription = transcribe_audio(audio_path)
        
        # Save transcription
        trans_file = OUTPUT_DIR / f"{safe_title}_transcription.txt"
        save_file(trans_file, transcription)
        print(f"✓ Transcription saved ({len(transcription)} characters)")
        
        # Step 3: Generate summary and flowchart
        print("\n[3/4] Generating summary, topics, and flowchart...")
        sections = create_summary_and_flowchart(transcription)
        
        # Create combined output
        combined_output = f"""# {title}
Channel: {channel}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## TOPICS COVERED

{sections.get('topics', 'Topics not available')}

---

## SUMMARY

{sections.get('summary', 'Summary not available')}

---

## FLOWCHART

```mermaid
{sections.get('flowchart', 'graph TD\nA[Flowchart not available]')}
```
"""
        
        # Save combined output
        summary_file = OUTPUT_DIR / f"{safe_title}_summary.md"
        save_file(summary_file, combined_output)
        
        print("\n" + "=" * 70)
        print("SUMMARY AND TOPICS")
        print("=" * 70)
        print(combined_output)
        
        # Step 4: Detailed notes for specific topics
        print("\n" + "=" * 70)
        print("[4/4] DETAILED NOTES FOR SPECIFIC TOPICS")
        print("=" * 70)
        
        while True:
            print("\nOptions:")
            print("  1. Generate detailed notes for a specific topic")
            print("  2. Exit")
            
            choice = input("\nYour choice (1 or 2): ").strip()
            
            if choice == '2':
                print("\n✓ All files saved in 'study_outputs' folder")
                print("=" * 70)
                break
            elif choice == '1':
                # Show available topics
                if sections.get('topics'):
                    print("\nAvailable topics from the video:")
                    print(sections['topics'])
                
                topic = input("\nEnter the topic for detailed notes: ").strip()
                
                if not topic:
                    print("Error: No topic provided")
                    continue
                
                print(f"\nGenerating detailed notes for: {topic}")
                detailed_notes = generate_detailed_notes(transcription, topic)
                
                # Save detailed notes
                safe_topic = sanitize_filename(topic)
                notes_file = OUTPUT_DIR / f"{safe_title}_notes_{safe_topic}.md"
                
                notes_content = f"""# Detailed Notes: {topic}
Video: {title}
Channel: {channel}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{detailed_notes}
"""
                
                save_file(notes_file, notes_content)
                
                print("\n" + "-" * 70)
                print(f"DETAILED NOTES: {topic}")
                print("-" * 70)
                print(detailed_notes)
                print("-" * 70)
                print(f"\n✓ Saved to: {notes_file}")
            else:
                print("Invalid choice. Please enter 1 or 2")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        logger.error(f"Main error: {e}", exc_info=True)
        print("\nPlease check:")
        print("  1. You have a valid Gemini API key in .env file")
        print("  2. FFmpeg is installed on your system")
        print("  3. The YouTube URL is valid and accessible")
        print("  4. yt-dlp is up to date (run: pip install --upgrade yt-dlp)")


if __name__ == "__main__":
    main()
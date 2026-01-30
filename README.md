# YouTube Audio Summarizer & Notes Generator

A Python tool to **fetch YouTube audio**, **convert it to text**, **summarize it**, and optionally **generate detailed notes** on user-specified topics. This project combines **yt-dlp, Whisper, LLMs,** for a seamless learning workflow.

---

## Features

- Download audio from YouTube videos or RSS/YouTube feeds using `yt-dlp`.
- Transcribe audio to text using **Whisper Large** (open-source speech-to-text model).
- Summarize content using **Mistral** or **LongT5** models.
- Visualize flowcharts of the studied content (optional).
- Allow the user to specify a topic to generate **detailed notes** using **Gemini AI**.
- Fully open-source and easy to install and run.

---

## Installation

Make sure you have **Python 3.10+** installed.

```bash
# Clone the repository
git clone https://github.com/your-username/YouTube-Audio-Summarizer.git
cd YouTube-Audio-Summarizer

# Create and activate virtual environment (optional)
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

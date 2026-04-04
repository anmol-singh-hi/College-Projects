import yt_dlp
import requests
import re
import os
import io
import google.generativeai as genai
from gtts import gTTS

# ---------------- CONFIG ----------------
# No longer strictly needed for summarization, but kept for file cleaning if used elsewhere
CHUNK_SIZE = 12000 

# ---------------- FILE CLEANING ----------------

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

def clean_vtt(vtt_text):
    lines = vtt_text.splitlines()
    cleaned_lines = []
    previous_line = ""
    for line in lines:
        line = line.strip()
        if not line or "WEBVTT" in line or "-->" in line:
            continue
        line = re.sub(r"<.*?>", "", line)
        if line != previous_line:
            cleaned_lines.append(line)
            previous_line = line
    full_text = " ".join(cleaned_lines)
    full_text = re.sub(r'([.!?]) +', r'\1\n\n', full_text)
    return full_text.strip()

# ---------------- TRANSCRIPT EXTRACTION ----------------

def get_transcript(video_url, language="en"):
    ydl_opts = {"skip_download": True, "quiet": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = clean_filename(info.get("title", "transcript"))
            subtitles = info.get("subtitles") or info.get("automatic_captions")

            if not subtitles:
                return None, None, "No subtitles available."

            if language not in subtitles:
                language = list(subtitles.keys())[0]

            for sub in subtitles[language]:
                if sub["ext"] == "vtt":
                    response = requests.get(sub["url"])
                    transcript_text = clean_vtt(response.text)
                    return title, transcript_text, None
        return None, None, "Transcript not found."
    except Exception as e:
        return None, None, str(e)

# ---------------- GEMINI SETUP ----------------

def setup_gemini():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Set GOOGLE_API_KEY environment variable.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")

# ---------------- SUMMARIZATION (Optimized for Quota) ----------------

def summarize_text(model, text, length_type="Short"):
    """
    Summarizes the entire text in one API call to avoid 429 Quota errors.
    Yields chunks for streaming in Streamlit.
    """
    word_count = len(text.split())
    
    # Adjusted ratios for better length control
    length_map = {
        "Short": word_count // 6,
        "Medium": word_count // 4,
        "Long": word_count // 3
    }
    target_words = length_map.get(length_type, word_count // 6)
    
    # Single prompt to save API quota
    prompt = f"""
    You are an expert summarizer. Provide a {length_type} summary of the following transcript.
    
    STRICT RULES:
    1. TARGET LENGTH: Approximately {target_words} words.
    2. FORMAT: Use plain text only. Do NOT use markdown (no #, *, or bold).
    3. STYLE: Natural spoken English, suitable for text-to-speech.
    4. Provide the summary as a cohesive narrative.

    TRANSCRIPT:
    {text}
    """

    # Stream=True allows the word-by-word effect in the frontend
    response = model.generate_content(prompt, stream=True)
    
    for chunk in response:
        if chunk.text:
            yield chunk.text

# ---------------- CLEAN FOR TTS ----------------

def clean_for_tts(text):
    text = re.sub(r'[#*`>-]', '', text)
    text = re.sub(r'\b\d+\.\s*', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ---------------- TEXT TO SPEECH (In-Memory) ----------------

def text_to_speech(text):
    """Generates audio in memory using gTTS."""
    tts = gTTS(text=text, lang='en', slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0) 
    return fp
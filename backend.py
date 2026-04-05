import yt_dlp
import requests
import re
import os
import io
import google.generativeai as genai
from gtts import gTTS
import warnings
from functools import lru_cache # Added for pre-fetch caching

warnings.simplefilter(action='ignore', category=FutureWarning)

# ---------------- FILE CLEANING ----------------

def clean_filename(name):
    """Removes characters that are illegal in file names across OSs."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def clean_vtt(vtt_text):
    """Cleans VTT transcript text by removing timestamps and metadata."""
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

# ---------------- TRANSCRIPT EXTRACTION (Optimized with Cache) ----------------

@lru_cache(maxsize=10) # Cache the last 10 URLs for instant retrieval
def get_transcript(video_url, language="en"):
    """
    Fetches transcript. Cached so pre-fetch and 
    actual generation don't double-download.
    """
    ydl_opts = {"skip_download": True, "quiet": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            title = clean_filename(info.get("title", "transcript"))
            subtitles = info.get("subtitles") or info.get("automatic_captions")

            if not subtitles:
                return None, None, "No subtitles available for this video."

            if language not in subtitles:
                language = list(subtitles.keys())[0]

            for sub in subtitles[language]:
                if sub["ext"] == "vtt":
                    response = requests.get(sub["url"])
                    transcript_text = clean_vtt(response.text)
                    return title, transcript_text, None
                    
        return None, None, "Transcript not found in the required format."
    except Exception as e:
        return None, None, str(e)

# ---------------- GEMINI SETUP ----------------

def setup_gemini():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Set GOOGLE_API_KEY environment variable.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash-lite")

# ---------------- SUMMARIZATION ----------------

def summarize_text(model, text, length_type="Short", custom_prompt=""):
    word_count = len(text.split())
    
    length_map = {
        "Short": max(50, word_count // 15),
        "Medium": max(100, word_count // 10),
        "Long": max(200, word_count // 5)
    }
    target_words = length_map.get(length_type, word_count // 6)
    
    user_spec_clause = f"\nADDITIONAL USER SPECIFICATIONS: {custom_prompt}" if custom_prompt else ""
    
    prompt = f"""
    You are an expert summarizer. Provide a {length_type} summary of the following transcript.
    
    STRICT RULES:
    1. TARGET LENGTH: Approximately {target_words} words.
    2. FORMAT: Use standard Markdown (bolding, bullet points) to make the summary readable.
    3. STYLE: Natural, fluid spoken English.
    4. Provide the summary as a cohesive narrative.
    {user_spec_clause}

    TRANSCRIPT:
    {text}
    """

    response = model.generate_content(prompt, stream=True)
    
    for chunk in response:
        if hasattr(chunk, 'text') and chunk.text:
            yield chunk.text

# ---------------- CLEAN FOR TTS ----------------

def clean_for_tts(text):
    """
    Refined cleaning to prevent '2.5' pauses and improve natural flow.
    """
    # 1. Remove Markdown headers (###) and bolding (**)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'[*_]{1,3}', '', text)
    
    # 2. FIX: Only remove list numbers at the START of a line (e.g., "1. ")
    # This prevents breaking numbers like "2.5" or "3.0"
    text = re.sub(r'(?m)^\d+\.\s+', '', text)
    
    # 3. Remove bullet points and dashes
    text = re.sub(r'^\s*[-•+]\s+', '', text, flags=re.MULTILINE)
    
    # 4. Clean up whitespace to prevent artificial gaps in speech
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

# ---------------- TEXT TO SPEECH ----------------

def text_to_speech(text):
    tts = gTTS(text=text, lang='en', slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0) 
    return fp
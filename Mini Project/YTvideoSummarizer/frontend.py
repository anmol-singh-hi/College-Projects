import streamlit as st
from backend import get_transcript, setup_gemini, summarize_text, clean_for_tts, text_to_speech

# ---------------- UI CONFIG ----------------
st.set_page_config(
    page_title="AI YouTube Video Summarizer", 
    page_icon="https://cdn-icons-png.flaticon.com/512/1384/1384060.png", # YouTube favicon
    layout="centered"
)

# --- Custom Professional CSS ---
st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    }
    
    /* Title Styling */
    h1 {
        color: #00d2ff;
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        text-align: center;
        padding-bottom: 20px;
    }
    
    /* Sidebar/Card look for the main input area */
    .stTextInput, .stSelectSlider {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Button Styling */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white;
        border: none;
        padding: 12px 30px;
        border-radius: 10px;
        font-weight: bold;
        transition: 0.3s;
        width: 100%;
    }
    
    div.stButton > button:first-child:hover {
        box-shadow: 0px 0px 15px 2px rgba(0, 210, 255, 0.4);
        transform: translateY(-2px);
    }
    
    /* Summary container styling */
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 15px !important;
        padding: 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Create a layout with an icon and title using Markdown
st.markdown(
    """
    <div style="display: flex; align-items: center;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png" width="50" style="margin-right: 15px;">
        <h1 style="margin: 0;">AI Youtube Video Summarizer</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------------- INPUT AREA ----------------
with st.container():
    youtube_url = st.text_input("Enter YouTube URL", placeholder="https://youtube.com/watch?v=...")
    
    summary_length = st.select_slider(
        "Summary Granularity",
        options=["Short", "Medium", "Long"],
        value="Short"
    )

    generate = st.button("✨ Generate Summary")

# ---------------- PROCESS & STREAMING ----------------
if generate and youtube_url:
    if 'current_summary' in st.session_state:
        del st.session_state['current_summary']

    with st.spinner("🔍 Fetching content..."):
        title, transcript, error = get_transcript(youtube_url)

    if error:
        st.error(f"❌ {error}")
    else:
        try:
            with st.status("🚀 Processing with Gemini Flash...", expanded=True) as status:
                st.write("Reading transcript...")
                model = setup_gemini()
                stream = summarize_text(model, transcript, length_type=summary_length)
                status.update(label="✅ Ready!", state="complete", expanded=False)

            st.markdown("### 🧠 AI Intelligence Report")
            with st.chat_message("assistant", avatar="🤖"):
                full_summary = st.write_stream(stream)
                st.session_state['current_summary'] = full_summary
                st.session_state['current_title'] = title
        
        except Exception as e:
            if "429" in str(e):
                st.warning("⏳ Quota paused. Waiting for cool-down...")
            else:
                st.error(f"Error: {e}")

# ---------------- PERSISTENT DISPLAY ----------------
if 'current_summary' in st.session_state and not generate:
    st.markdown("### 🧠 AI Intelligence Report")
    with st.chat_message("assistant", avatar="🤖"):
        st.write(st.session_state['current_summary'])

# ---------------- AUDIO SECTION ----------------
if 'current_summary' in st.session_state:
    st.write("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🔊 Generate Audio Narration"):
            with st.spinner("Synthesizing voice..."):
                clean_summary = clean_for_tts(st.session_state['current_summary'])
                audio_mem_file = text_to_speech(clean_summary)
                st.audio(audio_mem_file, format="audio/mp3")
                
                with col2:
                    st.download_button(
                        label="📥 Download MP3",
                        data=audio_mem_file,
                        file_name=f"{st.session_state['current_title']}.mp3",
                        mime="audio/mp3"
                    )

elif generate:
    st.warning("Please enter a valid YouTube URL.")
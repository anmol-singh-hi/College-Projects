import streamlit as st
from backend import get_transcript, setup_gemini, summarize_text, clean_for_tts, text_to_speech

# ---------------- UI CONFIG ----------------
st.set_page_config(
    page_title="AI YouTube Video Summarizer", 
    page_icon="https://cdn-icons-png.flaticon.com/512/1384/1384060.png", 
    layout="centered"
)

# --- SPEED HACK #1: GLOBAL AI INITIALIZATION ---
if "ai_model" not in st.session_state:
    try:
        st.session_state.ai_model = setup_gemini()
    except Exception as e:
        st.error(f"AI Service Offline: {e}")

# --- SPEED HACK #2: PRE-FETCH CALLBACK ---
def trigger_prefetch():
    url = st.session_state.get("url_input_key")
    if url:
        get_transcript(url)

# --- Custom Professional CSS ---
st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }
    h1 { color: #00d2ff; font-family: 'Inter', sans-serif; font-weight: 800; text-align: center; padding-bottom: 20px; }
    .stTextInput, .stSelectbox, .stTextArea {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 10px; border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1);
    }
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        color: white; border: none; padding: 12px 30px; border-radius: 10px; font-weight: bold; width: 100%;
    }
    .stChatMessage {
        background-color: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 15px !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div style="display: flex; align-items: center;"><img src="https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png" width="50" style="margin-right: 15px;"><h1 style="margin: 0;">AI Youtube Video Summarizer</h1></div>', unsafe_allow_html=True)

# ---------------- INPUT AREA ----------------
with st.container():
    youtube_url = st.text_input(
        "🔗 Enter YouTube URL", 
        placeholder="https://youtube.com/watch?v=...",
        key="url_input_key",
        on_change=trigger_prefetch
    )
    
    summary_length = st.selectbox("📊 Summary Granularity", options=["Short", "Medium", "Long"], index=0)
    custom_spec = st.text_area("📝 Custom Specifications (Optional)", placeholder="e.g., Focus on technical details...")
    generate = st.button("✨ Generate Summary")

# ---------------- PROCESS & STREAMING ----------------
if generate and youtube_url:
    st.session_state['current_summary'] = None
    st.session_state['audio_data'] = None 

    with st.spinner("🔍 Fetching content..."):
        title, transcript, error = get_transcript(youtube_url)

    if error:
        st.error(f"❌ {error}")
    else:
        try:
            with st.status("🚀 Intelligence analysis in progress...", expanded=False) as status:
                stream = summarize_text(
                    st.session_state.ai_model, 
                    transcript, 
                    length_type=summary_length, 
                    custom_prompt=custom_spec
                )
                status.update(label="✅ Analysis Complete", state="complete")

            st.markdown("### 🧠 AI Intelligence Report")
            with st.chat_message("assistant", avatar="🤖"):
                # Clean streaming display
                full_summary = st.write_stream(stream)
                st.session_state['current_summary'] = full_summary
                st.session_state['current_title'] = title
            
        except Exception as e:
            st.error(f"Error: {e}")

# ---------------- PERSISTENT DISPLAY ----------------
if st.session_state.get('current_summary') and not generate:
    st.markdown("### 🧠 AI Intelligence Report")
    
    with st.chat_message("assistant", avatar="🤖"):
        # Pure Markdown display - No copy buttons or code boxes
        st.markdown(st.session_state['current_summary'])

# ---------------- AUDIO SECTION ----------------
if st.session_state.get('current_summary'):
    st.write("---")
    
    if "audio_data" not in st.session_state:
        st.session_state.audio_data = None

    audio_area = st.empty()

    if st.session_state.audio_data is None:
        if audio_area.button("🔊 Generate Audio Narration", key="gen_audio_btn"):
            audio_area.empty()
            with audio_area.container():
                with st.spinner("Synthesizing voice..."):
                    clean_text = clean_for_tts(st.session_state['current_summary'])
                    audio_fp = text_to_speech(clean_text)
                    st.session_state.audio_data = audio_fp.getvalue()
            st.rerun()
    else:
        with audio_area.container():
            col1, col2 = st.columns([2, 1])
            with col1:
                st.audio(st.session_state.audio_data, format="audio/mp3")
                if st.button("🔄 Regenerate Audio"):
                    st.session_state.audio_data = None
                    st.rerun()
            with col2:
                st.download_button(
                    label="📥 Download MP3",
                    data=st.session_state.audio_data,
                    file_name=f"{st.session_state.get('current_title', 'summary')}.mp3",
                    mime="audio/mp3",
                    use_container_width=True
                )
elif generate and not youtube_url:
    st.warning("Please enter a valid YouTube URL.")
import streamlit as st
import google.generativeai as genai
import PyPDF2
import edge_tts
import asyncio
import tempfile
import re
import base64
import time
from google.api_core.exceptions import ResourceExhausted

# 1. UI Configuration
st.set_page_config(page_title="AI Classroom Simulator", layout="wide")
st.title("👨‍🏫 AI Classroom Simulator")
st.caption("Powered by Gemini 2.5 Flash")

# 2. The Sidebar (Engine & Settings)
with st.sidebar:
    st.header("⚙️ Classroom Setup")
    api_key = st.text_input("Enter Gemini API Key", type="password")
    uploaded_file = st.file_uploader("Drop your Course PDF here", type="pdf")
    
    st.markdown("---")
    mode = st.radio(
        "Select Learning Mode:",
        ("Seminar Mode (Text & Concepts)", "Chalkboard Mode (Heavy Math)")
    )
    
    st.markdown("---")
    voice_option = st.selectbox(
        "🗣️ Select Teacher Voice:",
        ("British Professor (Ryan)", "American Tutor (Aria)", "Nigerian Lecturer (Abeo)")
    )
    
    # Map the visual name to the actual Edge TTS voice code
    voice_mapping = {
        "British Professor (Ryan)": "en-GB-RyanNeural",
        "American Tutor (Aria)": "en-US-AriaNeural",
        "Nigerian Lecturer (Abeo)": "en-NG-AbeoNeural"
    }
    selected_voice = voice_mapping[voice_option]

# 3. Security Check
if not api_key:
    st.warning("Please enter your Gemini API Key in the sidebar to enter the classroom.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# 4. Memory (Remembering the chat and PDF)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

# ── Helper: safe generate with retries (Now using Chat Memory) ──────────────
def safe_generate_chat(chat_session, message, retries=3, wait=65):
    """Calls Gemini Chat with automatic retry on rate-limit errors."""
    for attempt in range(retries):
        try:
            return chat_session.send_message(message)
        except ResourceExhausted:
            if attempt < retries - 1:
                with st.spinner(f"Rate limit hit — waiting {wait}s before retry {attempt + 1}/{retries - 1}..."):
                    time.sleep(wait)
            else:
                raise   # re-raise after final attempt
        except Exception:
            raise

# ── Helper: trim text to a safe token budget (~6000 chars ≈ ~1500 tokens) ───
def trim_text(text, max_chars=6000):
    return text[:max_chars] + "\n\n[...document trimmed to fit token budget...]" if len(text) > max_chars else text


# 5. Ingestion & The Hook (Now giving the AI long-term memory)
if uploaded_file is not None and st.session_state.pdf_text == "":
    with st.spinner("Scanning course materials..."):
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        start_page = 15
        end_page = min(19, len(pdf_reader.pages))
        for page_num in range(start_page, end_page):
            text += pdf_reader.pages[page_num].extract_text()

        st.session_state.pdf_text = trim_text(text)

        if "Seminar" in mode:
            persona = "You are a conversational tutor. Keep explanations clean and text-based."
        else:
            persona = "You are a rigorous math professor at a chalkboard. Find math formulas and break them down step-by-step."

        # ✅ THE FIX: Start a continuous chat session and save it to Streamlit's memory
        st.session_state.chat = model.start_chat(history=[])

        # Build the ONE-TIME mega prompt
        initial_prompt = f"{persona}\n\nHere is the course material. Keep this in mind for the rest of our conversation:\n{st.session_state.pdf_text}\n\nWelcome the student to the course based on the text above. Ask if they want a 'Fresh Start' or have an 'Area of Concern'."

        try:
            # We send the mega-prompt through the chat helper
            response = safe_generate_chat(st.session_state.chat, initial_prompt)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except ResourceExhausted:
            st.session_state.pdf_text = ""
            st.error("⚠️ Rate-limited on start. Wait a few minutes, then re-upload.")
            st.stop()
        except Exception as e:
            st.session_state.pdf_text = ""
            st.error(f"Failed to generate the opening lecture: {e}")
            st.stop()
            
# 6. Draw the Chat UI
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio_html" in msg and msg["audio_html"]:
            st.markdown(msg["audio_html"], unsafe_allow_html=True)

# 7. Student Interaction (With Sleek Action Bar)
student_input = None

# The "Raise Hand" Quick Action
col1, col2 = st.columns([2, 8])
with col1:
    if st.button("✋ Raise Hand"):
        student_input = "✋ Excuse me, professor. I have a question about that."

# The Chat Bar
if typed_input := st.chat_input("Or type your specific question..."):
    student_input = typed_input

if student_input:
    # 1. Show student message
    st.session_state.messages.append({"role": "user", "content": student_input})
    with st.chat_message("user"):
        st.write(student_input)
    
    # 2. The Lightweight Chat Request
    if "Seminar" in mode:
        chat_message = f"(Remember: You are a conversational tutor. Hide thoughts in <thought> tags.)\n\nStudent asks: {student_input}"
    else:
        chat_message = f"(Remember: You are a rigorous math professor. Output step-by-step math. Hide thoughts in <thought> tags.)\n\nStudent asks: {student_input}"
    
    # 3. Anchor the AI Response
    with st.chat_message("assistant"):
        with st.spinner("Teacher is thinking..."):
            try:
                response = safe_generate_chat(st.session_state.chat, chat_message)
                raw_text = response.text
                
                # Clean text for UI
                ui_text = re.sub(r'<thought>.*?</thought>', '', raw_text, flags=re.DOTALL).strip()
                if not ui_text: ui_text = raw_text
                
                # Clean text for Voice
                voice_text = re.sub(r'[*#_\-`]+', '', ui_text)
                custom_audio_html = ""
                
                # Generate Audio
                async def generate_speech(text, file_path, voice_id):
                    communicate = edge_tts.Communicate(text, voice_id, rate="-15%")
                    await communicate.save(file_path)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    asyncio.run(generate_speech(voice_text, fp.name, selected_voice))
                    
                    with open(fp.name, "rb") as f:
                        audio_b64 = base64.b64encode(f.read()).decode()
                    
                    audio_id = f"audio_{len(st.session_state.messages)}"
                    safe_copy_text = ui_text.replace('\n', ' ').replace('"', '&quot;').replace("'", "&#39;")
                    
                    # THE BULLETPROOF HTML FIX
                    # Parentheses let us split it neatly in Python without breaking Streamlit's Markdown
                    custom_audio_html = (
                        f'<audio id="{audio_id}" src="data:audio/mp3;base64,{audio_b64}" autoplay '
                        f'onended="document.getElementById(\'btn_{audio_id}\').innerHTML = \'🔊\'"></audio>'
                        f'<div style="display: flex; gap: 15px; margin-top: 15px; align-items: center; color: #888;">'
                        f'<button id="btn_{audio_id}" onclick="var aud = document.getElementById(\'{audio_id}\'); if(aud.paused) {{ aud.play(); this.innerHTML = \'⏸️\'; }} else {{ aud.pause(); this.innerHTML = \'🔊\'; }}" style="background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 0; color: #888; transition: 0.2s;" onmouseover="this.style.color=\'#fff\'" onmouseout="this.style.color=\'#888\'" title="Listen">⏸️</button>'
                        f'<button onclick="navigator.clipboard.writeText(\'{safe_copy_text}\'); this.innerHTML=\'✅\'; setTimeout(()=>this.innerHTML=\'📋\', 2000);" style="background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 0; color: #888; transition: 0.2s;" onmouseover="this.style.color=\'#fff\'" onmouseout="this.style.color=\'#888\'" title="Copy Text">📋</button>'
                        f'<button style="background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 0; color: #888;" onmouseover="this.style.color=\'#fff\'" onmouseout="this.style.color=\'#888\'">👍</button>'
                        f'<button style="background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 0; color: #888;" onmouseover="this.style.color=\'#fff\'" onmouseout="this.style.color=\'#888\'">👎</button>'
                        f'<button style="background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 0; color: #888;" onmouseover="this.style.color=\'#fff\'" onmouseout="this.style.color=\'#888\'">🔄</button>'
                        f'</div>'
                    )
                    
            except Exception as e:
                pass
        
        # Write the text and the new action bar to the screen
        st.write(ui_text)
        if custom_audio_html:
            st.markdown(custom_audio_html, unsafe_allow_html=True)
            
        # Save to memory
        st.session_state.messages.append({
            "role": "assistant", 
            "content": ui_text,
            "audio_html": custom_audio_html
        })

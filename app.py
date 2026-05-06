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

# ── Helper: build the sandboxed action bar ───────────────────────────────────
def make_action_bar(audio_b64: str, audio_id: str, message_text: str) -> str:
    """
    Returns a self-contained HTML string to be rendered via components.v1.html.
    All JS runs inside an iframe — Streamlit cannot strip it.
    """
    audio_tag = ""
    listen_btn = "<span style='color:#555;font-size:0.8rem;'>No audio</span>"

    if audio_b64:
        audio_tag = f"""
        <audio id="{audio_id}"
               src="data:audio/mp3;base64,{audio_b64}"
               onplay="document.getElementById('btn_{audio_id}').innerHTML='⏸️'"
               onpause="document.getElementById('btn_{audio_id}').innerHTML='🔊'"
               onended="document.getElementById('btn_{audio_id}').innerHTML='🔊'">
        </audio>"""

        listen_btn = f"""
        <button id="btn_{audio_id}" class="action-btn" title="Listen / Pause"
            onclick="var a=document.getElementById('{audio_id}');
                     a.paused ? a.play() : a.pause();">
            ⏸️
        </button>"""

    # Escape the message for safe embedding in a JS template literal
    js_safe_text = (
        message_text
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("$", "\\$")
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: transparent;
    font-family: sans-serif;
    padding: 6px 0 2px 0;
  }}
  .bar {{
    display: flex;
    gap: 4px;
    align-items: center;
  }}
  .action-btn {{
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1.05rem;
    padding: 5px 8px;
    border-radius: 6px;
    color: #8e8ea0;
    transition: background 0.15s, color 0.15s;
  }}
  .action-btn:hover {{
    background: rgba(255,255,255,0.10);
    color: #ececf1;
  }}
  .action-btn.liked  {{ color: #19c37d; }}
  .action-btn.disliked {{ color: #ef4444; }}
  .toast {{
    display: inline-block;
    font-size: 0.75rem;
    color: #19c37d;
    margin-left: 6px;
    opacity: 0;
    transition: opacity 0.3s;
  }}
</style>
</head>
<body>
  {audio_tag}

  <div class="bar">
    {listen_btn}

    <!-- Copy -->
    <button class="action-btn" title="Copy text"
        onclick="
          navigator.clipboard.writeText(`{js_safe_text}`)
            .then(() => {{
              var t = document.getElementById('toast_{audio_id}');
              t.style.opacity = 1;
              setTimeout(() => t.style.opacity = 0, 1800);
            }});
        ">
      📋
    </button>
    <span class="toast" id="toast_{audio_id}">Copied!</span>

    <!-- Thumbs up -->
    <button class="action-btn" id="like_{audio_id}" title="Good response"
        onclick="
          this.classList.toggle('liked');
          document.getElementById('dislike_{audio_id}').classList.remove('disliked');
        ">
      👍
    </button>

    <!-- Thumbs down -->
    <button class="action-btn" id="dislike_{audio_id}" title="Bad response"
        onclick="
          this.classList.toggle('disliked');
          document.getElementById('like_{audio_id}').classList.remove('liked');
        ">
      👎
    </button>

    <!-- Retry (signals parent via postMessage) -->
    <button class="action-btn" title="Retry"
        onclick="window.parent.postMessage('retry', '*');">
      🔄
    </button>
  </div>

  <script>
    // Auto-play on load if audio exists
    var aud = document.getElementById('{audio_id}');
    if (aud) {{
      // Small delay — iframe needs to be fully painted first
      setTimeout(() => aud.play().catch(() => {{}}), 400);
    }}
  </script>
</body>
</html>"""


# ── Section 6: Draw the Chat UI ──────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg["role"] == "assistant" and msg.get("audio_html"):
            # height=54 is just enough for the one-row button bar
            components.html(msg["audio_html"], height=54, scrolling=False)


# ── Section 7: Student Interaction ───────────────────────────────────────────
student_input = None

col1, col2 = st.columns([2, 8])
with col1:
    if st.button("✋ Raise Hand"):
        student_input = "✋ Excuse me, professor. I have a question about that."

if typed_input := st.chat_input("Or type your specific question..."):
    student_input = typed_input

if student_input:

    if "chat" not in st.session_state:
        st.error("⚠️ Please upload your Course PDF first!")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": student_input})
    with st.chat_message("user"):
        st.write(student_input)

    if "Seminar" in mode:
        chat_message = f"(Conversational tutor. Hide reasoning in <thought> tags.)\n\nStudent: {student_input}"
    else:
        chat_message = f"(Rigorous math professor. Step-by-step. Hide reasoning in <thought> tags.)\n\nStudent: {student_input}"

    with st.chat_message("assistant"):
        with st.spinner("Teacher is thinking..."):

            # ── PART 1: Text ─────────────────────────────────────────────────
            try:
                response = safe_generate_chat(st.session_state.chat, chat_message)
                raw_text = response.text
                ui_text = re.sub(r'<thought>.*?</thought>', '', raw_text, flags=re.DOTALL).strip()
                if not ui_text:
                    ui_text = raw_text
                voice_text = re.sub(r'[*#_\-`]+', '', ui_text)
            except ResourceExhausted:
                st.error("⚠️ Rate limited after all retries. Wait 60 s and try again.")
                st.stop()
            except Exception as e:
                st.error(f"⚠️ Generation failed: {e}")
                st.stop()

            # ── PART 2: Audio ────────────────────────────────────────────────
            audio_b64 = ""
            try:
                async def generate_speech(text, path, voice):
                    await edge_tts.Communicate(text, voice, rate="-15%").save(path)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    asyncio.run(generate_speech(voice_text, fp.name, selected_voice))
                    with open(fp.name, "rb") as f:
                        audio_b64 = base64.b64encode(f.read()).decode()
            except Exception:
                pass  # Audio is optional — text still shows

        # ── PART 3: Render ───────────────────────────────────────────────────
        st.write(ui_text)

        audio_id  = f"audio_{len(st.session_state.messages)}"
        action_bar = make_action_bar(audio_b64, audio_id, ui_text)

        # components.html renders in a sandboxed iframe — JS works fully
        components.html(action_bar, height=54, scrolling=False)

        st.session_state.messages.append({
            "role": "assistant",
            "content": ui_text,
            "audio_html": action_bar,   # stored so section 6 can redraw it
        })

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
import streamlit.components.v1 as components # ✅ ADDED FOR THE UI FIX
import numpy as np
import pandas as pd

# 1. UI Configuration
st.set_page_config(page_title="AI Classroom Simulator", layout="wide")
st.title("👨‍🏫 AI Classroom Simulator")
st.caption("Powered by Gemini 2.5 Flash") # Updated to 1.5 for quota limits!

# 2. The Sidebar (Engine & Settings)
with st.sidebar:
    st.header("⚙️ Classroom Setup")
    
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

    st.markdown("---")
    
    # The Memory Wipe Button
    if st.button("🗑️ End Class (Clear Memory)"):
        st.session_state.messages = []
        st.session_state.pdf_text = ""
        if "chat" in st.session_state:
            del st.session_state.chat
        st.rerun()

# --- SECURE DUAL-KEY SETUP ---
if "api_keys" not in st.session_state:
    # Grab both keys from the vault
    key1 = st.secrets.get("GEMINI_API_KEY_1")
    key2 = st.secrets.get("GEMINI_API_KEY_2")
    
    # Store whichever ones actually exist
    st.session_state.api_keys = [k for k in [key1, key2] if k]
    st.session_state.current_key_index = 0

if not st.session_state.api_keys:
    st.error("Missing API Keys! Please add them to your Streamlit Cloud Secrets.")
    st.stop()

# Boot up the engine with the first key
genai.configure(api_key=st.session_state.api_keys[st.session_state.current_key_index])

# 4. Memory (Remembering the chat and PDF)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

# ── Helpers: Generation & Text ──────────────────────────────────────────────
def safe_generate_chat(chat_session, message):
    keys = st.session_state.api_keys
    
    # Try every key we have before giving up
    for attempt in range(len(keys)):
        try:
            return chat_session.send_message(message)
            
        except ResourceExhausted:
            # If the key is dead, flip the changeover switch to the next one!
            st.warning(f"🔋 Key {st.session_state.current_key_index + 1} exhausted! Switching to backup...")
            
            # Move to the next key index (loops back to 0 if we hit the end)
            st.session_state.current_key_index = (st.session_state.current_key_index + 1) % len(keys)
            
            # Reconfigure the global API with the new key
            new_key = keys[st.session_state.current_key_index]
            genai.configure(api_key=new_key)
            
            # We need to re-initialize the model and chat session with the new key,
            # while keeping the old conversation history perfectly intact!
            global model
            model = genai.GenerativeModel('gemini-2.5-flash') # Ensure this matches your actual model string!
            
            old_history = chat_session.history
            chat_session = model.start_chat(history=old_history)
            
            # The loop will restart and try the send_message again with the new key
            continue
            
        except Exception:
            raise # If it's a normal network error, just crash normally
            
    # If we loop through all keys and STILL fail, then we are truly out of juice
    st.error("⚠️ All backup API keys are exhausted! Please wait a few minutes.")
    st.stop()

def trim_text(text, max_chars=6000):
    return text[:max_chars] + "\n\n[...document trimmed to fit token budget...]" if len(text) > max_chars else text

def make_action_bar(audio_b64: str, audio_id: str, message_text: str) -> str:
    """
    Returns a self-contained HTML string rendered via components.v1.html.

    Cross-iframe audio-stop protocol:
      PLAY  → iframe  ──postMessage──▶  window.parent  (type: "audio_playing", id)
      COORD → parent  ──postMessage──▶  ALL iframes    (type: "stop_audio", except: id)
      STOP  → iframe  checks id, pauses self if not exempt
    """
    audio_tag = ""
    listen_btn = "<span style='color:#555;font-size:0.8rem;'>No audio</span>"

    if audio_b64:
        audio_tag = f"""
        <audio id="{audio_id}"
               src="data:audio/mp3;base64,{audio_b64}">
        </audio>"""

        listen_btn = f"""
        <button id="btn_{audio_id}" class="action-btn" title="Listen / Pause"
            onclick="togglePlay()">🔊</button>"""

    safe_text = (
        message_text
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; font-family: sans-serif; padding: 6px 0 2px 0; }}
  .bar {{ display: flex; gap: 4px; align-items: center; }}
  .action-btn {{ background: none; border: none; cursor: pointer; font-size: 1.05rem;
                 padding: 5px 8px; border-radius: 6px; color: #8e8ea0;
                 transition: background 0.15s, color 0.15s; }}
  .action-btn:hover {{ background: rgba(255,255,255,0.10); color: #ececf1; }}
  .action-btn.liked    {{ color: #19c37d; }}
  .action-btn.disliked {{ color: #ef4444; }}
  .toast {{ display: inline-block; font-size: 0.75rem; color: #19c37d;
            margin-left: 6px; opacity: 0; transition: opacity 0.3s; }}
</style>
</head>
<body>
  {audio_tag}
  <div id="text_{audio_id}" style="display:none;">{safe_text}</div>

  <div class="bar">
    {listen_btn}

    <!-- Copy -->
    <button class="action-btn" title="Copy text"
        onclick="
          var txt = document.getElementById('text_{audio_id}').innerText;
          navigator.clipboard.writeText(txt).then(() => {{
            var t = document.getElementById('toast_{audio_id}');
            t.style.opacity = 1;
            setTimeout(() => t.style.opacity = 0, 1800);
          }});
        ">📋</button>
    <span class="toast" id="toast_{audio_id}">Copied!</span>

    <!-- Like / Dislike -->
    <button class="action-btn" id="like_{audio_id}" title="Good response"
        onclick="this.classList.toggle('liked');
                 document.getElementById('dislike_{audio_id}').classList.remove('disliked');">👍</button>
    <button class="action-btn" id="dislike_{audio_id}" title="Bad response"
        onclick="this.classList.toggle('disliked');
                 document.getElementById('like_{audio_id}').classList.remove('liked');">👎</button>
  </div>

<script>
(function() {{
  var MY_ID = "{audio_id}";
  var aud   = document.getElementById(MY_ID);

  /* ── 1. COORDINATOR: inject once into the shared parent window ─────────────
     We stamp window.parent.__audioCoordReady so the block only runs the first
     time any iframe loads.  All subsequent iframes skip straight to step 2.  */
  if (window.parent && !window.parent.__audioCoordReady) {{
    window.parent.__audioCoordReady = true;

    window.parent.addEventListener("message", function (e) {{
      if (!e.data || e.data.type !== "audio_playing") return;

      var senderId = e.data.id;

      /* Fan the stop command out to every iframe in the Streamlit page */
      var frames = window.parent.document.querySelectorAll("iframe");
      frames.forEach(function (frame) {{
        try {{
          frame.contentWindow.postMessage(
            {{ type: "stop_audio", except: senderId }},
            "*"
          );
        }} catch (_) {{}}   /* cross-origin safety – silently skip */
      }});
    }});
  }}

  /* ── 2. LISTENER: this iframe obeys stop commands from the coordinator ──── */
  window.addEventListener("message", function (e) {{
    if (!e.data || e.data.type !== "stop_audio") return;
    if (e.data.except === MY_ID) return;   /* we are the protected player */
    if (aud && !aud.paused) {{
      aud.pause();
      var btn = document.getElementById("btn_" + MY_ID);
      if (btn) btn.innerHTML = "🔊";
    }}
  }});

  /* ── 3. BROADCASTER + UI: wire the audio element's own events ─────────────*/
  if (aud) {{
    /* Whenever THIS audio starts, tell the coordinator */
    aud.addEventListener("play", function () {{
      if (window.parent) {{
        window.parent.postMessage({{ type: "audio_playing", id: MY_ID }}, "*");
      }}
      var btn = document.getElementById("btn_" + MY_ID);
      if (btn) btn.innerHTML = "⏸️";
    }});

    aud.addEventListener("pause",  function () {{
      var btn = document.getElementById("btn_" + MY_ID);
      if (btn) btn.innerHTML = "🔊";
    }});
    aud.addEventListener("ended",  function () {{
      var btn = document.getElementById("btn_" + MY_ID);
      if (btn) btn.innerHTML = "🔊";
    }});

    /* Auto-play on load (slight delay lets the iframe finish painting) */
    setTimeout(function () {{ aud.play().catch(function () {{}}); }}, 400);
  }}

  /* ── 4. Toggle helper called by the listen button ─────────────────────────*/
  window.togglePlay = function () {{
    if (!aud) return;
    if (aud.paused) {{ aud.play().catch(function(){{}}); }}
    else            {{ aud.pause(); }}
  }};
}})();
</script>
</body>
</html>"""
# 5. Ingestion & The Hook
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

        st.session_state.chat = model.start_chat(history=[])
        initial_prompt = f"{persona}\n\nHere is the course material. Keep this in mind for the rest of our conversation:\n{st.session_state.pdf_text}\n\nWelcome the student to the course based on the text above. Ask if they want a 'Fresh Start' or have an 'Area of Concern'."

        try:
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

# ── 5.5 The Immediate Voice Switch Fix ────────────────────────────────────────
# Keep track of the current voice in memory
if "current_voice" not in st.session_state:
    st.session_state.current_voice = selected_voice

# If the dropdown changes, intercept it and re-record the very last message!
if selected_voice != st.session_state.current_voice:
    st.session_state.current_voice = selected_voice
    
    if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "assistant":
       with st.spinner("🎙️ Switching teacher's voice..."):
            last_msg = st.session_state.messages[-1]
            
           # THE DYNAMIC CHALKBOARD AUDIO FILTER (For Voice Switching)
            voice_text = re.sub(
                r'\$\$.*?\$\$', 
                lambda match: ' ... ' * max(1, len(match.group(0)) // 15), 
                last_msg["content"], 
                flags=re.DOTALL
            )
            
            # Clean up inline math and backslashes
            voice_text = voice_text.replace('$', '').replace('\\', '')
            voice_text = re.sub(r'[*#_\-`]+', '', voice_text)
            
            # Record the new MP3
            async def regenerate_speech(text, file_path, voice_id):
                communicate = edge_tts.Communicate(text, voice_id, rate="-10%")
                await communicate.save(file_path)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                asyncio.run(regenerate_speech(voice_text, fp.name, selected_voice))
                with open(fp.name, "rb") as f:
                    new_audio_b64 = base64.b64encode(f.read()).decode()
            
            # Rebuild the action bar and overwrite the old one in memory
            audio_id = f"audio_{len(st.session_state.messages) - 1}"
            new_action_bar = make_action_bar(new_audio_b64, audio_id, last_msg["content"])
            st.session_state.messages[-1]["audio_html"] = new_action_bar
            
        # Instantly refresh the screen so the new play button is loaded
            st.rerun()
            
# 6. Draw the Chat UI (✅ UPDATED TO REDRAW GRAPHS)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        
       # Redraw the action buttons and audio
        if msg["role"] == "assistant" and msg.get("audio_html"):
            html_to_render = msg["audio_html"]
            # Only the LAST message should autoplay on redraw.
            # All older iframes get their autoplay line neutered.
            is_last_message = (msg is st.session_state.messages[-1])
            if not is_last_message:
                html_to_render = html_to_render.replace(
                    "setTimeout(function () { aud.play().catch(function () {}); }, 400);",
                    "/* autoplay suppressed for old message */"
                )
            components.html(html_to_render, height=54, scrolling=False)
                
        # Redraw the action buttons and audio (only the last message autoplays)
        if msg["role"] == "assistant" and msg.get("audio_html"):
            html_to_render = msg["audio_html"]
            if msg is not st.session_state.messages[-1]:
                html_to_render = html_to_render.replace(
                    "setTimeout(function () { aud.play().catch(function () {}); }, 400);",
                    "/* autoplay suppressed for old message */"
                )
            components.html(html_to_render, height=54, scrolling=False)

# 7. Student Interaction
student_input = None
col1, col2, col3 = st.columns([2, 2, 6])
with col1:
    if st.button("✋ Raise Hand"):
        student_input = "✋ Excuse me, professor. I have a question about that."
with col2:
    if st.button("📝 Quiz Me"):
        student_input = "📝 Professor, let's pause the lecture. Please give me a 3-question multiple-choice quiz based strictly on the course materials to test my knowledge. IMPORTANT: Ask the questions now, but DO NOT give me the answers until I respond!"

if typed_input := st.chat_input("Type your specific question or quiz answers..."):
    student_input = typed_input

if student_input:
    if "chat" not in st.session_state:
        st.error("⚠️ Please upload your Course PDF first so the professor can review the materials!")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": student_input})
    with st.chat_message("user"):
        st.write(student_input)
    
    if "Seminar" in mode:
        chat_message = f"(Conversational tutor. Put internal reasoning strictly inside <thought> tags, then write your final response below them.)\n\nStudent asks: {student_input}"
    else:
        chat_message = f"(Remember: You are a rigorous math professor. Output step-by-step math. Hide thoughts in <thought> tags. IMPORTANT: You MUST format all mathematical symbols, equations, and variables using standard LaTeX. Use single $ for inline math and double $$ for standalone block equations. Do not use bolding for variables. IF the student asks to graph or visualize a function, output the raw Python formula using 'x' inside <plot> tags, like <plot>x**2</plot> or <plot>np.sin(x)</plot>.)\n\nStudent asks: {student_input}"
    
    # ✅ FIX: Un-indented so it runs for both modes, and added the chat bubble back!
    with st.chat_message("assistant"):
        with st.spinner("Teacher is thinking..."):
            
            # --- PART 1: TEXT GENERATION ---
            try:
                response = safe_generate_chat(st.session_state.chat, chat_message)
                raw_text = response.text
                ui_text = re.sub(r'<thought>.*?(?:</thought>|$)', '', raw_text, flags=re.DOTALL).strip()
                if not ui_text: 
                    ui_text = "I was just thinking about that. Could you clarify which part you'd like to break down?"
                
                # ✅ THE FIX: Stronger periods (. . .) and divides by 8 for much longer pauses!
                voice_text = re.sub(
                    r'\$\$.*?\$\$', 
                    lambda match: '. . . ' * max(1, len(match.group(0)) // 8), 
                    ui_text, 
                    flags=re.DOTALL
                )
                
                # Clean up inline math and backslashes
                voice_text = voice_text.replace('$', '').replace('\\', '')
                voice_text = re.sub(r'[*#_\-`]+', '', voice_text)
                
            except ResourceExhausted:
                st.error("⚠️ The professor ran out of daily free tokens!")
                st.stop()
            except Exception as e:
                st.error(f"⚠️ Network error: {e}")
                st.stop()

            # --- PART 2: AUDIO GENERATION ---
            audio_b64 = ""
            try:
                async def generate_speech(text, file_path, voice_id):
                    communicate = edge_tts.Communicate(text, voice_id, rate="-10%")
                    await communicate.save(file_path)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    asyncio.run(generate_speech(voice_text, fp.name, selected_voice))
                    with open(fp.name, "rb") as f:
                        audio_b64 = base64.b64encode(f.read()).decode()
            except Exception as e:
                pass # Silently skip audio if it fails
        
# --- PART 3: DRAW TO SCREEN (WITH INTERACTIVE GRAPHING) ---
        
        # 1. Check if the AI tried to draw a graph
        plot_formula = None
        plot_match = re.search(r'<plot>(.*?)</plot>', ui_text)
        if plot_match:
            plot_formula = plot_match.group(1).strip()
            # Remove the raw <plot> tag from the text so the user doesn't see it
            ui_text = re.sub(r'<plot>.*?</plot>', '', ui_text, flags=re.DOTALL).strip()
        
        # 2. Write the professor's text to the screen
        st.write(ui_text)
        
        # 3. Draw the interactive graph if a formula was found!
        if plot_formula:
            try:
                x = np.linspace(-10, 10, 400)
                safe_dict = {"x": x, "np": np}
                y = eval(plot_formula, {"__builtins__": None}, safe_dict)
                df = pd.DataFrame({"x": x, "y": y}).set_index("x")
                st.line_chart(df, use_container_width=True)
            except Exception as e:
                st.warning(f"⚠️ The professor's chalk broke while trying to graph: {plot_formula}")

        # 4. Build the action bar HTML but DON'T draw it live here.
        # The chat loop will draw it on the rerun — preventing duplicates.
        audio_id = f"audio_{len(st.session_state.messages)}"
        action_bar_html = make_action_bar(audio_b64, audio_id, ui_text)

        # 5. Save to memory, then rerun so the chat loop renders everything once.
        st.session_state.messages.append({
            "role": "assistant",
            "content": ui_text,
            "audio_html": action_bar_html,
            "plot_formula": plot_formula
        })
        st.rerun()
        
        # 6. Auto-Scroll down
        components.html(
            """
            <script>
                const doc = window.parent.document;
                const messages = doc.querySelectorAll('.stChatMessage');
                if (messages.length > 0) {
                    messages[messages.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
                }
            </script>
            """, height=0
        )
# ── 8. Export Notes (Moved to bottom so it gets the latest messages!) ────────
with st.sidebar:
    st.markdown("---")
    st.subheader("📥 Export Notes")
    
    # Check if there are messages to download
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        
        # UNIQUE KEY ADDED HERE
        export_format = st.selectbox(
            "Select Export Format:", 
            ["Web Page (.html) - Best for Math", "Markdown (.md)", "Plain Text (.txt)"],
            key="export_dropdown_menu_bottom" 
        )
        
        # Pre-build the raw text for MD and TXT options
        raw_text_content = "# 👨‍🏫 AI Classroom Lecture Notes\n\n"
        for msg in st.session_state.messages:
            role = "🎓 **Student:**" if msg["role"] == "user" else "👨‍🏫 **Professor:**"
            safe_text = msg.get('content', '') 
            raw_text_content += f"{role}\n{safe_text}\n\n---\n\n"
            
        # 1. HTML Output
        if "html" in export_format:
            html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MTH 105 Lecture Notes</title>
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; color: #333; line-height: 1.6; }
        h2 { border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }
        .message { margin-bottom: 24px; padding: 16px; border-radius: 8px; }
        .user { background-color: #f0f7ff; border-left: 4px solid #0066cc; }
        .assistant { background-color: #f9f9f9; border-left: 4px solid #10a37f; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .role { font-weight: bold; font-size: 0.85em; text-transform: uppercase; margin-bottom: 8px; color: #555; }
        .content { white-space: pre-wrap; }
        .chart-container { background: white; padding: 10px; border-radius: 8px; margin-top: 15px; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <h2>👨‍🏫 AI Classroom Lecture Notes</h2>
"""
            # We use enumerate to give each graph a unique ID (chart_0, chart_1, etc.)
            for i, msg in enumerate(st.session_state.messages):
                css_class = "user" if msg["role"] == "user" else "assistant"
                role_name = "🎓 Student" if msg["role"] == "user" else "👨‍🏫 Professor"
                safe_text = msg.get('content', '').replace('<', '&lt;').replace('>', '&gt;')
                
                html_content += f'\n    <div class="message {css_class}">\n        <div class="role">{role_name}</div>\n        <div class="content">{safe_text}</div>'
                
                # IF THIS MESSAGE HAS A GRAPH, DRAW IT IN HTML!
                if msg.get("plot_formula"):
                    try:
                        # 1. Recalculate the coordinates
                        x = np.linspace(-10, 10, 100)
                        safe_dict = {"x": x, "np": np}
                        y = eval(msg["plot_formula"], {"__builtins__": None}, safe_dict)
                        
                        # 2. THE DATA FIX: Convert numpy arrays to pure Python lists and round them 
                        # so the browser doesn't choke on giant 16-decimal floating-point numbers!
                        x_list = [round(float(val), 2) for val in x]
                        y_list = [round(float(val), 2) for val in y]
                        
                        # 3. Inject the HTML Canvas and the Chart.js script
                        html_content += f'''
        <div class="chart-container" style="position: relative; height: 350px; width: 100%;">
            <canvas id="chart_{i}"></canvas>
        </div>
        <script>
            // THE TIMING FIX: Tell the browser to wait until the page is fully drawn to execute the chart!
            window.addEventListener('DOMContentLoaded', function() {{
                const ctx = document.getElementById('chart_{i}').getContext('2d');
                new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: {x_list},
                        datasets: [{{
                            label: 'y = {msg["plot_formula"]}',
                            data: {y_list},
                            borderColor: '#10a37f',
                            backgroundColor: 'rgba(16, 163, 127, 0.1)',
                            borderWidth: 2,
                            pointRadius: 0,
                            fill: true,
                            tension: 0.4
                        }}]
                    }},
                    options: {{ 
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{ legend: {{ display: true }} }} 
                    }}
                }});
            }});
        </script>'''
                    except Exception as e:
                        pass # Silently skip if graph math fails
                
                # Close the message div
                html_content += '\n    </div>'
                
            html_content += "\n</body>\n</html>"
            
            # UNIQUE KEY ADDED HERE
            st.download_button(
                label="⬇️ Download HTML", 
                data=html_content, 
                file_name="Lecture_Notes.html", 
                mime="text/html",
                key="dl_btn_html"
            )
            st.caption("💡 *Need a PDF? Open this HTML file in your browser and press Ctrl+P (or Cmd+P) to 'Save as PDF'.*")
            
        # 3. Plain Text Output
        elif "txt" in export_format:
            clean_txt = raw_text_content.replace('**', '').replace('#', '').strip()
            # UNIQUE KEY ADDED HERE
            st.download_button(
                label="⬇️ Download Text", 
                data=clean_txt, 
                file_name="Lecture_Notes.txt", 
                mime="text/plain",
                key="dl_btn_txt"
            )

    else:
        st.info("Start the class to generate notes!")

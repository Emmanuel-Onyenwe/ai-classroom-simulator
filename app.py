import streamlit as st
import google.generativeai as genai
import PyPDF2
import edge_tts
import asyncio
import tempfile
import re
import base64
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

# 5. Ingestion & The Hook
if uploaded_file is not None and st.session_state.pdf_text == "":
    with st.spinner("Scanning course materials..."):
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page_num in range(min(25, len(pdf_reader.pages))):
            text += pdf_reader.pages[page_num].extract_text()

        st.session_state.pdf_text = text

        if "Seminar" in mode:
            persona = "You are a conversational tutor. Keep explanations clean and text-based."
        else:
            persona = "You are a rigorous math professor at a chalkboard. Find math formulas and break them down step-by-step."

        prompt = f"{persona}\nWelcome the student to the course based on the text below. Ask if they want a 'Fresh Start' or have an 'Area of Concern'.\n\nCourse Text:\n{st.session_state.pdf_text}"

        response = model.generate_content(prompt)
        st.session_state.messages.append({"role": "assistant", "content": response.text})

# 6. Draw the Chat UI (Now with memory for the Audio Buttons!)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        # If this message has an audio button saved, draw it!
        if "audio_html" in msg and msg["audio_html"]:
            st.markdown(msg["audio_html"], unsafe_allow_html=True)

# 7. Student Interaction (The Graceful Interruption)

# We create a variable to hold the student's message, whether from a button or typing
student_input = None

# THE FIX 2: Create a sleek "Raise Hand" quick action bubble
col1, col2, col3 = st.columns([1.5, 8, 1])
with col1:
    if st.button("✋ Raise Hand", help="Click to interrupt the professor"):
        student_input = "✋ Excuse me, professor. I have a question about that."

# The standard chat bar (in case you still want to type specific math questions)
if typed_input := st.chat_input("Or type your specific question..."):
    student_input = typed_input

# If the student clicked the button OR typed a message, trigger the AI
if student_input:
    
    # 1. Show student message immediately
    st.session_state.messages.append({"role": "user", "content": student_input})
    with st.chat_message("user"):
        st.write(student_input)
    
    # 2. Build the AI Persona
    if "Seminar" in mode:
        persona = "You are a conversational tutor."
    else:
        persona = "You are a rigorous math professor. Output step-by-step math."
        
    persona += "\nIMPORTANT: If you need to think through a problem first, wrap your internal reasoning completely inside <thought>...</thought> tags. The text outside the tags is your final, clean answer."
    full_context = f"{persona}\n\nCourse Material:\n{st.session_state.pdf_text}\n\nStudent asks: {student_input}"
    
    # 3. Anchor the AI Response at the bottom
    with st.chat_message("assistant"):
        with st.spinner("Teacher is thinking..."):
            try:
                response = model.generate_content(full_context)
                raw_text = response.text
                
                # Clean text for UI
                ui_text = re.sub(r'<thought>.*?</thought>', '', raw_text, flags=re.DOTALL).strip()
                if not ui_text: ui_text = raw_text
                
                # Clean text for Voice
                voice_text = re.sub(r'[*#_\-`]+', '', ui_text)
                
                custom_audio_html = ""
                
                async def generate_speech(text, file_path, voice_id):
                    communicate = edge_tts.Communicate(text, voice_id, rate="-15%")
                    await communicate.save(file_path)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    asyncio.run(generate_speech(voice_text, fp.name, selected_voice))
                    
                    with open(fp.name, "rb") as f:
                        audio_b64 = base64.b64encode(f.read()).decode()
                    
                    audio_id = f"audio_{len(st.session_state.messages)}"
                    
                    # THE FIX 1: The Smart Play/Pause Button
                    custom_audio_html = f"""
                        <audio id="{audio_id}" src="data:audio/mp3;base64,{audio_b64}" autoplay 
                            onplay="document.getElementById('btn_{audio_id}').innerText = '⏸️ Pause'"
                            onpause="document.getElementById('btn_{audio_id}').innerText = '🔊 Listen'"
                            onended="document.getElementById('btn_{audio_id}').innerText = '🔊 Listen'">
                        </audio>
                        <button id="btn_{audio_id}" onclick="
                            var aud = document.getElementById('{audio_id}');
                            if(aud.paused) {{ aud.play(); }} else {{ aud.pause(); }}
                        " style="background: none; border: 1px solid #4ade80; border-radius: 20px; font-size: 0.9rem; cursor: pointer; color: #4ade80; padding: 6px 16px; margin-top: 10px; transition: 0.2s;">
                            🔊 Listen
                        </button>
                    """
                    
            except ResourceExhausted:
                st.error("⚠️ The professor needs a quick sip of water! We hit the free-tier speed limit. Please wait 60 seconds and try again.")
                st.stop()
            except Exception as e:
                st.error(f"Audio generation failed: {e}")
        
        # Write the text and the button to the screen
        st.write(ui_text)
        if custom_audio_html:
            st.markdown(custom_audio_html, unsafe_allow_html=True)
            
        # Save EVERYTHING to memory
        st.session_state.messages.append({
            "role": "assistant", 
            "content": ui_text,
            "audio_html": custom_audio_html
        })
            "audio_html": custom_audio_html
        })

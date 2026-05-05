import streamlit as st
import google.generativeai as genai
import PyPDF2
import edge_tts
import asyncio
import tempfile
import re
import base64

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

# 6. Draw the Chat UI
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# 7. Student Interaction (The Graceful Interruption)
if student_input := st.chat_input("Raise your hand / Ask a question..."):
    # Show student message
    st.session_state.messages.append({"role": "user", "content": student_input})
    st.chat_message("user").write(student_input)
    
    # AI Responds
    if "Seminar" in mode:
        persona = "You are a conversational tutor."
    else:
        persona = "You are a rigorous math professor. Output step-by-step math."
        
    # THE FIX: Tell the AI to keep its thoughts hidden
    persona += "\nIMPORTANT: If you need to think through a problem first, wrap your internal reasoning completely inside <thought>...</thought> tags. The text outside the tags is your final, clean answer that will be spoken to the student."
        
    full_context = f"{persona}\n\nCourse Material:\n{st.session_state.pdf_text}\n\nStudent asks: {student_input}"
    
    with st.spinner("Teacher is thinking..."):
        response = model.generate_content(full_context)
        raw_text = response.text
        
        # THE FIX: Clean the text for UI (Remove the <thought> block so you don't read it)
        ui_text = re.sub(r'<thought>.*?</thought>', '', raw_text, flags=re.DOTALL).strip()
        if not ui_text: ui_text = raw_text # Fallback if AI forgets tags
        
        st.session_state.messages.append({"role": "assistant", "content": ui_text})
        st.chat_message("assistant").write(ui_text)
        
        # THE FIX: Clean the text for Voice (Strip markdown symbols so it doesn't speak them)
        voice_text = re.sub(r'[*#_\-`]+', '', ui_text)
        
        # Generate the Audio
        try:
            async def generate_speech(text, file_path, voice_id):
                communicate = edge_tts.Communicate(text, voice_id)
                await communicate.save(file_path)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                asyncio.run(generate_speech(voice_text, fp.name, selected_voice))
                
                # THE FIX: Create a sleek Base64 Speaker Button instead of the bulky player
                with open(fp.name, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                
                # We use the length of messages to give each audio button a unique HTML ID
                audio_id = f"audio_{len(st.session_state.messages)}"
                
                custom_audio_html = f"""
                    <audio id="{audio_id}" src="data:audio/mp3;base64,{audio_b64}" autoplay></audio>
                    <button onclick="document.getElementById('{audio_id}').play()" 
                        style="background: none; border: 1px solid #4ade80; border-radius: 5px; font-size: 1rem; cursor: pointer; color: #4ade80; padding: 5px 15px; margin-top: 10px;">
                        🔊 Listen
                    </button>
                """
                st.markdown(custom_audio_html, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"Audio generation failed: {e}")

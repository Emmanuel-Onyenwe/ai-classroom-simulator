import streamlit as st
import google.generativeai as genai
import PyPDF2
from gtts import gTTS
import tempfile

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

# 7. Student Interaction
if student_input := st.chat_input("Raise your hand / Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": student_input})
    st.chat_message("user").write(student_input)

    if "Seminar" in mode:
        persona = "You are a conversational tutor."
    else:
        persona = "You are a rigorous math professor. Output step-by-step math."

    full_context = f"{persona}\n\nCourse Material:\n{st.session_state.pdf_text}\n\nStudent asks: {student_input}"

    with st.spinner("Teacher is thinking..."):
        response = model.generate_content(full_context)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        st.chat_message("assistant").write(response.text)

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                tts = gTTS(text=response.text, lang='en', tld='co.uk')
                tts.save(fp.name)
                st.audio(fp.name, format="audio/mp3", autoplay=True)
        except Exception as e:
            st.error("Audio generation skipped. (Too much traffic or math formatting blocked it).")

import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import PyPDF2
import edge_tts
import asyncio
import tempfile
import re
import base64
import time
from google.api_core.exceptions import ResourceExhausted
import streamlit.components.v1 as components
import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════════
# 0. PAGE CONFIG  — must be the very first Streamlit call
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AI Classroom",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
# 0.1  GLOBAL THEME CSS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,400&display=swap');

/* ── TOKENS ──────────────────────────────────────────────────── */
:root {
  --bg:         #0b0b11;
  --bg2:        #10101a;
  --glass:      rgba(255,255,255,0.038);
  --glass-hov:  rgba(255,255,255,0.065);
  --border:     rgba(255,255,255,0.07);
  --border-hov: rgba(255,255,255,0.13);
  --text:       #ddddf0;
  --muted:      #6a6a90;
  --amber:      #c9a45a;
  --teal:       #3ca18d;
  --violet:     #8b7acc;
  --r-xl:       20px;
  --r-lg:       14px;
  --r-md:       10px;
  --r-sm:       7px;
}

/* ── BASE ────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
  font-family: 'DM Sans', sans-serif !important;
  background: var(--bg) !important;
  color: var(--text) !important;
}

/* Subtle noise overlay on the whole app */
.stApp::before {
  content: '';
  position: fixed; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.025'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 0;
  opacity: 0.4;
}

/* ── SIDEBAR ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: rgba(9,9,16,0.97) !important;
  border-right: 1px solid var(--border) !important;
  padding-top: 0 !important;
}
[data-testid="stSidebar"] > div { padding-top: 1.2rem !important; }
[data-testid="stSidebar"] *, [data-testid="stSidebar"] label { color: #9090b8 !important; }
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,[data-testid="stSidebar"] h4 {
  font-family: 'Sora', sans-serif !important;
  font-size: 0.65rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #5a5a80 !important;
}
[data-testid="stSidebar"] hr { border-color: var(--border) !important; margin: 10px 0 !important; }

/* sidebar file uploader */
[data-testid="stSidebar"] [data-testid="stFileUploader"] {
  background: rgba(255,255,255,0.02) !important;
  border: 1px dashed rgba(255,255,255,0.09) !important;
  border-radius: var(--r-md) !important;
  padding: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploader"] * { color: #7878a0 !important; }

/* sidebar selectbox */
[data-testid="stSidebar"] .stSelectbox > div > div {
  background: var(--glass) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  color: var(--text) !important;
  font-size: 0.82rem !important;
}

/* sidebar buttons */
[data-testid="stSidebar"] .stButton > button {
  width: 100% !important;
  background: var(--glass) !important;
  border: 1px solid var(--border) !important;
  color: #8888b8 !important;
  border-radius: var(--r-md) !important;
  font-size: 0.8rem !important;
  font-family: 'DM Sans', sans-serif !important;
  padding: 7px 14px !important;
  transition: all 0.18s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: rgba(139,122,204,0.12) !important;
  border-color: rgba(139,122,204,0.3) !important;
  color: var(--text) !important;
}

/* ── MAIN TITLE + CAPTION ────────────────────────────────────── */
h1 {
  font-family: 'Sora', sans-serif !important;
  font-weight: 700 !important;
  color: var(--text) !important;
  letter-spacing: -0.025em !important;
}
.stCaption { color: var(--muted) !important; font-size: 0.75rem !important; }
p { color: var(--text) !important; line-height: 1.7 !important; }

/* ── CHAT MESSAGES — GLASS CARDS ─────────────────────────────── */
[data-testid="stChatMessage"] {
  background: var(--glass) !important;
  backdrop-filter: blur(14px) !important;
  -webkit-backdrop-filter: blur(14px) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-xl) !important;
  padding: 18px 22px !important;
  margin-bottom: 10px !important;
  transition: border-color 0.2s, background 0.2s !important;
  position: relative;
}
[data-testid="stChatMessage"]:hover {
  background: var(--glass-hov) !important;
  border-color: var(--border-hov) !important;
}

/* Accent stripe on user messages */
[data-testid="stChatMessage"][data-testid*="user"],
div[data-testid="stChatMessage"]:has(svg[data-testid="chatAvatarIcon-user"]) {
  border-left: 2px solid var(--teal) !important;
}

/* ── CHAT INPUT ───────────────────────────────────────────────── */
[data-testid="stChatInput"] > div {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  border-radius: var(--r-lg) !important;
  transition: border-color 0.2s !important;
}
[data-testid="stChatInput"] > div:focus-within {
  border-color: rgba(139,122,204,0.35) !important;
  box-shadow: 0 0 0 3px rgba(139,122,204,0.08) !important;
}
[data-testid="stChatInput"] textarea {
  color: var(--text) !important;
  font-family: 'DM Sans', sans-serif !important;
}

/* ── TEXT INPUTS (login) ─────────────────────────────────────── */
.stTextInput > div > div {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stTextInput > div > div:focus-within {
  border-color: rgba(139,122,204,0.4) !important;
  box-shadow: 0 0 0 3px rgba(139,122,204,0.1) !important;
}
.stTextInput input { color: var(--text) !important; font-family: 'DM Sans', sans-serif !important; }
.stTextInput input::placeholder { color: var(--muted) !important; }

/* ── SELECTBOX ────────────────────────────────────────────────── */
.stSelectbox > div > div {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  color: var(--text) !important;
  font-size: 0.83rem !important;
}

/* ── MAIN BUTTONS ─────────────────────────────────────────────── */
.stButton > button {
  background: var(--glass) !important;
  border: 1px solid var(--border) !important;
  color: #adadce !important;
  border-radius: var(--r-md) !important;
  font-family: 'DM Sans', sans-serif !important;
  font-size: 0.83rem !important;
  font-weight: 500 !important;
  padding: 9px 18px !important;
  transition: all 0.18s ease !important;
  letter-spacing: 0.01em !important;
}
.stButton > button:hover {
  background: rgba(139,122,204,0.13) !important;
  border-color: rgba(139,122,204,0.35) !important;
  color: var(--text) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 20px rgba(139,122,204,0.12) !important;
}

/* ── TABS (login screen) ──────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  background: rgba(255,255,255,0.025) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  padding: 3px !important;
  gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  border-radius: 7px !important;
  color: var(--muted) !important;
  font-family: 'DM Sans', sans-serif !important;
  font-size: 0.85rem !important;
  padding: 7px 18px !important;
}
.stTabs [aria-selected="true"] {
  background: rgba(139,122,204,0.2) !important;
  color: var(--text) !important;
}

/* ── ALERTS ───────────────────────────────────────────────────── */
[data-testid="stAlert"] {
  background: rgba(255,255,255,0.03) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r-md) !important;
  font-size: 0.83rem !important;
}

/* ── CODE BLOCKS in chat ─────────────────────────────────────── */
[data-testid="stChatMessage"] code {
  background: rgba(255,255,255,0.07) !important;
  border-radius: 5px !important;
  color: var(--amber) !important;
  font-size: 0.87em !important;
  padding: 1px 5px !important;
}

/* ── SPINNER ─────────────────────────────────────────────────── */
[data-testid="stSpinner"] > div > div { border-top-color: var(--violet) !important; }

/* ── SCROLLBAR ───────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.09); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.16); }

/* ── MODE CHIP SELECTBOX ─────────────────────────────────────── */
.mode-chip .stSelectbox > div > div {
  background: rgba(255,255,255,0.03) !important;
  border: 1px solid rgba(255,255,255,0.07) !important;
  border-radius: 22px !important;
  font-size: 0.78rem !important;
  color: #adadce !important;
  min-height: 32px !important;
  padding: 0 10px !important;
}
.mode-chip .stSelectbox > div > div:hover { border-color: rgba(139,122,204,0.3) !important; }

/* ── ICON RAIL (full-height collapsed sidebar) ───────────────── */
#cls-rail {
  display: none;
  position: fixed !important;
  left: 0 !important; 
  top: 0 !important; 
  bottom: 0 !important;
  width: 60px !important;
  height: 100vh !important;
  flex-direction: column;
  align-items: center;
  z-index: 999999 !important;
  background: #0a0a12 !important;
  border-right: 1px solid rgba(255,255,255,0.06);
}
/* top section — brand + nav icons */
#cls-rail .rail-top {
  display: flex; flex-direction: column;
  align-items: center; gap: 2px;
  padding: 14px 0 0; flex: 1;
}
/* bottom section — user avatar */
#cls-rail .rail-bot {
  display: flex; flex-direction: column;
  align-items: center;
  padding: 0 0 14px;
}
.rail-ic {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 9px;
  color: #4a4a6a;
  font-size: 1rem;
  cursor: default;
  transition: background 0.15s, color 0.15s;
  user-select: none;
  margin: 1px 0;
}
.rail-ic:hover { background: rgba(255,255,255,0.06); color: #9090b8; }
.rail-ic.rail-brand {
  color: #8b7acc;
  font-size: 1.1rem;
  margin-bottom: 8px;
}
.rail-sep {
  width: 24px; height: 1px;
  background: rgba(255,255,255,0.05);
  margin: 5px 0;
}
.rail-avatar {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg,#8b7acc,#3ca18d);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; font-weight: 600;
  color: #fff; cursor: default;
  font-family: 'Sora', sans-serif;
}

/* ── TELEPROMPTER HIGHLIGHT (Active Message Pulse) ───────────── */
@keyframes active-pulse {
  0% { box-shadow: 0 0 0 0 rgba(139,122,204, 0.4); border-color: rgba(139,122,204, 0.8); }
  70% { box-shadow: 0 0 0 8px rgba(139,122,204, 0); border-color: rgba(139,122,204, 0.3); }
  100% { box-shadow: 0 0 0 0 rgba(139,122,204, 0); border-color: rgba(255,255,255,0.07); }
}

[data-testid="stChatMessage"]:has(svg[data-testid="chatAvatarIcon-assistant"]):last-of-type {
  animation: active-pulse 3s infinite;
  background: linear-gradient(145deg, var(--glass), rgba(139,122,204,0.05)) !important;
  border-left: 3px solid var(--violet) !important;
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SUPABASE
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase: Client = init_supabase()

if "user" not in st.session_state:
    st.session_state.user = None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LOGIN SCREEN
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.user is None:
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        # Brand mark (Flattened and Unicode-safe)
        st.markdown("""
        <div style="text-align:center;padding:32px 0 28px;">
          <div style="display:inline-flex;align-items:center;justify-content:center;width:56px;height:56px;border-radius:16px;margin-bottom:14px;background:linear-gradient(135deg,rgba(139,122,204,0.25),rgba(60,161,141,0.25));border:1px solid rgba(255,255,255,0.1);font-size:1.7rem;">&#9672;</div>
          <div style="font-family:'Sora',sans-serif;font-size:1.6rem;font-weight:700;color:#ddddf0;letter-spacing:-0.025em;">AI Classroom</div>
          <div style="font-size:0.8rem;color:#6a6a90;margin-top:5px;">Sign in to access your personal learning space</div>
        </div>
        """, unsafe_allow_html=True)

        tab_in, tab_up = st.tabs(["Sign In", "Create Account"])

        with tab_in:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            email = st.text_input("Email", key="li_e", placeholder="you@example.com", label_visibility="collapsed")
            pwd   = st.text_input("Password", type="password", key="li_p", placeholder="Password", label_visibility="collapsed")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("Sign In →", use_container_width=True, key="li_btn"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": pwd})
                    st.session_state.user = res.user
                    st.rerun()
                except Exception as e:
                    st.error(f"Sign in failed — {e}")

        with tab_up:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            ne = st.text_input("Email", key="su_e", placeholder="you@example.com", label_visibility="collapsed")
            np_ = st.text_input("Password", type="password", key="su_p", placeholder="Min. 6 characters", label_visibility="collapsed")
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if st.button("Create Account →", use_container_width=True, key="su_btn"):
                try:
                    supabase.auth.sign_up({"email": ne, "password": np_})
                    st.success("Account created — switch to Sign In to continue.")
                except Exception as e:
                    st.error(f"Sign up failed — {e}")

        st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# 3. SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    uemail = st.session_state.user.email
    initial = uemail[0].upper()
    
    # Flattened sidebar profile card
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:11px;padding:4px 0 12px;">
      <div style="flex-shrink:0;width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#8b7acc,#3ca18d);display:flex;align-items:center;justify-content:center;font-family:'Sora',sans-serif;font-size:0.9rem;color:#fff;font-weight:600;">{initial}</div>
      <div style="min-width:0;">
        <div style="font-size:0.8rem;color:#c8c8e8;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{uemail.split('@')[0]}</div>
        <div style="font-size:0.68rem;color:#5a5a80;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{uemail}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ... keep your Sign Out button right below this ...

    if st.button("Sign Out", key="so_btn"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.markdown("---")
# ... existing Sign Out button code ...
    if st.button("Sign Out", key="so_btn"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.markdown("---")
    
    # ⬇️ PASTE THIS NEW BLOCK HERE ⬇️
    st.markdown("#### 📚 Recent Lectures")
    try:
        past_sessions = supabase.table("class_sessions").select("id, topic").eq("user_id", st.session_state.user.id).order("created_at", desc=True).limit(5).execute()
        
        if not past_sessions.data:
            st.caption("No saved lectures yet.")
        else:
            for session in past_sessions.data:
                display_topic = session['topic'][:22] + "..." if len(session['topic']) > 22 else session['topic']
                if st.button(f"📄 {display_topic}", key=f"load_{session['id']}", use_container_width=True):
                    st.toast("Loading session feature coming soon!")
    except Exception as e:
        st.caption("Could not load history.")
        
    st.markdown("---")
    # ⬆️ END NEW BLOCK ⬆️

    st.markdown("#### Course Material")
    # ... rest of the file uploader code ...
    
    st.markdown("#### Course Material")
    uploaded_file = st.file_uploader(
        "pdf_upload", type="pdf",
        label_visibility="collapsed",
        help="Upload a PDF to start the lecture"
    )
    st.caption("Upload a PDF to start the session")

    st.markdown("---")
    st.markdown("#### Teacher Voice")
    voice_option = st.selectbox(
        "voice", ["British · Ryan", "American · Aria", "Nigerian · Abeo"],
        label_visibility="collapsed", key="voice_sel"
    )
    voice_map = {
        "British · Ryan":  "en-GB-RyanNeural",
        "American · Aria": "en-US-AriaNeural",
        "Nigerian · Abeo": "en-NG-AbeoNeural",
    }
    selected_voice = voice_map[voice_option]

    st.markdown("---")
    if st.button("Clear Session", key="cls_btn"):
        for k in ["messages", "pdf_text", "chat"]:
            st.session_state.pop(k, None)
        st.rerun()
# ── Icon rail (appears when sidebar is collapsed) ──────────────────────────────
st.markdown(f"""
<div id="cls-rail">
  <div class="rail-top">
    <div class="rail-ic rail-brand" title="AI Classroom">◈</div>
    <div class="rail-sep"></div>
    <div class="rail-ic" title="Course Material">↑</div>
    <div class="rail-ic" title="Teacher Voice">♪</div>
    <div class="rail-ic" title="Learning Mode">◎</div>
    <div class="rail-sep"></div>
    <div class="rail-ic" title="Export Notes">⎘</div>
    <div class="rail-ic" title="Clear Session">✕</div>
  </div>
  <div class="rail-bot">
    <div class="rail-avatar" title="{uemail}">{initial}</div>
  </div>
</div>
<script>
(function watchSidebar() {{
  var sb = document.querySelector('[data-testid="stSidebar"]');
  if (!sb) {{ setTimeout(watchSidebar, 350); return; }}
  var rail = document.getElementById('cls-rail');
  function sync() {{
    if (!rail) return;
    rail.style.display = (sb.getAttribute('aria-expanded') === 'false') ? 'flex' : 'none';
  }}
  new MutationObserver(sync).observe(sb, {{ attributes: true }});
  sync();
}})();
</script>
""", unsafe_allow_html=True)


""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. API KEYS
# ═══════════════════════════════════════════════════════════════════════════════
if "api_keys" not in st.session_state:
    k1 = st.secrets.get("GEMINI_API_KEY_1")
    k2 = st.secrets.get("GEMINI_API_KEY_2")
    st.session_state.api_keys = [k for k in [k1, k2] if k]
    st.session_state.current_key_index = 0

if not st.session_state.api_keys:
    st.error("Missing API keys — add GEMINI_API_KEY_1 to Streamlit secrets.")
    st.stop()

genai.configure(api_key=st.session_state.api_keys[st.session_state.current_key_index])
model = genai.GenerativeModel("gemini-2.5-flash")

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state: st.session_state.messages = []
if "pdf_text" not in st.session_state: st.session_state.pdf_text = ""
if "mode"     not in st.session_state: st.session_state.mode     = "Seminar"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def safe_generate_chat(chat_session, message):
    keys = st.session_state.api_keys
    for _ in range(len(keys)):
        try:
            return chat_session.send_message(message)
        except ResourceExhausted:
            st.warning(f"Key {st.session_state.current_key_index + 1} exhausted, switching…")
            st.session_state.current_key_index = (st.session_state.current_key_index + 1) % len(keys)
            genai.configure(api_key=keys[st.session_state.current_key_index])
            global model
            model = genai.GenerativeModel("gemini-2.5-flash")
            chat_session = model.start_chat(history=chat_session.history)
        except Exception:
            raise
    st.error("All API keys exhausted — please wait a few minutes.")
    st.stop()


def trim_text(text, max_chars=6000):
    return text[:max_chars] + "\n\n[…trimmed]" if len(text) > max_chars else text


def make_action_bar(audio_b64: str, audio_id: str, message_text: str) -> str:
    """
    Isolated-iframe action bar with cross-iframe audio-stop protocol.
    Uses a unique marker token so autoplay suppression is reliable.
    """
    audio_tag  = ""
    listen_btn = "<span style='color:#444;font-size:0.75rem;'>—</span>"

    if audio_b64:
        audio_tag  = f'<audio id="{audio_id}" src="data:audio/mp3;base64,{audio_b64}"></audio>'
        listen_btn = (
            f'<button id="btn_{audio_id}" class="ab" title="Play / Pause"'
            f' onclick="togglePlay()">▶</button>'
        )

    safe = (message_text
            .replace("&", "&amp;").replace('"', "&quot;")
            .replace("'", "&#39;").replace("<", "&lt;").replace(">", "&gt;"))

    # NOTE: The string __AUTOPLAY_TOKEN__ is used as a replacement anchor below.
    return f"""<!DOCTYPE html><html><head><style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:transparent;font-family:'DM Sans',sans-serif;padding:3px 0;}}
.bar{{display:flex;gap:3px;align-items:center;}}
.ab{{background:none;border:none;cursor:pointer;font-size:0.88rem;padding:5px 8px;
     border-radius:6px;color:#606090;transition:background .14s,color .14s;}}
.ab:hover{{background:rgba(255,255,255,.07);color:#ddddf0;}}
.ab.on-teal{{color:#3ca18d;}} .ab.on-red{{color:#c96b6b;}}
.toast{{font-size:0.7rem;color:#3ca18d;margin-left:3px;opacity:0;transition:opacity .3s;}}
</style></head>
<body>
  {audio_tag}
  <div id="tx_{audio_id}" style="display:none">{safe}</div>
  <div class="bar">
    {listen_btn}
    <button class="ab" title="Copy" onclick="
      navigator.clipboard.writeText(document.getElementById('tx_{audio_id}').innerText)
        .then(()=>{{var t=document.getElementById('tos_{audio_id}');
                    t.style.opacity=1;setTimeout(()=>t.style.opacity=0,1700);}})
    ">⎘</button>
    <span class="toast" id="tos_{audio_id}">Copied</span>
    <button class="ab" id="lk_{audio_id}"
      onclick="this.classList.toggle('on-teal');document.getElementById('dl_{audio_id}').classList.remove('on-red')">↑</button>
    <button class="ab" id="dl_{audio_id}"
      onclick="this.classList.toggle('on-red');document.getElementById('lk_{audio_id}').classList.remove('on-teal')">↓</button>
  </div>
<script>(function(){{
  var MY="{audio_id}", aud=document.getElementById(MY);
  /* ── coordinator (injected once into parent) ── */
  if(window.parent&&!window.parent.__aCoord){{
    window.parent.__aCoord=true;
    window.parent.addEventListener("message",function(e){{
      if(!e.data||e.data.type!=="a_play")return;
      window.parent.document.querySelectorAll("iframe").forEach(function(f){{
        try{{f.contentWindow.postMessage({{type:"a_stop",ex:e.data.id}},"*");}}catch(_){{}}
      }});
    }});
  }}
  /* ── stop listener ── */
  window.addEventListener("message",function(e){{
    if(!e.data||e.data.type!=="a_stop"||e.data.ex===MY)return;
    if(aud&&!aud.paused){{aud.pause();var b=document.getElementById("btn_"+MY);if(b)b.innerHTML="▶";}}
  }});
  /* ── events ── */
  if(aud){{
    aud.addEventListener("play",function(){{
      window.parent&&window.parent.postMessage({{type:"a_play",id:MY}},"*");
      var b=document.getElementById("btn_"+MY);if(b)b.innerHTML="⏸";
    }});
    aud.addEventListener("pause",function(){{var b=document.getElementById("btn_"+MY);if(b)b.innerHTML="▶";}});
    aud.addEventListener("ended",function(){{var b=document.getElementById("btn_"+MY);if(b)b.innerHTML="▶";}});
    /* __AUTOPLAY_TOKEN__ */ setTimeout(function(){{aud.play().catch(function(){{}});}},420);
  }}
  window.togglePlay=function(){{if(!aud)return;aud.paused?aud.play().catch(function(){{}}):aud.pause();}};
}})();</script>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PAGE HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex;align-items:center;gap:14px;padding:10px 2px 6px;">
  <div style="flex-shrink:0;width:44px;height:44px;border-radius:13px;
              background:linear-gradient(135deg,rgba(139,122,204,.22),rgba(60,161,141,.22));
              border:1px solid rgba(255,255,255,.09);
              display:flex;align-items:center;justify-content:center;font-size:1.45rem;">◈</div>
  <div>
    <div style="font-family:'Sora',sans-serif;font-size:1.25rem;font-weight:700;
                color:#ddddf0;letter-spacing:-0.02em;line-height:1.2;">AI Classroom</div>
    <div style="font-size:0.7rem;color:#5a5a80;margin-top:2px;letter-spacing:0.02em;">
      Powered by Gemini 2.5 Flash</div>
  </div>
</div>
<div style="height:1px;background:linear-gradient(90deg,rgba(139,122,204,.25),rgba(60,161,141,.2),transparent);
            margin:4px 0 14px;"></div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PDF INGESTION
# ═══════════════════════════════════════════════════════════════════════════════
if uploaded_file is not None and st.session_state.pdf_text == "":
    with st.spinner("Reading course material…"):
        reader = PyPDF2.PdfReader(uploaded_file)
        text = "".join(
            reader.pages[p].extract_text()
            for p in range(15, min(19, len(reader.pages)))
        )
        st.session_state.pdf_text = trim_text(text)

        if st.session_state.mode == "Seminar":
            persona = "You are a conversational tutor. Keep explanations clean and text-based."
        else:
            persona = "You are a rigorous math professor at a chalkboard. Find formulas and break them down step-by-step."

        st.session_state.chat = model.start_chat(history=[])
        try:
            resp = safe_generate_chat(
                st.session_state.chat,
                f"{persona}\n\nCourse material:\n{st.session_state.pdf_text}\n\n"
                "Welcome the student and ask if they want a 'Fresh Start' or have an 'Area of Concern'."
            )
            st.session_state.messages.append({"role": "assistant", "content": resp.text})
        except Exception as e:
            st.session_state.pdf_text = ""
            st.error(f"Failed to start session: {e}")
            st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# 8. VOICE SWITCH
# ═══════════════════════════════════════════════════════════════════════════════
if "current_voice" not in st.session_state:
    st.session_state.current_voice = selected_voice

if selected_voice != st.session_state.current_voice:
    st.session_state.current_voice = selected_voice
    msgs = st.session_state.messages
    if msgs and msgs[-1]["role"] == "assistant":
        with st.spinner("Switching voice…"):
            last = msgs[-1]
            vt = re.sub(r'\$\$.*?\$\$',
                        lambda m: ' ... ' * max(1, len(m.group(0)) // 15),
                        last["content"], flags=re.DOTALL)
            vt = re.sub(r'[*#_`$\\-]+', '', vt)
            async def _regen(t, p, v):
                await edge_tts.Communicate(t, v, rate="-10%").save(p)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                asyncio.run(_regen(vt, fp.name, selected_voice))
                nb64 = base64.b64encode(open(fp.name, "rb").read()).decode()
            aid = f"audio_{len(msgs) - 1}"
            msgs[-1]["audio_html"] = make_action_bar(nb64, aid, last["content"])
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 9. CHAT HISTORY  — glass cards, single render block, no duplicate
# ═══════════════════════════════════════════════════════════════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

        # Re-draw graph if this message had one
        if msg.get("plot_formula"):
            try:
                x = np.linspace(-10, 10, 400)
                y = eval(msg["plot_formula"], {"__builtins__": None}, {"x": x, "np": np})
                st.line_chart(
                    pd.DataFrame({"x": x, "y": y}).set_index("x"),
                    use_container_width=True
                )
            except Exception:
                pass

        # Action bar — ONLY ONE BLOCK (no duplicate)
        # Suppress autoplay for every message except the latest
        if msg["role"] == "assistant" and msg.get("audio_html"):
            html_to_render = msg["audio_html"]
            if msg is not st.session_state.messages[-1]:
                html_to_render = html_to_render.replace(
                    "/* __AUTOPLAY_TOKEN__ */ setTimeout(function(){aud.play().catch(function(){});},420);",
                    "/* autoplay suppressed */"
                )
            components.html(html_to_render, height=46, scrolling=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. INPUT BAR — mode chip + action buttons + chat input
# ═══════════════════════════════════════════════════════════════════════════════
# Mode chip (replaces sidebar radio — lives near the prompt)
chip_col, _, btn1_col, btn2_col = st.columns([2.2, 3.5, 1.2, 1.2])
with chip_col:
    with st.container():
        st.markdown('<div class="mode-chip">', unsafe_allow_html=True)
        mode_pick = st.selectbox(
            "mode_chip",
            ["◎ Seminar — Text & Concepts", "∑ Chalkboard — Heavy Math"],
            label_visibility="collapsed",
            key="mode_chip_sel"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    st.session_state.mode = "Seminar" if "Seminar" in mode_pick else "Chalkboard"

with btn1_col:
    raise_hand = st.button("✋ Excuse Me", key="rh_btn")
with btn2_col:
    quiz_me = st.button("✏ Quiz Me", key="qm_btn")

student_input = None
if raise_hand:
    student_input = "Excuse me, professor — I have a question about that."
if quiz_me:
    student_input = (
        "Professor, please give me a 3-question multiple-choice quiz strictly based on "
        "the course materials. Ask the questions now but hold the answers until I respond."
    )
if typed := st.chat_input("Ask a question, or type your quiz answers…"):
    student_input = typed


# ═══════════════════════════════════════════════════════════════════════════════
# 11. PROCESS STUDENT INPUT
# ═══════════════════════════════════════════════════════════════════════════════
if student_input:
    if "chat" not in st.session_state:
        st.error("Upload a course PDF first to open the session.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": student_input})
    with st.chat_message("user"):
        st.write(student_input)

    mode = st.session_state.mode
    if mode == "Seminar":
        prompt = (
            "(Conversational tutor. Put all internal reasoning inside <thought> tags, "
            "then write your response below them.)\n\nStudent: " + student_input
        )
    else:
        prompt = (
            "(Rigorous math professor at a chalkboard. Hide reasoning in <thought> tags. "
            "Format all math in LaTeX: $ for inline, $$ for block equations. "
            "If asked to graph, output the Python formula in <plot> tags, e.g. <plot>np.sin(x)</plot>.)\n\n"
            "Student: " + student_input
        )

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):

            # ── TEXT ──────────────────────────────────────────────────────────
            try:
                resp    = safe_generate_chat(st.session_state.chat, prompt)
                raw     = resp.text
                ui_text = re.sub(r'<thought>.*?(?:</thought>|$)', '', raw, flags=re.DOTALL).strip()
                if not ui_text:
                    ui_text = "Could you clarify which part you'd like to explore further?"

                vtext = re.sub(
                    r'\$\$.*?\$\$',
                    lambda m: '. . . ' * max(1, len(m.group(0)) // 8),
                    ui_text, flags=re.DOTALL
                )
                vtext = re.sub(r'[*#_`$\\-]+', '', vtext)
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

            # ── AUDIO ─────────────────────────────────────────────────────────
            audio_b64 = ""
            try:
                async def _speak(t, p, v):
                    await edge_tts.Communicate(t, v, rate="-10%").save(p)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    asyncio.run(_speak(vtext, fp.name, selected_voice))
                    audio_b64 = base64.b64encode(open(fp.name, "rb").read()).decode()
            except Exception:
                pass

        # ── PLOT CHECK ────────────────────────────────────────────────────────
        plot_formula = None
        pm = re.search(r'<plot>(.*?)</plot>', ui_text)
        if pm:
            plot_formula = pm.group(1).strip()
            ui_text = re.sub(r'<plot>.*?</plot>', '', ui_text, flags=re.DOTALL).strip()

        st.write(ui_text)

        if plot_formula:
            try:
                x = np.linspace(-10, 10, 400)
                y = eval(plot_formula, {"__builtins__": None}, {"x": x, "np": np})
                st.line_chart(
                    pd.DataFrame({"x": x, "y": y}).set_index("x"),
                    use_container_width=True
                )
            except Exception:
                st.warning(f"Could not render graph: {plot_formula}")

        # ── SAVE + RERUN (no live draw — chat loop draws on rerun) ────────────
        audio_id   = f"audio_{len(st.session_state.messages)}"
        action_bar = make_action_bar(audio_b64, audio_id, ui_text)

        st.session_state.messages.append({
            "role":         "assistant",
            "content":      ui_text,
            "audio_html":   action_bar,
            "plot_formula": plot_formula,
        })
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 12. EXPORT NOTES (sidebar, bottom)
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    if st.session_state.get("messages"):
        st.markdown("---")
        st.markdown("#### Export Notes")
        fmt = st.selectbox(
            "export_fmt",
            ["HTML — best for math", "Plain text"],
            label_visibility="collapsed",
            key="exp_fmt"
        )

        raw_md = "# AI Classroom Notes\n\n"
        for msg in st.session_state.messages:
            role = "Student" if msg["role"] == "user" else "Professor"
            raw_md += f"**{role}:**\n{msg.get('content','')}\n\n---\n\n"

        if "HTML" in fmt:
            html_out = """<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>Lecture Notes</title>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=DM+Sans:wght@400;500&display=swap');
  body{font-family:'DM Sans',sans-serif;max-width:820px;margin:40px auto;padding:24px;
       background:#0b0b11;color:#ddddf0;line-height:1.7;}
  h2{font-family:'Sora',sans-serif;font-weight:700;letter-spacing:-.02em;
     border-bottom:1px solid rgba(255,255,255,.07);padding-bottom:12px;margin-bottom:28px;}
  .msg{margin-bottom:18px;padding:18px 22px;border-radius:16px;
       border:1px solid rgba(255,255,255,.07);}
  .usr{border-left:2px solid #3ca18d;background:rgba(60,161,141,.06);}
  .ast{border-left:2px solid #8b7acc;background:rgba(139,122,204,.05);}
  .role{font-size:.68rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
        margin-bottom:10px;color:#5a5a80;}
  pre{white-space:pre-wrap;font-family:inherit;}
  ::-webkit-scrollbar{width:4px;} ::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);}
</style></head><body><h2>◈ AI Classroom Notes</h2>"""

            for i, msg in enumerate(st.session_state.messages):
                cls  = "usr" if msg["role"] == "user" else "ast"
                role = "Student" if msg["role"] == "user" else "Professor"
                txt  = msg.get("content", "").replace("<", "&lt;").replace(">", "&gt;")
                html_out += f'\n<div class="msg {cls}"><div class="role">{role}</div><pre>{txt}</pre>'

                if msg.get("plot_formula"):
                    try:
                        x  = np.linspace(-10, 10, 100)
                        y  = eval(msg["plot_formula"], {"__builtins__": None}, {"x": x, "np": np})
                        xl = [round(float(v), 2) for v in x]
                        yl = [round(float(v), 2) for v in y]
                        html_out += f"""
<div style="position:relative;height:280px;margin-top:14px;">
  <canvas id="c{i}"></canvas></div>
<script>
window.addEventListener('DOMContentLoaded',function(){{
  new Chart(document.getElementById('c{i}').getContext('2d'),{{
    type:'line',
    data:{{labels:{xl},datasets:[{{data:{yl},borderColor:'#3ca18d',
      backgroundColor:'rgba(60,161,141,0.1)',borderWidth:2,pointRadius:0,tension:0.4}}]}},
    options:{{responsive:true,maintainAspectRatio:false,
              plugins:{{legend:{{display:false}}}},
              scales:{{x:{{ticks:{{color:'#5a5a80'}},grid:{{color:'rgba(255,255,255,.05)'}}}},
                       y:{{ticks:{{color:'#5a5a80'}},grid:{{color:'rgba(255,255,255,.05)'}}}}}}}}
  }});
}});
</script>"""
                    except Exception:
                        pass
                html_out += '</div>'
            html_out += "</body></html>"

            st.download_button("↓ Download HTML", html_out, "notes.html", "text/html", key="dl_html")
            st.caption("Tip: open in browser → Ctrl+P → Save as PDF")
        else:
            clean = raw_md.replace("**", "").replace("#", "").strip()
            st.download_button("↓ Download TXT", clean, "notes.txt", "text/plain", key="dl_txt")
    else:
        st.caption("Start the session to generate notes")

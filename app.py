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
import uuid as uuid_lib
import json
from google.api_core.exceptions import ResourceExhausted
import streamlit.components.v1 as components
import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════════
# 0. PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AI Classroom",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
# 0.1  GLOBAL CSS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,400&display=swap');

:root {
  --bg:        #0b0b11;
  --glass:     rgba(255,255,255,0.038);
  --glass-hov: rgba(255,255,255,0.06);
  --border:    rgba(255,255,255,0.07);
  --bord-hov:  rgba(255,255,255,0.13);
  --text:      #ddddf0;
  --muted:     #6a6a90;
  --amber:     #c9a45a;
  --teal:      #3ca18d;
  --violet:    #8b7acc;
}

html,body,[class*="css"],.stApp {
  font-family:'DM Sans',sans-serif !important;
  background:var(--bg) !important;
  color:var(--text) !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
  background:rgba(9,9,16,0.98) !important;
  border-right:1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div { padding-top:1rem !important; }
[data-testid="stSidebar"] *, [data-testid="stSidebar"] label { color:#9090b8 !important; }
[data-testid="stSidebar"] h4 {
  font-family:'Sora',sans-serif !important;
  font-size:0.62rem !important; font-weight:600 !important;
  letter-spacing:0.12em; text-transform:uppercase; color:#4a4a70 !important;
}
[data-testid="stSidebar"] hr { border-color:var(--border) !important; margin:8px 0 !important; }
[data-testid="stSidebar"] [data-testid="stFileUploader"] {
  background:rgba(255,255,255,0.02) !important;
  border:1px dashed rgba(255,255,255,0.08) !important;
  border-radius:10px !important; padding:4px !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploader"] * { color:#6868a0 !important; }
[data-testid="stSidebar"] .stSelectbox > div > div {
  background:var(--glass) !important; border:1px solid var(--border) !important;
  border-radius:9px !important; font-size:0.81rem !important;
}
[data-testid="stSidebar"] .stButton > button {
  width:100% !important; background:var(--glass) !important;
  border:1px solid var(--border) !important; color:#8888b8 !important;
  border-radius:9px !important; font-size:0.79rem !important;
  font-family:'DM Sans',sans-serif !important; padding:6px 12px !important;
  transition:all .18s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background:rgba(139,122,204,0.12) !important;
  border-color:rgba(139,122,204,0.3) !important; color:var(--text) !important;
}

/* ── CHAT MESSAGES ── */
[data-testid="stChatMessage"] {
  background:var(--glass) !important;
  backdrop-filter:blur(12px) !important;
  -webkit-backdrop-filter:blur(12px) !important;
  border:1px solid var(--border) !important;
  border-radius:18px !important;
  padding:16px 20px !important; margin-bottom:9px !important;
  transition:border-color .2s,background .2s !important;
}
[data-testid="stChatMessage"]:hover {
  background:var(--glass-hov) !important; border-color:var(--bord-hov) !important;
}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
  border-left:2px solid var(--teal) !important;
}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
  border-left:2px solid var(--violet) !important;
}

/* ── CHAT INPUT ── */
[data-testid="stChatInput"] > div {
  background:rgba(255,255,255,0.04) !important;
  border:1px solid rgba(255,255,255,0.08) !important;
  border-radius:14px !important; transition:border-color .2s !important;
}
[data-testid="stChatInput"] > div:focus-within {
  border-color:rgba(139,122,204,0.35) !important;
  box-shadow:0 0 0 3px rgba(139,122,204,0.08) !important;
}
[data-testid="stChatInput"] textarea {
  color:var(--text) !important; font-family:'DM Sans',sans-serif !important;
}

/* ── TEXT INPUTS ── */
.stTextInput > div > div {
  background:rgba(255,255,255,0.04) !important;
  border:1px solid var(--border) !important;
  border-radius:10px !important; transition:border-color .2s, box-shadow .2s !important;
}
.stTextInput > div > div:focus-within {
  border-color:rgba(139,122,204,0.4) !important;
  box-shadow:0 0 0 3px rgba(139,122,204,0.1) !important;
}
.stTextInput input { color:var(--text) !important; font-family:'DM Sans',sans-serif !important; }
.stTextInput input::placeholder { color:var(--muted) !important; }

/* ── SELECTBOX ── */
.stSelectbox > div > div {
  background:rgba(255,255,255,0.04) !important;
  border:1px solid var(--border) !important;
  border-radius:10px !important; font-size:0.83rem !important;
}

/* ── BUTTONS ── */
.stButton > button {
  background:var(--glass) !important; border:1px solid var(--border) !important;
  color:#adadce !important; border-radius:10px !important;
  font-family:'DM Sans',sans-serif !important; font-size:0.83rem !important;
  font-weight:500 !important; padding:8px 16px !important; transition:all .18s ease !important;
}
.stButton > button:hover {
  background:rgba(139,122,204,0.13) !important;
  border-color:rgba(139,122,204,0.35) !important;
  color:var(--text) !important; transform:translateY(-1px) !important;
}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"] {
  background:rgba(255,255,255,0.025) !important; border:1px solid var(--border) !important;
  border-radius:10px !important; padding:3px !important; gap:2px !important;
}
.stTabs [data-baseweb="tab"] {
  background:transparent !important; border-radius:7px !important;
  color:var(--muted) !important; font-family:'DM Sans',sans-serif !important;
  font-size:0.85rem !important; padding:7px 20px !important;
}
.stTabs [aria-selected="true"] {
  background:rgba(139,122,204,0.2) !important; color:var(--text) !important;
}

/* ── ALERTS ── */
[data-testid="stAlert"] {
  background:rgba(255,255,255,0.03) !important; border:1px solid var(--border) !important;
  border-radius:10px !important; font-size:0.82rem !important;
}

/* ── SPINNER ── */
[data-testid="stSpinner"] > div > div { border-top-color:var(--violet) !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width:4px; }
::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.09); border-radius:4px; }

/* ── MODE CHIP ── */
.mode-chip .stSelectbox > div > div {
  background:rgba(255,255,255,0.03) !important; border:1px solid rgba(255,255,255,0.07) !important;
  border-radius:20px !important; font-size:0.77rem !important; color:#adadce !important;
  min-height:32px !important;
}
.mode-chip .stSelectbox > div > div:hover { border-color:rgba(139,122,204,0.3) !important; }

/* ── NOW COVERING BANNER ── */
.now-covering {
  display:inline-flex; align-items:center; gap:8px; padding:5px 14px 5px 10px;
  background:rgba(139,122,204,0.07); border:1px solid rgba(139,122,204,0.16);
  border-radius:20px; font-size:0.72rem; color:#9a8fc8;
  margin-bottom:12px; max-width:100%; overflow:hidden;
}
.nc-dot {
  width:6px; height:6px; border-radius:50%; background:#8b7acc; flex-shrink:0;
  animation:ncpulse 2s ease-in-out infinite;
}
@keyframes ncpulse { 0%,100%{opacity:1;} 50%{opacity:0.35;} }
.nc-text { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

/* ── ICON RAIL ── */
#cls-rail {
  display:none; position:fixed; left:0; top:0; bottom:0; width:50px;
  flex-direction:column; align-items:center; z-index:99999;
  background:#090910; border-right:1px solid rgba(255,255,255,0.06);
}
#cls-rail .rt { display:flex; flex-direction:column; align-items:center; gap:1px; padding:12px 0 0; flex:1; }
#cls-rail .rb { padding:0 0 12px; }
.ric {
  width:36px; height:36px; display:flex; align-items:center; justify-content:center;
  border-radius:8px; color:#3a3a5a; font-size:0.95rem;
  transition:background .14s,color .14s; user-select:none; margin:1px 0;
}
.ric:hover { background:rgba(255,255,255,0.07); color:#9090b8; }
.ric.brand { color:#8b7acc; font-size:1.05rem; margin-bottom:6px; }
.rsep { width:22px; height:1px; background:rgba(255,255,255,0.05); margin:4px 0; }
.ravatar {
  width:28px; height:28px; border-radius:50%;
  background:linear-gradient(135deg,#8b7acc,#3ca18d);
  display:flex; align-items:center; justify-content:center;
  font-size:0.72rem; font-weight:600; color:#fff; font-family:'Sora',sans-serif;
}

/* ── LOGIN TABS — centered, auto-width, not full-stretch ── */
.stTabs [data-baseweb="tab-list"] {
  display:inline-flex !important;          /* shrink to content */
  width:auto !important;
  margin:0 auto !important;               /* centre in column  */
}
/* wrapper to actually centre the inline-flex child */
[data-testid="stTabs"] > div:first-child {
  display:flex !important;
  justify-content:center !important;
}

/* ── MOBILE ── */
@media (max-width:768px) {
  /* chat bubbles */
  [data-testid="stChatMessage"] {
    padding:10px 13px !important; border-radius:13px !important;
  }

  /* ── COMPACT PROMPT AREA ── */
  /* The input itself: shorter min-height so it doesn't dominate */
  [data-testid="stChatInput"] > div {
    border-radius:11px !important;
    min-height:44px !important;
  }
  [data-testid="stChatInput"] textarea {
    font-size:0.88rem !important;
    min-height:44px !important;
    padding:10px 14px !important;
  }
  /* submit button inside chat input */
  [data-testid="stChatInput"] button {
    width:34px !important; height:34px !important;
  }

  /* ── MODE CHIP + RAISE/QUIZ row ── */
  .stButton > button {
    padding:6px 10px !important; font-size:0.76rem !important;
  }

  /* ── GENERAL TEXT ── */
  p { font-size:0.88rem !important; }

  /* ── HIDE SIDEBAR TOGGLE LABEL ── */
  [data-testid="stSidebarCollapseButton"] span { display:none !important; }
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SUPABASE
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase: Client = init_supabase()
if "user" not in st.session_state:
    st.session_state.user = None


# ─── Session persistence ───────────────────────────────────────────────────────
def save_session_to_db():
    if not st.session_state.get("user") or not st.session_state.get("messages"):
        return
    sid = st.session_state.setdefault("session_id", str(uuid_lib.uuid4()))
    title = "New session"
    for m in st.session_state.messages:
        txt = m.get("content","").strip()
        if txt:
            title = re.sub(r'\s+',' ', txt)[:60]
            break
    lean = [{"role": m["role"], "content": m.get("content","")} for m in st.session_state.messages]
    try:
        supabase.table("chat_sessions").upsert({
            "id": sid,
            "user_id": str(st.session_state.user.id),
            "title": title,
            "messages": json.dumps(lean),
            "updated_at": "now()",
        }).execute()
    except Exception:
        pass

def load_recent_sessions():
    if not st.session_state.get("user"):
        return []
    try:
        res = (supabase.table("chat_sessions")
               .select("id,title,updated_at")
               .eq("user_id", str(st.session_state.user.id))
               .order("updated_at", desc=True).limit(8).execute())
        return res.data or []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LOGIN
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.user is None:
    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown("""
        <div style="text-align:center;padding:40px 0 24px;">
          <div style="display:inline-flex;align-items:center;justify-content:center;
                      width:60px;height:60px;border-radius:18px;margin-bottom:16px;
                      background:linear-gradient(135deg,rgba(139,122,204,0.22),rgba(60,161,141,0.22));
                      border:1px solid rgba(255,255,255,0.1);font-size:1.8rem;">◈</div>
          <div style="font-family:'Sora',sans-serif;font-size:1.7rem;font-weight:700;
                      color:#ddddf0;letter-spacing:-0.025em;">AI Classroom</div>
          <div style="font-size:0.8rem;color:#6a6a90;margin-top:6px;">
            Sign in to access your personal learning space</div>
        </div>
        """, unsafe_allow_html=True)

        t_in, t_up = st.tabs(["Sign In", "Create Account"])
        with t_in:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            em = st.text_input("e", key="li_e", placeholder="you@example.com", label_visibility="collapsed")
            pw = st.text_input("p", key="li_p", placeholder="Password", type="password", label_visibility="collapsed")
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            if st.button("Sign In →", use_container_width=True, key="li_btn"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                    st.session_state.user = res.user
                    st.rerun()
                except Exception as e:
                    st.error(f"Sign in failed — {e}")

        with t_up:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            ne  = st.text_input("e2", key="su_e", placeholder="you@example.com", label_visibility="collapsed")
            np_ = st.text_input("p2", key="su_p", placeholder="Min. 6 characters", type="password", label_visibility="collapsed")
            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            if st.button("Create Account →", use_container_width=True, key="su_btn"):
                try:
                    supabase.auth.sign_up({"email": ne, "password": np_})
                    st.success("Account created — switch to Sign In to continue.")
                except Exception as e:
                    st.error(f"Sign up failed — {e}")
        st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
uemail  = st.session_state.user.email
initial = uemail[0].upper()

with st.sidebar:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;padding:2px 0 10px;">
      <div style="flex-shrink:0;width:32px;height:32px;border-radius:50%;
                  background:linear-gradient(135deg,#8b7acc,#3ca18d);
                  display:flex;align-items:center;justify-content:center;
                  font-family:'Sora',sans-serif;font-size:0.85rem;color:#fff;font-weight:600;">
        {initial}</div>
      <div style="min-width:0;">
        <div style="font-size:0.78rem;color:#c8c8e8;font-weight:500;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
          {uemail.split('@')[0]}</div>
        <div style="font-size:0.66rem;color:#5a5a80;white-space:nowrap;
                    overflow:hidden;text-overflow:ellipsis;">{uemail}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Sign Out", key="so_btn"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.markdown("---")
    st.markdown("#### Course Material")
    uploaded_file = st.file_uploader("pdf", type="pdf", label_visibility="collapsed")
    st.caption("Upload a PDF to start the session")

    st.markdown("---")
    st.markdown("#### Teacher Voice")
    voice_option = st.selectbox(
        "voice", ["British · Ryan", "American · Aria", "Nigerian · Abeo"],
        label_visibility="collapsed", key="voice_sel"
    )
    voice_map = {"British · Ryan":"en-GB-RyanNeural","American · Aria":"en-US-AriaNeural","Nigerian · Abeo":"en-NG-AbeoNeural"}
    selected_voice = voice_map[voice_option]

    # ── Recent sessions ──
    st.markdown("---")
    st.markdown("#### Recent Sessions")
    recent = load_recent_sessions()
    if recent:
        for s in recent:
            label = (s.get("title") or "Untitled")[:42]
            if st.button(f"↩  {label}", key=f"sess_{s['id']}"):
                try:
                    row = (supabase.table("chat_sessions").select("messages")
                           .eq("id", s["id"]).single().execute())
                    restored = json.loads(row.data["messages"])
                    st.session_state.messages   = restored
                    st.session_state.session_id = s["id"]
                    st.session_state.pdf_text   = " "
                    st.session_state.pop("chat", None)
                    st.rerun()
                except Exception:
                    st.error("Could not restore session.")
    else:
        st.caption("No recent sessions yet")

    st.markdown("---")
    if st.button("Clear Session", key="cls_btn"):
        for k in ["messages","pdf_text","chat","session_id"]:
            st.session_state.pop(k, None)
        st.rerun()


# ── Icon rail HTML (injected directly into page DOM) ──────────────────────────
st.markdown(f"""
<div id="cls-rail">
  <div class="rt">
    <div class="ric brand" title="AI Classroom">◈</div>
    <div class="rsep"></div>
    <div class="ric" title="Upload PDF">⬆</div>
    <div class="ric" title="Teacher Voice">♪</div>
    <div class="ric" title="Recent Sessions">⏱</div>
    <div class="rsep"></div>
    <div class="ric" title="Export">⬇</div>
    <div class="ric" title="Clear Session">✕</div>
  </div>
  <div class="rb">
    <div class="ravatar" title="{uemail}">{initial}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# JS in components.html so it can access window.parent DOM
components.html("""
<script>
(function(){
  /* ── 1. Auto-collapse sidebar on mobile (<= 768px) ── */
  function collapseIfMobile() {
    try {
      var sb = window.parent.document.querySelector('[data-testid="stSidebar"]');
      if (!sb) return;
      var btn = window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"]');
      if (window.parent.innerWidth <= 768 && sb.getAttribute('aria-expanded') !== 'false' && btn) {
        btn.click();
      }
    } catch(e) {}
  }
  // Run once after DOM settles
  setTimeout(collapseIfMobile, 600);
  // Re-run on orientation change
  window.parent.addEventListener('resize', collapseIfMobile);

  /* ── 2. Icon rail sync ── */
  function poll(){
    try {
      var sb   = window.parent.document.querySelector('[data-testid="stSidebar"]');
      var rail = window.parent.document.getElementById('cls-rail');
      if (!sb || !rail) { setTimeout(poll, 300); return; }
      function sync() {
        var w = sb.getBoundingClientRect().width;
        var collapsed = sb.getAttribute('aria-expanded') === 'false' || w < 60;
        rail.style.display = collapsed ? 'flex' : 'none';
      }
      new MutationObserver(sync).observe(sb, {attributes:true});
      new ResizeObserver(sync).observe(sb);
      sync();
    } catch(e) { setTimeout(poll, 400); }
  }
  poll();
})();
</script>
""", height=0)


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
            st.warning(f"Key {st.session_state.current_key_index+1} exhausted, switching…")
            st.session_state.current_key_index = (st.session_state.current_key_index + 1) % len(keys)
            genai.configure(api_key=keys[st.session_state.current_key_index])
            global model
            model = genai.GenerativeModel("gemini-2.5-flash")
            chat_session = model.start_chat(history=chat_session.history)
        except Exception:
            raise
    st.error("All API keys exhausted.")
    st.stop()

def trim_text(text, max_chars=6000):
    return text[:max_chars] + "\n\n[…trimmed]" if len(text) > max_chars else text

def clean_for_tts(text, is_math=False):
    """Strip LaTeX/markdown and cap length for edge_tts — works for BOTH modes."""
    if is_math:
        text = re.sub(r'\$\$.*?\$\$',
                      lambda m: '. . . ' * max(1, len(m.group(0)) // 8),
                      text, flags=re.DOTALL)
    text = re.sub(r'\$[^$\n]+\$', '', text)   # inline LaTeX
    text = re.sub(r'[\\*#_`]+', '', text)       # markdown symbols
    text = re.sub(r'\s+', ' ', text).strip()
    # Hard cap: long seminar responses caused edge_tts timeouts
    if len(text) > 1800:
        text = text[:1800] + ". See full reply above."
    return text

# SVG icons — clear at any scale
_PL = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>'
_PA = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>'
_CP = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'
_TU = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>'
_TD = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3z"/><path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>'

def make_action_bar(audio_b64: str, audio_id: str, message_text: str) -> str:
    audio_tag  = ""
    listen_btn = "<span style='color:#333;font-size:0.7rem'>—</span>"
    if audio_b64:
        audio_tag  = f'<audio id="{audio_id}" src="data:audio/mp3;base64,{audio_b64}"></audio>'
        listen_btn = f'<button id="btn_{audio_id}" class="ab" title="Play/Pause" onclick="togglePlay()">{_PL}</button>'
    safe = (message_text.replace("&","&amp;").replace('"',"&quot;")
            .replace("'","&#39;").replace("<","&lt;").replace(">","&gt;"))

    return f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:transparent;font-family:'DM Sans',sans-serif;padding:2px 0;}}
.bar{{display:flex;gap:2px;align-items:center;}}
.ab{{display:inline-flex;align-items:center;justify-content:center;background:none;border:none;
     cursor:pointer;width:36px;height:36px;border-radius:8px;color:#5a5a88;
     transition:background .13s,color .13s;}}
.ab:hover{{background:rgba(255,255,255,.07);color:#c0c0e0;}}
.ab.ok{{color:#3ca18d !important;}} .ab.no{{color:#c96b6b !important;}}
.ab svg{{pointer-events:none;}}
.sp{{width:1px;height:18px;background:rgba(255,255,255,.08);margin:0 2px;}}
.toast{{font-size:0.68rem;color:#3ca18d;margin-left:3px;opacity:0;transition:opacity .3s;}}
</style></head><body>
  {audio_tag}
  <div id="tx_{audio_id}" style="display:none">{safe}</div>
  <div class="bar">
    {listen_btn}
    <div class="sp"></div>
    <button class="ab" title="Copy" onclick="
      navigator.clipboard.writeText(document.getElementById('tx_{audio_id}').innerText)
        .then(()=>{{var t=document.getElementById('tos_{audio_id}');
          t.style.opacity=1;setTimeout(()=>t.style.opacity=0,1800);}})
    ">{_CP}</button>
    <span class="toast" id="tos_{audio_id}">Copied!</span>
    <div class="sp"></div>
    <button class="ab" id="lk_{audio_id}" title="Helpful"
      onclick="this.classList.toggle('ok');document.getElementById('dl_{audio_id}').classList.remove('no')">{_TU}</button>
    <button class="ab" id="dl_{audio_id}" title="Not helpful"
      onclick="this.classList.toggle('no');document.getElementById('lk_{audio_id}').classList.remove('ok')">{_TD}</button>
  </div>
<script>(function(){{
  var MY="{audio_id}", aud=document.getElementById(MY);
  if(window.parent&&!window.parent.__aC){{
    window.parent.__aC=true;
    window.parent.addEventListener("message",function(e){{
      if(!e.data||e.data.t!=="apl")return;
      window.parent.document.querySelectorAll("iframe").forEach(function(f){{
        try{{f.contentWindow.postMessage({{t:"ast",ex:e.data.id}},"*");}}catch(_){{}}
      }});
    }});
  }}
  window.addEventListener("message",function(e){{
    if(!e.data||e.data.t!=="ast"||e.data.ex===MY)return;
    if(aud&&!aud.paused){{aud.pause();var b=document.getElementById("btn_"+MY);if(b)b.innerHTML='{_PL}';}}
  }});
  if(aud){{
    aud.addEventListener("play",function(){{
      window.parent&&window.parent.postMessage({{t:"apl",id:MY}},"*");
      var b=document.getElementById("btn_"+MY);if(b)b.innerHTML='{_PA}';
    }});
    aud.addEventListener("pause",function(){{var b=document.getElementById("btn_"+MY);if(b)b.innerHTML='{_PL}';}});
    aud.addEventListener("ended",function(){{var b=document.getElementById("btn_"+MY);if(b)b.innerHTML='{_PL}';}});
    /* __AUTOPLAY_TOKEN__ */ setTimeout(function(){{aud.play().catch(function(){{}});}},420);
  }}
  window.togglePlay=function(){{if(!aud)return;aud.paused?aud.play().catch(function(){{}}):aud.pause();}};
}})();</script>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PAGE HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex;align-items:center;gap:13px;padding:8px 2px 4px;">
  <div style="flex-shrink:0;width:42px;height:42px;border-radius:12px;
              background:linear-gradient(135deg,rgba(139,122,204,.2),rgba(60,161,141,.2));
              border:1px solid rgba(255,255,255,.09);
              display:flex;align-items:center;justify-content:center;font-size:1.35rem;">◈</div>
  <div>
    <div style="font-family:'Sora',sans-serif;font-size:1.2rem;font-weight:700;
                color:#ddddf0;letter-spacing:-0.02em;line-height:1.2;">AI Classroom</div>
    <div style="font-size:0.68rem;color:#5a5a80;margin-top:1px;">Powered by Gemini 2.5 Flash</div>
  </div>
</div>
<div style="height:1px;background:linear-gradient(90deg,rgba(139,122,204,.22),rgba(60,161,141,.18),transparent);margin:6px 0 12px;"></div>
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
        st.session_state.session_id = str(uuid_lib.uuid4())
        if st.session_state.mode == "Seminar":
            persona = "You are a warm, conversational tutor. Keep explanations clear and engaging."
        else:
            persona = "You are a rigorous math professor at a chalkboard. Find formulas and break them down step-by-step with LaTeX."
        st.session_state.chat = model.start_chat(history=[])
        try:
            resp = safe_generate_chat(
                st.session_state.chat,
                f"{persona}\n\nCourse material:\n{st.session_state.pdf_text}\n\n"
                "Welcome the student warmly and ask if they want a 'Fresh Start' or have an 'Area of Concern'."
            )
            st.session_state.messages.append({"role":"assistant","content":resp.text})
            save_session_to_db()
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
            vt = clean_for_tts(last["content"], is_math=(st.session_state.mode=="Chalkboard"))
            async def _regen(t, p, v):
                await edge_tts.Communicate(t, v, rate="-10%").save(p)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                asyncio.run(_regen(vt, fp.name, selected_voice))
                nb64 = base64.b64encode(open(fp.name,"rb").read()).decode()
            aid = f"audio_{len(msgs)-1}"
            msgs[-1]["audio_html"] = make_action_bar(nb64, aid, last["content"])
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 9. "NOW COVERING" BANNER  — always shows current topic so student never gets lost
# ═══════════════════════════════════════════════════════════════════════════════
def extract_topic(text: str) -> str:
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'[*#_`$\\]+', '', clean).strip()
    for s in re.split(r'(?<=[.!?])\s+', clean):
        s = s.strip()
        if len(s) > 10:
            return (s[:72] + "…") if len(s) > 72 else s
    return clean[:72]

last_prof = next((m for m in reversed(st.session_state.messages) if m["role"]=="assistant"), None)
if last_prof:
    topic = extract_topic(last_prof.get("content",""))
    st.markdown(f"""
    <div class="now-covering">
      <div class="nc-dot"></div>
      <span class="nc-text">
        <span style="color:#b0a0dc;font-weight:500;">Now covering</span>
        &nbsp;·&nbsp; {topic}
      </span>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. CHAT HISTORY
# ═══════════════════════════════════════════════════════════════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("plot_formula"):
            try:
                x = np.linspace(-10,10,400)
                y = eval(msg["plot_formula"],{"__builtins__":None},{"x":x,"np":np})
                st.line_chart(pd.DataFrame({"x":x,"y":y}).set_index("x"),use_container_width=True)
            except Exception:
                pass
        if msg["role"]=="assistant" and msg.get("audio_html"):
            htm = msg["audio_html"]
            if msg is not st.session_state.messages[-1]:
                htm = htm.replace(
                    "/* __AUTOPLAY_TOKEN__ */ setTimeout(function(){aud.play().catch(function(){});},420);",
                    "/* suppressed */"
                )
            components.html(htm, height=44, scrolling=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 11. INPUT BAR
# ═══════════════════════════════════════════════════════════════════════════════
chip_col, _, btn1_col, btn2_col = st.columns([2.4, 3.2, 1.1, 1.1])
with chip_col:
    st.markdown('<div class="mode-chip">', unsafe_allow_html=True)
    mode_pick = st.selectbox(
        "mc", ["◎  Seminar — Text & Concepts", "∑  Chalkboard — Heavy Math"],
        label_visibility="collapsed", key="mode_chip_sel"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    st.session_state.mode = "Seminar" if "Seminar" in mode_pick else "Chalkboard"

with btn1_col:
    raise_hand = st.button("✋ Raise", key="rh_btn")   # hand emoji + "Raise" only
with btn2_col:
    quiz_me = st.button("✏ Quiz Me", key="qm_btn")

student_input = None
if raise_hand:
    student_input = "Excuse me professor — I have a question about that."
if quiz_me:
    student_input = (
        "Professor, give me a 3-question multiple-choice quiz strictly based on "
        "the course materials. Ask the questions now but hold the answers until I respond."
    )
if typed := st.chat_input("Ask a question, or type your quiz answers…"):
    student_input = typed


# ═══════════════════════════════════════════════════════════════════════════════
# 12. PROCESS INPUT
# ═══════════════════════════════════════════════════════════════════════════════
if student_input:
    if "chat" not in st.session_state:
        st.error("Upload a course PDF first to open the session.")
        st.stop()

    st.session_state.messages.append({"role":"user","content":student_input})
    with st.chat_message("user"):
        st.write(student_input)

    mode = st.session_state.mode
    prompt = (
        "(Conversational tutor. Put reasoning in <thought> tags; write response below them.)\n\nStudent: "
        if mode=="Seminar" else
        "(Rigorous math professor. Hide reasoning in <thought> tags. LaTeX: $ inline, $$ block. Graphs: <plot>formula</plot>.)\n\nStudent: "
    ) + student_input

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            # TEXT
            try:
                resp    = safe_generate_chat(st.session_state.chat, prompt)
                raw     = resp.text
                ui_text = re.sub(r'<thought>.*?(?:</thought>|$)', '', raw, flags=re.DOTALL).strip()
                if not ui_text:
                    ui_text = "Could you clarify which part you'd like to explore?"
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

            # AUDIO — both modes now use clean_for_tts
            vtext     = clean_for_tts(ui_text, is_math=(mode=="Chalkboard"))
            audio_b64 = ""
            try:
                async def _speak(t, p, v):
                    await edge_tts.Communicate(t, v, rate="-10%").save(p)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    asyncio.run(_speak(vtext, fp.name, selected_voice))
                    audio_b64 = base64.b64encode(open(fp.name,"rb").read()).decode()
            except Exception as tts_err:
                st.caption(f"Audio unavailable: {tts_err}")

        # PLOT
        plot_formula = None
        pm = re.search(r'<plot>(.*?)</plot>', ui_text)
        if pm:
            plot_formula = pm.group(1).strip()
            ui_text = re.sub(r'<plot>.*?</plot>', '', ui_text, flags=re.DOTALL).strip()

        st.write(ui_text)
        if plot_formula:
            try:
                x = np.linspace(-10,10,400)
                y = eval(plot_formula,{"__builtins__":None},{"x":x,"np":np})
                st.line_chart(pd.DataFrame({"x":x,"y":y}).set_index("x"),use_container_width=True)
            except Exception:
                st.warning(f"Could not render: {plot_formula}")

        # SAVE + RERUN
        audio_id   = f"audio_{len(st.session_state.messages)}"
        action_bar = make_action_bar(audio_b64, audio_id, ui_text)
        st.session_state.messages.append({
            "role":"assistant","content":ui_text,
            "audio_html":action_bar,"plot_formula":plot_formula
        })
        save_session_to_db()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 13. EXPORT NOTES
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    if st.session_state.get("messages"):
        st.markdown("---")
        st.markdown("#### Export Notes")
        fmt = st.selectbox("ef",["HTML — best for math","Plain text"],label_visibility="collapsed",key="exp_fmt")
        raw_md = "# AI Classroom Notes\n\n"
        for msg in st.session_state.messages:
            role = "Student" if msg["role"]=="user" else "Professor"
            raw_md += f"**{role}:**\n{msg.get('content','')}\n\n---\n\n"

        if "HTML" in fmt:
            html_out = """<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>Lecture Notes</title>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Sora:wght@700&family=DM+Sans:wght@400;500&display=swap');
  body{font-family:'DM Sans',sans-serif;max-width:820px;margin:40px auto;padding:24px;background:#0b0b11;color:#ddddf0;line-height:1.7;}
  h2{font-family:'Sora',sans-serif;border-bottom:1px solid rgba(255,255,255,.07);padding-bottom:12px;margin-bottom:28px;}
  .msg{margin-bottom:18px;padding:18px 22px;border-radius:16px;border:1px solid rgba(255,255,255,.07);}
  .usr{border-left:2px solid #3ca18d;background:rgba(60,161,141,.06);}
  .ast{border-left:2px solid #8b7acc;background:rgba(139,122,204,.05);}
  .role{font-size:.66rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px;color:#5a5a80;}
  pre{white-space:pre-wrap;font-family:inherit;}
</style></head><body><h2>◈ AI Classroom Notes</h2>"""
            for i, msg in enumerate(st.session_state.messages):
                cls  = "usr" if msg["role"]=="user" else "ast"
                role = "Student" if msg["role"]=="user" else "Professor"
                txt  = msg.get("content","").replace("<","&lt;").replace(">","&gt;")
                html_out += f'\n<div class="msg {cls}"><div class="role">{role}</div><pre>{txt}</pre>'
                if msg.get("plot_formula"):
                    try:
                        x  = np.linspace(-10,10,100)
                        y  = eval(msg["plot_formula"],{"__builtins__":None},{"x":x,"np":np})
                        xl = [round(float(v),2) for v in x]
                        yl = [round(float(v),2) for v in y]
                        html_out += f"""<div style="position:relative;height:260px;margin-top:14px;">
<canvas id="c{i}"></canvas></div><script>
window.addEventListener('DOMContentLoaded',function(){{new Chart(document.getElementById('c{i}').getContext('2d'),{{
  type:'line',data:{{labels:{xl},datasets:[{{data:{yl},borderColor:'#3ca18d',
  backgroundColor:'rgba(60,161,141,.1)',borderWidth:2,pointRadius:0,tension:0.4}}]}},
  options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},
  scales:{{x:{{ticks:{{color:'#5a5a80'}},grid:{{color:'rgba(255,255,255,.05)'}}}},
           y:{{ticks:{{color:'#5a5a80'}},grid:{{color:'rgba(255,255,255,.05)'}}}}}}}}
}});}});</script>"""
                    except Exception:
                        pass
                html_out += '</div>'
            html_out += "</body></html>"
            st.download_button("↓ Download HTML", html_out, "notes.html", "text/html", key="dl_html")
            st.caption("Open in browser → Ctrl+P → Save as PDF")
        else:
            clean = raw_md.replace("**","").replace("#","").strip()
            st.download_button("↓ Download TXT", clean, "notes.txt", "text/plain", key="dl_txt")
    else:
        st.caption("Start the session to generate notes")

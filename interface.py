import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account
import time
import requests
from langchain_mongodb.chat_message_histories import MongoDBChatMessageHistory
from pymongo import MongoClient
from datetime import datetime
import json

st.set_page_config(
page_title=“SmartStudy”,
page_icon=“✦”,
layout=“centered”,
initial_sidebar_state=“expanded”,
)

# — CUSTOM CSS —

st.markdown(”””

<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;1,400&family=DM+Sans:wght@300;400;500&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Background */
.stApp {
    background-color: #F7F5F2;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #1C1917 !important;
    border-right: none;
}
[data-testid="stSidebar"] * {
    color: #E8E4DF !important;
}
[data-testid="stSidebar"] .stMarkdown h4 {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #78716C !important;
    margin-bottom: 0.5rem;
}
[data-testid="stSidebar"] hr {
    border-color: #292524 !important;
}
[data-testid="stSidebar"] .stRadio label {
    font-size: 0.875rem;
    color: #D6D0CA !important;
}
[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
    color: #D6D0CA !important;
}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton button {
    background-color: transparent !important;
    border: 1px solid #292524 !important;
    color: #A8A29E !important;
    border-radius: 8px !important;
    font-size: 0.8rem !important;
    font-family: 'DM Sans', sans-serif !important;
    text-align: left !important;
    transition: all 0.2s ease !important;
    padding: 0.5rem 0.75rem !important;
    white-space: pre-wrap !important;
    height: auto !important;
    line-height: 1.4 !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background-color: #292524 !important;
    color: #E8E4DF !important;
    border-color: #44403C !important;
}

/* New conversation button */
[data-testid="stSidebar"] .stButton:first-of-type button {
    background-color: #292524 !important;
    color: #E8E4DF !important;
    border-color: #44403C !important;
    font-weight: 500 !important;
}

/* ── Main content ── */
.block-container {
    padding-top: 2.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 740px !important;
}

/* ── Title ── */
h1 {
    font-family: 'Lora', serif !important;
    font-weight: 500 !important;
    font-size: 2rem !important;
    color: #1C1917 !important;
    letter-spacing: -0.02em !important;
    margin-bottom: 0 !important;
}
h2, h3 {
    font-family: 'Lora', serif !important;
    font-weight: 500 !important;
    color: #1C1917 !important;
}

/* Subtitle */
.stMarkdown p {
    color: #78716C;
    font-size: 0.925rem;
    line-height: 1.6;
}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0.75rem 0 !important;
}
[data-testid="stChatMessage"][data-testid*="user"] {
    background: transparent !important;
}

/* User bubble */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) .stMarkdown {
    background: #FFFFFF;
    border: 1px solid #E7E4E0;
    border-radius: 18px 18px 4px 18px;
    padding: 0.875rem 1.125rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* Assistant bubble */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) .stMarkdown {
    background: #FFFFFF;
    border: 1px solid #E7E4E0;
    border-radius: 18px 18px 18px 4px;
    padding: 0.875rem 1.125rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* Avatar icons */
[data-testid="chatAvatarIcon-user"] {
    background: #1C1917 !important;
    color: #F7F5F2 !important;
}
[data-testid="chatAvatarIcon-assistant"] {
    background: #D4A853 !important;
    color: #1C1917 !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] {
    border-radius: 24px !important;
    border: 1.5px solid #D6D0CA !important;
    background: #FFFFFF !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #1C1917 !important;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1) !important;
}
[data-testid="stChatInput"] textarea {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    color: #1C1917 !important;
}

/* ── Buttons (main) ── */
.stButton button {
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    transition: all 0.2s ease !important;
    border: 1.5px solid #D6D0CA !important;
    background: #FFFFFF !important;
    color: #1C1917 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
}
.stButton button:hover {
    background: #1C1917 !important;
    color: #F7F5F2 !important;
    border-color: #1C1917 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
}
.stButton button[kind="primary"] {
    background: #1C1917 !important;
    color: #F7F5F2 !important;
    border-color: #1C1917 !important;
}
.stButton button[kind="primary"]:hover {
    background: #44403C !important;
    border-color: #44403C !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border: 1.5px dashed #D6D0CA !important;
    border-radius: 14px !important;
    background: #FFFFFF !important;
    padding: 1rem !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #1C1917 !important;
}

/* ── Status box ── */
[data-testid="stStatus"] {
    border-radius: 12px !important;
    border: 1px solid #E7E4E0 !important;
    background: #FFFFFF !important;
}

/* ── Alerts & success ── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.875rem !important;
}

/* ── Progress bar ── */
[data-testid="stProgress"] > div > div {
    background: #1C1917 !important;
    border-radius: 99px !important;
}
[data-testid="stProgress"] > div {
    background: #E7E4E0 !important;
    border-radius: 99px !important;
}

/* ── Divider ── */
hr {
    border-color: #E7E4E0 !important;
    margin: 1.25rem 0 !important;
}

/* ── Info/warning/error boxes ── */
.stInfo, .stSuccess, .stWarning, .stError {
    border-radius: 10px !important;
    font-size: 0.875rem !important;
}

/* ── Quiz container ── */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
    border-radius: 12px !important;
}

/* ── Caption ── */
.stCaption, caption {
    color: #A8A29E !important;
    font-size: 0.78rem !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] {
    color: #78716C !important;
}

/* ── Radio ── */
.stRadio label {
    font-size: 0.875rem !important;
}

/* Hide streamlit branding */
#MainMenu, footer, header {visibility: hidden;}
</style>

“””, unsafe_allow_html=True)

# — CONFIGURATION —

BUCKET_NAME = “pdf_bucket_project”
PROJECT_ID = “projet-cloud-computing-493007”
MONGO_URI = “mongodb+srv://projetcloud:projetcloud@geminirag.shbfocl.mongodb.net/?appName=GeminiRAG”
MONGO_DB = “smartstudy”
MONGO_COLLECTION = “chat_history”

API_BASE_URL = “https://smartstudy-api-64317660927.europe-west1.run.app”
API_ASK_URL = f”{API_BASE_URL}/ask”
API_QUIZ_URL = f”{API_BASE_URL}/quiz”

# — HELPERS —

def get_storage_client():
try:
if “gcp_service_account” in st.secrets:
creds = service_account.Credentials.from_service_account_info(
st.secrets[“gcp_service_account”]
)
return storage.Client(project=PROJECT_ID, credentials=creds)
except Exception:
pass
return storage.Client(project=PROJECT_ID)

def get_mongo_client():
return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

def get_chat_history(session_id: str) -> MongoDBChatMessageHistory:
return MongoDBChatMessageHistory(
session_id=session_id,
connection_string=MONGO_URI,
collection_name=MONGO_COLLECTION,
database_name=MONGO_DB,
)

def save_message(session_id: str, role: str, content: str):
history = get_chat_history(session_id)
if role == “user”:
history.add_user_message(content)
else:
history.add_ai_message(content)

def save_quiz_to_history(session_id: str, questions: list, answers: dict, score: int, total: int):
pct = round(100 * score / total)
user_msg = f”📝 **Quiz effectué** — {len(questions)} questions sur ce document.”
lines = [f”## 🧠 Résultat du Quiz — {score}/{total} ({pct}%)\n”]
for i, q in enumerate(questions):
user_answer = answers.get(i)
correct = q[“correct_index”]
is_correct = user_answer == correct
icon = “✅” if is_correct else “❌”
lines.append(f”**{icon} Q{i+1}. {q[‘question’]}**”)
if user_answer is not None:
lines.append(f”- Ta réponse : {chr(65 + user_answer)}. {q[‘options’][user_answer]}”)
if not is_correct and user_answer is not None:
lines.append(f”- Bonne réponse : {chr(65 + correct)}. {q[‘options’][correct]}”)
lines.append(f”- 💡 {q[‘explanation’]}\n”)
ai_msg = “\n”.join(lines)
save_message(session_id, “user”, user_msg)
save_message(session_id, “assistant”, ai_msg)
load_past_sessions.clear()
load_session_messages.clear()

@st.cache_data(ttl=30)
def load_past_sessions():
try:
client = get_mongo_client()
col = client[MONGO_DB][MONGO_COLLECTION]
sample = col.find_one()
if sample is None:
return []
session_field = next(
(f for f in [“SessionId”, “session_id”, “sessionId”] if f in sample), None
)
if not session_field:
return []
sessions = col.aggregate([
{”$group”: {
“_id”: f”${session_field}”,
“last_updated”: {”$max”: “$_id”},
“message_count”: {”$sum”: 1},
}},
{”$sort”: {“last_updated”: -1}},
{”$limit”: 30},
])
return list(sessions)
except Exception as e:
st.session_state[“mongo_error”] = str(e)
return []

@st.cache_data(ttl=60)
def load_session_messages(session_id: str):
try:
client = get_mongo_client()
col = client[MONGO_DB][MONGO_COLLECTION]
sample = col.find_one()
if sample is None:
return []
session_field = next(
(f for f in [“SessionId”, “session_id”, “sessionId”] if f in sample), None
)
if not session_field:
return []
docs = list(col.find({session_field: session_id}).sort(”_id”, 1))
messages = []
for doc in docs:
history_raw = doc.get(“History”) or doc.get(“history”, {})
if isinstance(history_raw, str):
try:
history_raw = json.loads(history_raw)
except Exception:
continue
msg_type = history_raw.get(“type”, “”)
data = history_raw.get(“data”, {})
content = data.get(“content”, “”) if data else history_raw.get(“content”, “”)
if not content:
continue
if msg_type == “human”:
messages.append({“role”: “user”, “content”: content})
elif msg_type == “ai”:
messages.append({“role”: “assistant”, “content”: content})
return messages
except Exception as e:
st.session_state[“mongo_error”] = str(e)
return []

def format_session_label(session_id: str):
parts = session_id.rsplit(”_”, 1)
if len(parts) == 2:
filename = parts[0]
try:
ts = int(parts[1])
date = datetime.fromtimestamp(ts).strftime(”%d %b, %H:%M”)
return filename, date
except ValueError:
pass
return session_id, “”

# — STATE INITIALIZATION —

defaults = {
“file_ready”: False,
“messages”: [],
“current_filename”: None,
“session_id”: None,
“quiz_data”: None,
“quiz_answers”: {},
“quiz_submitted”: False,
“show_quiz”: False,
“mongo_error”: None,
}
for key, val in defaults.items():
if key not in st.session_state:
st.session_state[key] = val

# — SIDEBAR —

with st.sidebar:
st.markdown(”## ✦ SmartStudy”)
st.markdown(”—”)

```
mode = st.radio(
    "Mode",
    options=["persona", "normal"],
    format_func=lambda x: "Tuteur Personnalisé" if x == "persona" else "Mode Direct",
    label_visibility="collapsed",
)

st.markdown("---")

if st.button("＋  Nouvelle session", use_container_width=True):
    for key in list(defaults.keys()):
        st.session_state[key] = defaults[key]
    st.rerun()

if st.session_state.file_ready and not st.session_state.show_quiz:
    if st.button("◎  Lancer un quiz", use_container_width=True):
        st.session_state.show_quiz = True
        st.session_state.quiz_data = None
        st.session_state.quiz_answers = {}
        st.session_state.quiz_submitted = False
        st.rerun()

st.markdown("---")
st.markdown("#### Historique")

if st.session_state.get("mongo_error"):
    st.error(f"MongoDB : {st.session_state.mongo_error}")

past_sessions = load_past_sessions()

if not past_sessions:
    st.caption("Aucune conversation pour l'instant.")
else:
    for s in past_sessions:
        sid = s["_id"]
        if not sid:
            continue
        filename, date = format_session_label(sid)
        is_active = sid == st.session_state.session_id
        label = f"{'▸  ' if is_active else '    '}{filename}\n     {date}" if date else filename

        if st.button(label, key=f"sess_{sid}", use_container_width=True):
            msgs = load_session_messages(sid)
            parts = sid.rsplit("_", 1)
            st.session_state.messages = msgs
            st.session_state.session_id = sid
            st.session_state.current_filename = parts[0] if len(parts) == 2 else sid
            st.session_state.file_ready = True
            st.session_state.show_quiz = False
            st.session_state.quiz_data = None
            st.session_state.quiz_answers = {}
            st.session_state.quiz_submitted = False
            st.rerun()
```

# ══════════════════════════════

# MAIN

# ══════════════════════════════

# — SECTION 1 : UPLOAD —

if not st.session_state.file_ready:
st.markdown(”# SmartStudy”)
st.markdown(“Ton espace d’apprentissage intelligent. Charge un cours, pose tes questions, teste tes connaissances.”)
st.markdown(”—”)

```
uploaded_file = st.file_uploader(
    "Dépose ton fichier PDF ici",
    type="pdf",
    label_visibility="collapsed",
)

if uploaded_file is not None:
    st.markdown(f"**{uploaded_file.name}** · {round(uploaded_file.size / 1024)} Ko")
    if st.button("Analyser le document →", type="primary"):
        with st.status("Traitement en cours…", expanded=True) as status:
            st.write("Envoi vers Google Cloud Storage…")
            client = get_storage_client()
            bucket = client.bucket(BUCKET_NAME)
            blob = bucket.blob(uploaded_file.name)
            blob.upload_from_file(uploaded_file)
            st.session_state.current_filename = uploaded_file.name
            st.write(f"Document reçu.")

            st.write("Analyse et indexation…")
            st.write("Environ 30 à 60 secondes.")
            time.sleep(45)

            st.write("Prêt.")
            status.update(label="Document prêt ✓", state="complete", expanded=False)

        st.session_state.session_id = f"{uploaded_file.name}_{int(time.time())}"
        st.session_state.file_ready = True
        st.session_state.messages = []
        load_past_sessions.clear()
        st.balloons()
        st.rerun()
```

# — SECTION 2A : QUIZ —

elif st.session_state.file_ready and st.session_state.show_quiz:
col_title, col_close = st.columns([6, 1])
with col_title:
st.markdown(”## Quiz”)
st.caption(f”Document : {st.session_state.current_filename}”)
with col_close:
st.markdown(”<br>”, unsafe_allow_html=True)
if st.button(“✕”, use_container_width=True):
st.session_state.show_quiz = False
st.session_state.quiz_data = None
st.session_state.quiz_answers = {}
st.session_state.quiz_submitted = False
if “quiz_saved” in st.session_state:
del st.session_state.quiz_saved
st.rerun()

```
st.markdown("---")

if st.session_state.quiz_data is None:
    import random
    with st.spinner("Génération du quiz…"):
        try:
            res = requests.post(
                API_QUIZ_URL,
                json={
                    "question": "",
                    "filename": st.session_state.current_filename,
                    "seed": random.randint(1, 999999),
                },
                timeout=120,
            )
            if res.status_code == 200:
                data = res.json()
                quiz_obj = data.get("quiz")
                if isinstance(quiz_obj, dict) and "questions" in quiz_obj:
                    st.session_state.quiz_data = quiz_obj["questions"]
                    st.rerun()
                else:
                    st.error("Le quiz n'a pas pu être généré.")
                    st.json(data)
            else:
                st.error(f"Erreur {res.status_code} : {res.text}")
        except Exception as e:
            st.error(f"Erreur : {e}")

if st.session_state.quiz_data:
    questions = st.session_state.quiz_data

    if not st.session_state.quiz_submitted:
        st.info(f"{len(questions)} questions — réponds à chacune puis soumets.")

        for i, q in enumerate(questions):
            with st.container(border=True):
                st.markdown(f"**{i+1}.** {q['question']}")
                choice = st.radio(
                    "",
                    options=list(range(len(q["options"]))),
                    format_func=lambda x, opts=q["options"]: f"{chr(65+x)}. {opts[x]}",
                    key=f"quiz_q_{i}",
                    index=None,
                    label_visibility="collapsed",
                )
                if choice is not None:
                    st.session_state.quiz_answers[i] = choice

        all_answered = len(st.session_state.quiz_answers) == len(questions)

        if not all_answered:
            st.caption(f"{len(st.session_state.quiz_answers)}/{len(questions)} réponses")

        if st.button(
            "Soumettre →" if all_answered else f"Répondre à toutes les questions ({len(st.session_state.quiz_answers)}/{len(questions)})",
            disabled=not all_answered,
            use_container_width=True,
            type="primary",
        ):
            st.session_state.quiz_submitted = True
            st.rerun()

    else:
        score = sum(
            1 for i, q in enumerate(questions)
            if st.session_state.quiz_answers.get(i) == q["correct_index"]
        )
        total = len(questions)
        pct = round(100 * score / total)

        if pct >= 80:
            st.success(f"**{score}/{total}** — Excellent travail.")
        elif pct >= 50:
            st.warning(f"**{score}/{total}** — Quelques points à revoir.")
        else:
            st.error(f"**{score}/{total}** — À retravailler, mais tu y arriveras.")

        st.progress(pct / 100)
        st.markdown("---")

        for i, q in enumerate(questions):
            user_answer = st.session_state.quiz_answers.get(i)
            correct = q["correct_index"]
            is_correct = user_answer == correct

            with st.container(border=True):
                st.markdown(f"{'✓' if is_correct else '✗'}  **Q{i+1}. {q['question']}**")

                for j, opt in enumerate(q["options"]):
                    prefix = chr(65 + j)
                    if j == correct:
                        st.markdown(f"→ **{prefix}. {opt}** *(bonne réponse)*")
                    elif j == user_answer and not is_correct:
                        st.markdown(f"✗ {prefix}. {opt} *(ta réponse)*")
                    else:
                        st.markdown(f"  {prefix}. {opt}")

                st.caption(f"💡 {q['explanation']}")
                if q.get("source"):
                    st.caption(f"Source : {q['source']}")

        if st.session_state.session_id and "quiz_saved" not in st.session_state:
            try:
                save_quiz_to_history(
                    st.session_state.session_id,
                    questions,
                    st.session_state.quiz_answers,
                    score,
                    total,
                )
                st.session_state.quiz_saved = True
                st.toast("Quiz sauvegardé ✓")
            except Exception as e:
                st.warning(f"Quiz non sauvegardé : {e}")

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Refaire un quiz", use_container_width=True):
                st.session_state.quiz_data = None
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                if "quiz_saved" in st.session_state:
                    del st.session_state.quiz_saved
                st.rerun()
        with col2:
            if st.button("Retour au chat →", use_container_width=True, type="primary"):
                st.session_state.show_quiz = False
                if "quiz_saved" in st.session_state:
                    del st.session_state.quiz_saved
                st.rerun()
```

# — SECTION 2B : CHAT —

elif st.session_state.file_ready:
st.markdown(f”### {st.session_state.current_filename}”)
mode_label = “Tuteur personnalisé” if mode == “persona” else “Mode direct”
st.caption(f”{mode_label}  ·  Utilise la sidebar pour lancer un quiz”)
st.markdown(”—”)

```
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Pose ta question…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    body = {
        "question": prompt,
        "filename": st.session_state.current_filename,
        "mode": mode,
    }

    with st.chat_message("assistant"):
        with st.spinner(""):
            try:
                res = requests.post(API_ASK_URL, json=body, timeout=120)

                if res.status_code == 200:
                    data = res.json()
                    reponse_ia = data.get("answer", "Aucune réponse reçue.")
                    st.markdown(reponse_ia)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": reponse_ia}
                    )
                    if st.session_state.session_id:
                        try:
                            save_message(st.session_state.session_id, "user", prompt)
                            save_message(st.session_state.session_id, "assistant", reponse_ia)
                            load_past_sessions.clear()
                            load_session_messages.clear()
                        except Exception as e:
                            st.warning(f"Non sauvegardé : {e}")
                else:
                    st.error(f"Erreur {res.status_code} : {res.text}")

            except Exception as e:
                st.error(f"Erreur : {e}")
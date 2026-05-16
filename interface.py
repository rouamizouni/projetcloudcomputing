import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account
import time
import requests
import random
from langchain_mongodb.chat_message_histories import MongoDBChatMessageHistory
from pymongo import MongoClient
from datetime import datetime
import json

st.set_page_config(page_title="SmartStudy Tutor", page_icon="🎓", layout="centered")

# — CONFIGURATION —

BUCKET_NAME = "pdf_bucket_project"
PROJECT_ID = "projet-cloud-computing-493007"
MONGO_URI = "mongodb+srv://projetcloud:projetcloud@geminirag.shbfocl.mongodb.net/?appName=GeminiRAG"
MONGO_DB = "smartstudy"
MONGO_COLLECTION = "chat_history"

API_BASE_URL = "https://smartstudy-api-64317660927.europe-west1.run.app"
API_ASK_URL = f"{API_BASE_URL}/ask"
API_QUIZ_URL = f"{API_BASE_URL}/quiz"

# — HELPERS —

def get_storage_client():
try:
if "gcp_service_account" in st.secrets:
creds = service_account.Credentials.from_service_account_info(
st.secrets["gcp_service_account"]
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
if role == "user":
history.add_user_message(content)
else:
history.add_ai_message(content)

def save_quiz_to_history(session_id: str, questions: list, answers: dict, score: int, total: int):
pct = round(100 * score / total)
user_msg = f" **Quiz effectué** — {len(questions)} questions sur ce document."
lines = [f"## Résultat du Quiz — {score}/{total} ({pct}%)\n"]
for i, q in enumerate(questions):
user_answer = answers.get(i)
correct = q["correct_index"]
is_correct = user_answer == correct
icon = "✅" if is_correct else "❌"
lines.append(f"**{icon} Q{i+1}. {q['question']}**")
if user_answer is not None:
lines.append(f"- Ta réponse : {chr(65 + user_answer)}. {q[´options'][user_answer]}")
if not is_correct and user_answer is not None:
lines.append(f"- Bonne réponse : {chr(65 + correct)}. {q['options'][correct]}")
lines.append(f"- 💡 {q[‘explanation’]}\n")
ai_msg = "\n".join(lines)
save_message(session_id, "user", user_msg)
save_message(session_id, "assistant", ai_msg)
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
(f for f in ["SessionId", "session_id", "sessionId"] if f in sample), None
)
if not session_field:
return []
sessions = col.aggregate([
{"$group”: {
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
date = datetime.fromtimestamp(ts).strftime(”%d/%m %H:%M”)
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
st.title(“🎓 SmartStudy”)

```
mode = st.radio(
    "Mode du tuteur",
    options=["persona", "normal"],
    format_func=lambda x: "🎓 Tuteur Personna" if x == "persona" else "📝 Mode Normal",
)

st.divider()

if st.button("✏️ Nouvelle conversation", use_container_width=True):
    for key in list(defaults.keys()):
        st.session_state[key] = defaults[key]
    st.rerun()

if st.session_state.file_ready and not st.session_state.show_quiz:
    if st.button("🧠 Lancer un quiz", use_container_width=True, type="primary"):
        st.session_state.show_quiz = True
        st.session_state.quiz_data = None
        st.session_state.quiz_answers = {}
        st.session_state.quiz_submitted = False
        st.rerun()

st.divider()
st.markdown("#### 🕐 Conversations récentes")

if st.session_state.get("mongo_error"):
    st.error(f"MongoDB : {st.session_state.mongo_error}")

past_sessions = load_past_sessions()

if not past_sessions:
    st.caption("Aucune conversation sauvegardee.")
else:
    for s in past_sessions:
        sid = s["_id"]
        if not sid:
            continue
        filename, date = format_session_label(sid)
        is_active = sid == st.session_state.session_id
        prefix = "▶ " if is_active else ""
        label = f"{prefix}📄 {filename}\n🕐 {date}" if date else f"{prefix}📄 {filename}"

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

# — MAIN —

st.title(“🎓 SmartStudy Tutor”)
st.markdown(”### Bienvenue dans ton espace d’apprentissage intelligent”)

# — SECTION 1 : UPLOAD —

if not st.session_state.file_ready:
st.write(“Telecharge ton cours en PDF pour commencer la session.”)

```
with st.container():
    uploaded_file = st.file_uploader("Choisis ton fichier PDF", type="pdf")

    if uploaded_file is not None:
        if st.button("Lancer l'analyse du cours"):
            with st.status("Traitement du document...", expanded=True) as status:
                st.write("📤 Envoi du fichier vers Google Cloud Storage...")
                client = get_storage_client()
                bucket = client.bucket(BUCKET_NAME)
                blob = bucket.blob(uploaded_file.name)
                blob.upload_from_file(uploaded_file)
                st.session_state.current_filename = uploaded_file.name
                st.write(f"✅ Fichier `{uploaded_file.name}` envoye.")

                st.write("🔍 Analyse et indexation du document en cours...")
                st.write("(Cela peut prendre 30 a 60 secondes)")
                time.sleep(45)

                st.write("✅ Document indexe !")
                status.update(label="Analyse terminee !", state="complete", expanded=False)

            st.session_state.session_id = f"{uploaded_file.name}_{int(time.time())}"
            st.session_state.file_ready = True
            st.session_state.messages = []
            load_past_sessions.clear()
            st.balloons()
            st.rerun()
```

# — SECTION 2A : QUIZ —

if st.session_state.file_ready and st.session_state.show_quiz:
st.divider()

```
col_title, col_close = st.columns([5, 1])
with col_title:
    st.subheader("🧠 Quiz interactif")
with col_close:
    if st.button("✖ Fermer", use_container_width=True):
        st.session_state.show_quiz = False
        st.session_state.quiz_data = None
        st.session_state.quiz_answers = {}
        st.session_state.quiz_submitted = False
        if "quiz_saved" in st.session_state:
            del st.session_state.quiz_saved
        st.rerun()

if st.session_state.quiz_data is None:
    with st.spinner("🎓 Le mentor prepare ton quiz..."):
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
                    st.error("Le quiz n'a pas pu etre genere correctement.")
                    st.json(data)
            else:
                st.error(f"Erreur {res.status_code} : {res.text}")
        except Exception as e:
            st.error(f"Erreur de connexion : {e}")

if st.session_state.quiz_data:
    questions = st.session_state.quiz_data

    if not st.session_state.quiz_submitted:
        st.info(f"📋 **{len(questions)} questions** — Choisis une reponse pour chacune, puis soumets.")

        for i, q in enumerate(questions):
            with st.container(border=True):
                st.markdown(f"**Question {i+1}.** {q['question']}")
                choice = st.radio(
                    "Ta reponse :",
                    options=list(range(len(q["options"]))),
                    format_func=lambda x, opts=q["options"]: f"{chr(65+x)}. {opts[x]}",
                    key=f"quiz_q_{i}",
                    index=None,
                )
                if choice is not None:
                    st.session_state.quiz_answers[i] = choice

        all_answered = len(st.session_state.quiz_answers) == len(questions)
        if st.button("Soumettre mes reponses", disabled=not all_answered,
                     use_container_width=True, type="primary"):
            st.session_state.quiz_submitted = True
            st.rerun()

        if not all_answered:
            st.caption(f"Reponses donnees : {len(st.session_state.quiz_answers)}/{len(questions)}")

    else:
        score = sum(
            1 for i, q in enumerate(questions)
            if st.session_state.quiz_answers.get(i) == q["correct_index"]
        )
        total = len(questions)
        pct = round(100 * score / total)

        if pct >= 80:
            st.success(f"🏆 Excellent ! Score : **{score}/{total}** ({pct}%)")
            feedback = "Tu maitrises bien ce chapitre. Continue comme ca !"
        elif pct >= 50:
            st.warning(f"👍 Pas mal ! Score : **{score}/{total}** ({pct}%)")
            feedback = "Quelques notions a revoir. Regarde bien les explications ci-dessous."
        else:
            st.error(f"📚 A retravailler. Score : **{score}/{total}** ({pct}%)")
            feedback = "Pas de panique, c'est en se trompant qu'on apprend ! Lis bien les corrections."

        st.markdown(f"_{feedback}_")
        st.progress(pct / 100)
        st.divider()

        for i, q in enumerate(questions):
            user_answer = st.session_state.quiz_answers.get(i)
            correct = q["correct_index"]
            is_correct = user_answer == correct

            with st.container(border=True):
                icon = "✅" if is_correct else "❌"
                st.markdown(f"### {icon} Question {i+1}")
                st.markdown(f"**{q['question']}**")

                for j, opt in enumerate(q["options"]):
                    prefix = chr(65 + j)
                    if j == correct:
                        st.markdown(f"- **{prefix}. {opt}**  _(bonne reponse)_")
                    elif j == user_answer and not is_correct:
                        st.markdown(f"- {prefix}. {opt}  _(ta reponse)_")
                    else:
                        st.markdown(f"- {prefix}. {opt}")

                st.info(f"💡 **Explication :** {q['explanation']}")
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
                st.toast("✅ Quiz sauvegarde dans ton historique !", icon="💾")
            except Exception as e:
                st.warning(f"Quiz non sauvegarde : {e}")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refaire un nouveau quiz", use_container_width=True):
                st.session_state.quiz_data = None
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                if "quiz_saved" in st.session_state:
                    del st.session_state.quiz_saved
                st.rerun()
        with col2:
            if st.button("💬 Retour au chat", use_container_width=True):
                st.session_state.show_quiz = False
                if "quiz_saved" in st.session_state:
                    del st.session_state.quiz_saved
                st.rerun()
```

# — SECTION 2B : CHAT —

elif st.session_state.file_ready:
st.success(f”**Document actif :** `{st.session_state.current_filename}`”)
st.divider()

```
mode_label = "🎓 Mentor" if mode == "persona" else "📝 Direct"
st.subheader(f"Pose tes questions — Mode {mode_label}")
st.caption("Astuce : utilise le bouton **🧠 Lancer un quiz** dans la sidebar pour te tester.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ex: Resume les points cles pour moi"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    body = {
        "question": prompt,
        "filename": st.session_state.current_filename,
        "mode": mode,
    }

    with st.chat_message("assistant"):
        with st.spinner("Je reflechis..."):
            try:
                res = requests.post(API_ASK_URL, json=body, timeout=120)

                if res.status_code == 200:
                    data = res.json()
                    reponse_ia = data.get("answer", "Aucune reponse recue.")
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
                            st.warning(f"Non sauvegarde : {e}")
                else:
                    st.error(f"Erreur {res.status_code} : {res.text}")

            except Exception as e:
                st.error(f"Erreur de connexion : {e}")
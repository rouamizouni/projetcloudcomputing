import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account
import time
import requests
from langchain_mongodb.chat_message_histories import MongoChatMessageHistory

st.set_page_config(page_title="SmartStudy Tutor", page_icon="🎓", layout="centered")

# --- CONFIGURATION ---
BUCKET_NAME = "pdf_bucket_project"
PROJECT_ID = "projet-cloud-computing-493007"

API_BASE_URL = "https://smartstudy-api-64317660927.europe-west1.run.app"
API_ASK_URL = f"{API_BASE_URL}/ask"
API_QUIZ_URL = f"{API_BASE_URL}/quiz"

<<<<<<< HEAD
st.title("SmartStudy Tutor")
st.markdown("### Welcome to your intelligent learning space")
st.write("Upload your course as PDF to start the session.")
=======

def get_storage_client():
    """Marche en local (gcloud auth) ET sur Streamlit Cloud (secrets.toml)."""
    try:
        if "gcp_service_account" in st.secrets:
            creds = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"]
            )
            return storage.Client(project=PROJECT_ID, credentials=creds)
    except Exception:
        pass  # Pas de secrets.toml en local, on retombe sur gcloud auth
    return storage.Client(project=PROJECT_ID)


st.title("🎓 SmartStudy Tutor")
st.markdown("### Bienvenue dans ton espace d'apprentissage intelligent")
>>>>>>> 83a2abc (code de l'interface)

# State initialization
if "file_ready" not in st.session_state:
    st.session_state.file_ready = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_filename" not in st.session_state:
    st.session_state.current_filename = None
<<<<<<< HEAD
if "save_to_history" not in st.session_state:
    st.session_state.save_to_history = False

# Initialize MongoDB Chat History
chat_with_history = None


# --- SECTION 1: FILE UPLOAD ---
with st.container():
    uploaded_file = st.file_uploader("Choose your PDF file", type="pdf")

    if uploaded_file is not None and not st.session_state.file_ready:
        if st.button("Start Course Analysis"):
            with st.status("Processing document...", expanded=True) as status:
                st.write(" Sending file to Google Cloud Storage...")
                client = storage.Client(project=PROJECT_ID)
                bucket = client.bucket(BUCKET_NAME)
                blob = bucket.blob(uploaded_file.name)
                blob.upload_from_file(uploaded_file)
                st.write("File uploaded.")

                st.write(" Document analysis and indexing in progress...")
                st.write("(This may take 30 to 60 seconds)")
                time.sleep(45)

                st.write("Document indexed!")
                status.update(label="Analysis complete!", state="complete", expanded=False)
=======
if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "quiz_answers" not in st.session_state:
    st.session_state.quiz_answers = {}
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False
if "show_quiz" not in st.session_state:
    st.session_state.show_quiz = False


# --- SIDEBAR : choix du mode + actions ---
with st.sidebar:
    st.header("⚙️ Paramètres")
    mode = st.radio(
        "Mode du tuteur",
        options=["persona", "normal"],
        format_func=lambda x: "🎓 Tuteur Personna" if x == "persona" else " Mode Normal",
        help=(
            "**Tuteur Personna** : ton académique, citations, tips, questions de réflexion.\n\n"
            "**Mode Normal** : réponses directes et concises."
        ),
    )

    st.divider()

    if st.session_state.file_ready and st.session_state.current_filename:
        st.success(f" Document actif :\n`{st.session_state.current_filename}`")

        if st.button("Charger un autre PDF", use_container_width=True):
            st.session_state.file_ready = False
            st.session_state.messages = []
            st.session_state.current_filename = None
            st.session_state.quiz_data = None
            st.session_state.quiz_answers = {}
            st.session_state.quiz_submitted = False
            st.session_state.show_quiz = False
            st.rerun()

        if not st.session_state.show_quiz:
            if st.button("Lancer un quiz interactif", use_container_width=True, type="primary"):
                st.session_state.show_quiz = True
                st.session_state.quiz_data = None
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.rerun()


# --- SECTION 1 : UPLOAD ---
if not st.session_state.file_ready:
    st.write("Télécharge ton cours en PDF pour commencer la session.")

    with st.container():
        uploaded_file = st.file_uploader("Choisis ton fichier PDF", type="pdf")

        if uploaded_file is not None:
            if st.button("Lancer l'analyse du cours"):
                with st.status("Traitement du document...", expanded=True) as status:
                    st.write("Envoi du fichier vers Google Cloud Storage...")
                    client = get_storage_client()
                    bucket = client.bucket(BUCKET_NAME)
                    blob = bucket.blob(uploaded_file.name)
                    blob.upload_from_file(uploaded_file)
                    st.session_state.current_filename = uploaded_file.name
                    st.write(f" Fichier `{uploaded_file.name}` envoyé.")

                    st.write("Analyse et indexation du document en cours...")
                    st.write("(Cela peut prendre 30 à 60 secondes)")
                    time.sleep(45)
>>>>>>> 83a2abc (code de l'interface)

                    st.write(" Document indexé !")
                    status.update(label="Analyse terminée !", state="complete", expanded=False)

<<<<<<< HEAD
# --- SECTION 2: CHAT ---


# Button to change PDF
if st.session_state.file_ready:
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📄 Load Another PDF"):
            st.session_state.file_ready = False
            st.session_state.messages = []
            st.session_state.current_filename = None
            st.session_state.save_to_history = False
            st.rerun()
    
    with col2:
        if st.button("💾 " + ("Disable History" if st.session_state.save_to_history else "Enable History")):
            st.session_state.save_to_history = not st.session_state.save_to_history
            st.rerun()



if st.session_state.file_ready:
    st.success(f"**Active Document:** `{st.session_state.current_filename}`")
    
    # Display history status
    if st.session_state.save_to_history:
        st.info("💾 History enabled - your conversations will be saved")
    
    st.divider()
    st.subheader(" Ask Questions About Your Course")
=======
                st.session_state.file_ready = True
                st.balloons()
                st.rerun()


# --- SECTION 2A : MODE QUIZ INTERACTIF ---
if st.session_state.file_ready and st.session_state.show_quiz:
    st.divider()

    col_title, col_close = st.columns([5, 1])
    with col_title:
        st.subheader(" Quiz interactif")
    with col_close:
        if st.button("✖ Fermer", use_container_width=True):
            st.session_state.show_quiz = False
            st.session_state.quiz_data = None
            st.session_state.quiz_answers = {}
            st.session_state.quiz_submitted = False
            st.rerun()

    # Génération du quiz si pas encore fait
    if st.session_state.quiz_data is None:
        with st.spinner(" Le mentor prépare ton quiz..."):
            try:
                res = requests.post(
                    API_QUIZ_URL,
                    json={"question": "", "filename": st.session_state.current_filename},
                    timeout=120,
                )
                if res.status_code == 200:
                    data = res.json()
                    quiz_obj = data.get("quiz")
                    if isinstance(quiz_obj, dict) and "questions" in quiz_obj:
                        st.session_state.quiz_data = quiz_obj["questions"]
                        st.rerun()
                    else:
                        st.error("Le quiz n'a pas pu être généré correctement.")
                        st.json(data)
                else:
                    st.error(f"Erreur {res.status_code} : {res.text}")
            except Exception as e:
                st.error(f"Erreur de connexion : {e}")

    # Affichage du quiz
    if st.session_state.quiz_data:
        questions = st.session_state.quiz_data

        # === Avant soumission : formulaire interactif ===
        if not st.session_state.quiz_submitted:
            st.info(f" **{len(questions)} questions** — Choisis une réponse pour chacune, puis soumets.")

            for i, q in enumerate(questions):
                with st.container(border=True):
                    st.markdown(f"**Question {i+1}.** {q['question']}")
                    choice = st.radio(
                        "Ta réponse :",
                        options=list(range(len(q["options"]))),
                        format_func=lambda x, opts=q["options"]: f"{chr(65+x)}. {opts[x]}",
                        key=f"quiz_q_{i}",
                        index=None,
                    )
                    if choice is not None:
                        st.session_state.quiz_answers[i] = choice

            all_answered = len(st.session_state.quiz_answers) == len(questions)
            if st.button(
                "Soumettre mes réponses",
                disabled=not all_answered,
                use_container_width=True,
                type="primary",
            ):
                st.session_state.quiz_submitted = True
                st.rerun()

            if not all_answered:
                st.caption(f"Réponses données : {len(st.session_state.quiz_answers)}/{len(questions)}")

        # === Après soumission : résultats ===
        else:
            score = sum(
                1 for i, q in enumerate(questions)
                if st.session_state.quiz_answers.get(i) == q["correct_index"]
            )
            total = len(questions)
            pct = round(100 * score / total)

            # Score visuel + feedback
            if pct >= 80:
                st.success(f" Excellent ! Score : **{score}/{total}** ({pct}%)")
                feedback = "Tu maîtrises bien ce chapitre. Continue comme ça !"
            elif pct >= 50:
                st.warning(f" Pas mal ! Score : **{score}/{total}** ({pct}%)")
                feedback = "Quelques notions à revoir. Regarde bien les explications ci-dessous."
            else:
                st.error(f" À retravailler. Score : **{score}/{total}** ({pct}%)")
                feedback = "Pas de panique, c'est en se trompant qu'on apprend ! Lis bien les corrections."

            st.markdown(f"_{feedback}_")
            st.progress(pct / 100)
            st.divider()

            # Détail question par question
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
                            st.markdown(f"- **{prefix}. {opt}**  _(bonne réponse)_")
                        elif j == user_answer and not is_correct:
                            st.markdown(f"- {prefix}. {opt}  _(ta réponse)_")
                        else:
                            st.markdown(f"- {prefix}. {opt}")

                    st.info(f" **Explication :** {q['explanation']}")
                    if q.get("source"):
                        st.caption(f"Source : {q['source']}")

            st.divider()

            # Boutons d'action après le quiz
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Refaire un nouveau quiz", use_container_width=True):
                    st.session_state.quiz_data = None
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_submitted = False
                    st.rerun()
            with col2:
                if st.button(" Retour au chat", use_container_width=True):
                    st.session_state.show_quiz = False
                    st.rerun()


# --- SECTION 2B : CHAT ---
elif st.session_state.file_ready:
    st.success(f"**Document actif :** `{st.session_state.current_filename}`")
    st.divider()

    mode_label = "🎓 Mentor" if mode == "persona" else " Direct"
    st.subheader(f"Pose tes questions — Mode {mode_label}")
    st.caption("Astuce : utilise le bouton ** Lancer un quiz interactif** dans la sidebar pour te tester.")
>>>>>>> 83a2abc (code de l'interface)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ex: Summarize the key points for me"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        body = {
            "question": prompt,
            "filename": st.session_state.current_filename,
            "mode": mode,
        }

        with st.chat_message("assistant"):
<<<<<<< HEAD
            with st.spinner("Searching through your documents..."):
                try:
                    res = requests.post(
                        API_ASK_URL,  # ← Note the /ask at the end
                        json={"question": prompt, "filename": st.session_state.current_filename },
=======
            with st.spinner("Je réfléchis..."):
                try:
                    res = requests.post(
                        API_ASK_URL,
                        json=body,
>>>>>>> 83a2abc (code de l'interface)
                        timeout=120,
                    )

                    if res.status_code == 200:
                        data = res.json()
                        reponse_ia = data.get("answer", "No response received.")
                        st.markdown(reponse_ia)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": reponse_ia}
                        )
                        
                        # Save to MongoDB only if enabled
                        if st.session_state.save_to_history:
                            if chat_with_history is None and st.session_state.current_filename:
                                chat_with_history = MongoChatMessageHistory(
                                    session_id=st.session_state.current_filename,
                                    connection_string="mongodb+srv://projetcloud:projetcloud@geminirag.shbfocl.mongodb.net/?appName=GeminiRAG",
                                    collection_name="chat_history",
                                    database_name="smartstudy"
                                )
                            if chat_with_history:
                                chat_with_history.add_user_message(prompt)
                                chat_with_history.add_ai_message(reponse_ia)
                    else:
                        error_msg = f"Error {res.status_code}: {res.text}"
                        st.error(error_msg)

                except Exception as e:
<<<<<<< HEAD
                    st.error(f"Connection error: {e}")

=======
                    st.error(f"Erreur de connexion : {e}")
>>>>>>> 83a2abc (code de l'interface)

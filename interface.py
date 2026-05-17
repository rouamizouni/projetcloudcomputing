import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account
import time
import requests
import random
import hashlib
import uuid
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from langchain_mongodb.chat_message_histories import MongoDBChatMessageHistory
from pymongo import MongoClient
from datetime import datetime, timedelta
import json
from urllib.parse import urlencode

st.set_page_config(page_title="SmartStudy Tutor", page_icon="🎓", layout="centered")

# — CONFIGURATION —

BUCKET_NAME = "pdf_bucket_project"
PROJECT_ID = "projet-cloud-computing-493007"
MONGO_URI = "mongodb+srv://projetcloud:projetcloud@geminirag.shbfocl.mongodb.net/?appName=GeminiRAG"
MONGO_DB = "smartstudy"
MONGO_COLLECTION = "chat_history"
USERS_COLLECTION = "users"
RESET_COLLECTION = "password_resets"

API_BASE_URL = "https://smartstudy-api-64317660927.europe-west1.run.app"
API_ASK_URL = f"{API_BASE_URL}/ask"
API_QUIZ_URL = f"{API_BASE_URL}/quiz"

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# ══════════════════════════════════════════
# VALIDATION
# ══════════════════════════════════════════

def is_valid_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))

def check_password_strength(password: str) -> tuple:
    issues = []
    if len(password) < 8:
        issues.append("At least 8 characters")
    if not re.search(r"[A-Z]", password):
        issues.append("At least one uppercase letter")
    if not re.search(r"[0-9]", password):
        issues.append("At least one digit")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_-]', password):
        issues.append("At least one special character (!@#$…)")
    return len(issues) == 0, issues

def password_strength_bar(password: str):
    if not password:
        return
    score = 0
    if len(password) >= 8:
        score += 1
    if re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[0-9]", password):
        score += 1
    if re.search(r'[!@#$%^&*(),.?":{}|<>_-]', password):
        score += 1
    labels = ["Very Weak", "Weak", "Medium", "Strong", "Very Strong"]
    icons = ["🔴", "🟠", "🟡", "🟢", "✅"]
    st.progress(score / 4, text=f"{icons[score]} Strength: {labels[score]}")

# ══════════════════════════════════════════
# EMAIL
# ══════════════════════════════════════════

def send_reset_email(to_email: str, reset_link: str) -> bool:
    try:
        smtp_email = st.secrets["email"]["smtp_user"]
        smtp_password = st.secrets["email"]["smtp_password"]
        smtp_host = st.secrets["email"].get("smtp_host", "smtp.gmail.com")
        smtp_port = int(st.secrets["email"].get("smtp_port", 587))
    except Exception:
        st.error("Email configuration missing in Streamlit secrets.")
        return False

    html_body = f"""
    <html><body style="font-family: sans-serif; max-width: 500px; margin: auto; padding: 20px;">
        <h2 style="color: #1C1917;">🎓 SmartStudy — Password Reset</h2>
        <p>You requested a password reset.</p>
        <p>Click the button below within <strong>30 minutes</strong>:</p>
        <a href="{reset_link}" style="
            display: inline-block; background: #1C1917; color: white;
            padding: 12px 24px; border-radius: 8px; text-decoration: none;
            font-size: 15px; margin: 16px 0;">Reset My Password</a>
        <p style="color: #888; font-size: 13px;">
            If you did not request this, ignore this email.<br>
            Link: {reset_link}
        </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "SmartStudy — Password Reset"
    msg["From"] = smtp_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# ══════════════════════════════════════════
# AUTH HELPERS
# ══════════════════════════════════════════

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_mongo_client():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

def get_user_by_email(email: str):
    client = get_mongo_client()
    return client[MONGO_DB][USERS_COLLECTION].find_one({"email": email.lower().strip()})

def create_user(email: str, username: str, password: str) -> tuple:
    if not is_valid_email(email):
        return False, "Invalid email format."
    is_strong, issues = check_password_strength(password)
    if not is_strong:
        return False, " · ".join(issues)
    client = get_mongo_client()
    col = client[MONGO_DB][USERS_COLLECTION]
    if col.find_one({"email": email.lower().strip()}):
        return False, "This email is already in use."
    col.insert_one({
        "email": email.lower().strip(),
        "username": username.strip(),
        "password": hash_password(password),
        "created_at": datetime.utcnow(),
        "auth_method": "email",
    })
    return True, "OK"

def login_user(email: str, password: str):
    user = get_user_by_email(email)
    if user and user.get("password") and user["password"] == hash_password(password):
        return user
    return None

def create_reset_token(email: str) -> str:
    token = uuid.uuid4().hex
    client = get_mongo_client()
    col = client[MONGO_DB][RESET_COLLECTION]
    col.delete_many({"email": email.lower().strip()})
    col.insert_one({
        "email": email.lower().strip(),
        "token": token,
        "expires_at": datetime.utcnow() + timedelta(minutes=30),
        "used": False,
    })
    return token

def verify_reset_token(token: str) -> str:
    client = get_mongo_client()
    col = client[MONGO_DB][RESET_COLLECTION]
    doc = col.find_one({"token": token, "used": False})
    if not doc:
        return None
    if datetime.utcnow() > doc["expires_at"]:
        return None
    return doc["email"]

def consume_reset_token(token: str, new_password: str) -> bool:
    email = verify_reset_token(token)
    if not email:
        return False
    client = get_mongo_client()
    client[MONGO_DB][USERS_COLLECTION].update_one(
        {"email": email},
        {"$set": {"password": hash_password(new_password)}}
    )
    client[MONGO_DB][RESET_COLLECTION].update_one(
        {"token": token},
        {"$set": {"used": True}}
    )
    return True

def upsert_google_user(google_id: str, email: str, username: str, picture: str = None):
    client = get_mongo_client()
    col = client[MONGO_DB][USERS_COLLECTION]
    existing = col.find_one({"google_id": google_id})
    if not existing:
        existing_email = col.find_one({"email": email.lower().strip()})
        if existing_email:
            col.update_one(
                {"email": email.lower().strip()},
                {"$set": {"google_id": google_id, "picture": picture}}
            )
        else:
            col.insert_one({
                "email": email.lower().strip(),
                "username": username,
                "google_id": google_id,
                "picture": picture,
                "created_at": datetime.utcnow(),
                "auth_method": "google",
            })
        return col.find_one({"google_id": google_id})
    else:
        col.update_one({"google_id": google_id}, {"$set": {"picture": picture}})
        return col.find_one({"google_id": google_id})

def get_google_auth_url() -> str:
    try:
        client_id = st.secrets["google_oauth"]["client_id"]
        redirect_uri = st.secrets["google_oauth"]["redirect_uri"]
    except Exception:
        return None
        
    if "oauth_state" not in st.session_state:
        st.session_state["oauth_state"] = uuid.uuid4().hex
        
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": st.session_state["oauth_state"]
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

def exchange_google_code(code: str) -> dict:
    try:
        client_id = st.secrets["google_oauth"]["client_id"]
        client_secret = st.secrets["google_oauth"]["client_secret"]
        redirect_uri = st.secrets["google_oauth"]["redirect_uri"]
    except Exception:
        return None
    token_res = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })
    if token_res.status_code != 200:
        return None
    access_token = token_res.json().get("access_token")
    user_res = requests.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    if user_res.status_code != 200:
        return None
    return user_res.json()

def get_app_url() -> str:
    try:
        return st.secrets["google_oauth"]["redirect_uri"]
    except Exception:
        return "http://localhost:8501"

# ══════════════════════════════════════════
# APP HELPERS
# ══════════════════════════════════════════

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
    user_msg = f"📝 **Quiz completed** — {len(questions)} questions on this document."
    lines = [f"## 🧠 Quiz Result — {score}/{total} ({pct}%)\n"]
    for i, q in enumerate(questions):
        user_answer = answers.get(i)
        correct = q["correct_index"]
        is_correct = user_answer == correct
        icon = "✅" if is_correct else "❌"
        lines.append(f"**{icon} Q{i+1}. {q['question']}**")
        if user_answer is not None:
            lines.append(f"- Your answer: {chr(65 + user_answer)}. {q['options'][user_answer]}")
        if not is_correct and user_answer is not None:
            lines.append(f"- Correct answer: {chr(65 + correct)}. {q['options'][correct]}")
        lines.append(f"- 💡 {q['explanation']}\n")
    ai_msg = "\n".join(lines)
    save_message(session_id, "user", user_msg)
    save_message(session_id, "assistant", ai_msg)
    load_past_sessions.clear()
    load_session_messages.clear()

@st.cache_data(ttl=30)
def load_past_sessions(user_id: str):
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
            {"$match": {session_field: {"$regex": f"^{user_id}__"}}},
            {"$group": {
                "_id": f"${session_field}",
                "last_updated": {"$max": "$_id"},
                "message_count": {"$sum": 1},
            }},
            {"$sort": {"last_updated": -1}},
            {"$limit": 30},
        ])
        return list(sessions)
    except Exception as e:
        st.session_state["mongo_error"] = str(e)
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
            (f for f in ["SessionId", "session_id", "sessionId"] if f in sample), None
        )
        if not session_field:
            return []
        docs = list(col.find({session_field: session_id}).sort("_id", 1))
        messages = []
        for doc in docs:
            history_raw = doc.get("History") or doc.get("history", {})
            if isinstance(history_raw, str):
                try:
                    history_raw = json.loads(history_raw)
                except Exception:
                    continue
            msg_type = history_raw.get("type", "")
            data = history_raw.get("data", {})
            content = data.get("content", "") if data else history_raw.get("content", "")
            if not content:
                continue
            if msg_type == "human":
                messages.append({"role": "user", "content": content})
            elif msg_type == "ai":
                messages.append({"role": "assistant", "content": content})
        return messages
    except Exception:
        return []

def format_session_label(session_id: str):
    if "**" in session_id:
        session_id = session_id.split("**", 1)[1]
    parts = session_id.rsplit("_", 1)
    if len(parts) == 2:
        filename = parts[0]
        try:
            ts = int(parts[1])
            date = datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")
            return filename, date
        except ValueError:
            pass
    return session_id, ""

def make_session_id(user_id: str, filename: str) -> str:
    return f"{user_id}__{filename}_{int(time.time())}"

def get_filename_from_session(session_id: str) -> str:
    if "**" in session_id:
        session_id = session_id.split("**", 1)[1]
    parts = session_id.rsplit("_", 1)
    return parts[0] if len(parts) == 2 else session_id

# ══════════════════════════════════════════
# STATE INITIALIZATION
# ══════════════════════════════════════════

auth_defaults = {
    "authenticated": False,
    "user_id": None,
    "username": None,
    "is_guest": False,
}
app_defaults = {
    "file_ready": False,
    "messages": [],
    "current_filename": None,
    "session_id": None,
    "quiz_data": None,
    "quiz_answers": {},
    "quiz_submitted": False,
    "show_quiz": False,
    "mongo_error": None,
}
for key, val in {**auth_defaults, **app_defaults}.items():
    if key not in st.session_state:
        st.session_state[key] = val

def reset_app_state():
    for key, val in app_defaults.items():
        st.session_state[key] = val

# ══════════════════════════════════════════
# HANDLE RESET PASSWORD FROM URL
# ══════════════════════════════════════════

query_params = st.query_params

if "reset_token" in query_params and not st.session_state.authenticated:
    token = query_params.get("reset_token")
    email = verify_reset_token(token)

    st.title("🎓 SmartStudy — New Password")
    st.divider()

    if not email:
        st.error("This link is invalid or has expired. Please request a new one.")
    else:
        st.success(f"Reset password for **{email}**")
        new_pw = st.text_input("New password", type="password", key="reset_pw1")
        if new_pw:
            password_strength_bar(new_pw)
            _, issues = check_password_strength(new_pw)
            for issue in issues:
                st.caption(f"  • {issue}")
        new_pw2 = st.text_input("Confirm password", type="password", key="reset_pw2")

        if st.button("Save new password", type="primary", use_container_width=True):
            if not new_pw or not new_pw2:
                st.error("Please fill in both fields.")
            elif new_pw != new_pw2:
                st.error("Passwords do not match.")
            else:
                is_strong, issues = check_password_strength(new_pw)
                if not is_strong:
                    st.error(" · ".join(issues))
                else:
                    ok = consume_reset_token(token, new_pw)
                    if ok:
                        st.success("✅ Password updated! You can now log in.")
                        st.query_params.clear()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Error updating password. Please try again.")
    st.stop()

# ══════════════════════════════════════════
# HANDLE GOOGLE OAUTH CALLBACK
# ══════════════════════════════════════════

if "code" in query_params and not st.session_state.authenticated:
    code = query_params.get("code")
    returned_state = query_params.get("state")
    
    if returned_state == st.session_state.get("oauth_state"):
        with st.spinner("Signing in with Google…"):
            user_info = exchange_google_code(code)
            if user_info:
                google_id = user_info.get("sub")
                email = user_info.get("email", "")
                name = user_info.get("name", email.split("@")[0])
                picture = user_info.get("picture", "")
                user = upsert_google_user(google_id, email, name, picture)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_id = str(user["_id"])
                    st.session_state.username = user["username"]
                    st.session_state.is_guest = False
                    reset_app_state()
                    st.query_params.clear()
                    st.rerun()
            else:
                st.error("Google sign-in failed. Please try again.")
                st.query_params.clear()
    else:
        st.error("OAuth state verification mismatch. Potential cross-site request detected.")
        st.query_params.clear()

# ══════════════════════════════════════════
# AUTH PAGE
# ══════════════════════════════════════════

def show_auth_page():
    st.title("🎓 SmartStudy Tutor")
    st.markdown("### Welcome to your intelligent learning space")
    st.divider()

    tab_login, tab_signup, tab_guest = st.tabs(["🔑 Sign In", "📝 Create Account", "👤 Guest Mode"])

    # --- SIGN IN ---
    with tab_login:
        st.markdown("#### Sign In")

        google_url = get_google_auth_url()
        if google_url:
            st.markdown(
                f"""<a href="{google_url}" target="_self">
                <button style="width:100%;padding:10px;border-radius:8px;border:1px solid #ddd;
                background:#fff;font-size:15px;cursor:pointer;margin-bottom:12px;">
                <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width="18"/>
                  Continue with Google
                </button></a>""",
                unsafe_allow_html=True,
            )
            st.markdown("---")

        email = st.text_input("Email", key="login_email", placeholder="you@example.com")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Sign In", type="primary", use_container_width=True, key="btn_login"):
            if not email or not password:
                st.error("Please fill in all fields.")
            elif not is_valid_email(email):
                st.error("Invalid email format.")
            else:
                user = login_user(email, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_id = str(user["_id"])
                    st.session_state.username = user["username"]
                    st.session_state.is_guest = False
                    reset_app_state()
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

        st.markdown("---")
        with st.expander("🔓 Forgot your password?"):
            forgot_email = st.text_input("Your email", key="forgot_email", placeholder="you@example.com")
            if st.button("Send reset link", use_container_width=True, key="btn_forgot"):
                if not forgot_email:
                    st.error("Please enter your email.")
                elif not is_valid_email(forgot_email):
                    st.error("Invalid email format.")
                else:
                    user = get_user_by_email(forgot_email)
                    if user:
                        token = create_reset_token(forgot_email)
                        reset_link = f"{get_app_url()}?reset_token={token}"
                        sent = send_reset_email(forgot_email, reset_link)
                        if sent:
                            st.success("✅ Email sent! Check your inbox (and spam folder).")
                    else:
                        st.success("✅ If this email exists, a reset link has been sent.")

    # --- SIGN UP ---
    with tab_signup:
        st.markdown("#### Create Account")

        google_url = get_google_auth_url()
        if google_url:
            st.markdown(
                f"""<a href="{google_url}" target="_self">
                <button style="width:100%;padding:10px;border-radius:8px;border:1px solid #ddd;
                background:#fff;font-size:15px;cursor:pointer;margin-bottom:12px;">
                <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width="18"/>
                  Sign Up with Google
                </button></a>""",
                unsafe_allow_html=True,
            )
            st.markdown("---")

        new_username = st.text_input("Name / Username", key="signup_username", placeholder="e.g. Marie")
        new_email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
        if new_email and not is_valid_email(new_email):
            st.warning("Invalid email format.")

        new_password = st.text_input("Password", type="password", key="signup_password")
        if new_password:
            password_strength_bar(new_password)
            _, issues = check_password_strength(new_password)
            for issue in issues:
                st.caption(f"  • {issue}")

        new_password2 = st.text_input("Confirm password", type="password", key="signup_password2")
        if new_password and new_password2 and new_password != new_password2:
            st.warning("Passwords do not match.")

        if st.button("Create Account", type="primary", use_container_width=True, key="btn_signup"):
            if not new_username or not new_email or not new_password:
                st.error("Please fill in all fields.")
            elif not is_valid_email(new_email):
                st.error("Invalid email format.")
            elif new_password != new_password2:
                st.error("Passwords do not match.")
            else:
                ok, msg = create_user(new_email, new_username, new_password)
                if ok:
                    st.success("✅ Account created! You can now sign in.")
                else:
                    st.error(msg)

    # --- GUEST ---
    with tab_guest:
        st.markdown("#### Guest Mode")
        st.info("In guest mode, your conversations are not saved. They disappear when you close the tab.")
        if st.button("Continue as Guest", use_container_width=True, key="btn_guest"):
            st.session_state.authenticated = True
            st.session_state.user_id = f"guest_{uuid.uuid4().hex[:8]}"
            st.session_state.username = "Guest"
            st.session_state.is_guest = True
            reset_app_state()
            st.rerun()

if not st.session_state.authenticated:
    show_auth_page()
    st.stop()

# ══════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════

with st.sidebar:
    st.title("🎓 SmartStudy")

    if st.session_state.is_guest:
        st.caption("👤 Guest Mode")
    else:
        st.caption(f"👋 Hello, **{st.session_state.username}**")

    mode = st.radio(
        "Tutor mode",
        options=["persona", "normal"],
        format_func=lambda x: "🎓 Persona Mentor" if x == "persona" else "📝 Direct Mode",
    )

    st.divider()

    if st.button("✏️ New conversation", use_container_width=True):
        reset_app_state()
        st.rerun()

    if st.session_state.file_ready and not st.session_state.show_quiz:
        if st.button("🧠 Start a quiz", use_container_width=True, type="primary"):
            st.session_state.show_quiz = True
            st.session_state.quiz_data = None
            st.session_state.quiz_answers = {}
            st.session_state.quiz_submitted = False
            if "quiz_saved" in st.session_state:
                del st.session_state.quiz_saved
            st.rerun()

    if not st.session_state.is_guest:
        st.divider()
        st.markdown("#### 🕐 Recent conversations")

        if st.session_state.get("mongo_error"):
            st.error(f"MongoDB: {st.session_state.mongo_error}")

        past_sessions = load_past_sessions(st.session_state.user_id)

        if not past_sessions:
            st.caption("No saved conversations yet.")
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
                    st.session_state.messages = msgs
                    st.session_state.session_id = sid
                    st.session_state.current_filename = get_filename_from_session(sid)
                    st.session_state.file_ready = True
                    st.session_state.show_quiz = False
                    st.session_state.quiz_data = None
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_submitted = False
                    st.rerun()
    else:
        st.divider()
        st.caption("💡 Sign in to save your conversations.")

    st.divider()
    if st.button("🚪 Sign out", use_container_width=True):
        for key in list({**auth_defaults, **app_defaults}.keys()):
            st.session_state[key] = {**auth_defaults, **app_defaults}[key]
        st.rerun()

# — MAIN —

st.title("🎓 SmartStudy Tutor")
st.markdown("### Welcome to your intelligent learning space")

# — SECTION 1: UPLOAD —

if not st.session_state.file_ready:
    st.write("Upload your course PDF to start the session.")
    with st.container():
        uploaded_file = st.file_uploader("Choose your PDF file", type="pdf")
        if uploaded_file is not None:
            if st.button("Start course analysis"):
                with st.status("Processing document…", expanded=True) as status:
                    st.write("📤 Uploading file to Google Cloud Storage…")
                    client = get_storage_client()
                    bucket = client.bucket(BUCKET_NAME)
                    blob = bucket.blob(uploaded_file.name)
                    blob.upload_from_file(uploaded_file)
                    st.session_state.current_filename = uploaded_file.name
                    st.write(f"✅ File `{uploaded_file.name}` uploaded.")
                    st.write("🔍 Analyzing and indexing document…")
                    st.write("(This may take 30 to 60 seconds)")
                    time.sleep(45)
                    st.write("✅ Document indexed!")
                    status.update(label="Analysis complete!", state="complete", expanded=False)
                st.session_state.session_id = make_session_id(st.session_state.user_id, uploaded_file.name)
                st.session_state.file_ready = True
                st.session_state.messages = []
                if not st.session_state.is_guest:
                    load_past_sessions.clear()
                st.balloons()
                st.rerun()

# — SECTION 2A: QUIZ —

if st.session_state.file_ready and st.session_state.show_quiz:
    st.divider()
    col_title, col_close = st.columns([5, 1])
    with col_title:
        st.subheader("🧠 Interactive Quiz")
    with col_close:
        if st.button("✖ Close", use_container_width=True):
            st.session_state.show_quiz = False
            st.session_state.quiz_data = None
            st.session_state.quiz_answers = {}
            st.session_state.quiz_submitted = False
            if "quiz_saved" in st.session_state:
                del st.session_state.quiz_saved
            st.rerun()

    if st.session_state.quiz_data is None:
        with st.spinner("🎓 Preparing your quiz..."):
            try:
                res = requests.post(
                    API_QUIZ_URL,
                    json={
                        "filename": st.session_state.current_filename,
                        "seed": random.randint(1, 999999),
                        "timestamp": int(time.time())
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
                        st.error("Could not generate the quiz correctly.")
                        st.json(data)
                else:
                    st.error(f"Error {res.status_code}: {res.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

    if st.session_state.quiz_data:
        questions = st.session_state.quiz_data

        if not st.session_state.quiz_submitted:
            st.info(f"📋 **{len(questions)} questions** — Choose one answer per question, then submit.")
            for i, q in enumerate(questions):
                with st.container(border=True):
                    st.markdown(f"**Question {i+1}.** {q['question']}")
                    choice = st.radio(
                        "Your answer:",
                        options=list(range(len(q["options"]))),
                        format_func=lambda x, opts=q["options"]: f"{chr(65+x)}. {opts[x]}",
                        key=f"quiz_q_{i}",
                        index=None,
                    )
                    if choice is not None:
                        st.session_state.quiz_answers[i] = choice

            all_answered = len(st.session_state.quiz_answers) == len(questions)
            if st.button("Submit answers", disabled=not all_answered,
                        use_container_width=True, type="primary"):
                st.session_state.quiz_submitted = True
                st.rerun()
            if not all_answered:
                st.caption(f"Answered: {len(st.session_state.quiz_answers)}/{len(questions)}")

        else:
            score = sum(
                1 for i, q in enumerate(questions)
                if st.session_state.quiz_answers.get(i) == q["correct_index"]
            )
            total = len(questions)
            pct = round(100 * score / total)

            if pct >= 80:
                st.success(f"🏆 Excellent! Score: **{score}/{total}** ({pct}%)")
                feedback = "You have a solid grasp of this chapter. Keep it up!"
            elif pct >= 50:
                st.warning(f"👍 Not bad! Score: **{score}/{total}** ({pct}%)")
                feedback = "A few things to review. Check the explanations below."
            else:
                st.error(f"📚 Needs work. Score: **{score}/{total}** ({pct}%)")
                feedback = "Don't worry, mistakes are how we learn! Read the corrections carefully."

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
                            st.markdown(f"- **{prefix}. {opt}** *(correct answer)*")
                        elif j == user_answer and not is_correct:
                            st.markdown(f"- {prefix}. {opt} *(your answer)*")
                        else:
                            st.markdown(f"- {prefix}. {opt}")
                    st.info(f"💡 **Explanation:** {q['explanation']}")
                    if q.get("source"):
                        st.caption(f"Source: {q['source']}")

            if not st.session_state.is_guest and st.session_state.session_id and "quiz_saved" not in st.session_state:
                try:
                    save_quiz_to_history(st.session_state.session_id, questions,
                                         st.session_state.quiz_answers, score, total)
                    st.session_state.quiz_saved = True
                    st.toast("✅ Quiz saved to your history!", icon="💾")
                except Exception as e:
                    st.warning(f"Quiz not saved: {e}")

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 New quiz", use_container_width=True):
                    st.session_state.quiz_data = None
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_submitted = False
                    if "quiz_saved" in st.session_state:
                        del st.session_state.quiz_saved
                    st.rerun()
            with col2:
                if st.button("💬 Back to chat", use_container_width=True):
                    st.session_state.show_quiz = False
                    if "quiz_saved" in st.session_state:
                        del st.session_state.quiz_saved
                    st.rerun()

# — SECTION 2B: CHAT —

elif st.session_state.file_ready:
    st.success(f"**Active document:** `{st.session_state.current_filename}`")
    if st.session_state.is_guest:
        st.warning("👤 Guest mode — this conversation will not be saved.")
    st.divider()

    mode_label = "🎓 Mentor" if mode == "persona" else "📝 Direct"
    st.subheader(f"Ask your questions — {mode_label} mode")
    st.caption("Tip: use **🧠 Start a quiz** in the sidebar to test yourself.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("e.g. Summarize the key points for me"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        body = {
            "question": prompt,
            "filename": st.session_state.current_filename,
            "mode": mode,
        }

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    res = requests.post(API_ASK_URL, json=body, timeout=120)
                    if res.status_code == 200:
                        data = res.json()
                        reponse_ia = data.get("answer", "No response received.")
                        st.markdown(reponse_ia)
                        st.session_state.messages.append({"role": "assistant", "content": reponse_ia})
                        if not st.session_state.is_guest and st.session_state.session_id:
                            try:
                                save_message(st.session_state.session_id, "user", prompt)
                                save_message(st.session_state.session_id, "assistant", reponse_ia)
                                load_past_sessions.clear()
                                load_session_messages.clear()
                            except Exception as e:
                                st.warning(f"Not saved: {e}")
                    else:
                        st.error(f"Error {res.status_code}: {res.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")
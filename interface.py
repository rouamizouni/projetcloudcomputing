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
        "code": code
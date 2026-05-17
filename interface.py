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
    if not is_valid_email
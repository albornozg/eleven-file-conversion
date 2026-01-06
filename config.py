import os
import requests
import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError

def get_secret(key: str, default: str = "") -> str:
    """
    Try Streamlit secrets.toml first, fall back to environment variables.
    Works both on Streamlit Cloud and on Render.
    """
    try:
        return st.secrets[key]
    except (KeyError, StreamlitSecretNotFoundError):
        return os.getenv(key, default)

ELEVEN_API_KEY = get_secret("ELEVEN_API_KEY")
APP_USER = get_secret("APP_USER", "team")
APP_PASS = get_secret("APP_PASS", "strong_password")

# Simple in-app login
def authenticate():
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False

    if not st.session_state.auth_ok:
        with st.form("login", clear_on_submit=False):
            st.subheader("Login")
            u = st.text_input("Username", value="", key="u")
            p = st.text_input("Password", value="", type="password", key="p")
            ok = st.form_submit_button("Enter")
            if ok:
                if u == APP_USER and p == APP_PASS:
                    st.session_state.auth_ok = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        st.stop()

# Fetch subscription tier
def get_subscription_tier():
    url = "https://api.elevenlabs.io/v1/user/subscription"
    headers = {"xi-api-key": ELEVEN_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("tier", "unknown").lower()
        else:
            return "unknown"
    except Exception:
        return "unknown"

def get_tier():
    if "subscription_tier" not in st.session_state:
        st.session_state["subscription_tier"] = get_subscription_tier()
    return st.session_state["subscription_tier"]

def supports_pcm_func(tier):
    return tier in ["pro", "scale", "business", "enterprise"]

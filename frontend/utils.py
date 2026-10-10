import streamlit as st
import time
from datetime import datetime, timedelta

# --- i18n Dictionary ---
@st.cache_data
def get_i18n():
    return {
        "en": {
            "login": "Login",
            "patient_login": "Patient Login",
            "doctor_login": "Doctor Login",
            "register": "Register",
            "unverified": "Self-reported",
            "verified": "Provider-attested",
            "sos": "Emergency SOS",
            "logout": "Logout",
            "read_only_mode": "READ ONLY MODE - EMERGENCY ACCESS"
        },
        "hi": {
            "login": "लॉग इन करें",
            "patient_login": "मरीज लॉग इन",
            "doctor_login": "डॉक्टर लॉग इन",
            "register": "पंजीकरण करें",
            "unverified": "स्वयं रिपोर्ट किया गया",
            "verified": "प्रदाता द्वारा प्रमाणित",
            "sos": "आपातकालीन SOS",
            "logout": "लॉग आउट",
            "read_only_mode": "केवल पढ़ने के लिए - आपातकालीन पहुँच"
        },
        "ta": {
            "login": "உள்நுழைக",
            "patient_login": "நோயாளி உள்நுழைவு",
            "doctor_login": "மருத்துவர் உள்நுழைவு",
            "register": "பதிவு செய்",
            "unverified": "சுய அறிக்கை",
            "verified": "வழங்குநரால் சான்றளிக்கப்பட்டது",
            "sos": "அவசரகால SOS",
            "logout": "வெளியேறு",
            "read_only_mode": "படிக்க மட்டும் - அவசரகால அணுகல்"
        }
    }

def init_session():
    # Enforce strictly defined session state keys
    defaults = {
        "access_token": None, "refresh_token": None, "role": None, 
        "user_id": None, "mk": None, "search_key": None, 
        "access_mode": "CONSENTED", # or "EMERGENCY"
        "sos_expires_at": None, "scope": [], 
        "lang": "en", "text_scale": 1.0, "last_activity": time.time()
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def check_idle_timeout():
    # 15-minute idle auto-logout
    if st.session_state.get("user_id"):
        idle_time = time.time() - st.session_state.last_activity
        if idle_time > 900: # 15 mins
            logout(reason="Session expired due to 15 minutes of inactivity.")
        else:
            st.session_state.last_activity = time.time()

def logout(reason="Logged out safely."):
    # Zeroise sensitive data
    st.session_state.access_token = None
    st.session_state.role = None
    st.session_state.user_id = None
    st.session_state.mk = None
    st.session_state.search_key = None
    st.session_state.access_mode = "CONSENTED"
    st.session_state.sos_expires_at = None
    st.session_state.scope = []
    st.success(reason)
    time.sleep(1)
    st.switch_page("pages/00_Landing.py")

def require_auth(allowed_roles=None):
    check_idle_timeout()
    if not st.session_state.get("user_id"):
        st.warning("Please log in to access this page.")
        st.stop()
    if allowed_roles and st.session_state.role not in allowed_roles:
        st.error("Outside your consent scope or role permissions.")
        st.stop()

def enforce_readonly():
    # Returns True if we are in Emergency mode, used to disable write widgets
    if st.session_state.get("access_mode") == "EMERGENCY":
        st.error(get_i18n()[st.session_state.lang]["read_only_mode"])
        return True
    return False

def apply_text_scale():
    # CSS injection for accessibility base font size
    scale = st.session_state.get("text_scale", 1.0)
    css = f"""
    <style>
        html, body, [class*="css"]  {{
            font-size: {int(16 * scale)}px !important;
        }}
        .stButton>button {{
            font-weight: 600;
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
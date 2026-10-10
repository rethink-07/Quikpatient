import streamlit as st
from utils import init_session, apply_text_scale, get_i18n, logout

st.set_page_config(page_title="QuikPatient", page_icon="⚕️", layout="centered", initial_sidebar_state="expanded")

init_session()
apply_text_scale()
t = get_i18n()[st.session_state.lang]

# Global Top Bar Accessibility Settings
with st.sidebar:
    st.header("Accessibility")
    st.session_state.lang = st.selectbox(
        "Language / भाषा / மொழி", 
        ["en", "hi", "ta"], 
        format_func=lambda x: {"en": "English", "hi": "हिन्दी", "ta": "தமிழ்"}[x],
        label_visibility="collapsed"
    )
    st.session_state.text_scale = st.slider("Text Size", min_value=0.8, max_value=1.5, step=0.1, value=1.0)
    
    if st.session_state.get("user_id"):
        st.divider()
        if st.button(t["logout"], use_container_width=True):
            logout()

# --- DYNAMIC NAVIGATION ---
pages = {
    "Public": [
        st.Page("pages/00_Landing.py", title="Home", icon="🏠"),
        st.Page("pages/01_Auth.py", title="Portal Login", icon="🔐"),
    ]
}

# If logged in as Patient, inject patient pages
if st.session_state.get("role") == "PATIENT":
    pages["Patient Portal"] = [
        st.Page("pages/02_Patient_Timeline.py", title="Timeline", icon="📅"),
        st.Page("pages/03_Ongoing_Meds.py", title="Ongoing Meds", icon="💊"),
        st.Page("pages/04_ABDM_Sync.py", title="ABDM Sync", icon="🔄"),
        st.Page("pages/05_Upload_Document.py", title="Upload Document", icon="📤"),
        st.Page("pages/06_General_Info.py", title="General Info", icon="👤"),
        st.Page("pages/07_Consents_Log.py", title="Consents & Log", icon="🛡️"),
        st.Page("pages/08_Changelog.py", title="Changelog", icon="📜"),
        st.Page("pages/15_Security.py", title="Security Explainer", icon="🔒"),
    ]

# If logged in as Doctor, inject doctor pages
elif st.session_state.get("role") == "DOCTOR":
    pages["Doctor Portal"] = [
        st.Page("pages/09_Doctor_Dashboard.py", title="My Patients", icon="👥"),
        st.Page("pages/10_Doctor_SOS.py", title="Emergency SOS", icon="🚨"),
        st.Page("pages/11_Patient_View.py", title="Patient View", icon="🏥"),
        st.Page("pages/12_Clinical_Search.py", title="Clinical Search", icon="🔍"),
        st.Page("pages/13_Prescribe.py", title="Prescribe", icon="✍️"),
        st.Page("pages/14_Extended_Access.py", title="Request Access", icon="⏳"),
    ]

nav = st.navigation(pages)
nav.run()
import streamlit as st
from utils import require_auth

require_auth(["DOCTOR"])

st.title("My Patients")
st.info("⚖️ **Minimum-necessary access. Every action is logged and visible to the patient.**")

c1, c2, c3 = st.columns(3)
if c1.button("➕ New Patient Encounter", use_container_width=True):
    st.toast("Create new encounter logic...")
if c2.button("🔑 Unlock with Encounter Key", use_container_width=True):
    st.toast("Prompt for 6-digit encounter key...")
if c3.button("🚨 Emergency Access (SOS)", type="primary", use_container_width=True):
    st.switch_page("pages/10_Doctor_SOS.py")

st.divider()

# Patient Roster
patients = [
    {"name": "Aarav Sharma", "demo": "47/M", "scope": "All Records", "expiry": "82 days (31-Dec-2026)", "state": "Unlocked", "mode": "CONSENTED"},
    {"name": "Priya Patel", "demo": "34/F", "scope": "Prescription Only", "expiry": "2 hours (10-Oct-2026)", "state": "Unlocked", "mode": "CONSENTED"},
    {"name": "Unknown Trauma", "demo": "??/M", "scope": "Read-Only (Emergency)", "expiry": "1hr 34mins", "state": "Unlocked", "mode": "EMERGENCY READ-ONLY"}
]

for p in patients:
    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.markdown(f"**{p['name']}** | {p['demo']}")
            if p['mode'] == "EMERGENCY READ-ONLY":
                st.markdown("<span style='color: white; background: #dc2626; padding: 2px 6px; border-radius: 4px; font-size: 0.8em;'>EMERGENCY READ-ONLY</span>", unsafe_allow_html=True)
            else:
                st.markdown("<span style='color: #0d9488; background: #ccfbf1; padding: 2px 6px; border-radius: 4px; font-size: 0.8em;'>CONSENTED</span>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"**Scope:** `{p['scope']}`")
            st.caption(f"Expires in: {p['expiry']}")
        with col3:
            if st.button("Open Chart", key=f"open_{p['name']}", type="primary"):
                st.session_state.current_patient = p['name']
                st.session_state.access_mode = "EMERGENCY" if p['mode'] == "EMERGENCY READ-ONLY" else "CONSENTED"
                st.switch_page("pages/11_Patient_View.py")
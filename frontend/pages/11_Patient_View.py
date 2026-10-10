import streamlit as st
from utils import require_auth
from utils_ui import record_card

require_auth(["DOCTOR"])

if not st.session_state.get("current_patient"):
    st.switch_page("pages/09_Doctor_Dashboard.py")

if st.session_state.get("access_mode") == "EMERGENCY":
    st.markdown("<div style='background: #dc2626; color: white; padding: 10px; text-align: center; font-weight: bold; margin-bottom: 20px;'>🚨 EMERGENCY READ-ONLY MODE ACTIVE. EXPIRES IN 01:34:00.</div>", unsafe_allow_html=True)

st.title(f"Patient: {st.session_state.current_patient}")

col_main, col_side = st.columns([3, 1])

with col_side:
    st.subheader("Critical")
    with st.container(border=True):
        st.markdown("**Blood Group:** B+")
        st.markdown("**Allergies:**")
        st.markdown("<span style='color: #dc2626; font-weight: bold;'>⚠️ Penicillin</span>", unsafe_allow_html=True)
        st.markdown("**Active Meds:**")
        st.markdown("- Metformin 500mg\n- Lisinopril 10mg")

with col_main:
    # Navigation sub-menu
    c1, c2, c3 = st.columns(3)
    if c1.button("Search Records"): st.switch_page("pages/12_Clinical_Search.py")
    if c2.button("Prescribe / Manage Meds"): st.switch_page("pages/13_Prescribe.py")
    if c3.button("Request Extended Access"): st.switch_page("pages/14_Extended_Access.py")
    
    st.divider()
    st.subheader("Clinical Timeline")
    
    # In-scope record
    record_card({
        "date_ist": "10-Oct-2026 14:30 IST",
        "doctor": "Dr. S. Patil",
        "specialty": "Cardiology",
        "facility": "City General",
        "provenance": "VERIFIED",
        "source_text": "Provider-attested",
        "diagnoses": ["Hypertension"],
        "medications": [{"name": "Lisinopril", "dose": "10mg", "freq": "OD", "route": "Oral", "duration": "Ongoing"}],
        "has_attachment": False
    })
    
    # Out of scope blurred record
    st.markdown("""
    <div style='filter: blur(4px); pointer-events: none; opacity: 0.6; border: 1px solid #ccc; padding: 15px; border-radius: 8px; margin-top: 10px;'>
        <p><b>05-Sep-2026</b> | Unknown Facility</p>
        <p>Out of scope diagnosis</p>
        <p>Out of scope medication</p>
    </div>
    <div style='text-align: center; margin-top: -60px; z-index: 10; position: relative;'>
        <span style='background: white; padding: 5px 10px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
        🔒 No consent for this record type. 3 records hidden. <a href='#'>Request access</a>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    # Self-reported record
    st.write("")
    st.write("")
    record_card({
        "date_ist": "15-Aug-2026 10:15 IST",
        "doctor": "Self-Reported",
        "specialty": "N/A",
        "facility": "Home Upload",
        "provenance": "UNVERIFIED",
        "source_text": "Self-reported",
        "diagnoses": [],
        "medications": [{"name": "Ibuprofen", "dose": "400mg", "freq": "SOS", "route": "Oral", "duration": "3 days"}],
        "has_attachment": True
    })
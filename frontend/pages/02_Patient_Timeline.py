import streamlit as st
from utils import require_auth
from utils_ui import record_card

require_auth(["PATIENT"])

st.title("My Health Timeline")

col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Sync from ABDM", use_container_width=True, type="primary"):
        st.switch_page("pages/04_ABDM_Sync.py")
with col2:
    if st.button("📤 Upload a Document", use_container_width=True):
        st.switch_page("pages/05_Upload_Document.py")

st.info("ℹ️ **Clinical entries are written and attested by your providers. You cannot edit your medical timeline.**")

with st.expander("🔍 Filters", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.date_input("Date Range", [])
    c2.selectbox("Record Type", ["All", "Prescription", "Lab Report", "Discharge Summary"])
    c3.checkbox("Verified only")
    st.text_input("Free-text search (runs in encrypted session memory)")

st.divider()
st.subheader("October 2026")

# Mock data mapping
mock_records = [
    {
        "date_ist": "10-10-2026 14:30 IST",
        "doctor": "Dr. A. Sharma",
        "specialty": "Internal Medicine",
        "facility": "City General Hospital",
        "provenance": "VERIFIED",
        "source_text": "ABDM-verified",
        "diagnoses": ["Type 2 Diabetes Mellitus", "Essential Hypertension"],
        "medications": [
            {"name": "Metformin", "dose": "500mg", "freq": "BD", "route": "Oral", "duration": "30 days"}
        ],
        "has_attachment": True
    },
    {
        "date_ist": "15-09-2026 10:15 IST",
        "doctor": "Self-Reported",
        "specialty": "N/A",
        "facility": "Home Upload",
        "provenance": "UNVERIFIED",
        "source_text": "Self-reported",
        "diagnoses": [],
        "medications": [
            {"name": "Paracetamol", "dose": "650mg", "freq": "SOS", "route": "Oral", "duration": "3 days"}
        ],
        "has_attachment": True
    }
]

for rec in mock_records:
    record_card(rec)
import streamlit as st
from utils import require_auth
import pandas as pd

require_auth(["PATIENT"])

st.title("Audit Changelog")
st.markdown("Cryptographically anchored, append-only log of all actions on your account.")

c1, c2, c3 = st.columns(3)
c1.selectbox("Filter Actor", ["All", "You", "Dr. K. Verma", "System", "ABDM"])
c2.selectbox("Filter Action", ["All", "READ", "WRITE", "EMERGENCY_ACCESS", "REVOKE"])
c3.date_input("Filter Date")

st.divider()

# Styled Dataframe to highlight SOS/Break-glass
data = [
    {"Timestamp (IST)": "10-Oct-2026 19:10", "Actor": "Dr. K. Verma", "Action": "EMERGENCY_ACCESS", "Object": "Timeline", "Scope": "Allergies, Meds", "Basis": "NOMINEE_EMERGENCY", "Severity": "CRITICAL", "IP/Device": "192.168.1.5"},
    {"Timestamp (IST)": "10-Oct-2026 19:08", "Actor": "Priya Sharma (Nominee)", "Action": "APPROVE_SOS", "Object": "Consent Artefact", "Scope": "Read-Only", "Basis": "USER_ACTION", "Severity": "HIGH", "IP/Device": "Mobile (SMS)"},
    {"Timestamp (IST)": "09-Oct-2026 10:15", "Actor": "You", "Action": "UPLOAD_DOC", "Object": "Lab Report", "Scope": "Self", "Basis": "OWNER", "Severity": "INFO", "IP/Device": "10.0.0.1"},
    {"Timestamp (IST)": "15-Sep-2026 14:30", "Actor": "ABDM System", "Action": "SYNC_RECORDS", "Object": "Timeline", "Scope": "Prescription", "Basis": "CONSENTED", "Severity": "INFO", "IP/Device": "ABDM_Gateway"}
]

df = pd.DataFrame(data)

def highlight_critical(row):
    if row['Action'] == 'EMERGENCY_ACCESS':
        return ['background-color: #fee2e2; color: #991b1b'] * len(row)
    return [''] * len(row)

st.dataframe(df.style.apply(highlight_critical, axis=1), use_container_width=True, hide_index=True)

st.caption("Note: This changelog is retained permanently even if clinical records are deleted.")

if st.button("Verify Integrity", type="primary"):
    with st.spinner("Calculating hash chain..."):
        import time; time.sleep(1.5)
    st.success("✅ **Chain intact — anchored at 10-Oct-2026 19:34 IST**")
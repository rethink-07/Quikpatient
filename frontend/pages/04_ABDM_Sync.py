import streamlit as st
import time
from utils import require_auth

require_auth(["PATIENT"])

st.title("Sync from ABDM")

# Stepper State
if "sync_step" not in st.session_state:
    st.session_state.sync_step = 1

if st.session_state.sync_step == 1:
    st.subheader("Step 1: Authenticate")
    st.text_input("ABHA ID")
    if st.button("Send OTP"):
        st.session_state.sync_step = 2
        st.rerun()

elif st.session_state.sync_step == 2:
    st.subheader("Step 2: Choose Scope")
    st.text_input("Enter OTP")
    st.multiselect("Record Types", ["Prescription", "DiagnosticReport", "OPConsultation", "DischargeSummary"], default=["Prescription"])
    if st.button("Request Consent"):
        st.session_state.sync_step = 3
        st.session_state.sync_job_start = time.time()
        st.rerun()

elif st.session_state.sync_step == 3:
    st.subheader("Step 3: Approve in ABHA App")
    st.info("Consent request sent. Please open your ABHA app and approve the request.")
    
    @st.fragment(run_every="2s")
    def poll_consent():
        elapsed = time.time() - st.session_state.sync_job_start
        if elapsed < 4:
            st.warning("Status: ⏳ REQUESTED - Waiting for user...")
        elif elapsed < 8:
            st.success("Status: ✅ GRANTED - Fetching records...")
            with st.spinner("Decrypting payload..."):
                time.sleep(1)
            st.session_state.sync_step = 4
            st.rerun()
            
    poll_consent()

elif st.session_state.sync_step == 4:
    st.success("Sync Complete!")
    st.markdown("### **12 new verified records added, 2 merged with existing self-reported entries.**")
    st.button("[Review merges]")
    if st.button("Return to Timeline"):
        st.session_state.sync_step = 1
        st.switch_page("pages/02_Patient_Timeline.py")

st.divider()
st.subheader("Active Consents")
st.markdown("""
| Artefact ID | Scope | Expiry | Action |
|-------------|-------|--------|--------|
| `REQ-9012`  | Prescription | 2026-12-31 | [Revoke] |
""")
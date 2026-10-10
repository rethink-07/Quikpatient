import streamlit as st
import time
from utils import require_auth

require_auth(["DOCTOR"])

st.title("🚨 Emergency SOS Wizard")

if "sos_step" not in st.session_state:
    st.session_state.sos_step = 1

st.markdown("**Facility Context:** Trauma Center, City Hospital (NMC-5544)")
st.info("⚠️ **Your SOS rights are active.** Limit: 5 per month. Misuse is auditable and reportable.")

if st.session_state.sos_step == 1:
    st.subheader("Step 1: Identify Patient & Declare Reason")
    c1, c2 = st.columns(2)
    c1.text_input("ABHA ID / Phone / Patient ID")
    c2.selectbox("Second Signal", ["ABHA QR Scan", "Demographic Match", "Biometric (if available)"])
    
    st.selectbox("MANDATORY Reason", ["Unconscious", "Trauma", "Altered Mental Status", "Cannot Consent", "Other"])
    st.text_area("Clinical Detail (Required)", help="Explain why consent cannot be obtained.")
    
    if st.button("Identify Patient"):
        st.session_state.sos_step = 2
        st.rerun()

elif st.session_state.sos_step == 2:
    st.subheader("Step 2: Identity Confidence")
    st.markdown("### Candidate Found: A**** S*****, 47/M, B+")
    st.progress(95, text="Confidence Score: 95% (Demographic Match)")
    
    st.warning("The patient will be notified immediately on all channels. Misuse is auditable and reportable.")
    confirm = st.checkbox("I confirm this is the correct patient and an emergency exists.")
    
    if st.button("Request Nominee Approval", type="primary", disabled=not confirm):
        st.session_state.sos_step = 3
        st.session_state.sos_start_time = time.time()
        st.rerun()

elif st.session_state.sos_step == 3:
    st.subheader("Step 3: Notifying Nominees")
    
    @st.fragment(run_every="2s")
    def poll_nominees():
        elapsed = time.time() - st.session_state.sos_start_time
        countdown = max(0, 60 - int(elapsed))
        st.metric("Timeout Countdown (Server-driven)", f"{countdown}s")
        
        st.markdown("- **Nominee 1 (Spouse):** +91-98765***** | 📱 SMS | " + ("🟢 Approved" if elapsed > 4 else "🟡 Delivered"))
        st.markdown("- **Nominee 2 (Son):** +91-91234***** | 🔔 Push | " + ("🟡 Sent" if elapsed < 8 else "🔴 No Response"))
        
        if elapsed > 4: # Simulated approval
            st.success("Access Approved by Nominee 1!")
            time.sleep(1.5)
            st.session_state.sos_step = 4
            st.rerun()
        elif countdown == 0:
            st.error("Timeout reached. Failing over to Break-glass minimum set.")
            time.sleep(1.5)
            st.session_state.sos_step = 4
            st.session_state.sos_timeout = True
            st.rerun()
            
    poll_nominees()

elif st.session_state.sos_step == 4:
    if st.session_state.get("sos_timeout"):
        st.error("🚨 BREAK-GLASS MINIMUM SET")
        st.caption("Fully audited and reported to the patient. Server Shamir share utilized.")
        st.markdown("**Name:** Aarav Sharma | **Age/Sex:** 47/M | **Blood Group:** B+")
        st.markdown("**Allergies:** Penicillin (CRITICAL)")
        st.markdown("**Active Meds:** Metformin 500mg, Lisinopril 10mg")
    else:
        st.success("Nominee Approved! Entering Emergency Read-Only View.")
        if st.button("Enter Chart ->"):
            st.session_state.current_patient = "Aarav Sharma"
            st.session_state.access_mode = "EMERGENCY"
            st.switch_page("pages/11_Patient_View.py")
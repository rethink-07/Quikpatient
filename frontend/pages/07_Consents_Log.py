import streamlit as st
from utils import require_auth
from datetime import datetime

require_auth(["PATIENT"])

st.title("Consents & Access Log")

tab_active, tab_pending, tab_sos = st.tabs(["Active Grants", "Pending Requests", "🚨 Emergency SOS Log"])

with tab_active:
    st.subheader("Active Doctor Access")
    with st.container(border=True):
        st.markdown("### Dr. S. Patil | City Hospital")
        st.markdown("**Scope:** `Prescription`, `Lab Report`")
        st.markdown("**Valid for:** 01-Jan-2026 to 31-Dec-2026")
        st.caption("Expires in: 82 days (31-Dec-2026 IST)")
        
        c1, c2 = st.columns(2)
        c1.button("Revoke Access", key="rev_patil")
        
        # Hard Revoke with confirmation logic
        if "confirm_hard_revoke" not in st.session_state:
            st.session_state.confirm_hard_revoke = False
            
        if c2.button("Hard revoke (rotate keys)", type="primary"):
            st.session_state.confirm_hard_revoke = True
            
        if st.session_state.confirm_hard_revoke:
            st.error("⚠️ **Warning:** Hard revocation rotates your master keys. It re-encrypts all records and kills ALL previously shared keys for ALL doctors instantly. Proceed?")
            if st.button("Confirm Hard Revoke (Irreversible)"):
                st.session_state.confirm_hard_revoke = False
                st.success("Keys rotated. All external access severed.")
                st.rerun()

with tab_pending:
    st.subheader("Pending Access Requests")
    with st.container(border=True):
        st.markdown("### Dr. M. Gupta | Apollo Clinic")
        st.markdown("**Requested Scope:** `Discharge Summary`")
        st.markdown("**Date Interval:** 01-Oct-2026 to 10-Oct-2026")
        st.markdown("**Clinical Reason:** Post-op review")
        
        c1, c2 = st.columns(2)
        c1.button("Approve", type="primary", use_container_width=True)
        with c2.popover("Deny", use_container_width=True):
            st.text_input("Reason for denial (Optional)")
            st.button("Confirm Deny")

with tab_sos:
    st.subheader("Emergency Access Log")
    st.info("Showing 'Break-glass' and Nominee-approved emergencies. Doctors abusing this system can be suspended.")
    
    with st.container(border=True):
        st.markdown("<h3 style='color: #dc2626;'>🚨 ACTIVE EMERGENCY ACCESS</h3>", unsafe_allow_html=True)
        st.markdown("**Requesting Doctor:** Dr. K. Verma (NMC-5544) | Trauma Center")
        st.markdown("**Timestamp:** 10-Oct-2026 19:10 IST")
        st.markdown("**Declared Reason:** Unconscious (RTA)")
        st.markdown("**Legal Basis:** `NOMINEE_EMERGENCY`")
        st.markdown("**Approving Nominee:** Priya Sharma (Spouse)")
        st.markdown("**Scope Viewed:** Allergies, Active Medications, Blood Group")
        st.markdown("**Expiry:** 10-Oct-2026 21:10 IST (in 1hr 34mins)")
        
        c1, c2 = st.columns(2)
        c1.button("Terminate emergency access now", type="primary")
        with c2.popover("Report this access"):
            st.warning("If this emergency access was fraudulent, file an abuse report. Reported doctors can have SOS rights suspended pending an audit.")
            st.text_area("Details")
            st.button("Submit Abuse Report")
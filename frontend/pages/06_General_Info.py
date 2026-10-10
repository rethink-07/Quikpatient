import streamlit as st
from utils import require_auth
from datetime import datetime

require_auth(["PATIENT"])

st.title("General Info & Nominees")

# Simulated New Encounter Prompt Modal
if st.session_state.get("new_encounter_flag", True):
    with st.container(border=True):
        st.info("🔔 **A new visit was recorded today.** Review your general information to ensure it's up to date?")
        c1, c2 = st.columns(2)
        if c1.button("Update now", use_container_width=True):
            st.session_state.new_encounter_flag = False
            st.rerun()
        if c2.button("Keep existing", use_container_width=True):
            st.session_state.new_encounter_flag = False
            st.toast("Choice audited. No updates made.")
            st.rerun()

st.subheader("Personal Information")
st.caption("Last updated: 3 months ago")

with st.form("gen_info"):
    c1, c2 = st.columns(2)
    c1.text_input("Full Name", value="Aarav Sharma")
    c2.text_input("Blood Group", value="B+", disabled=True, help="Must be verified by a lab to change.")
    
    st.text_area("Chronic Conditions", value="Type 2 Diabetes Mellitus\nEssential Hypertension")
    
    if st.form_submit_button("Save Information", type="primary"):
        st.success("Information updated and audited.")

st.divider()

st.subheader("Emergency Nominees")
st.info("Nominees can approve 'break-glass' emergency access for doctors when you cannot consent.")

# Nominee Card 1
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**1. Priya Sharma (Spouse)**")
        st.markdown("📱 +91-98765XXXXX | 🟢 *Last SMS delivered OK (01-Oct-2026)*")
        st.toggle("May approve emergency read-only access", value=True, key="nom_1_toggle")
    with col2:
        st.button("Remove", key="rem_1")
        st.button("Move Down ⬇️", key="dn_1")

# Nominee Card 2
with st.container(border=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**2. Rahul Sharma (Son)**")
        st.markdown("📱 +91-91234XXXXX | 🟡 *Delivery unconfirmed*")
        st.toggle("May approve emergency read-only access", value=True, key="nom_2_toggle")
    with col2:
        st.button("Remove", key="rem_2")
        st.button("Move Up ⬆️", key="up_2")

with st.expander("➕ Add New Nominee"):
    st.text_input("Name")
    st.text_input("Phone Number")
    st.button("Send OTP to Confirm Nominee")

st.divider()
st.subheader("Guardian & Minor Controls")
st.warning("🔒 **Guardian (not available in this prototype)**\nThe backend requires specific verified legal mapping via ABDM to enable guardian workflows. This interface is currently disabled.")
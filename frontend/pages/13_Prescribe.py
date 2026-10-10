import streamlit as st
from utils import require_auth, enforce_readonly

require_auth(["DOCTOR"])

st.title("Prescribe & Manage Medications")

# Guard against Emergency Read-Only writes
if enforce_readonly():
    st.stop()

st.info("Note: Pushing prescriptions back to ABDM (HIP role) is currently on the roadmap. Saves are local to the QuikPatient ledger.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("New Prescription")
    with st.form("rx_form"):
        med = st.selectbox("Medicine (Autocomplete)", ["Metformin", "Penicillin V", "Ibuprofen", "Amoxicillin"])
        c1, c2, c3 = st.columns(3)
        dose = c1.text_input("Dose", "500mg")
        freq = c2.text_input("Freq", "BD")
        route = c3.text_input("Route", "Oral")
        dur = st.text_input("Duration / Start Date", "30 days, starting today")
        linked_dx = st.text_input("Linked Diagnosis", "Type 2 Diabetes")
        notes = st.text_area("Clinical Notes")
        
        # Warning Engine Simulation
        if med == "Penicillin V":
            st.error("🚨 **ALLERGY CONFLICT:** Patient has a known Penicillin allergy.")
            override_reason = st.text_input("ALLERGY OVERRIDE: Typed clinical justification required")
            st.caption("This override will be logged and shown to the patient.")
        
        submit = st.form_submit_button("Sign & Save Prescription (VERIFIED)", type="primary")
        if submit:
            if med == "Penicillin V" and not override_reason:
                st.error("Cannot prescribe: Override justification missing.")
            else:
                st.success("Prescription signed and anchored to ledger.")

with col2:
    st.subheader("Active & Unverified Medications")
    
    st.markdown("#### Unverified (Self-Reported)")
    with st.container(border=True):
        st.warning("⚠️ **Ibuprofen 400mg SOS** (Self-reported)")
        st.caption("Excluded from warning engine until confirmed.")
        if st.toggle("I have confirmed this medication with the patient"):
            st.success("Added to warning engine. Status -> Corroborated.")

    st.markdown("#### Provider-Attested")
    with st.container(border=True):
        st.markdown("🛡️ **Lisinopril 10mg OD**")
        st.caption("Started 10-Oct-2026")
        c1, c2 = st.columns(2)
        with c1.popover("Modify"):
            st.text_input("New Dose/Freq")
            st.text_input("Reason")
            st.button("Amend")
        with c2.popover("Stop"):
            st.text_input("Reason for stopping")
            st.button("Stop Medication", type="primary")
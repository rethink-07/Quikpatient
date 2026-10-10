import streamlit as st
from utils import require_auth

require_auth(["DOCTOR"])

st.title("Request Extended Access")

with st.form("req_ext"):
    st.date_input("Date Interval Needed", [])
    st.multiselect("Record Types", ["Discharge Summary", "DiagnosticReport", "Immunization"])
    st.text_input("Clinical Reason (Visible to Patient)")
    st.selectbox("Requested Duration", ["24 Hours", "7 Days", "30 Days", "1 Year"])
    if st.form_submit_button("Submit Request"):
        st.success("Request sent to patient for approval.")
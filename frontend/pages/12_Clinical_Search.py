import streamlit as st
from utils import require_auth

require_auth(["DOCTOR"])

st.title("Clinical Search")

st.markdown("Try: `liver history`, `HbA1c trend`, `all antibiotics prescribed`")
query = st.text_input("Search terms", "HbA1c trend")

if query:
    st.markdown("### Results for 'HbA1c trend'")
    st.caption("Matches highlighted. Showing 2 in-scope hits. 1 out-of-scope hit hidden.")
    
    with st.container(border=True):
        st.markdown("**Endocrinology (Grouped)**")
        st.markdown("- **10-Sep-2026**: Lab Report - <mark>HbA1c</mark>: 7.2%", unsafe_allow_html=True)
        st.markdown("- **15-Jun-2026**: Lab Report - <mark>HbA1c</mark>: 7.5%", unsafe_allow_html=True)
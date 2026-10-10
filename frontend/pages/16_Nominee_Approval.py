import streamlit as st

st.set_page_config(page_title="Emergency Request", layout="centered")

st.markdown("<h2 style='text-align: center; color: #dc2626;'>🚨 URGENT: EMERGENCY ACCESS REQUEST</h2>", unsafe_allow_html=True)

st.warning("""
**Dr. K. Verma (Trauma Center)** is requesting immediate emergency access to **Aarav Sharma's** medical records. 
Reason given: **Unconscious (RTA)**.
""")

st.info("You are registered as a Nominee for Aarav Sharma. You hold a cryptographic share required to unlock these records.")

otp = st.text_input("Enter the OTP sent to your phone to cryptographically sign this approval", type="password")

c1, c2 = st.columns(2)
if c1.button("DENY ACCESS", type="secondary", use_container_width=True):
    st.success("Access securely denied. The doctor will only see the break-glass minimum set.")
if c2.button("APPROVE EMERGENCY ACCESS", type="primary", use_container_width=True):
    if otp == "123456":
        st.success("✅ Your Share Submitted. The server is combining keys. Access granted for 2 hours.")
    else:
        st.error("Invalid OTP.")
import streamlit as st

st.title("⚕️ QuikPatient")
st.markdown("### Patient owns, provider attests, nominee unlocks in emergencies.")

st.markdown("""
- **Unified verified timeline:** See your entire medical history in one place.
- **Encrypted consent-based sharing:** You decide which doctors see what data.
- **Emergency SOS via nominee:** Safe, break-glass access when you need it most.
""")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**1. Claim ABHA**\nSync your official health records securely.")
with col2:
    st.info("**2. Add Nominees**\nAssign trusted family for emergency unlock.")
with col3:
    st.success("**3. Take Control**\nShare instantly with a zero-knowledge architecture.")

st.divider()
c1, c2 = st.columns(2)
with c1:
    if st.button("Patient Login / Register", use_container_width=True, type="primary"):
        st.switch_page("pages/01_Auth.py")
with c2:
    if st.button("Doctor / Clinical Login", use_container_width=True):
        st.switch_page("pages/01_Auth.py")

st.markdown("---")
st.markdown(
    "<small>Simulated / ABDM-sandbox data. Not a medical device. Not for clinical use. "
    "[Trust Model](/security) | [Privacy & Security](/security)</small>", 
    unsafe_allow_html=True
)
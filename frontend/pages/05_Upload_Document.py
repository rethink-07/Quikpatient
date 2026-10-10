import streamlit as st
import time
from utils import require_auth

require_auth(["PATIENT"])

st.title("Upload a Document")
st.info("Documents uploaded here are marked as **Self-reported** until a provider corroborates them.")

doc_file = st.file_uploader("Upload PDF/JPG/PNG", type=["pdf", "jpg", "png"])
cam_file = st.camera_input("Or take a photo of your record")

if (doc_file or cam_file) and "ocr_done" not in st.session_state:
    with st.spinner("Running encrypted OCR in session..."):
        time.sleep(2) # simulate job
        st.session_state.ocr_done = True
        st.rerun()

if st.session_state.get("ocr_done"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Document Preview")
        st.caption("Rendering in-memory...")
        st.image("https://via.placeholder.com/400x500.png?text=Prescription+Scan", use_column_width=True)
    
    with col2:
        st.markdown("### Review Extracted Data")
        doc_type = st.selectbox("Document Type", ["Prescription", "Lab Report", "Discharge Summary"])
        doc_date = st.date_input("Date")
        
        doc_name = st.text_input("Doctor Name", "Dr. S. Patil")
        st.markdown("✅ *Matches a registered practitioner (NMC-8821)*") # NEVER says "verified"
        
        st.markdown("#### Medications Found")
        with st.container(border=True):
            st.text_input("Medicine Name", "Telmisartan")
            st.markdown("✅ *Matched in dictionary*")
            
            dose = st.text_input("Dose", "40mg")
            st.warning("⚠️ Low OCR confidence on Dose.")
            dose_check = st.checkbox("I checked this number against my prescription — a wrong dose is dangerous.")
            
            freq = st.text_input("Frequency", "OD")
            
        if st.button("Save to Timeline", type="primary", disabled=not dose_check):
            st.session_state.show_unverified_banner = True
            del st.session_state.ocr_done
            st.rerun()

if st.session_state.get("show_unverified_banner"):
    st.warning("⚠️ Unverified — added by you from a document. Clinicians will see this is self-reported.", icon="⚠️")
    if st.button("Go to Timeline"):
        st.session_state.show_unverified_banner = False
        st.switch_page("pages/02_Patient_Timeline.py")
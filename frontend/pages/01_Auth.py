import streamlit as st
import api
from utils import init_session

init_session()

st.title("Portal Access")

tab_pat, tab_doc, tab_reg = st.tabs(["Patient Login", "Doctor Login", "Patient Registration"])

with tab_pat:
    st.subheader("Patient Login")
    with st.form("pat_login"):
        user_id = st.text_input("ABHA ID or Patient ID")
        pwd = st.text_input("Password", type="password")
        pph = st.text_input("Decryption Passphrase", type="password", help="Used only in this session to unlock your records.")
        totp = st.text_input("TOTP (Authenticator App)")
        
        if st.form_submit_button("Login", type="primary"):
            if user_id and pwd and pph:
                res = api.login(user_id, pwd, "PATIENT")
                if res:
                    st.session_state.update(res)
                    # Simulated crypto boundary: derive master key in session
                    st.session_state.mk = b"simulated_derived_key_bytes" 
                    st.success("Logged in securely.")
                    st.switch_page("pages/02_Patient_Timeline.py")
            else:
                st.error("All fields are required.")
    st.caption("[Forgot password?] | [Lost passphrase? Use recovery code]")

with tab_doc:
    st.subheader("Doctor Login")
    # Using fragments to handle NMC verify without refreshing the whole page
    @st.fragment
    def doc_auth_fragment():
        doc_uid = st.text_input("User ID", key="doc_uid")
        doc_pwd = st.text_input("Password", type="password", key="doc_pwd")
        doc_nmc = st.text_input("Doctor ID (NMC Registration)", help="e.g., NMC-12345", key="doc_nmc")
        
        # Inline verification state
        is_verified = False
        if doc_nmc:
            with st.spinner("Verifying with NMC/HPR…"):
                ver = api.verify_doctor_nmc(doc_nmc)
                if ver["status"] == "verified":
                    st.success(f"Verified — {ver['name']}, {ver['council']}, Reg {doc_nmc}, valid till {ver['valid_till']}")
                    is_verified = True
                else:
                    st.error("Not found in register")
        
        doc_totp = st.text_input("TOTP", disabled=not is_verified)
        if st.button("Doctor Login", disabled=not is_verified, type="primary"):
            res = api.login(doc_uid, doc_pwd, "DOCTOR")
            if res:
                st.session_state.update(res)
                st.success("Logged in successfully.")
                st.switch_page("pages/09_Doctor_Dashboard.py")
    doc_auth_fragment()

with tab_reg:
    st.subheader("New Patient Registration")
    
    guard_check = st.checkbox("I am registering as a Guardian or on behalf of a minor.")
    if guard_check:
        st.error("Guardian and minor flows are not implemented in this prototype. Backend returns 403.")
    else:
        st.markdown("##### Step 1: General Info")
        name = st.text_input("Full Name")
        c1, c2, c3 = st.columns(3)
        dob = c1.date_input("DOB")
        sex = c2.selectbox("Sex", ["Male", "Female", "Other"])
        bg = c3.selectbox("Blood Group", ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"])
        
        allergies = st.multiselect("Known Allergies", ["Penicillin", "Peanuts", "Sulfa Drugs", "Latex", "None"])
        
        st.markdown("##### Step 2: Nominees (Emergency SOS)")
        st.info("Nominees must be registered now — they cannot be added during an emergency.")
        nom_name = st.text_input("Nominee Name")
        nom_rel = st.selectbox("Relationship", ["Spouse", "Child", "Parent", "Sibling", "Friend"])
        nom_phone = st.text_input("Phone Number")
        nom_approve = st.toggle("May approve emergency read-only access", value=True)
        
        st.markdown("##### Step 3: Security & Passphrase")
        reg_pwd = st.text_input("Account Password", type="password")
        reg_pph = st.text_input("Decryption Passphrase", type="password", help="This encrypts your records.")
        st.progress(60, text="Passphrase Strength: Fair")
        
        st.warning("⚠️ If you lose both your passphrase and recovery code, nobody — including us — can recover your encrypted records.")
        saved_code = st.checkbox("I have saved my 12-word recovery code securely.")
        print_card = st.checkbox("Generate emergency printable QR card")
        
        if st.button("Register Patient Profile", type="primary", disabled=not saved_code):
            st.success("Profile created! Please log in.")
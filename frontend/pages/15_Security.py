import streamlit as st
from utils import apply_text_scale

apply_text_scale()

st.title("Privacy & Security Architecture")
st.markdown("### How QuikPatient protects your data without locking it away during emergencies.")

st.markdown("""
### 1. The Encryption Chain
We use a zero-knowledge architecture. The server stores your data, but cannot read it.
*   **Your Passphrase** passes through **Argon2id** (a slow hashing function) to derive your **Master Key**.
*   The Master Key decrypts individual **Per-Record Keys**.
*   When you share a record with a doctor, the Per-Record Key is sealed to the **Doctor's Public Key**.
*   *Limitation:* Because the cryptography runs entirely in your browser/Streamlit session, this is a **trusted session boundary, not true end-to-end encryption (E2E).**
""")

st.info("⚠️ **Warning:** If you lose both your passphrase and your 12-word recovery code, your records are completely unrecoverable. We cannot reset it for you.")

st.markdown("""
### 2. The Emergency "Break-Glass" Path
When a doctor declares a medical emergency and you are unconscious, they need access without your passphrase. We use **Shamir's Secret Sharing (2-of-3)**:
1.  **Server Share:** Held by our servers.
2.  **Nominee Share:** Held cryptographically by your registered nominees.
3.  **Printed Card Share:** Embedded in your printable emergency QR card.

*How it works:* The doctor requests access. The server notifies your nominees via SMS/Push. If a nominee approves, their share + the server share combine to unlock a short-lived, **read-only** view of your records. 
*Note:* This is **nominee-mediated disclosure, not patient consent.** The server holding a share is a deliberate availability-versus-secrecy trade-off to save lives.
""")

st.warning("📱 **A note on SMS:** SMS is a weak, unencrypted channel. We strictly enforce that **no Protected Health Information (PHI) is ever sent in a message body.**")

st.markdown("""
### 3. Audit & Governance
*   **Search Limitations:** While records are encrypted, searching metadata (like tags or dates) reveals query repetition patterns to the server.
*   **Compliance:** This system aligns with HIPAA safeguards, the **DPDP Act 2023** (India), and the **ABDM Health Data Management (HDM) Policy**.
*   **Append-only:** Every read, write, and emergency unlock is written to an immutable changelog visible to the patient.
""")
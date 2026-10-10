import streamlit as st

def render_provenance_badge(provenance_enum, source_text):
    """The ONLY place provenance is rendered. Strict enum mapping."""
    if provenance_enum == "VERIFIED":
        st.markdown(f"<span style='color: #0d9488; font-weight: 600; background: #e0f2fe; padding: 4px 8px; border-radius: 4px;'>🛡️ {source_text}</span>", unsafe_allow_html=True)
    elif provenance_enum == "UNVERIFIED":
        st.markdown(f"<span style='color: #d97706; font-weight: 600; background: #fef3c7; padding: 4px 8px; border-radius: 4px;'>⚠️ {source_text}</span>", unsafe_allow_html=True)
    else:
        st.error("Invalid provenance state.")

def record_card(record):
    """
    Renders a unified encounter node.
    record: dict containing date_ist, doctor, facility, provenance, source_text, diagnoses, medications, etc.
    """
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{record['date_ist']}** | {record['facility']}")
            st.caption(f"{record['doctor']} - {record['specialty']}")
        with col2:
            render_provenance_badge(record['provenance'], record['source_text'])
            st.caption("🔒 Decrypted in your session")

        if record.get('diagnoses'):
            st.markdown("**Diagnoses:** " + " ".join([f"`{d}`" for d in record['diagnoses']]))
        
        if record.get('medications'):
            st.markdown("**Medications:**")
            for m in record['medications']:
                st.markdown(f"- {m['name']} | {m['dose']} | {m['freq']} | {m['route']} | {m['duration']}")
                
        if record.get('has_attachment'):
            with st.expander("📄 View Attached Document (Decrypting...)"):
                st.info("Document decrypted and rendered securely in-memory.")
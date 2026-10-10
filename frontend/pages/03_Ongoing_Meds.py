import streamlit as st
import plotly.graph_objects as go
from utils import require_auth
from datetime import datetime

require_auth(["PATIENT", "DOCTOR"])

st.title("Ongoing Medications & Treatments")

# In a real app, dates are parsed from backend IST strings.
fig = go.Figure()

# Verified Medication (Solid Teal)
fig.add_trace(go.Bar(
    y=["Metformin 500mg BD"],
    x=[30], # duration in days for mock
    base=["2026-09-10"], # start date
    orientation='h',
    marker=dict(color="#0d9488"),
    name="Provider-attested"
))

# Unverified Medication (Amber Hatched)
fig.add_trace(go.Bar(
    y=["Ayurvedic Supplement"],
    x=[60],
    base=["2026-08-15"],
    orientation='h',
    marker=dict(color="#fef3c7", pattern_shape="/", line_color="#d97706", line_width=2),
    name="Self-reported"
))

# Plot Formatting
fig.update_layout(
    barmode='overlay',
    title="Active Prescriptions (Arrow indicates ongoing)",
    xaxis_type='date',
    yaxis=dict(autorange="reversed"),
    height=300,
    margin=dict(l=20, r=20, t=40, b=20)
)
# TODAY Marker
fig.add_vline(x="2026-10-10", line_width=2, line_dash="dash", line_color="red", annotation_text="TODAY")

st.plotly_chart(fig, use_container_width=True)

st.error("⚠️ Conflict detected: 'Ibuprofen' (Self-reported) interacts with your active 'Lisinopril'. Discuss with your provider.")

with st.expander("Stopped / Completed Medications"):
    st.markdown("- **Amoxicillin 500mg TDS** — Stopped on 05-09-2026 by Dr. A. Sharma (Course completed)")
    st.markdown("  - *Amendment Chain: Original Rx (01-09-2026) -> Stopped (05-09-2026)*")
import json
import os
from urllib.error import URLError
from urllib.request import urlopen

import streamlit as st

st.set_page_config(page_title="QuikPatient Operations", page_icon=None, layout="centered")
st.title("QuikPatient service status")
st.caption("Operational status only. This page does not display patient information.")

health_url = os.getenv("API_HEALTH_URL", "http://127.0.0.1:8080/api/healthz")
try:
    with urlopen(health_url, timeout=3) as response:
        payload = json.loads(response.read())
    st.success(f"API: {payload.get('status', 'unknown')}")
    st.write(
        {
            "mode": payload.get("mode"),
            "database": payload.get("database"),
            "worker": payload.get("worker"),
        }
    )
except (URLError, TimeoutError, ValueError):
    st.error("API health check is unavailable.")

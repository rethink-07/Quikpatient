import streamlit as st
import time

# --- Exception Classes for Error Mapping ---
class QuikPatientAPIError(Exception): pass
class APIUnauthorized(QuikPatientAPIError): pass      # 401
class APIForbidden(QuikPatientAPIError): pass         # 403
class APIConflict(QuikPatientAPIError): pass          # 409
class APILocked(QuikPatientAPIError): pass            # 423
class APIRateLimit(QuikPatientAPIError): pass         # 429

def handle_api_errors(func):
    """Decorator to map HTTP-like exceptions to UI state securely without PHI."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIUnauthorized:
            st.session_state.user_id = None
            st.error("Session expired. Please log in again.")
            st.stop()
        except APIForbidden:
            st.error("🔒 Outside your consent scope. [Request access]")
            st.stop()
        except APIConflict:
            st.warning("This record was superseded — please refresh.")
        except APILocked:
            st.warning("🔒 Locked — enter encounter key to view.")
        except APIRateLimit:
            st.error("Rate-limit reached. Please wait 60 seconds and try again.")
    return wrapper

@handle_api_errors
def verify_doctor_nmc(doctor_id):
    """Simulates a call to /auth/doctor/verify"""
    time.sleep(0.8) # Simulate network
    if doctor_id.startswith("NMC-"):
        return {"status": "verified", "name": "Dr. A. Sharma", "council": "Delhi Medical Council", "valid_till": "2028"}
    return {"status": "not_found"}

@handle_api_errors
def login(user_id, password, role):
    # Simulated auth endpoint returning standard payload
    if password == "password123":
        return {
            "access_token": "mock_jwt_token",
            "refresh_token": "mock_refresh_token",
            "role": role,
            "user_id": user_id,
            "scope": ["read", "write"]
        }
    raise APIUnauthorized("Invalid credentials")
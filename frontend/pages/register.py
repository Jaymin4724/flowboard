import streamlit as st

from frontend.api import auth as auth_api
from frontend.api.exceptions import ApiError

_PENDING_EMAIL_KEY = "_pending_registration_email"


def render() -> None:
    st.title("Register")

    if st.session_state.get(_PENDING_EMAIL_KEY):
        _render_otp_step()
    else:
        _render_registration_step()


def _render_registration_step() -> None:
    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")

    if not submitted:
        return

    if not username or not email or not password:
        st.error("All fields are required.")
        return
    if password != confirm:
        st.error("Passwords do not match.")
        return
    if len(password) < 8:
        st.error("Password must be at least 8 characters.")
        return

    try:
        message = auth_api.register(email, username, password)
    except ApiError as exc:
        st.error(exc.message)
        return

    # The backend either emails an OTP or (if EMAIL_SERVICE_ACTIVE=false)
    # creates the account directly - only show the OTP step in the former case.
    if "OTP" in message:
        st.session_state[_PENDING_EMAIL_KEY] = email
        st.info(message)
        st.rerun()
    else:
        st.success(message)


def _render_otp_step() -> None:
    email = st.session_state[_PENDING_EMAIL_KEY]
    st.write(f"Enter the OTP sent to **{email}**.")

    with st.form("otp_form"):
        otp = st.text_input("OTP")
        submitted = st.form_submit_button("Verify")

    if st.button("Use a different email"):
        st.session_state.pop(_PENDING_EMAIL_KEY, None)
        st.rerun()

    if not submitted:
        return
    if not otp:
        st.error("Enter the OTP.")
        return

    try:
        auth_api.verify_otp(email, otp)
    except ApiError as exc:
        st.error(exc.message)
        return

    st.session_state.pop(_PENDING_EMAIL_KEY, None)
    st.success("Account verified. You can now log in.")

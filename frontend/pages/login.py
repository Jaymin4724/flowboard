import streamlit as st

from frontend.api import auth as auth_api, users as users_api
from frontend.api.exceptions import ApiError
from frontend.auth import session


def render() -> None:
    st.title("Log in")

    if session.is_authenticated():
        st.success("You're already logged in.")
        return

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if not submitted:
        return

    if not email or not password:
        st.error("Email and password are required.")
        return

    try:
        access_token, refresh_token = auth_api.login(email, password)
    except ApiError as exc:
        st.error(exc.message)
        return

    session.set_tokens(access_token, refresh_token)

    try:
        session.set_current_user(users_api.get_me())
    except ApiError:
        pass

    st.success("Logged in.")
    st.rerun()

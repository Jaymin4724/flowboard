import streamlit as st

from frontend.auth import session


def require_auth() -> None:
    if not session.is_authenticated():
        st.warning("Please log in to continue.")
        st.stop()


def require_admin() -> None:
    require_auth()
    if not session.get_is_admin():
        st.error("You don't have access to this page.")
        st.stop()

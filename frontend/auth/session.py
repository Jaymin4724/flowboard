import streamlit as st

_ACCESS = "access_token"
_REFRESH = "refresh_token"
_USER = "current_user"
_IS_ADMIN = "is_admin"


def get_access_token() -> str | None:
    return st.session_state.get(_ACCESS)


def get_refresh_token() -> str | None:
    return st.session_state.get(_REFRESH)


def set_access_token(token: str | None) -> None:
    st.session_state[_ACCESS] = token


def set_refresh_token(token: str | None) -> None:
    st.session_state[_REFRESH] = token


def set_tokens(access_token: str, refresh_token: str) -> None:
    set_access_token(access_token)
    set_refresh_token(refresh_token)


def is_authenticated() -> bool:
    return bool(get_access_token())


def get_current_user() -> dict | None:
    return st.session_state.get(_USER)


def set_current_user(user: dict | None) -> None:
    st.session_state[_USER] = user


def get_is_admin() -> bool | None:
    """None means not probed yet this session; True/False is the probed result."""
    return st.session_state.get(_IS_ADMIN)


def set_is_admin(value: bool) -> None:
    st.session_state[_IS_ADMIN] = value


def clear_session() -> None:
    for key in (_ACCESS, _REFRESH, _USER, _IS_ADMIN):
        st.session_state.pop(key, None)

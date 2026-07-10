import streamlit as st

from frontend.api import auth as auth_api, users as users_api
from frontend.api.exceptions import ApiError
from frontend.auth import session
from frontend.components.guards import require_auth


def render() -> None:
    require_auth()
    st.title("My Profile")

    try:
        user = users_api.get_me()
    except ApiError as exc:
        st.error(exc.message)
        return
    session.set_current_user(user)

    st.write(f"**Username:** {user['username']}")
    st.write(f"**Email:** {user['email']}")
    st.write(f"**Verified:** {'Yes' if user['is_verified'] else 'No'}")

    _render_photo_section(user)
    st.divider()
    _render_edit_form(user)
    st.divider()
    _render_logout_and_delete()


def _render_photo_section(user: dict) -> None:
    st.subheader("Profile photo")
    if user.get("profile_photo_key"):
        try:
            url = users_api.get_profile_photo_url(user["id"])
        except ApiError as exc:
            st.error(exc.message)
            url = None
        if url:
            st.image(url, width=150)
        if st.button("Remove photo"):
            try:
                users_api.delete_profile_photo(user["id"])
            except ApiError as exc:
                st.error(exc.message)
            else:
                st.rerun()
    else:
        st.caption("No profile photo set.")

    uploaded = st.file_uploader("Upload a new photo", type=["png", "jpg", "jpeg"])
    if uploaded is not None and st.button("Save photo"):
        try:
            users_api.upload_profile_photo(user["id"], uploaded.name, uploaded.getvalue(), uploaded.type)
        except ApiError as exc:
            st.error(exc.message)
        else:
            st.success("Photo updated.")
            st.rerun()


def _render_edit_form(user: dict) -> None:
    st.subheader("Edit profile")
    with st.form("edit_profile_form"):
        username = st.text_input("Username", value=user["username"])
        email = st.text_input("Email", value=user["email"])
        new_password = st.text_input("New password (leave blank to keep current)", type="password")
        submitted = st.form_submit_button("Save changes")

    if not submitted:
        return

    fields = {}
    if username != user["username"]:
        fields["username"] = username
    if email != user["email"]:
        fields["email"] = email
    if new_password:
        if len(new_password) < 8:
            st.error("Password must be at least 8 characters.")
            return
        fields["password"] = new_password

    if not fields:
        st.info("Nothing to update.")
        return

    try:
        users_api.update_me(**fields)
    except ApiError as exc:
        st.error(exc.message)
    else:
        st.success("Profile updated.")
        st.rerun()


def _render_logout_and_delete() -> None:
    col1, col2 = st.columns(2)
    if col1.button("Log out"):
        _logout()
        st.rerun()
    if col2.button("Deactivate my account"):
        st.session_state["_confirm_delete"] = True

    if st.session_state.get("_confirm_delete"):
        st.warning("This will deactivate your account. Are you sure?")
        c1, c2 = st.columns(2)
        if c1.button("Yes, deactivate"):
            try:
                users_api.delete_me()
            except ApiError as exc:
                st.error(exc.message)
            else:
                _logout()
                st.session_state.pop("_confirm_delete", None)
                st.rerun()
        if c2.button("Cancel"):
            st.session_state.pop("_confirm_delete", None)
            st.rerun()


def _logout() -> None:
    refresh_token = session.get_refresh_token()
    access_token = session.get_access_token()
    if refresh_token:
        try:
            auth_api.logout(refresh_token, access_token)
        except ApiError:
            pass  # best-effort: token may already be expired/blacklisted
    session.clear_session()

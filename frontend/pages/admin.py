import streamlit as st

from frontend.api import admin as admin_api
from frontend.api.exceptions import ApiError
from frontend.components.guards import require_admin
from frontend.components.item_form import render_item_form

_PAGE_SIZE = 10
_EDITING_KEY = "_admin_editing_item_id"


def render() -> None:
    require_admin()
    st.title("Admin")

    tab_items, tab_users = st.tabs(["Items", "Users"])
    with tab_items:
        _render_items_tab()
    with tab_users:
        _render_users_tab()


def _render_items_tab() -> None:
    with st.expander("Create item (as admin)"):
        result = render_item_form(key="admin_create_item_form")
        if result:
            try:
                admin_api.create_item(**result)
            except ApiError as exc:
                st.error(exc.message)
            else:
                st.success("Item created.")
                st.rerun()

    page = st.session_state.get("_admin_items_page", 1)
    try:
        items = admin_api.list_items_detailed(page=page, size=_PAGE_SIZE)
    except ApiError as exc:
        st.error(exc.message)
        return

    if not items:
        st.info("No items.")

    for item in items:
        if st.session_state.get(_EDITING_KEY) == item["id"]:
            _render_item_edit_form(item)
            continue

        with st.container(border=True):
            st.markdown(f"**{item['title']}** — {item['status']}")
            st.caption(f"Owner: {item['username']} ({item['email']})")
            cols = st.columns(2)
            if cols[0].button("Edit", key=f"admin_edit_{item['id']}"):
                st.session_state[_EDITING_KEY] = item["id"]
                st.rerun()
            if cols[1].button("Delete", key=f"admin_delete_{item['id']}"):
                try:
                    admin_api.delete_item(item["id"])
                except ApiError as exc:
                    st.error(exc.message)
                else:
                    st.rerun()

    cols = st.columns(2)
    if cols[0].button("Previous", disabled=page <= 1, key="admin_items_prev"):
        st.session_state["_admin_items_page"] = page - 1
        st.rerun()
    if cols[1].button("Next", disabled=len(items) < _PAGE_SIZE, key="admin_items_next"):
        st.session_state["_admin_items_page"] = page + 1
        st.rerun()


def _render_item_edit_form(item: dict) -> None:
    result = render_item_form(key=f"admin_edit_item_form_{item['id']}", initial=item)
    if st.button("Cancel edit", key=f"admin_cancel_edit_{item['id']}"):
        st.session_state.pop(_EDITING_KEY, None)
        st.rerun()
    if result:
        try:
            admin_api.update_item(item["id"], **result)
        except ApiError as exc:
            st.error(exc.message)
        else:
            st.session_state.pop(_EDITING_KEY, None)
            st.success("Item updated.")
            st.rerun()


def _render_users_tab() -> None:
    page = st.session_state.get("_admin_users_page", 1)
    try:
        users = admin_api.list_users(page=page, size=_PAGE_SIZE)
    except ApiError as exc:
        st.error(exc.message)
        return

    if not users:
        st.info("No users.")

    for user in users:
        with st.container(border=True):
            st.markdown(f"**{user['username']}** ({user['email']})")
            st.caption(f"Active: {user['is_active']} | Verified: {user['is_verified']}")
            cols = st.columns(2)
            if cols[0].button("Toggle verified", key=f"admin_toggle_verified_{user['id']}"):
                try:
                    admin_api.update_user(user["id"], is_verified=not user["is_verified"])
                except ApiError as exc:
                    st.error(exc.message)
                else:
                    st.rerun()
            if cols[1].button("Deactivate", key=f"admin_deactivate_{user['id']}"):
                try:
                    admin_api.deactivate_user(user["id"])
                except ApiError as exc:
                    st.error(exc.message)
                else:
                    st.rerun()

    cols = st.columns(2)
    if cols[0].button("Previous", disabled=page <= 1, key="admin_users_prev"):
        st.session_state["_admin_users_page"] = page - 1
        st.rerun()
    if cols[1].button("Next", disabled=len(users) < _PAGE_SIZE, key="admin_users_next"):
        st.session_state["_admin_users_page"] = page + 1
        st.rerun()

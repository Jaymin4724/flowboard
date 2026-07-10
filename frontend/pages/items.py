import streamlit as st

from frontend.api import items as items_api
from frontend.api.exceptions import ApiError
from frontend.components.guards import require_auth
from frontend.components.item_card import render_item_card
from frontend.components.item_form import render_item_form
from frontend.utils.time import local_to_utc_iso, utc_iso_to_local_display

_EDITING_KEY = "_editing_item_id"
_REMINDING_KEY = "_reminding_item_id"
_PAGE_KEY = "_items_page"
_PAGE_SIZE = 10


def render() -> None:
    require_auth()
    st.title("My Items")

    with st.expander("Add a new item"):
        result = render_item_form(key="create_item_form")
        if result:
            try:
                items_api.create_item(**result)
            except ApiError as exc:
                st.error(exc.message)
            else:
                st.success("Item created.")
                st.rerun()

    page = st.session_state.get(_PAGE_KEY, 1)
    try:
        items = items_api.list_items(page=page, size=_PAGE_SIZE)
    except ApiError as exc:
        st.error(exc.message)
        return

    if not items:
        st.info("No items yet.")

    for item in items:
        if st.session_state.get(_EDITING_KEY) == item["id"]:
            _render_edit_form(item)
            continue
        if st.session_state.get(_REMINDING_KEY) == item["id"]:
            _render_reminder_form(item)
            continue

        action = render_item_card(item)
        if action == "edit":
            st.session_state[_EDITING_KEY] = item["id"]
            st.rerun()
        elif action == "remind":
            st.session_state[_REMINDING_KEY] = item["id"]
            st.rerun()
        elif action == "delete":
            try:
                items_api.delete_item(item["id"])
            except ApiError as exc:
                st.error(exc.message)
            else:
                st.rerun()

    cols = st.columns(2)
    if cols[0].button("Previous page", disabled=page <= 1):
        st.session_state[_PAGE_KEY] = page - 1
        st.rerun()
    if cols[1].button("Next page", disabled=len(items) < _PAGE_SIZE):
        st.session_state[_PAGE_KEY] = page + 1
        st.rerun()


def _render_edit_form(item: dict) -> None:
    result = render_item_form(key=f"edit_item_form_{item['id']}", initial=item)
    if st.button("Cancel edit", key=f"cancel_edit_{item['id']}"):
        st.session_state.pop(_EDITING_KEY, None)
        st.rerun()
    if result:
        try:
            items_api.update_item(item["id"], **result)
        except ApiError as exc:
            st.error(exc.message)
        else:
            st.session_state.pop(_EDITING_KEY, None)
            st.success("Item updated.")
            st.rerun()


def _render_reminder_form(item: dict) -> None:
    st.write(f"Set a reminder for **{item['title']}**")
    st.caption(f"Current reminder: {utc_iso_to_local_display(item.get('remind_me_at'))}")
    with st.form(key=f"reminder_form_{item['id']}"):
        remind_date = st.date_input("Date")
        remind_time = st.time_input("Time")
        submitted = st.form_submit_button("Save reminder")
    if st.button("Cancel", key=f"cancel_remind_{item['id']}"):
        st.session_state.pop(_REMINDING_KEY, None)
        st.rerun()
    if not submitted:
        return

    remind_at_iso = local_to_utc_iso(remind_date, remind_time)
    try:
        items_api.schedule_reminder(item["id"], remind_at_iso)
    except ApiError as exc:
        st.error(exc.message)
    else:
        st.session_state.pop(_REMINDING_KEY, None)
        st.success("Reminder set.")
        st.rerun()

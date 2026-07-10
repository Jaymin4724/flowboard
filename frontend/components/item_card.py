import streamlit as st

from frontend.utils.time import utc_iso_to_local_display

_STATUS_BADGE = {
    "pending": "⚪ pending",
    "running": "🔵 running",
    "completed": "🟢 completed",
    "deactivated": "⚫ deactivated",
}


def render_item_card(item: dict) -> str | None:
    """Renders one item row with Edit/Remind/Delete buttons. Returns which
    action was clicked this run ('edit' | 'remind' | 'delete'), or None."""
    action = None
    remind_at = item.get("remind_me_at")
    remind_label = "Edit reminder" if remind_at else "Remind"

    with st.container(border=True):
        cols = st.columns([5, 2, 1, 1, 1])
        cols[0].markdown(f"**{item['title']}**")
        if item.get("desc"):
            cols[0].caption(item["desc"])
        if remind_at:
            # This line (and the button label below) is the visible signal
            # that a reminder is active - once the backend's beat/worker
            # fires it and clears remind_me_at, it disappears and the
            # button reverts to "Remind" on the next list refresh.
            cols[0].caption(f"⏰ Reminder set for {utc_iso_to_local_display(remind_at)}")
        cols[1].markdown(_STATUS_BADGE.get(item["status"], item["status"]))
        if cols[2].button("Edit", key=f"edit_{item['id']}"):
            action = "edit"
        if cols[3].button(remind_label, key=f"remind_{item['id']}"):
            action = "remind"
        if cols[4].button("Delete", key=f"delete_{item['id']}"):
            action = "delete"
    return action

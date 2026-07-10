import streamlit as st

_STATUSES = ["pending", "running", "completed", "deactivated"]


def render_item_form(*, key: str, initial: dict | None = None) -> dict | None:
    """Renders a create/edit item form inside an st.form (so the API call
    fires once on submit, not on every keystroke rerun). Returns the
    submitted {title, desc, status} dict, or None if not submitted /
    validation failed this run. The caller is responsible for calling the
    API and triggering st.rerun() on success."""
    initial = initial or {}
    with st.form(key=key, clear_on_submit=not initial):
        title = st.text_input("Title", value=initial.get("title", ""))
        desc = st.text_area("Description", value=initial.get("desc") or "")
        status = st.selectbox(
            "Status", options=_STATUSES, index=_STATUSES.index(initial.get("status", "pending"))
        )
        submitted = st.form_submit_button("Save")

    if not submitted:
        return None
    if not title.strip():
        st.error("Title is required.")
        return None
    return {"title": title.strip(), "desc": desc.strip() or None, "status": status}

from datetime import date, datetime, time, timezone


def local_to_utc_iso(date_value: date, time_value: time) -> str:
    """Combine a st.date_input/st.time_input pair (naive, local wall-clock
    values) into a timezone-aware UTC ISO-8601 string for the API.

    Streamlit's date/time widgets return naive values with no timezone info.
    We treat them as the machine's local time (datetime.astimezone() on a
    naive value assumes exactly that) and convert to UTC, since the backend
    rejects reminders that resolve to the past and compares against
    timezone-aware `remind_me_at` values elsewhere.
    """
    local_dt = datetime.combine(date_value, time_value)
    aware_local = local_dt.astimezone()
    return aware_local.astimezone(timezone.utc).isoformat()


def utc_iso_to_local_display(value: str | None) -> str:
    if not value:
        return "—"
    # Pydantic v2's JSON mode serializes UTC datetimes with a trailing "Z"
    # (e.g. "2026-07-10T11:15:00Z"), which datetime.fromisoformat() only
    # understands from Python 3.11 onward - normalize it so this works on
    # 3.10 too (this project targets >=3.10).
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")

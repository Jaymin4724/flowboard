import sys
from pathlib import Path

# Streamlit runs this file with sys.path[0] set to frontend/, not the repo
# root, so `import frontend.*` would otherwise fail regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from frontend.api import admin as admin_api
from frontend.api.exceptions import ApiError
from frontend.auth import session
from frontend.pages import admin as admin_page
from frontend.pages import items, login, profile, register

st.set_page_config(page_title="FlowBoard", page_icon="🗂️", layout="wide")

# Session lives only in st.session_state (memory) for this tab - a browser
# refresh starts a brand-new session and logs the user out. There is no
# cross-reload persistence.

if session.is_authenticated() and session.get_is_admin() is None:
    try:
        session.set_is_admin(admin_api.probe_is_admin())
    except ApiError:
        session.set_is_admin(False)

if session.is_authenticated():
    pages = [
        st.Page(items.render, title="Items", icon="📋", url_path="items", default=True),
        st.Page(profile.render, title="Profile", icon="👤", url_path="profile"),
    ]
    if session.get_is_admin():
        pages.append(st.Page(admin_page.render, title="Admin", icon="🛠️", url_path="admin"))
else:
    pages = [
        st.Page(login.render, title="Log in", icon="🔑", url_path="login", default=True),
        st.Page(register.render, title="Register", icon="📝", url_path="register"),
    ]

nav = st.navigation(pages)
nav.run()

"""Alpha HR dashboard: entry point.

Run locally:   streamlit run streamlit_app.py
Each page lives in its own file under app_pages/ and can be edited on its own.
"""
import streamlit as st

from lib import auth, data, ui
from lib.metrics import pretty

st.set_page_config(page_title="Alpha HR Dashboard", page_icon=":material/monitoring:", layout="wide")
ui.inject_css()
auth.require_sign_in()

# The first read happens before any page is drawn, so pages never start empty.
try:
    snapshot = data.get_snapshot(max_age=None)   # reads only if this session has no data yet
except Exception as err:   # only if even the saved outage copy can't be loaded
    st.error(f"Couldn't load any data: {err}")
    st.stop()

navigation = st.navigation([
    st.Page("app_pages/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("app_pages/where.py", title="Where", icon=":material/location_on:"),
    st.Page("app_pages/factors.py", title="Factors", icon=":material/balance:"),
    st.Page("app_pages/voice.py", title="Employee voice", icon=":material/forum:"),
    st.Page("app_pages/cost.py", title="Cost & scenarios", icon=":material/payments:"),
])

with st.sidebar:
    st.markdown('<p class="sidebar-label">Filters · apply to every page</p>', unsafe_allow_html=True)
    employees = snapshot.employees
    for column, (label, all_label) in data.FILTERS.items():
        options = [""] + sorted(employees[column].dropna().unique().tolist(), key=pretty)
        st.selectbox(label, options, key=f"filter_{column}",
                     format_func=lambda v, all_label=all_label: all_label if v == "" else pretty(v))
    st.divider()
    st.toggle("Live updates", value=True, key="live_refresh",
              help=f"Checks the database for changes every {data.CHECK_SECONDS} s and re-reads it every "
                   f"{data.FULL_REFRESH_SECONDS // 60} min, or at once when rows are added or removed. "
                   "Turn off to pause.")
    if st.button("Refresh now", width="stretch",
                 help=f"Re-read the whole database now (at most once every {data.MANUAL_REFRESH_MIN_SECONDS} s)."):
        data.get_snapshot(force=True)
        st.rerun()
    if st.button("Sign out", width="stretch"):
        auth.sign_out()

navigation.run()

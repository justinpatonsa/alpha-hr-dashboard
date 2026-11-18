"""One shared sign-in for the group. The username and password live in the app's secrets
(APP_USERNAME, APP_PASSWORD), never in the repo."""
import hmac
import time

import streamlit as st

from lib import settings

MAX_TRIES = 5
LOCK_SECONDS = 60


def _matches(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode(), expected.encode())


def require_sign_in() -> None:
    if st.session_state.get("signed_in"):
        return
    username, password = settings.get("APP_USERNAME"), settings.get("APP_PASSWORD")
    _, middle, _ = st.columns([1, 1.15, 1])
    with middle:
        st.markdown(
            '<div class="page-head" style="margin-top:8vh"><p class="eyebrow">DATA 6520 · Alpha Manufacturing Solutions</p>'
            '<h1>HR dashboard</h1><p class="question">Sign in with your group\'s dashboard login.</p></div>',
            unsafe_allow_html=True,
        )
        if not username or not password:
            st.error("Sign-in isn't set up yet. Add APP_USERNAME and APP_PASSWORD to the app's secrets.")
            st.stop()
        with st.form("sign_in"):
            given_user = st.text_input("Username", autocomplete="username")
            given_password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            locked = st.session_state.get("locked_until", 0) - time.time()
            if locked > 0:
                st.error(f"Too many attempts. Try again in {int(locked) + 1} seconds.")
            elif _matches(given_user.strip().casefold(), username.casefold()) and _matches(given_password, password):
                st.session_state["signed_in"] = True
                st.session_state.pop("tries", None)
                st.rerun()
            else:
                time.sleep(1)  # slows down guessing
                tries = st.session_state.get("tries", 0) + 1
                st.session_state["tries"] = tries
                if tries >= MAX_TRIES:
                    st.session_state["locked_until"] = time.time() + LOCK_SECONDS
                    st.session_state["tries"] = 0
                st.error("That username and password didn't work.")
        st.caption("The data comes live from the course Supabase database, read-only.")
    st.stop()


def sign_out() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

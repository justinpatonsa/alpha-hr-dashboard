"""Page furniture shared by every page: CSS, header, KPI tiles, section titles, tables and the
live fragment that updates the page body (checking the database every 20 seconds) without moving anything."""
from html import escape

import pandas as pd
import streamlit as st

from lib import data

CSS = """
<style>
/* A refresh must not fade, flash or move anything: keep stale elements fully visible. */
[data-testid="stElementContainer"][data-stale="true"], [data-stale="true"] { opacity: 1 !important; transition: none !important; }
.block-container { padding-top: 3.4rem; max-width: 1320px; }
.page-head { border-bottom: 3px solid #7aa83a; padding-bottom: .65rem; margin-bottom: .35rem; }
.page-head .eyebrow { font-size: .74rem; letter-spacing: .05em; text-transform: uppercase; opacity: .62; margin: 0; }
.page-head h1 { font-size: 2rem; line-height: 1.15; margin: .1rem 0 0; padding: 0; font-weight: 700; }
.page-head .question { margin: .3rem 0 0; font-size: 1.02rem; opacity: .8; }
.live { font-size: .84rem; opacity: .85; height: 1.6rem; display: flex; gap: .5rem; align-items: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.live .dot { width: .55rem; height: .55rem; border-radius: 50%; background: #0ca30c; flex: none; }
.live.paused .dot { background: #898781; }
.live.warn .dot { background: #fab219; }
.fallback-banner { border: 1px solid #fab219; border-left: 5px solid #fab219; background: rgba(250,178,25,.12);
                   border-radius: 10px; padding: .6rem .9rem; margin: .4rem 0 .3rem; font-size: .92rem; line-height: 1.4; }
.fallback-banner::before { content: "⚠ "; }
.fallback-banner .why { font-size: .8rem; opacity: .75; margin-top: .2rem; overflow-wrap: anywhere; }
.kpi { border: 1px solid rgba(128,128,120,.28); border-radius: 12px; padding: 14px 16px; height: 132px; overflow: hidden;
       background: rgba(128,128,120,.05); }
.kpi { container-type: inline-size; }
.kpi .label { font-size: .8rem; font-weight: 600; opacity: .78; line-height: 1.25; max-height: 2.5em; overflow: hidden; }
.kpi .value { font-size: clamp(1rem, 11.5cqi, 1.9rem); font-weight: 650; line-height: 1.2; margin-top: .3rem; white-space: nowrap; }
.kpi.hero { border-top: 3px solid #7aa83a; }
.kpi.hero .value { font-size: clamp(1.5rem, 22cqi, 3rem); line-height: 1.05; }
.kpi .note { font-size: .78rem; opacity: .68; margin-top: .25rem; line-height: 1.3; max-height: 2.6em; overflow: hidden; }
.kpi.small { height: 108px; }
.kpi.small .value { font-size: clamp(1rem, 13cqi, 1.5rem); }
.section-title { font-weight: 650; font-size: 1.08rem; margin: .9rem 0 0; line-height: 1.3; }
.section-sub { font-size: .87rem; opacity: .72; margin: .1rem 0 .1rem; min-height: 1.2rem; }
.footnote { font-size: .8rem; opacity: .65; margin-top: -.3rem; }
section[data-testid="stSidebar"] .sidebar-label { font-size: .78rem; letter-spacing: .04em; text-transform: uppercase; opacity: .6; margin: .2rem 0 -.2rem; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, question: str) -> None:
    # Second lock: a page never draws (or reads data) unless this session has signed in,
    # even if Streamlit were ever to run a page file without going through streamlit_app.py.
    if not st.session_state.get("signed_in"):
        st.stop()
    st.markdown(
        f'<div class="page-head"><p class="eyebrow">Alpha Manufacturing Solutions · HR dashboard</p>'
        f'<h1>{escape(title)}</h1><p class="question">{escape(question)}</p></div>',
        unsafe_allow_html=True,
    )


def kpi_row(tiles: list[dict], small: bool = False) -> None:
    """Exactly four tiles of fixed height; the first is the page's hero number."""
    widths = [1] * len(tiles) if small else [1.35] + [1] * (len(tiles) - 1)
    for col, t in zip(st.columns(widths, gap="small"), tiles):
        cls = "kpi small" if small else ("kpi hero" if t.get("hero") else "kpi")
        col.markdown(
            f'<div class="{cls}"><div class="label" title="{escape(t["label"])}">{escape(t["label"])}</div>'
            f'<div class="value">{escape(str(t["value"]))}</div><div class="note">{escape(t.get("note", ""))}</div></div>',
            unsafe_allow_html=True,
        )


def section(title: str, subtitle: str = "") -> None:
    st.markdown(f'<p class="section-title">{escape(title)}</p><p class="section-sub">{escape(subtitle)}</p>',
                unsafe_allow_html=True)


def footnote(text: str) -> None:
    st.markdown(f'<p class="footnote">{escape(text)}</p>', unsafe_allow_html=True)


def table(title: str, df: pd.DataFrame, key: str) -> None:
    with st.expander(title, key=key):
        st.dataframe(df, hide_index=True, width="stretch")


def _status(snap: data.Snapshot, live: bool) -> None:
    t = snap.loaded_at.strftime("%H:%M:%S")
    rows = sum(snap.rows_read.values())
    if snap.source == "fallback":
        # One element either way (banner + status line), so the page keeps the same structure.
        reason = (snap.fallback_reason or "unknown error")[:220]
        st.markdown(
            f'<div class="fallback-banner"><strong>Not live data.</strong> The course database (Supabase) '
            f'can\'t be read right now, so every figure on this page comes from the saved '
            f'{escape(data.FALLBACK_LABEL)} copy of the four tables. The app checks the live database '
            f'every {data.FALLBACK_RETRY_SECONDS} s and switches back automatically when it answers.'
            f'<div class="why">Reason: {escape(reason)}</div></div>'
            f'<div class="live warn"><span class="dot"></span><span>Saved copy · {escape(data.FALLBACK_LABEL)} · '
            f'{rows:,} rows from 4 tables · last live check at {t}</span></div>',
            unsafe_allow_html=True,
        )
        return
    if snap.error:
        cls = "live warn"
        text = (f"Couldn't reach the database at {snap.failed_at:%H:%M:%S}. Showing the data read at {t}; "
                f"trying again in {data.CHECK_SECONDS} s. ({snap.error})")
    elif live:
        cls = "live"
        checked = (snap.checked_at or snap.loaded_at).strftime("%H:%M:%S")
        text = (f"Live · checked {checked} · full read at {t} ({rows:,} rows) · "
                f"re-reads every {data.FULL_REFRESH_SECONDS // 60} min, or at once when rows change")
    else:
        cls = "live paused"
        text = f"Paused · last read at {t} · turn live refresh back on in the sidebar"
    st.markdown(f'<div class="{cls}"><span class="dot"></span><span>{escape(text)}</span></div>', unsafe_allow_html=True)


def live(render, key: str) -> None:
    """Run render(df, snapshot) in a fragment that ticks every 20 seconds. Each tick asks lib/data
    for the latest shared read, which checks the database cheaply and re-reads it when needed.

    Only this fragment reruns, so the header, sidebar and scroll position stay put. Each
    render emits the same elements in the same order, so Streamlit updates them in place."""
    # Read the sidebar settings during the full run and hand them to the fragment, because the
    # sidebar widgets don't run again when only the fragment refreshes.
    is_live = st.session_state.get("live_refresh", True)
    filters = data.current_filters()
    first_run = [True]

    def body():
        # The first run (page opened, filter changed) redraws at once from the latest read;
        # the timed reruns after it fetch fresh data.
        snap = data.get_snapshot(max_age=None if first_run[0] else data.REFRESH_SECONDS - 2)
        first_run[0] = False
        _status(snap, is_live)
        df = data.apply_filters(snap.employees, filters)
        if df.empty:
            st.info("No employees match the current filters. Widen them in the sidebar.")
            return
        render(df, snap)

    st.fragment(body, run_every=data.REFRESH_SECONDS if is_live else None, key=key)()

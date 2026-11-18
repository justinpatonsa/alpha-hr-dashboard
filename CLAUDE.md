# CLAUDE.md

This repo is a **Streamlit multipage app**. `streamlit_app.py` is the entry point, and each page is one file in `pages/`. It's hosted on Streamlit Community Cloud, which redeploys on every push to `main`. The older static site lives in `docs/` and is served by GitHub Pages. Its own rules are in `docs/README.md`.

Read `README.md` and `DESIGN.md` before changing anything.

## Hard rules

- **No secrets, ever.** The repo is public. Supabase and dashboard logins come only from Streamlit secrets or environment variables, read through `lib/settings.py`. Never commit `.streamlit/secrets.toml` or a `.env`.
- **Read-only database.** The Supabase project is shared by the whole class. Read data only through `lib/supabase_client.py` (GET to `/rest/v1`). Never POST, PATCH, PUT or DELETE a table.
- **Live data only.** No CSV, Excel, pickle or parquet copies of the data, and no `st.cache_data` on table rows. Every figure comes from the snapshot in `lib/data.py`, which re-reads every 20 seconds.
- **No layout jumps.** Page bodies run inside `ui.live(render, key=...)`:
  - Give every chart a fixed height via `charts.style(fig, height)` and a unique `key` in `charts.show`.
  - Emit the same elements in the same order on every run.
  - Don't add elements that appear only sometimes during a refresh.
- **Escape database text** with `html.escape` before any `unsafe_allow_html`.
- **Reuse the pieces:** `metrics.py` for calculations, `charts.py` colours (BLUE, ORANGE, AQUA, RED, GREY, SEQUENTIAL), and `ui.kpi_row` / `ui.section` / `ui.table`.

## Test before pushing

```bash
streamlit run streamlit_app.py   # needs .streamlit/secrets.toml filled in locally
```

Open every page and wait for at least one refresh, which is when the status line's time changes. Check that nothing moves and the terminal shows no errors.

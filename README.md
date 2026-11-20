# Alpha HR Dashboard

A live HR turnover dashboard for the DATA 6520 Alpha Manufacturing Solutions project, built with **Streamlit**. Each page is its own Python file, so you can work on one page without touching the others.

- **Code:** <https://github.com/justinpatonsa/alpha-hr-dashboard>
- **App:** hosted on Streamlit Community Cloud, which redeploys every time `main` changes
- **Design:** see [`DESIGN.md`](DESIGN.md) for the layout, colours, refresh behaviour and what each page answers
- **Older static version:** [`docs/`](docs/), served by GitHub Pages as a fallback

> **Changing the dashboard with an AI assistant** (ChatGPT, Claude, Copilot…)? Open [`AI_GUIDE.md`](AI_GUIDE.md), copy everything below its line into the AI, then add your request. It covers the rules, files, data and step-by-step recipes.

## Pages

| File | Page | Question it answers |
|---|---|---|
| `app_pages/overview.py` | Overview | How many left in 2025, at what rate, and when? |
| `app_pages/where.py` | Where | Which plants, departments, roles and shifts run well above the rate? |
| `app_pages/factors.py` | Factors | How do leavers differ from stayers? |
| `app_pages/voice.py` | Employee voice | What do the survey and exit interviews say, and who do they cover? |
| `app_pages/cost.py` | Cost & scenarios | What do departures cost, and what would an improvement save? |

To add a page, create `app_pages/<name>.py` following the pattern below, then add one `st.Page(...)` line to `streamlit_app.py`.

## How a page works

```python
from lib import charts, metrics as m, ui

ui.page_header("Title", "The question this page answers")   # drawn once

def render(df, snap):         # df = the filtered, joined employee table; runs on every 20 s tick
    ui.kpi_row([...])         # four fixed-height tiles, the first is the hero
    ui.section("Chart title", "subtitle")
    charts.show(charts.style(fig, height), key="unique_key")

ui.live(render, key="page_name")
```

`ui.live` ticks every 20 seconds and calls `render` again with the latest shared read. `lib/data.py` checks row counts on each tick, and re-reads everything every 5 minutes, or at once when counts change. **Don't make it read more often:** the class database has a small transfer allowance, and a 20-second full re-read once got the project blocked. Only the page body updates, and it updates in place. **To keep the screen from jumping:**
- Give every chart a fixed height and a unique `key`.
- Always draw the same elements in the same order.
- Put messages into fixed slots instead of making them appear only sometimes.

## How it connects to the data

- The app signs in to the course Supabase project **on the server** with one group member's course login, kept in the app's **Secrets** and never in the repo. It reads the four tables with read-only GET requests, 1,000 rows per request.
- `lib/data.py` joins them into one row per employee (`employees` + `compensation_training` + `employee_surveys` + `exit_interviews`, all one-to-one on `employee_id`).
- Viewers sign in to the dashboard with the **group's shared username and password** (`APP_USERNAME` / `APP_PASSWORD`, also in Secrets).

## Rules

1. **No passwords in the repo, ever.** It's public. Secrets go only in Streamlit Cloud's Secrets box or in your own gitignored `.streamlit/secrets.toml`.
2. **Read-only.** The database is shared by the whole class. Only `GET` requests, through `lib/supabase_client.py`.
3. **Live data only.** No CSV, Excel or pickle copies of the data in the repo, and no caching rows to disk. Every figure comes from the live read. The one exception is the outage fallback in `data/snapshot_2026-10-28/`. `lib/data.py` uses it only while Supabase can't be read, shows a "Not live data" banner on every page, and switches back to live data by itself when the database answers. Don't use those files for anything else.
4. **Escape database text** before putting it in HTML (`html.escape`). The helpers in `lib/ui.py` already do this.

## Run it on your computer

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then fill it in (never commit it)
streamlit run streamlit_app.py
```

The app opens at <http://localhost:8501>.

## Deploy on Streamlit Community Cloud (one time)

1. Go to <https://share.streamlit.io> and sign in with GitHub (the account that owns the repo).
2. Click **Create app → Deploy a public app from GitHub**, then fill in:
   - **Repository:** `justinpatonsa/alpha-hr-dashboard`
   - **Branch:** `main`
   - **Main file path:** `streamlit_app.py`
   - **App URL:** pick one, for example `alpha-hr-dashboard`
3. Open **Advanced settings**:
   - Choose Python **3.12**.
   - Paste the filled-in contents of `.streamlit/secrets.toml.example` into **Secrets**.
4. Click **Deploy**. After that, every push to `main` redeploys automatically.

To change a password later, edit the app's **Settings → Secrets**. The app restarts with the new value.

## Files

```
streamlit_app.py          entry point: sign-in, sidebar filters, navigation
app_app_pages/*.py                one file per page
lib/settings.py           reads secrets / environment variables
lib/supabase_client.py    read-only Supabase access (sign-in, paging, counts)
lib/data.py               the live snapshot: fetch, join, filter
lib/metrics.py            analytics shared by pages
lib/charts.py             Plotly helpers with the palette baked in
lib/ui.py                 header, KPI tiles, live fragment, CSS
lib/auth.py               the group sign-in
.streamlit/config.toml    theme and settings (no secrets)
docs/                     the older static GitHub Pages version
```

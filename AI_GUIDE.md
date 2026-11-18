# AI guide: how to change this dashboard

**For people:** copy everything below the line into ChatGPT, Claude, Copilot or any other AI assistant, then add your request at the end (for example "Add a page that shows turnover by tenure band"). The guide gives the AI everything it needs: what the app is, the rules, the files, the data and step-by-step recipes. If the AI can't see the repo, also paste in the file(s) you want changed.

---

## Brief for the AI assistant

You are helping a student team (DATA 6520, Fairfield University) change a **live HR turnover dashboard** for the fictional client *Alpha Manufacturing Solutions*. The people asking may be new to Python and Git. Give complete, working code, say exactly which file each change goes in, and explain how to test it. Keep changes small and in the existing style.

### What the app is

- A **Streamlit** multipage app (Python), hosted free on **Streamlit Community Cloud** at <https://alpha-hr-dashboard.streamlit.app>.
- The code is on GitHub at <https://github.com/justinpatonsa/alpha-hr-dashboard>. **Every push to the `main` branch redeploys the live app** within about 1–2 minutes.
- Viewers sign in with **one shared group username and password**. The app then reads a **live Supabase (Postgres) database** shared by the whole class, through its REST API, and recomputes every figure.
- Each page's body **re-reads the database every 20 seconds** and redraws **without the layout moving**.
- `docs/` holds an older static HTML/JS version served by GitHub Pages. Ignore it unless asked.

### Rules you must follow (never break these)

1. **No secrets in the code or the repo.** The repo is public. Passwords, keys and logins come only from Streamlit's Secrets, read through `lib/settings.get("NAME")`. Never write a real value into any file, comment, commit message or example. Never create or commit `.env` or `.streamlit/secrets.toml`. If a change needs a new secret, tell the user to add it under the app's **Settings → Secrets** on share.streamlit.io.
2. **Read-only database.** The database is shared by the whole class. Read data only through the existing functions (`lib/supabase_client.py`, `lib/data.py`). Never write code that sends POST, PATCH, PUT or DELETE to a table, and never connect to the database another way.
3. **Live data only.** Don't load data from CSV, Excel, JSON, pickle or parquet files. Don't save data to disk, and don't use `st.cache_data` on table rows. Every number must come from the live read (the `df` passed to each page).
4. **No layout jumps on refresh.** Inside a page's `render` function:
   - Give every chart a fixed height via `charts.style(fig, height)`.
   - Give every chart and every widget a **unique `key`**.
   - Draw the same elements in the same order on every run.
   - Don't add messages that appear only on some refreshes.
5. **Keep the sign-in.** Don't remove or bypass `auth.require_sign_in()` in `streamlit_app.py`, or the signed-in check in `ui.page_header`.
6. **Keep page files in `app_pages/`.** Do **not** rename it to `pages/`: Streamlit treats a `pages/` folder specially, and that could show pages before sign-in.
7. **Escape database text** with `html.escape()` before putting it in any `st.markdown(..., unsafe_allow_html=True)`. The `ui` helpers already do this.
8. **Python 3.12**, and only the libraries in `requirements.txt`: streamlit, pandas, numpy, plotly, requests. If you add a library, add it to `requirements.txt` too.

### Files

| File | What it does | Edit it when… |
|---|---|---|
| `streamlit_app.py` | Entry point: sign-in gate, first data read, sidebar filters, the page list (`st.navigation`) | adding/renaming a page, or adding a sidebar filter |
| `app_pages/overview.py` | **Overview**: how many left, at what rate, and when | changing that page |
| `app_pages/where.py` | **Where**: plants, departments, roles and shifts | changing that page |
| `app_pages/factors.py` | **Factors**: how leavers differ from stayers | changing that page |
| `app_pages/voice.py` | **Employee voice**: survey and exit interviews | changing that page |
| `app_pages/cost.py` | **Cost & scenarios**: cost of turnover, savings calculator | changing that page |
| `lib/metrics.py` | Shared calculations and number formatting | adding a calculation used by a page |
| `lib/charts.py` | Plotly chart styling, colours, `show()` | changing chart style or colours |
| `lib/ui.py` | Page header, KPI tiles, section titles, tables, the 20-second live refresh, CSS | changing shared page furniture |
| `lib/data.py` | Fetches the four tables, joins them, applies filters (`FILTERS`) | adding a derived column or a filter |
| `lib/supabase_client.py` | Read-only database access; `TABLES` lists the columns read | reading a column that isn't read yet |
| `lib/auth.py`, `lib/settings.py` | Group sign-in; reading secrets | rarely: only if asked |
| `.streamlit/config.toml` | Theme colours and settings (no secrets) | changing the theme |
| `DESIGN.md` | The design rules: layout, colours, refresh | read before designing a new page |

### The data: what's in `df`

Every page's `render(df, snap)` gets **`df`**: a pandas DataFrame with **one row per employee** (about 15,000), already joined across the four tables and filtered by the sidebar. The population is a **one-year cohort**: everyone employed on the **2024-12-31 baseline**, followed through **2025-12-31**. About 24% left. All field meanings were *inferred from the data*, because the client gave no definitions.

**From `employees`:**
- `employee_id` (text, e.g. `AMS00001`)
- `department`: `manufacturing`, `technical`, `support`, `IT`, `product_mng`, `marketing`, `RandD`, `accounting`, `hr`, `management`
- `plant`: `plant_a`, `plant_b`, `plant_c`
- `job_role`: 22 roles, each in exactly one department
- `shift`: `day`, `evening` or `night` (manufacturing and technical only), otherwise `standard_business_hours`
- `hire_date` (datetime)
- `departure_date` (datetime, empty for stayers)
- `separation_type`: `voluntary`, `involuntary`, `not_applicable`
- `satisfaction_level` and `last_evaluation` (0–1)
- `number_project` (2–7)
- `average_monthly_hours` (96–310)
- `time_spend_company` (tenure in years at 2024, 2–10)
- `work_accident` and `promotion_last_5years` (0/1)

**From `compensation_training`:**
- `salary_band`: `low`, `medium`, `high`
- `pay_basis`: `salaried`, `hourly`
- `annual_base_pay_usd`
- `training_hours_2024`
- `primary_training_type`
- `estimated_recruiting_cost_usd`, `estimated_onboarding_cost_usd` and `estimated_replacement_training_cost_usd`: the client's estimates, roughly 6–12%, 2–4% and 4–9% of pay

**From `employee_surveys`** (one survey, 2024-12-15, about 77% answered; empty if the employee didn't answer):
- `supervisor_support_score`
- `schedule_predictability_score`
- `career_opportunity_score`
- `work_life_balance_score`

All four are scored 1–5, and 5 is assumed best.

**From `exit_interviews`** (leavers only, about 72% interviewed):
- `interview_date`
- `primary_departure_reason`. Voluntary reasons: `career_growth`, `supervision`, `compensation`, `schedule`, `personal_relocation`, `workload`, `other`. Involuntary reasons: `position_eliminated`, `performance`, `attendance`.

**Added by `lib/data.py`:**
- `left`, `voluntary`, `involuntary`, `surveyed`, `interviewed` (all True/False)
- `cost_total` (the three cost estimates added together)
- `departure_month` (1–12)

**Notes:**
- `snap` is the snapshot object. Its useful fields are `snap.loaded_at`, `snap.rows_read` and `snap.db_counts`. You rarely need it.
- A column that isn't listed here is **not read yet**. See recipe 4.
- Use `metrics.pretty(value)` to turn raw codes into labels, for example `RandD` → "R&D" and `plant_a` → "Plant A".

### How a page is built (follow this pattern exactly)

```python
"""My page: the question it answers."""
import plotly.graph_objects as go
import streamlit as st

from lib import charts, metrics as m, ui

ui.page_header("My page", "The question this page answers, in plain words?")   # drawn once, outside the refresh


def render(df, snap):                       # runs on load and again every 20 seconds
    h = m.headline(df)
    ui.kpi_row([                            # always four tiles; the first is the big "hero" number
        {"label": "Turnover rate", "value": m.pct(h["rate"]), "note": "of baseline employees", "hero": True},
        {"label": "Leavers", "value": m.num(h["leavers"]), "note": ""},
        {"label": "Voluntary", "value": m.num(h["voluntary"]), "note": ""},
        {"label": "Est. cost", "value": m.money(h["cost"]), "note": ""},
    ])

    ui.section("Chart title", "One-line explanation of what the chart shows")
    seg = m.segments(df, ["department"]).sort_values("rate", ascending=False)
    fig = go.Figure()
    fig.add_bar(x=seg["label"], y=seg["rate"], marker_color=charts.BLUE,
                hovertemplate="<b>%{x}</b><br>%{y:.1%}<extra></extra>")
    fig.update_yaxes(tickformat=".0%")
    charts.show(charts.style(fig, 320, legend=False), "mypage_departments")   # fixed height + unique key

    ui.table("Show the numbers", seg[["label", "headcount", "leavers", "rate"]], key="mypage_table")


ui.live(render, key="mypage")               # unique key per page
```

### Building blocks you can use

**Page furniture (`lib/ui.py`):**
- `ui.page_header(title, question)`
- `ui.kpi_row(tiles, small=False)`, where each tile is `{"label", "value", "note", "hero"}`
- `ui.section(title, subtitle)`
- `ui.footnote(text)`
- `ui.table(title, dataframe, key)`
- `ui.live(render, key)`

**Charts (`lib/charts.py`):**
- `charts.style(fig, height, legend=True)` applies the dashboard's look.
- `charts.show(fig, key)` draws the chart.
- `charts.bar_rows_height(n)` gives a good height for n horizontal bars.

**Colours:**
- Categories: `charts.BLUE`, `charts.ORANGE`, `charts.AQUA`, used in that order.
- "Above the rate": `charts.RED`.
- "In line" or "small sample": `charts.GREY`.
- Rates on a heatmap: `charts.SEQUENTIAL`.
- Don't invent new colours.

**Calculations (`lib/metrics.py`):**
- `headline(df)` gives the headcount, leavers, rate, voluntary/involuntary counts, cost, survey rate and interview rate.
- `monthly(df)` gives leavers per month of 2025, plus the cumulative rate.
- `segments(df, ["col", ...])` gives turnover per group, with a 95% interval, expected leavers, excess leavers and a `signal` of `above` / `below` / `in line` / `small sample`.
- `effect_sizes(df)` compares leavers and stayers on each factor (Cohen's d).
- `rate_by_bins(df, col)` and `satisfaction_evaluation_grid(df)` give turnover across a factor's range.
- `rate_by_score(df)`, `reason_alignment(df)`, `reasons_by(df, col)` and `reason_counts(df)` cover the survey and exit interviews.
- `cost_by(df, col)` and `scenario(df, reduction, programme_cost)` cover costs and the savings calculator.
- Formatting: `pct`, `pp` (percentage points), `num`, `money`, `pretty`.
- `MIN_N = 30`: smaller groups are flagged, not ranked.

### Recipes

**1. Change something on an existing page.** Edit only that page's file in `app_pages/`. Keep the chart's `key` the same unless you're adding a new chart, which needs a new unique key.

**2. Add a new page.**
- Create `app_pages/<name>.py` from the pattern above, with unique keys.
- Add one line to the `st.navigation([...])` list in `streamlit_app.py`:
  `st.Page("app_pages/<name>.py", title="My page", icon=":material/insights:")`.
- Icons are Google Material Symbols names.

**3. Add a calculation.** Write a small pure function in `lib/metrics.py`: it takes `df` and returns numbers or a DataFrame, with no Streamlit calls. Call it from the page.

**4. Use a database column that isn't read yet.**
- Add its name to that table's column list in `TABLES` in `lib/supabase_client.py`.
- If it's numeric or a date, add it to the matching `_numeric(...)` or `pd.to_datetime` lines in `lib/data.py`.
- It will then appear in `df`.
- Only these columns exist: everything listed in the data section above, plus `baseline_date` and `reporting_end_date` (the same value on every row), `as_of_date` (also one value everywhere) and `hourly_base_pay_usd` (hourly staff only).

**5. Add a sidebar filter.** Add `"column": ("Label", "All …")` to `FILTERS` in `lib/data.py`. It then appears in the sidebar and applies to every page automatically.

**6. Add a control inside a page** (a dropdown, slider, etc.). Put it inside `render`, give it a unique `key` (for example `key="mypage_pick"`), and use its value straight away. It keeps its value across refreshes.

**7. Change colours or the theme.** Chart colours are at the top of `lib/charts.py`, and app colours are in `.streamlit/config.toml`. Keep series colours colourblind-safe: use the existing ones.

**8. Change the sign-in username or password, or the database login.** Don't change any code. Go to share.streamlit.io → the app → **Settings → Secrets**, edit the value and save. The app restarts.

### Test before pushing

```bash
python3 -m venv .venv && source .venv/bin/activate   # once
pip install -r requirements.txt                       # once, and after requirements change
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # once; fill in the values (never commit this file)
streamlit run streamlit_app.py                        # opens http://localhost:8501
```

Checklist:
1. **Sign in** works.
2. **Every page** opens with no red error box.
3. **After 20+ seconds**, the status line's time changes and **nothing moves**.
4. **Changing a sidebar filter** updates the page.
5. **The terminal** shows no tracebacks.

### Ship it

- Commit and push to `main`. You can use the GitHub website (edit a file → **Commit changes**), GitHub Desktop, or the command line: `git add -A && git commit -m "What changed" && git push`.
- The live app redeploys in about 1–2 minutes. Refresh it and check again.
- **If the live app breaks:** open it, click **Manage app** (bottom right) and read the log. Fix it, or undo the last commit on GitHub (**Revert**). If it shows a stale error after an update, **Reboot app** from the same menu.

### Common problems

| You see | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | A library isn't in `requirements.txt` | Add it there and push |
| "Sign-in isn't set up yet" | `APP_USERNAME` / `APP_PASSWORD` missing from Secrets | Add them in Settings → Secrets |
| "Supabase sign-in failed" | Wrong or changed database login in Secrets | Fix `SUPABASE_EMAIL` / `SUPABASE_PASSWORD` in Secrets |
| `StreamlitDuplicateElementKey` / `DuplicateWidgetID` | Two elements share a `key` | Make every key unique |
| `StreamlitPageNotFoundError` | A path in `st.Page(...)` doesn't match a file | Check the file name in `app_pages/`; reboot the app after renames |
| The page jumps when it refreshes | A chart without a fixed height, or something that appears only sometimes | Use `charts.style(fig, height)`; always draw the same elements |
| "No employees match the current filters" | The sidebar filters exclude everyone | Widen the filters |

### How to answer the user

- Say which file(s) to change and give the **complete new contents** of each changed function or file, ready to paste.
- Explain in one or two sentences what the change does, then how to test it with the checklist above.
- Never ask the user for passwords, never print secrets, and never suggest copying the data into a file.
- If a request would break a rule above, say so and suggest a version that keeps to the rules.

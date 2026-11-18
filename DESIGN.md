# Design overview

A short guide to how the dashboard is meant to look and behave. Keep new pages consistent with it.

## What it's for

HR leadership at Alpha Manufacturing want to know who left in 2025, where turnover concentrates, why people left, and what it costs. Each page answers one of the RFP's sub-questions and opens with that question in plain words:

| Page | Question it answers | Depth beyond the headline |
|---|---|---|
| **Overview** | How many left, at what rate, and when? | Departures by month (voluntary vs involuntary), and the three segments with the most *excess* departures, meaning leavers above what the company rate predicts |
| **Where** | Which plants, departments, roles and shifts run hot? | Department × plant heatmap; each role's rate with a 95% confidence interval, flagged only when it is *significantly* above the company rate; shift comparison |
| **Factors** | How do leavers differ from stayers? | Every factor ranked by effect size (standardised difference), turnover rate across each factor's range, and a satisfaction × performance map that shows the leaver clusters |
| **Employee voice** | What do surveys and exit interviews say, and who do they cover? | Turnover rate at each survey score; whether what people said in the survey matches the reason they later gave for leaving; whose voice is missing (coverage by department); reasons by department |
| **Cost & scenarios** | What do departures cost, and what would an improvement save? | Cost split into recruiting, onboarding and training; cost per leaver by band; a scenario calculator (target segment, reduction %, optional programme cost → savings and net) |

## Layout (the same on every page)

1. **Header:** the page title, its question, and a live-status line ("Live · updated 10:42:05 · refreshes every 20 s").
2. **KPI row:** four tiles of fixed height. Exactly one hero number per page.
3. **Primary chart:** full width.
4. **Two supporting charts:** side by side, stacking on narrow screens.
5. **Detail table:** inside an expander, so every charted value is also readable as text.

Filters (plant, department, shift, pay basis) sit in the sidebar and apply to every page.

## Visual language

- **Chrome:** the team's green (`#7aa83a`) is used only for the accent rule and the active state, never for data.
- **Data colours** are the validated dataviz palette:
  - Categorical: blue `#2a78d6` (primary / voluntary / stayed), orange `#eb6834` (secondary / involuntary / left).
  - Sequential: blue light → dark, for rates on heatmaps.
  - Diverging: blue ↔ red with a grey midpoint, for "above / below the company rate".
- **Marks:** bars ≤ 24 px, hairline grids, no dual axes. Labels go on a few chosen marks only, and tooltips carry the rest.
- **Small samples are not shown as facts.** Segments with fewer than 30 people are greyed out or flagged.
- **Text:** the system sans, and numbers in the design's own formats (23.8%, $34.9M, 1,284).

## Live data and refresh

- The app reads the four Supabase tables live: read-only GET requests, paged 1,000 rows at a time, then joined in pandas.
- **Every 20 seconds** the page body re-reads the database (`st.fragment(run_every=20)`). Changing a filter re-slices the latest read without waiting.
- **No layout jumps on refresh:**
  - Every element keeps its position and size between refreshes: fixed-height tiles and charts, a constant element order, and messages written into fixed slots instead of appearing and disappearing.
  - Streamlit's usual fade-out during a rerun is turned off. The status line is what tells you an update happened.
  - If one read fails, the last good data stays on screen and the status line says so.
- A sidebar toggle pauses live refresh, which saves requests to the shared class database. Each open tab makes about 53 small requests every 20 seconds.

## Access

- Viewers sign in once with the **group's shared username and password**, kept in Streamlit Cloud's secrets.
- The app itself signs in to Supabase with one member's course login, also kept in secrets.
- No password ever goes in the repo.

## Code layout

```
streamlit_app.py      entry point: sign-in gate, sidebar filters, navigation
pages/                one file per page (edit a page without touching the others)
lib/settings.py       reads secrets / environment
lib/supabase_client.py  read-only Supabase access (sign-in, paging, counts)
lib/data.py           live snapshot: fetch, join, filter
lib/metrics.py        analytics shared by pages
lib/charts.py         chart helpers with the palette baked in
lib/ui.py             page header, KPI tiles, live fragment, CSS
```

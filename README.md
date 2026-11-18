# Alpha HR Dashboard

A live HR turnover dashboard for the DATA 6520 Alpha Manufacturing Solutions project. It's a static site for GitHub Pages: plain HTML, CSS and JavaScript, with no build step and no server.

## How it works

- **Sign-in:** each viewer signs in with **their own** Supabase login from the instructor. The browser sends it straight to Supabase Auth and keeps the session token in `sessionStorage`, which is cleared when the tab closes.
- **Live data, no cache:** after sign-in, the browser reads the four tables (`employees`, `compensation_training`, `employee_surveys`, `exit_interviews`) with read-only GET requests. It pages through them 1,000 rows at a time, the most Supabase returns per request. Every figure is computed in the browser from that fresh read. Nothing is cached or saved, and **Refresh data** reads everything again.
- **Check:** the *Data connection* card compares the rows read with the database's own count for each table.
- **What's in the repo:** only the project URL and the publishable key (`assets/config.js`). The publishable key is designed to be public. On its own it reads nothing, because every table refuses the anonymous role. **Never commit a password**, and don't add a `.env`.

## Files

| File | What it does |
|---|---|
| `index.html` | Page layout: sign-in, filters, tiles, chart cards, data connection |
| `assets/config.js` | Supabase project URL and publishable key (public values only) |
| `assets/supabase.js` | Sign-in, token refresh, sign-out, password change, paged reads |
| `assets/metrics.js` | Joins the tables and computes every figure (pure functions) |
| `assets/charts.js` | Bar charts with hover tooltips and a table view |
| `assets/app.js` | Wires it all together |
| `assets/styles.css` | Look and feel, with light and dark mode |

To add a "View by" option to the turnover chart, add an entry to `DIMENSIONS` in `assets/metrics.js`.

## Run it locally

```bash
cd alpha_hr_dashboard
python3 -m http.server 5210
```

Then open <http://localhost:5210> and sign in. Opening `index.html` directly from the file system won't work, because browsers block JavaScript modules on `file://` pages.

## Publish on GitHub Pages

1. Push to the `main` branch.
2. In the repo, go to **Settings → Pages → Build and deployment**, then set **Source: Deploy from a branch**, **Branch: `main`**, **folder: `/ (root)`**.
3. After a minute or so, the site is live at `https://<owner>.github.io/alpha-hr-dashboard/`.

## Course rules this follows

- Read-only access: only GET requests touch data, and nothing writes to the shared database.
- The dashboard reads the live database directly, with no cached data and no downloaded CSVs as a source.
- No passwords in GitHub or in shared code.

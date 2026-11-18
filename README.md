# Alpha HR Dashboard

A live HR turnover dashboard for the DATA 6520 Alpha Manufacturing Solutions project.

- **Live site:** <https://justinpatonsa.github.io/alpha-hr-dashboard/>
- **Code:** <https://github.com/justinpatonsa/alpha-hr-dashboard>

It's a static website: plain HTML, CSS and JavaScript files, with no server and no build step. **Whatever is on the `main` branch is the site.** Push a change to `main`, and the live site updates by itself about a minute later.

> **Using an AI assistant (Claude, ChatGPT, Copilot …)?** Give it this whole README first. The section
> [For your AI assistant](#for-your-ai-assistant) has a prompt to paste, and the [Rules](#rules-read-these-first) apply to
> everything it writes. Claude Code reads `CLAUDE.md` in this folder automatically.

---

## Contents

1. [Quick start](#quick-start)
2. [How the site connects to the data](#how-the-site-connects-to-the-data)
3. [Rules (read these first)](#rules-read-these-first)
4. [What's in this repo](#whats-in-this-repo)
5. [The data you can use](#the-data-you-can-use)
6. [Making a change](#making-a-change)
7. [Test on your own computer](#test-on-your-own-computer)
8. [Push your change to GitHub](#push-your-change-to-github)
9. [Check that it's live](#check-that-its-live)
10. [Working together without overwriting each other](#working-together-without-overwriting-each-other)
11. [Troubleshooting](#troubleshooting)
12. [For your AI assistant](#for-your-ai-assistant)

---

## Quick start

1. **Accept the invite.** Sign in to GitHub and open
   <https://github.com/justinpatonsa/alpha-hr-dashboard/invitations>, then click **Accept invitation**.
   That gives you write access, which is what lets you push.
2. **Open the live site and sign in** with *your own* Supabase login. It's in the email from the instructor
   titled "DATA 6520: Your individual Supabase database credentials".
3. **Change your initial password.** Once you're signed in, click **Change password** (top right). The instructor asks
   everyone to do this.
4. **Get the code** onto your computer (see [Push your change](#push-your-change-to-github) for three ways).
5. **Make a change, test it locally, push it to `main`.** The live site updates within about a minute.

---

## How the site connects to the data

**The connection is permanent, and nobody's login is stored anywhere.**

- The site knows *where* the database is from two public values in `assets/config.js`: the Supabase project
  URL and the project's **publishable key**. Both are designed to be public. On its own the publishable key
  can read **nothing**, because every table refuses anonymous access.
- Every person who opens the site signs in with **their own** instructor-issued Supabase login. The browser
  sends it straight to Supabase, gets back a session token, and uses that token to read the tables.
  The token is kept in `sessionStorage`, so it disappears when the tab closes.
- So there's nothing to "re-establish" after anyone leaves the call. The code is connected for good. Each
  viewer just signs in when they open the site, the way you would on any website.
- The site only needs updating if the instructor ever changes the project URL or the publishable key.
  In that case, edit `assets/config.js`, and also the `connect-src` address in the security line at the top of `index.html`.
- **Live, no cache:** every number is computed in the browser from a fresh read of the database each time
  someone signs in or presses **Refresh data**. If the instructor changes a value in the database, it shows up
  on the next refresh. That's the RFP's live-update test.

---

## Rules (read these first)

These come from the instructor's email and the RFP. Breaking one can fail the project or expose someone's account.

1. **Never put a password in this repo.** No `.env` files, and no logins in code, comments, commit messages, screenshots
   or issues. The repo is **public**: anyone on the internet can read every file and every past version.
   The only key allowed is the publishable key that's already in `assets/config.js`.
2. **Read-only.** The database is shared by the whole class. Code may only *read* data (HTTP `GET` to
   `/rest/v1/...`). Never send `POST`, `PATCH`, `PUT` or `DELETE` to a table. The one exception is the password
   change, which goes to `/auth/v1/user`.
3. **Live data only.** No CSV, Excel or JSON copies of the data in the repo, and no saving rows to `localStorage`,
   `sessionStorage` or IndexedDB. Every figure must come from the live read.
4. **Don't break sign-in or the security line.** `assets/supabase.js` and the `Content-Security-Policy` `<meta>`
   tag in `index.html` protect the site. Change them only on purpose (see [Add a chart library](#4-add-a-chart-library)).
5. **Treat database text as untrusted.** Put values on the page with `textContent` (or `new Option(text, value)`),
   never with `innerHTML`.
6. **Test locally before you push.** Whatever reaches `main` goes live for everyone.

---

## What's in this repo

| File | What it does | Edit it when… |
|---|---|---|
| `index.html` | Page layout: sign-in form, filters, KPI tiles, chart cards, data-connection table, password dialog | you add or move a card or tile |
| `assets/styles.css` | Look and feel, colour tokens, light and dark mode | you change the styling |
| `assets/config.js` | Supabase project URL and publishable key (public values only) | the instructor changes the project or key |
| `assets/supabase.js` | Sign-in, token refresh, sign-out, password change, paged read-only reads, row counts | you need a column that isn't read yet (`TABLES`) |
| `assets/metrics.js` | Joins the four tables and computes every figure (pure functions, no fetching) | you add a calculation or a "View by" option |
| `assets/charts.js` | Horizontal bar charts with tooltips, legend and a "Show table" view | you need a new kind of chart |
| `assets/app.js` | Wires it together: sign-in, loading, filters, rendering each card | you add a card or change what a card shows |
| `.nojekyll` | Tells GitHub Pages to serve the files exactly as they are | never (leave it) |
| `.gitignore` | Keeps `.env` files and other secrets out of Git | never (leave it) |
| `CLAUDE.md` | Instructions Claude Code reads automatically | the rules change |

**How a page load works:** `app.js` → sign-in via `supabase.js` → `fetchAll()` reads each table in pages of
1,000 rows (the most Supabase returns per request) → `metrics.js` joins and calculates → `charts.js` draws.
The **Data connection** card at the bottom checks that the rows read match the database's own count.

---

## The data you can use

All four tables are in the same Supabase project, joined on `employee_id`. Each of the three child tables has **at most one
row per employee**, so joins are one-to-one. The field meanings below were *worked out from the data*, because the client
didn't provide definitions.

The population is a **one-year cohort**: everyone employed on the baseline date of **2024-12-31**, followed through **2025-12-31**.
About 15,000 employees, and roughly 24% left during 2025. The dashboard shows the live figures.

**`employees`** (one row per employee; key `employee_id`, e.g. `AMS00001`)
`employee_id, department, plant, job_role, shift, hire_date, baseline_date, reporting_end_date, departure_date,
separation_type, left, satisfaction_level, last_evaluation, number_project, average_monthly_hours,
time_spend_company, work_accident, promotion_last_5years`
- `department`: manufacturing, technical, support, IT, product_mng, marketing, RandD, accounting, hr, management
- `plant`: plant_a, plant_b, plant_c · `shift`: day / evening / night (manufacturing and technical only), otherwise standard_business_hours
- `left`: 1 = left during 2025, 0 = stayed · `separation_type`: voluntary, involuntary, not_applicable (stayed)
- `departure_date`: set only for leavers · `time_spend_company`: tenure in whole years at 2024
- `satisfaction_level`, `last_evaluation`: 0–1 scores · `work_accident`, `promotion_last_5years`: 0/1

**`compensation_training`** (one row per employee; key `employee_id`)
`employee_id, as_of_date, salary_band, pay_basis, annual_base_pay_usd, hourly_base_pay_usd, training_hours_2024,
primary_training_type, estimated_recruiting_cost_usd, estimated_onboarding_cost_usd, estimated_replacement_training_cost_usd`
- `salary_band`: low / medium / high · `pay_basis`: salaried / hourly (`hourly_base_pay_usd` is empty for salaried staff)
- `primary_training_type`: leadership, safety, technical_skills, professional_development, none
- The three `estimated_..._cost_usd` columns are the client's estimates of the cost of replacing that employee.

**`employee_surveys`** (one survey wave, 2024-12-15; about 77% of employees answered; key `survey_id`)
`survey_id, employee_id, survey_date, supervisor_support_score, schedule_predictability_score,
career_opportunity_score, work_life_balance_score` (each score 1–5, with 5 assumed best)

**`exit_interviews`** (leavers only; about 72% of leavers were interviewed; key `exit_interview_id`)
`exit_interview_id, employee_id, interview_date, primary_departure_reason`
- Voluntary reasons: career_growth, supervision, compensation, schedule, personal_relocation, workload, other
- Involuntary reasons: position_eliminated, performance, attendance
- A few interviews are dated January 2026, just after the reporting window.

In JavaScript, after `joinTables()` each employee record has the `employees` columns directly, plus `e.comp`
(compensation_training row), `e.survey` (survey row or `null`), `e.exit` (exit interview or `null`),
`e.left` (true/false) and `e.cost` (the three cost estimates added up).

---

## Making a change

### 1. Use a column the site doesn't read yet
The site reads only the columns it needs. To use another one, add it to that table's `columns` list in `TABLES`
at the top of `assets/supabase.js`. It's comma-separated, with **no spaces**, and must match the names above exactly.

### 2. Add a "View by" option to the turnover chart
Add an entry to `DIMENSIONS` in `assets/metrics.js`, for example:
```js
{ id: "accident", label: "Workplace accident", get: (e) => (Number(e.work_accident) === 1 ? "yes" : "no") },
```

### 3. Add a new chart card
1. **`index.html`:** copy one `<article class="card" id="card-...">` block inside `<section class="grid">` and give it a new
   `id` (e.g. `card-tenure`), a title and a subtitle. Keep the empty `<div class="chart"></div>`.
2. **`assets/metrics.js`:** write a function that takes the employee records and returns the rows you want to plot.
3. **`assets/app.js`:** write a `renderTenure(emps)` that calls
   `renderBars(chart("card-tenure"), spec)`, and call it from `render()` so the filters apply to it.
   `spec` looks like this (see the comment in `assets/charts.js`):
   ```js
   {
     series: [{ id: "s1", label: "Turnover rate" }],               // 2 series → a legend is drawn
     rows: [{ label, aria, tip: { title, lines: [{ value, label, series }], note },
              bars: [{ value, display, series: "s1" }] }],
     max,          // optional: the value a full bar stands for (e.g. 5 for survey scores)
     labelSpace,   // px kept free for the value label at the end of the bar
     note,         // optional line under the chart
     table: { columns: [{ label, num }], rows: [[...cells]] },     // the "Show table" view
   }
   ```
   Colours come from the CSS tokens `--series-1` (blue) and `--series-2` (orange) in `styles.css`. Use `"s1"`/`"s2"`.

### 4. Add a chart library
The site deliberately loads nothing from other websites. To use something like Chart.js or Plotly:
- **Simplest:** download the library's `.min.js` file into `assets/vendor/` and load it with
  `<script src="assets/vendor/....min.js"></script>`. No security change is needed.
- **From a CDN:** use an exact, pinned version (e.g. from `cdnjs.cloudflare.com`), and add that host to `script-src`
  in the `Content-Security-Policy` `<meta>` tag in `index.html`, or the browser will block it.

### 5. Things that won't work here
- **Python, R or Streamlit can't run on GitHub Pages.** Pages only serves files to the browser, so anything that
  should appear on the site has to be HTML/CSS/JavaScript. Python is still fine for analysis on your own laptop. In that case,
  keep your login in a local `.env` file that is **never** committed (`.gitignore` already blocks `.env`).
- **No build tools** (React, Vite, npm). Keep to plain files so anyone can edit them in a browser.

---

## Test on your own computer

Browsers block JavaScript modules on pages opened straight from disk, so double-clicking `index.html` **won't work**.
Run a tiny local web server from the repo folder instead:

```bash
cd alpha-hr-dashboard          # the folder with index.html in it
python3 -m http.server 5210    # Windows: py -m http.server 5210
```

Open <http://localhost:5210>, sign in, and check:
- the page loads with no red errors in the browser console (right-click → **Inspect** → **Console**),
- your change appears and responds to the Plant and Department filters,
- the **Data connection** card still shows ✓ Matches for all four tables.

Stop the server with `Ctrl+C`.

---

## Push your change to GitHub

You need to have accepted the invite first. Pick whichever way suits you. They all end the same way:
the change lands on `main`, and the site updates.

### A. In the browser (no tools to install)
- **Edit one file:** open the file on GitHub → click the ✏️ pencil (**Edit this file**) → paste the new content →
  **Commit changes…** → write a short message → *Commit directly to the `main` branch* → **Commit changes**.
- **Upload new or changed files:** open the folder they belong in (e.g. `assets/`) → **Add file → Upload files** → drag
  the files in → write a short message → **Commit changes**. A file with the same name replaces the old one.

### B. GitHub Desktop (recommended if you'll change several files)
1. Install it from <https://desktop.github.com> and sign in with your GitHub account.
2. **File → Clone repository → `justinpatonsa/alpha-hr-dashboard`**.
3. Before you start each time, click **Fetch origin / Pull origin** to get everyone's latest changes.
4. Edit the files in the cloned folder, test locally, then in GitHub Desktop write a summary and click
   **Commit to main → Push origin**.

### C. Command line
```bash
git clone https://github.com/justinpatonsa/alpha-hr-dashboard.git
cd alpha-hr-dashboard
git pull                        # every time before you start
# … edit and test …
git add index.html assets/app.js          # name the files you changed
git commit -m "Add tenure chart"
git push
```
GitHub doesn't accept account passwords for `git push`. Sign in once with GitHub Desktop, or with `gh auth login`
from the GitHub CLI.

**Before every commit, check it doesn't include a password or a data file** (see [Rules](#rules-read-these-first)).

---

## Check that it's live

1. On GitHub, open the **Actions** tab. A run called **pages build and deployment** starts after each push.
   Wait for the green tick (usually under a minute). A red ✕ means the publish failed, and the old version stays live.
2. Open <https://justinpatonsa.github.io/alpha-hr-dashboard/> and **hard-refresh** (Mac `Cmd+Shift+R`,
   Windows `Ctrl+F5`). GitHub caches pages for up to about 10 minutes, so an ordinary refresh may still show the old version.

**Undo a bad change:** in GitHub Desktop, open **History**, right-click the commit, then **Revert changes in commit**, and push.
In the browser, open the file → **History** → open the last good version → copy its contents → edit the file → paste → commit.

---

## Working together without overwriting each other

Everyone pushes to the same `main` branch, so:
- **Pull before you start** (GitHub Desktop: *Pull origin*; command line: `git pull`). Editing in the browser always starts from the latest version.
- **Say in the group chat which file you're editing**, and avoid two people changing the same file at once.
  `app.js` and `index.html` are the files most likely to clash.
- **Make small changes and push them often**, each with a clear message ("Add tenure chart", not "updates").
- **Check the live site after every push.** If you broke it, revert straight away (see above).

---

## Troubleshooting

| What you see | Likely cause | Fix |
|---|---|---|
| "That email and password didn't work." | Wrong login, or you changed your password | Use the login from your instructor email, or your new password |
| Signed out after a while | Your session ended, or you closed the tab | Sign in again |
| "Couldn't read the data: … permission denied" | The request went out without a signed-in token | Sign out and back in; don't call Supabase without `supabase.js` |
| Console: "Refused to load the script …" | The security line in `index.html` blocks it | See [Add a chart library](#4-add-a-chart-library) |
| Console: "Failed to load module script" or a 404 for a file | A wrong path, or a file wasn't uploaded | Check names and folders match exactly (they're case-sensitive) |
| A blank page when opening `index.html` directly | `file://` pages can't load modules | Use the local server ([Test on your own computer](#test-on-your-own-computer)) |
| The live site still shows the old version | GitHub's cache | Wait for the green tick in **Actions**, then hard-refresh |
| "Data connection" shows ✕ Differs | Rows read ≠ the database's count | Press **Refresh data**. If it persists, a paging change broke `fetchAll()` |

---

## For your AI assistant

Paste this README into your assistant, then paste the prompt below, then the **current** contents of every file you
want changed (or connect it to this GitHub repo). Without the current files it will guess, and guesses break things.

```text
You are helping my DATA 6520 group extend a static HR dashboard hosted on GitHub Pages
(repo justinpatonsa/alpha-hr-dashboard). The README above describes it; follow it exactly.

Hard rules:
- Plain HTML/CSS/JavaScript ES modules only. No build step, no npm, no frameworks, no server code.
  Python, R and Streamlit cannot run on GitHub Pages.
- Never put a password, token, .env file or secret in any file. The only key allowed is the publishable key
  already in assets/config.js. The repo is public.
- Read-only: only GET requests to Supabase /rest/v1 through the functions in assets/supabase.js
  (fetchAll, countRows). Never write to the database.
- Live data only: no CSV/JSON copies of the data, no caching rows in localStorage/sessionStorage/IndexedDB.
- Insert any database value into the page with textContent, never innerHTML.
- Keep the Content-Security-Policy meta tag in index.html. If you add a library, either vendor its .min.js into
  assets/vendor/ or tell me exactly which host to add to script-src, with a pinned version.
- Reuse what exists: TABLES in supabase.js (add columns there), joinTables() and the metric functions in
  metrics.js, renderBars() in charts.js, and the render() flow in app.js so the Plant/Department filters apply.
- Use the colour tokens in styles.css (--series-1, --series-2, etc.); don't hard-code colours.

When you answer:
- Give me COMPLETE replacement files (not fragments), each headed with its exact path, e.g. assets/app.js.
- List which files changed and why, in one line each.
- Tell me how to test it locally (python3 -m http.server 5210, then http://localhost:5210) and what I should see.
- Point out anything that could break sign-in, the live data load, or the Data connection check.
```

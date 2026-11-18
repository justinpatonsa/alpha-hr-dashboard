# CLAUDE.md

This repo is a **static GitHub Pages site**: plain HTML, CSS and JavaScript ES modules, with no build step and no server. Whatever is on `main` is the live site (<https://justinpatonsa.github.io/alpha-hr-dashboard/>), so a push to `main` publishes it.

Read `README.md` before changing anything. It explains the files, the data, how to add a column, a "View by" option or a chart card, how to test, and how to push.

## Hard rules

- **No secrets, ever.** The repo is public. No passwords, tokens or `.env` files, and no logins in code, comments or commits. The only key allowed is the publishable key already in `assets/config.js`.
- **Read-only database.** The Supabase project is shared by the whole class. Touch data only with `GET` requests to `/rest/v1`, through `fetchAll()` and `countRows()` in `assets/supabase.js`. Never `POST`, `PATCH`, `PUT` or `DELETE` to a table. The only exception is the password change, which goes to `/auth/v1/user`.
- **Live data only.** No CSV, Excel or JSON copies of the data, and never store rows in `localStorage`, `sessionStorage` or IndexedDB. Every figure is computed from the live read.
- **Plain files only.** No npm, bundlers, frameworks or server code. Python, R and Streamlit can't run on GitHub Pages.
- **Keep the `Content-Security-Policy` meta tag in `index.html`.** For a new library, either vendor its `.min.js` into `assets/vendor/`, or add one pinned CDN host to `script-src` and say so.
- **Database text is untrusted.** Insert it with `textContent` or `new Option()`, never `innerHTML`.
- **Reuse the existing pieces.** That means `TABLES` (columns read), `joinTables()` and the metric functions in `metrics.js`, `renderBars()` in `charts.js`, and `render()` in `app.js`, so the Plant and Department filters apply. Use the colour tokens in `styles.css`.

## Test before pushing

```bash
python3 -m http.server 5210   # then open http://localhost:5210 and sign in
```

Check three things: the console has no errors, the change responds to the filters, and the **Data connection** card shows ✓ Matches for all four tables.

# Outage fallback: saved copy of the four tables (28 Oct 2026)

These files are **not** a data source for the dashboard. `lib/data.py` uses them only when
the live Supabase database can't be read, for example when the instructor's project is
restricted for going over its quota (HTTP 402). While they're in use:

- every page shows a "Not live data" banner that names the date of this copy and the reason,
- the app tries the live database again every 60 seconds and switches back by itself.

They come from a full read of the live database on 28 Oct 2026. At that point the row counts
matched the database: employees 14,999, compensation_training 14,999, employee_surveys
11,567 and exit_interviews 2,562. The course rules require live data, so don't read these files
anywhere else, don't add other copies, and delete this folder once it's no longer needed.

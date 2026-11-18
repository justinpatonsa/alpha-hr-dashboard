"""Read-only access to the course Supabase project, from the server.

Signs in with one course login from the settings, refreshes the session before it expires,
and reads tables with GET requests only. Supabase returns at most 1,000 rows per request,
so tables are read in key order, asking for the rows after the last key seen (keyset paging)
until a page comes back empty.
"""
import threading
import time

import requests

from lib import settings

PAGE_SIZE = 1000
MAX_PAGES = 100
TIMEOUT = 20

# table -> (unique key it is paged by, columns read)
TABLES = {
    "employees": ("employee_id", [
        "employee_id", "department", "plant", "job_role", "shift", "hire_date", "departure_date",
        "separation_type", "left", "satisfaction_level", "last_evaluation", "number_project",
        "average_monthly_hours", "time_spend_company", "work_accident", "promotion_last_5years",
    ]),
    "compensation_training": ("employee_id", [
        "employee_id", "salary_band", "pay_basis", "annual_base_pay_usd", "training_hours_2024",
        "primary_training_type", "estimated_recruiting_cost_usd", "estimated_onboarding_cost_usd",
        "estimated_replacement_training_cost_usd",
    ]),
    "employee_surveys": ("survey_id", [
        "survey_id", "employee_id", "supervisor_support_score", "schedule_predictability_score",
        "career_opportunity_score", "work_life_balance_score",
    ]),
    "exit_interviews": ("exit_interview_id", [
        "exit_interview_id", "employee_id", "interview_date", "primary_departure_reason",
    ]),
}

REQUIRED = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_EMAIL", "SUPABASE_PASSWORD")


class SupabaseError(Exception):
    pass


def _message(response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200] or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        return body.get("msg") or body.get("message") or body.get("error_description") or body.get("error") or str(body)[:200]
    return str(body)[:200]


class Client:
    """One signed-in session shared by the app. The token is a session credential, not data."""

    def __init__(self):
        self._lock = threading.Lock()
        self._local = threading.local()
        self._token = None
        self._refresh_token = None
        self._expires = 0.0
        self._load_settings()

    def _load_settings(self):
        self.url = (settings.get("SUPABASE_URL") or "").rstrip("/")
        self.key = settings.get("SUPABASE_PUBLISHABLE_KEY")
        self.email = settings.get("SUPABASE_EMAIL")
        self.password = settings.get("SUPABASE_PASSWORD")

    def missing(self) -> list[str]:
        values = dict(zip(REQUIRED, (self.url, self.key, self.email, self.password)))
        return [name for name, value in values.items() if not value]

    def _http(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            self._local.session = requests.Session()
        return self._local.session

    def _token_request(self, grant: str, body: dict):
        try:
            r = self._http().post(f"{self.url}/auth/v1/token", params={"grant_type": grant},
                                  headers={"apikey": self.key}, json=body, timeout=TIMEOUT)
        except requests.RequestException as err:
            raise SupabaseError(f"Can't reach Supabase: {err}") from err
        if r.status_code == 200 and "access_token" in r.json():
            return r.json()
        return None

    def _sign_in(self):
        payload = None
        if self._refresh_token:
            payload = self._token_request("refresh_token", {"refresh_token": self._refresh_token})
        if payload is None:
            payload = self._token_request("password", {"email": self.email, "password": self.password})
        if payload is None:
            self._load_settings()  # the password may have been changed in the secrets
            payload = self._token_request("password", {"email": self.email, "password": self.password})
        if payload is None:
            raise SupabaseError("Supabase sign-in failed. Check SUPABASE_EMAIL and SUPABASE_PASSWORD in the app's secrets.")
        self._token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token")
        self._expires = time.time() + int(payload.get("expires_in", 3600))

    def headers(self, force: bool = False) -> dict:
        missing = self.missing()
        if missing:
            raise SupabaseError("Missing from the app's secrets: " + ", ".join(missing))
        with self._lock:
            if force or not self._token or time.time() > self._expires - 60:
                self._sign_in()
            return {"apikey": self.key, "Authorization": f"Bearer {self._token}"}

    def _get(self, table: str, params: dict, extra: dict | None = None) -> requests.Response:
        url = f"{self.url}/rest/v1/{table}"
        for attempt in (1, 2):
            try:
                r = self._http().get(url, params=params, headers={**self.headers(force=attempt == 2), **(extra or {})},
                                     timeout=TIMEOUT)
            except requests.RequestException as err:
                raise SupabaseError(f"{table}: can't reach Supabase ({err})") from err
            if r.status_code != 401:
                break
        if r.status_code not in (200, 206):
            raise SupabaseError(f"{table}: HTTP {r.status_code}: {_message(r)}")
        return r

    def fetch_all(self, table: str) -> tuple[list[dict], int]:
        """Every row of the table in key order, and the number of requests it took."""
        key, columns = TABLES[table]
        rows, last = [], None
        for page in range(1, MAX_PAGES + 1):
            params = {"select": ",".join(columns), "order": f"{key}.asc", "limit": PAGE_SIZE}
            if last is not None:
                params[key] = f"gt.{last}"
            batch = self._get(table, params).json()
            if not batch:
                return rows, page
            rows.extend(batch)
            last = batch[-1][key]
        raise SupabaseError(f"{table}: stopped after {MAX_PAGES} pages")

    def count(self, table: str) -> int | None:
        """count(*) as the database reports it, from a request that returns no rows."""
        key, _ = TABLES[table]
        r = self._get(table, {"select": key, "limit": 0}, {"Prefer": "count=exact"})
        total = (r.headers.get("Content-Range") or "").split("/")[-1]
        return int(total) if total.isdigit() else None

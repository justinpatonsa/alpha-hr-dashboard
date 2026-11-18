"""Analytics shared by the pages. Pure pandas: every function takes the (filtered) employee table."""
import numpy as np
import pandas as pd

from lib.data import COST_COLUMNS, SCORE_COLUMNS

MIN_N = 30          # segments smaller than this are flagged, not ranked
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

NAMES = {
    "RandD": "R&D", "product_mng": "Product management", "hr": "HR", "IT": "IT",
    "plant_a": "Plant A", "plant_b": "Plant B", "plant_c": "Plant C",
    "standard_business_hours": "Standard hours",
}


def pretty(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)) or value == "":
        return "Unknown"
    s = str(value)
    if s in NAMES:
        return NAMES[s]
    s = s.replace("_", " ")
    return s[:1].upper() + s[1:]


# ---------- formatting ----------
def pct(v, digits=1) -> str:
    return "–" if v is None or pd.isna(v) else f"{v * 100:.{digits}f}%"


def pp(v, digits=1) -> str:
    return "–" if v is None or pd.isna(v) else f"{v * 100:+.{digits}f} pts"


def num(v) -> str:
    return "–" if v is None or pd.isna(v) else f"{v:,.0f}"


def money(v) -> str:
    if v is None or pd.isna(v):
        return "–"
    a = abs(v)
    if a >= 1e6:
        return f"${v / 1e6:.1f}M"
    if a >= 1e3:
        return f"${v / 1e3:.1f}K" if a < 1e5 else f"${v / 1e3:.0f}K"
    return f"${v:,.0f}"


# ---------- headline ----------
def headline(df: pd.DataFrame) -> dict:
    n = len(df)
    leavers = df[df["left"]]
    costed = leavers["cost_total"].dropna()
    return {
        "headcount": n,
        "leavers": len(leavers),
        "voluntary": int(df["voluntary"].sum()),
        "involuntary": int(df["involuntary"].sum()),
        "rate": len(leavers) / n if n else None,
        "voluntary_rate": df["voluntary"].sum() / n if n else None,
        "cost": costed.sum(),
        "cost_per_leaver": costed.mean() if len(costed) else None,
        "high_performers_lost": int((leavers["last_evaluation"] >= 0.8).sum()),
        "survey_rate": df["surveyed"].mean() if n else None,
        "interview_rate": leavers["interviewed"].mean() if len(leavers) else None,
    }


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Leavers per calendar month of 2025, split by type, with the cumulative turnover rate."""
    n = len(df)
    out = pd.DataFrame({"month": range(1, 13), "label": MONTHS})
    for kind in ("voluntary", "involuntary"):
        counts = df[df[kind]].groupby("departure_month").size()
        out[kind] = out["month"].map(counts).fillna(0).astype(int)
    out["leavers"] = out["voluntary"] + out["involuntary"]
    out["monthly_rate"] = out["leavers"] / n if n else np.nan
    out["cumulative_rate"] = out["leavers"].cumsum() / n if n else np.nan
    return out


# ---------- segments ----------
def wilson(k, n, z=1.96):
    """95% Wilson interval for a proportion; works on arrays."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = k / n
        denom = 1 + z ** 2 / n
        centre = (p + z ** 2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return centre - half, centre + half


def segments(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Turnover per segment, compared with the whole selection.

    expected = what the segment would lose at the selection's rate; excess = leavers above that.
    A segment is 'above' / 'below' only when its 95% interval excludes the selection rate."""
    overall = df["left"].mean() if len(df) else np.nan
    g = df.groupby(by, dropna=False).agg(headcount=("employee_id", "size"), leavers=("left", "sum"),
                                          voluntary=("voluntary", "sum")).reset_index()
    g["rate"] = g["leavers"] / g["headcount"]
    g["low"], g["high"] = wilson(g["leavers"], g["headcount"])
    g["expected"] = g["headcount"] * overall
    g["excess"] = g["leavers"] - g["expected"]
    g["vs_selection"] = g["rate"] - overall
    g["signal"] = np.select([g["headcount"] < MIN_N, g["low"] > overall, g["high"] < overall],
                            ["small sample", "above", "below"], "in line")
    g["label"] = g[by].apply(lambda r: " · ".join(pretty(v) for v in r), axis=1)
    return g


# ---------- factors ----------
FACTORS = {
    "satisfaction_level": ("Satisfaction", lambda v: f"{v:.2f}"),
    "last_evaluation": ("Last evaluation", lambda v: f"{v:.2f}"),
    "average_monthly_hours": ("Monthly hours", lambda v: f"{v:.0f} h"),
    "number_project": ("Projects", lambda v: f"{v:.1f}"),
    "time_spend_company": ("Tenure (years)", lambda v: f"{v:.1f}"),
    "annual_base_pay_usd": ("Annual base pay", money),
    "training_hours_2024": ("Training hours", lambda v: f"{v:.0f} h"),
    "promotion_last_5years": ("Promoted (share)", lambda v: pct(v)),
    "work_accident": ("Work accident (share)", lambda v: pct(v)),
}


def effect_sizes(df: pd.DataFrame) -> pd.DataFrame:
    """Leavers vs stayers on each factor, as a standardised difference (Cohen's d)."""
    rows = []
    for col, (label, fmt) in FACTORS.items():
        a = df.loc[df["left"], col].dropna()
        b = df.loc[~df["left"], col].dropna()
        if len(a) < 2 or len(b) < 2:
            continue
        pooled = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2))
        d = (a.mean() - b.mean()) / pooled if pooled else 0.0
        rows.append({"factor": col, "label": label, "leavers": a.mean(), "stayers": b.mean(), "d": d,
                     "leavers_fmt": fmt(a.mean()), "stayers_fmt": fmt(b.mean())})
    out = pd.DataFrame(rows)
    if len(out):
        out["size"] = pd.cut(out["d"].abs(), [-1, 0.2, 0.5, 0.8, 99], labels=["negligible", "small", "medium", "large"])
        out = out.reindex(out["d"].abs().sort_values(ascending=False).index)
    return out


BINS = {
    "satisfaction_level": (np.round(np.arange(0, 1.01, 0.1), 2), lambda l, r: f"{l:.1f}–{r:.1f}"),
    "last_evaluation": (np.round(np.arange(0.3, 1.01, 0.1), 2), lambda l, r: f"{l:.1f}–{r:.1f}"),
    "average_monthly_hours": (np.arange(75, 326, 25), lambda l, r: f"{l:.0f}–{r:.0f}"),
    "number_project": (np.arange(1.5, 8, 1), lambda l, r: f"{l + 0.5:.0f}"),
    "time_spend_company": (np.arange(1.5, 11, 1), lambda l, r: f"{l + 0.5:.0f}"),
    "annual_base_pay_usd": (np.arange(30000, 150001, 15000), lambda l, r: f"${l / 1e3:.0f}–{r / 1e3:.0f}K"),
    "training_hours_2024": (np.arange(-0.5, 81, 10), lambda l, r: f"{max(l, 0):.0f}–{r:.0f}"),
}


def rate_by_bins(df: pd.DataFrame, col: str) -> pd.DataFrame:
    edges, fmt = BINS[col]
    cats = pd.cut(df[col], edges, include_lowest=True)
    g = df.groupby(cats, observed=False).agg(headcount=("employee_id", "size"), leavers=("left", "sum")).reset_index()
    g["label"] = [fmt(iv.left, iv.right) for iv in g[col]]
    g["rate"] = np.where(g["headcount"] > 0, g["leavers"] / g["headcount"].replace(0, np.nan), np.nan)
    g["small"] = g["headcount"] < MIN_N
    return g


def satisfaction_evaluation_grid(df: pd.DataFrame, step=0.1) -> pd.DataFrame:
    s_edges = np.round(np.arange(0, 1.0001, step), 2)
    e_edges = np.round(np.arange(0.3, 1.0001, step), 2)
    d = df.assign(s=pd.cut(df["satisfaction_level"], s_edges, include_lowest=True),
                  e=pd.cut(df["last_evaluation"], e_edges, include_lowest=True))
    g = d.groupby(["e", "s"], observed=False).agg(headcount=("employee_id", "size"), leavers=("left", "sum")).reset_index()
    g["rate"] = g["leavers"] / g["headcount"].replace(0, np.nan)
    g["s_mid"] = [iv.mid for iv in g["s"]]
    g["e_mid"] = [iv.mid for iv in g["e"]]
    return g


# ---------- voice ----------
def rate_by_score(df: pd.DataFrame) -> pd.DataFrame:
    """Turnover rate among survey respondents at each score (1–5), per question."""
    resp = df[df["surveyed"]]
    rows = []
    for col, label in SCORE_COLUMNS.items():
        g = resp.groupby(col).agg(headcount=("employee_id", "size"), leavers=("left", "sum"))
        for score in range(1, 6):
            n = int(g["headcount"].get(score, 0))
            k = int(g["leavers"].get(score, 0))
            rows.append({"question": label, "score": score, "headcount": n, "leavers": k,
                         "rate": k / n if n else np.nan})
    return pd.DataFrame(rows)


# A departure reason and the survey question that measures the same thing.
REASON_QUESTION = {
    "supervision": "supervisor_support_score",
    "schedule": "schedule_predictability_score",
    "career_growth": "career_opportunity_score",
    "workload": "work_life_balance_score",
}


def reason_alignment(df: pd.DataFrame) -> pd.DataFrame:
    """Did the survey see it coming? Mean score of leavers who gave a reason vs other interviewed
    voluntary leavers, on the question that matches that reason."""
    pool = df[df["voluntary"] & df["interviewed"] & df["surveyed"]]
    rows = []
    for reason, col in REASON_QUESTION.items():
        cited = pool[pool["primary_departure_reason"].eq(reason)][col]
        others = pool[~pool["primary_departure_reason"].eq(reason)][col]
        rows.append({"reason": pretty(reason), "question": SCORE_COLUMNS[col], "cited": cited.mean(),
                     "others": others.mean(), "n_cited": len(cited), "n_others": len(others),
                     "gap": cited.mean() - others.mean()})
    return pd.DataFrame(rows)


def reasons_by(df: pd.DataFrame, by: str = "department") -> pd.DataFrame:
    """Share of each group's interviewed leavers giving each reason."""
    d = df[df["left"] & df["interviewed"]]
    if d.empty:
        return pd.DataFrame()
    t = pd.crosstab(d[by], d["primary_departure_reason"])
    shares = t.div(t.sum(axis=1), axis=0)
    shares["_n"] = t.sum(axis=1)
    return shares


def reason_counts(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["left"] & df["interviewed"]]
    g = d.groupby(["primary_departure_reason", "separation_type"]).size().reset_index(name="leavers")
    g["share"] = g["leavers"] / len(d) if len(d) else np.nan
    g["label"] = g["primary_departure_reason"].map(pretty)
    return g.sort_values("leavers", ascending=False)


# ---------- cost ----------
def cost_by(df: pd.DataFrame, by: str) -> pd.DataFrame:
    leavers = df[df["left"]]
    g = leavers.groupby(by).agg(leavers=("employee_id", "size"), **{k: (k, "sum") for k in COST_COLUMNS}).reset_index()
    g["total"] = g[list(COST_COLUMNS)].sum(axis=1)
    g["per_leaver"] = g["total"] / g["leavers"]
    g["label"] = g[by].map(pretty)
    return g.sort_values("total", ascending=False)


def scenario(df: pd.DataFrame, reduction: float, programme_cost: float) -> dict:
    """What preventing a share of voluntary departures in this selection would be worth,
    using the client's own replacement-cost estimates for those leavers."""
    vol = df[df["voluntary"]]
    per = vol["cost_total"].mean() if len(vol) else 0.0
    avoided = len(vol) * reduction
    gross = avoided * per
    pool = len(vol) * per
    return {
        "voluntary": len(vol),
        "cost_per_voluntary": per,
        "avoided": avoided,
        "gross": gross,
        "net": gross - programme_cost,
        "break_even": programme_cost / pool if pool else None,
        "new_rate": (df["left"].sum() - avoided) / len(df) if len(df) else None,
    }

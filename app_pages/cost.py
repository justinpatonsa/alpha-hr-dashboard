"""Cost & scenarios (SQ5): what do departures cost, and what would a realistic improvement save?"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from lib import charts, metrics as m, ui
from lib.data import COST_COLUMNS

ui.page_header("Cost & scenarios", "What did 2025 departures cost, and what would a realistic improvement save?")

COMPONENT_COLOURS = [charts.BLUE, charts.ORANGE, charts.AQUA]
BAND_ORDER = ["low", "medium", "high"]


def render(df, snap):
    leavers = df[df["left"]]
    total = leavers["cost_total"].sum()
    parts = {label: leavers[col].sum() for col, label in COST_COLUMNS.items()}
    tiles = [{"label": "Estimated cost of 2025 departures", "value": m.money(total), "hero": True,
              "note": f"{m.num(len(leavers))} leavers · client's replacement-cost estimates"}]
    for label, value in parts.items():
        tiles.append({"label": label, "value": m.money(value),
                      "note": f"{m.pct(value / total if total else None, 0)} of the total"})
    ui.kpi_row(tiles)

    # ---- cost by department, split into components ----
    by_dept = m.cost_by(df, "department").iloc[::-1]
    ui.section("Where the cost falls", "Estimated replacement cost of 2025 leavers by department")
    fig = go.Figure()
    for (col, label), colour in zip(COST_COLUMNS.items(), COMPONENT_COLOURS):
        fig.add_bar(y=by_dept["label"], x=by_dept[col], orientation="h", name=label, marker_color=colour,
                    hovertemplate=f"{label}: <b>%{{x:$,.0f}}</b><extra></extra>")
    fig.add_scatter(y=by_dept["label"], x=by_dept["total"], mode="text", showlegend=False,
                    text=[f"  {m.money(v)}" for v in by_dept["total"]], textposition="middle right",
                    customdata=by_dept["leavers"], hovertemplate="Total <b>%{x:$,.0f}</b> · %{customdata:,} leavers<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.38, hovermode="y unified")
    fig.update_xaxes(tickprefix="$", tickformat="~s", range=[0, by_dept["total"].max() * 1.15 if len(by_dept) else 1])
    fig.update_yaxes(showgrid=False)
    charts.show(charts.style(fig, charts.bar_rows_height(len(by_dept), row=30, extra=70)), "cost_departments")

    left, right = st.columns(2, gap="large")

    # ---- cost per leaver by salary band ----
    with left:
        band = m.cost_by(df, "salary_band").set_index("salary_band").reindex(BAND_ORDER).dropna(subset=["leavers"])
        ui.section("Cost per leaver by salary band", "Average estimated replacement cost for one departure")
        fig = go.Figure()
        fig.add_bar(x=[m.pretty(b) for b in band.index], y=band["per_leaver"], marker_color=charts.BLUE,
                    text=[m.money(v) for v in band["per_leaver"]], textposition="outside", cliponaxis=False,
                    customdata=np.column_stack([band["leavers"], band["total"]]),
                    hovertemplate="<b>%{x} band</b><br>%{y:$,.0f} per leaver<br>%{customdata[0]:,.0f} leavers · "
                                  "%{customdata[1]:$,.0f} in total<extra></extra>")
        fig.update_layout(bargap=0.55)
        fig.update_yaxes(tickprefix="$", tickformat="~s", rangemode="tozero")
        charts.show(charts.style(fig, 330, legend=False), "cost_bands")

    # ---- scenario ----
    with right:
        ui.section("Scenario: keep some of the people who chose to leave",
                   "Uses the voluntary leavers in the current selection and their own cost estimates")
        segments = [""] + sorted(df["department"].unique().tolist(), key=m.pretty)
        seg = st.selectbox("Target", segments, key="cost_segment",
                           format_func=lambda v: "Everyone in the selection" if v == "" else m.pretty(v))
        c1, c2 = st.columns(2)
        reduction = c1.slider("Reduce voluntary departures by", 0, 50, 10, step=1, format="%d%%", key="cost_reduction") / 100
        programme = c2.number_input("Programme cost (optional, $)", min_value=0, value=0, step=25_000,
                                    key="cost_programme")
        target = df if seg == "" else df[df["department"] == seg]
        s = m.scenario(target, reduction, float(programme))
        ui.kpi_row([
            {"label": "Departures avoided", "value": f"{s['avoided']:,.0f}",
             "note": f"of {s['voluntary']:,} voluntary leavers"},
            {"label": "Gross saving", "value": m.money(s["gross"]),
             "note": f"at {m.money(s['cost_per_voluntary'])} per leaver"},
            {"label": "Net of programme", "value": m.money(s["net"]),
             "note": ("break-even at " + m.pct(s["break_even"], 0) + " fewer") if programme and s["break_even"] is not None
             else "add a programme cost to see break-even"},
        ], small=True)
        ui.footnote(f"Turnover in this target would fall to {m.pct(s['new_rate'])}. "
                    "Savings use the client's replacement-cost estimates; they are an indication, not a forecast.")

    ui.table("Show cost by department", by_dept.iloc[::-1].assign(
        **{label: by_dept.iloc[::-1][col].map(m.money) for col, label in COST_COLUMNS.items()},
        total=lambda d: d["total"].map(m.money), per_leaver=lambda d: d["per_leaver"].map(m.money),
    )[["label", "leavers", *COST_COLUMNS.values(), "total", "per_leaver"]].rename(columns={
        "label": "Department", "leavers": "Leavers", "total": "Total", "per_leaver": "Per leaver"}), key="cost_table")


ui.live(render, key="cost")

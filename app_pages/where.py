"""Where (SQ2): which plants, departments, roles and shifts run well above the rate?"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from lib import charts, metrics as m, ui

ui.page_header("Where", "Which plants, departments, roles and shifts run well above the overall rate?")

SIGNAL_STYLE = {
    "above": ("Significantly above", charts.RED),
    "in line": ("Not significantly different", charts.GREY),
    "below": ("Significantly below", charts.BLUE),
    "small sample": (f"Fewer than {m.MIN_N} people", "rgba(169,168,160,0.45)"),
}


def render(df, snap):
    overall = df["left"].mean()
    dept = m.segments(df, ["department"])
    plant = m.segments(df, ["plant"])
    roles = m.segments(df, ["job_role"])
    cells = m.segments(df, ["plant", "department"])
    ranked = dept[dept["headcount"] >= m.MIN_N].sort_values("rate", ascending=False)
    top_dept = ranked.iloc[0] if len(ranked) else None
    top_plant = plant.sort_values("rate", ascending=False).iloc[0]
    worst_cell = cells[cells["headcount"] >= m.MIN_N].nlargest(1, "excess")
    above = int((roles["signal"] == "above").sum())

    ui.kpi_row([
        {"label": "Highest department rate", "hero": True,
         "value": m.pct(top_dept["rate"]) if top_dept is not None else "–",
         "note": f"{top_dept['label']} · {m.pp(top_dept['vs_selection'])} vs overall" if top_dept is not None else ""},
        {"label": "Highest plant rate", "value": m.pct(top_plant["rate"]),
         "note": f"{top_plant['label']} · {m.pp(top_plant['vs_selection'])} vs overall"},
        {"label": "Roles significantly above", "value": f"{above} of {len(roles)}",
         "note": "95% interval sits wholly above the overall rate"},
        {"label": "Most extra departures", "value": f"+{worst_cell['excess'].iloc[0]:,.0f}" if len(worst_cell) else "–",
         "note": worst_cell["label"].iloc[0] if len(worst_cell) else ""},
    ])

    # ---- department x plant heatmap ----
    ui.section("Turnover by department and plant", f"Each cell is the share who left; the overall rate is {m.pct(overall)}")
    order = dept.sort_values("rate", ascending=False)["department"].tolist()
    plants = sorted(cells["plant"].unique())
    grid = cells.set_index(["department", "plant"])
    z, text, custom = [], [], []
    for d in order:
        zr, tr, cr = [], [], []
        for p in plants:
            if (d, p) in grid.index:
                r = grid.loc[(d, p)]
                small = r["headcount"] < m.MIN_N
                zr.append(np.nan if small else r["rate"])
                tr.append(f"n<{m.MIN_N}" if small else m.pct(r["rate"]))
                cr.append([int(r["leavers"]), int(r["headcount"]), m.pp(r["vs_selection"])])
            else:
                zr.append(np.nan); tr.append(""); cr.append([0, 0, "–"])
        z.append(zr); text.append(tr); custom.append(cr)
    fig = go.Figure(go.Heatmap(
        z=z, x=[m.pretty(p) for p in plants], y=[m.pretty(d) for d in order], text=text, customdata=custom,
        texttemplate="%{text}", colorscale=charts.SEQUENTIAL, xgap=2, ygap=2,
        colorbar=dict(title="", tickformat=".0%", thickness=10, len=0.9),
        hovertemplate="<b>%{y} · %{x}</b><br>%{z:.1%} turnover<br>%{customdata[0]:,} of %{customdata[1]:,} left"
                      "<br>%{customdata[2]} vs overall<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top", showgrid=False)
    charts.show(charts.style(fig, 40 * len(order) + 70, legend=False), "where_heatmap")

    left, right = st.columns([1.25, 1], gap="large")

    # ---- roles with confidence intervals ----
    with left:
        ui.section("Job roles against the overall rate",
                   "Dot = role's turnover rate; line = its 95% confidence interval")
        r = roles.sort_values("rate", ascending=True)
        fig = go.Figure()
        for signal, (name, colour) in SIGNAL_STYLE.items():
            s = r[r["signal"] == signal]
            fig.add_scatter(
                x=s["rate"], y=s["label"], mode="markers", name=name,
                marker=dict(size=10, color=colour, line=dict(width=2, color="rgba(255,255,255,0.9)")),
                error_x=dict(type="data", symmetric=False, array=s["high"] - s["rate"], arrayminus=s["rate"] - s["low"],
                             color=colour, thickness=2, width=0),
                customdata=np.column_stack([s["leavers"], s["headcount"], s["low"], s["high"]]) if len(s) else None,
                hovertemplate=("<b>%{y}</b><br>%{x:.1%} turnover (95% CI %{customdata[2]:.1%}–%{customdata[3]:.1%})"
                               "<br>%{customdata[0]:,} of %{customdata[1]:,} left<extra></extra>"),
            )
        fig.add_vline(x=overall, line_width=1, line_color=charts.GREY)
        fig.add_annotation(x=overall, y=1, yref="paper", text=f"overall {m.pct(overall)}", showarrow=False,
                           xanchor="left", yanchor="bottom", xshift=4, font=dict(size=12))
        fig.update_yaxes(categoryorder="array", categoryarray=r["label"].tolist(), showgrid=False)
        fig.update_xaxes(tickformat=".0%")
        charts.show(charts.style(fig, charts.bar_rows_height(len(r), row=24, extra=80)), "where_roles")

    # ---- shifts ----
    with right:
        shifts = m.segments(df[df["shift"] != "standard_business_hours"], ["department", "shift"])
        ui.section("Shifts", "Turnover by shift in the departments that run day, evening and night shifts")
        fig = go.Figure()
        shift_order = [s for s in ("day", "evening", "night") if s in set(shifts["shift"])]
        for colour, d in zip((charts.BLUE, charts.ORANGE, charts.AQUA), sorted(shifts["department"].unique())):
            s = shifts[shifts["department"] == d].set_index("shift").reindex(shift_order)
            fig.add_bar(x=[m.pretty(x) for x in shift_order], y=s["rate"], name=m.pretty(d), marker_color=colour,
                        text=[m.pct(v) for v in s["rate"]], textposition="outside", cliponaxis=False,
                        customdata=np.column_stack([s["leavers"].fillna(0), s["headcount"].fillna(0)]),
                        hovertemplate=f"<b>{m.pretty(d)} · %{{x}}</b><br>%{{y:.1%}} turnover"
                                      "<br>%{customdata[0]:,.0f} of %{customdata[1]:,.0f} left<extra></extra>")
        fig.update_layout(barmode="group", bargap=0.45, bargroupgap=0.12)
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        charts.show(charts.style(fig, 340), "where_shifts")
        if shifts.empty:
            ui.footnote("No shift-based departments in the current selection.")

    ui.table("Show every role with its confidence interval", roles.sort_values("rate", ascending=False).assign(
        rate=lambda d: d["rate"].map(m.pct), low=lambda d: d["low"].map(m.pct), high=lambda d: d["high"].map(m.pct),
        vs_selection=lambda d: d["vs_selection"].map(m.pp),
    )[["label", "headcount", "leavers", "rate", "low", "high", "vs_selection", "signal"]].rename(columns={
        "label": "Role", "headcount": "Employees", "leavers": "Left", "rate": "Turnover", "low": "95% CI low",
        "high": "95% CI high", "vs_selection": "vs overall", "signal": "Signal"}), key="where_table")


ui.live(render, key="where")

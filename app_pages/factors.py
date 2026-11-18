"""Factors (SQ3): how do leavers differ from stayers?"""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from lib import charts, metrics as m, ui

ui.page_header("Factors", "How do leavers differ from stayers on satisfaction, workload, pay and training?")

PICKABLE = {k: m.FACTORS[k][0] for k in m.BINS}


def render(df, snap):
    es = m.effect_sizes(df)
    tiles = []
    for i, row in enumerate(es.head(4).itertuples()):
        tiles.append({"label": f"{row.label}: leavers vs stayers", "value": f"{row.leavers_fmt} vs {row.stayers_fmt}",
                      "note": f"{row.size} difference (d = {row.d:+.2f})", "hero": i == 0})
    while len(tiles) < 4:
        tiles.append({"label": "–", "value": "–", "note": ""})
    ui.kpi_row(tiles)

    # ---- effect sizes ----
    ui.section("What separates leavers from stayers",
               "Standardised difference (Cohen's d) between the two groups, largest first")
    e = es.iloc[::-1]  # largest at the top
    fig = go.Figure()
    for name, colour, mask in (("Leavers higher", charts.RED, e["d"] >= 0), ("Leavers lower", charts.BLUE, e["d"] < 0)):
        s = e[mask]
        fig.add_bar(y=s["label"], x=s["d"], orientation="h", name=name, marker_color=colour,
                    text=[f"{d:+.2f}" for d in s["d"]], textposition="outside", cliponaxis=False,
                    customdata=np.column_stack([s["leavers_fmt"], s["stayers_fmt"], s["size"].astype(str)]) if len(s) else None,
                    hovertemplate="<b>%{y}</b><br>Leavers %{customdata[0]} · stayers %{customdata[1]}"
                                  "<br>d = %{x:+.2f} (%{customdata[2]})<extra></extra>")
    fig.update_layout(barmode="relative", bargap=0.38)
    fig.update_yaxes(categoryorder="array", categoryarray=e["label"].tolist(), showgrid=False)
    lim = max(0.9, float(es["d"].abs().max()) * 1.25) if len(es) else 1
    fig.update_xaxes(range=[-lim, lim], zeroline=True, zerolinecolor=charts.GREY, zerolinewidth=1)
    charts.show(charts.style(fig, charts.bar_rows_height(len(e), row=32, extra=70)), "factors_effects")
    ui.footnote("Rule of thumb: |d| below 0.2 is negligible, 0.5 is medium, 0.8 or more is large. "
                "A difference is not proof of cause.")

    left, right = st.columns(2, gap="large")

    # ---- rate across a factor's range ----
    with left:
        ui.section("Turnover across the range", "Pick a factor to see the turnover rate at each level")
        pick = st.selectbox("Factor", list(PICKABLE), format_func=PICKABLE.get, key="factors_pick",
                            label_visibility="collapsed")
        b = m.rate_by_bins(df, pick)
        fig = go.Figure()
        fig.add_bar(x=b["label"], y=b["rate"], marker_color=[charts.GREY if s else charts.BLUE for s in b["small"]],
                    customdata=np.column_stack([b["leavers"], b["headcount"]]),
                    hovertemplate="<b>%{x}</b><br>%{y:.1%} turnover<br>%{customdata[0]:,} of %{customdata[1]:,} left"
                                  "<extra></extra>")
        fig.add_hline(y=df["left"].mean(), line_width=1, line_color=charts.GREY)
        fig.update_layout(bargap=0.35)
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        fig.update_xaxes(type="category", title=None)
        charts.show(charts.style(fig, 320, legend=False), "factors_range")
        ui.footnote(f"Grey bars cover fewer than {m.MIN_N} people. The line is the overall rate.")

    # ---- satisfaction x evaluation map ----
    with right:
        ui.section("Who leaves: satisfaction × last evaluation",
                   "Each cell is a group of employees; darker means more of them left")
        g = m.satisfaction_evaluation_grid(df)
        pivot = g.pivot(index="e_mid", columns="s_mid", values="rate")
        counts = g.pivot(index="e_mid", columns="s_mid", values="headcount")
        leavers = g.pivot(index="e_mid", columns="s_mid", values="leavers")
        z = pivot.where(counts >= 15)
        fig = go.Figure(go.Heatmap(
            z=z.values, x=[f"{v:.2f}" for v in pivot.columns], y=[f"{v:.2f}" for v in pivot.index],
            customdata=np.dstack([leavers.values, counts.values]), colorscale=charts.SEQUENTIAL, zmin=0, zmax=1,
            xgap=2, ygap=2, colorbar=dict(title="", tickformat=".0%", thickness=10, len=0.9),
            hovertemplate="Satisfaction ≈ %{x} · evaluation ≈ %{y}<br><b>%{z:.0%}</b> left"
                          "<br>%{customdata[0]:,} of %{customdata[1]:,}<extra></extra>",
        ))
        fig.update_xaxes(title="Satisfaction level", showgrid=False)
        fig.update_yaxes(title="Last evaluation", showgrid=False)
        charts.show(charts.style(fig, 360, legend=False), "factors_map")
        ui.footnote("Cells with fewer than 15 people are left blank.")

    ui.table("Show the leaver vs stayer comparison", es.assign(d=es["d"].round(2))[
        ["label", "leavers_fmt", "stayers_fmt", "d", "size"]].rename(columns={
        "label": "Factor", "leavers_fmt": "Leavers (mean)", "stayers_fmt": "Stayers (mean)", "d": "Cohen's d",
        "size": "Size"}), key="factors_table")


ui.live(render, key="factors")

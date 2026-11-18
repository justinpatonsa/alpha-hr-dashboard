"""Overview (SQ1): how many employees left in 2025, at what rate, and when?"""
import plotly.graph_objects as go
import streamlit as st

from lib import charts, metrics as m, ui

ui.page_header("Overview", "How many employees left in 2025, at what rate, and when did they go?")


def render(df, snap):
    h = m.headline(df)
    vol_share = h["voluntary"] / h["leavers"] if h["leavers"] else None
    ui.kpi_row([
        {"label": "Turnover rate, 2025", "value": m.pct(h["rate"]), "hero": True,
         "note": f"{m.num(h['leavers'])} of {m.num(h['headcount'])} baseline employees left"},
        {"label": "Voluntary turnover", "value": m.pct(h["voluntary_rate"]),
         "note": f"{m.num(h['voluntary'])} chose to leave · {m.pct(vol_share, 0)} of all leavers"},
        {"label": "High performers lost", "value": m.num(h["high_performers_lost"]),
         "note": "leavers rated 0.80 or higher at their last evaluation"},
        {"label": "Estimated replacement cost", "value": m.money(h["cost"]),
         "note": f"about {m.money(h['cost_per_leaver'])} per leaver (client estimates)"},
    ])

    # ---- departures by month ----
    mon = m.monthly(df)
    ui.section("Departures by month", "Leavers in each month of 2025, voluntary and involuntary")
    fig = go.Figure()
    fig.add_bar(x=mon["label"], y=mon["voluntary"], name="Voluntary", marker_color=charts.BLUE,
                hovertemplate="<b>%{y:,}</b> voluntary<extra></extra>")
    fig.add_bar(x=mon["label"], y=mon["involuntary"], name="Involuntary", marker_color=charts.ORANGE,
                hovertemplate="<b>%{y:,}</b> involuntary<extra></extra>")
    fig.add_scatter(x=mon["label"], y=mon["leavers"], mode="none", showlegend=False,
                    customdata=mon["monthly_rate"],
                    hovertemplate="<b>%{y:,}</b> in total · %{customdata:.1%} of the baseline<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.62, hovermode="x unified")
    fig.update_yaxes(tickformat=",", rangemode="tozero")
    charts.show(charts.style(fig, 320), "overview_monthly")

    left, right = st.columns(2, gap="large")

    # ---- cumulative turnover ----
    with left:
        ui.section("Cumulative turnover", "Share of the baseline workforce that had left by each month end")
        fig = go.Figure()
        fig.add_scatter(x=mon["label"], y=mon["cumulative_rate"], mode="lines+markers", name="Cumulative",
                        line=dict(color=charts.BLUE, width=2), marker=dict(size=7, color=charts.BLUE),
                        customdata=mon["leavers"].cumsum(),
                        hovertemplate="%{x}: <b>%{y:.1%}</b> · %{customdata:,} leavers so far<extra></extra>")
        end = mon.iloc[-1]
        fig.add_annotation(x=end["label"], y=end["cumulative_rate"], text=m.pct(end["cumulative_rate"]),
                           showarrow=False, xanchor="right", yanchor="bottom", yshift=8, font=dict(size=13))
        fig.update_yaxes(tickformat=".0%", rangemode="tozero")
        charts.show(charts.style(fig, 300, legend=False), "overview_cumulative")

    # ---- excess departures ----
    with right:
        seg = m.segments(df, ["plant", "department"])
        top = seg[seg["headcount"] >= m.MIN_N].nlargest(6, "excess")
        ui.section("Where the extra departures are",
                   "Plant × department segments that lost the most people beyond the overall rate")
        fig = go.Figure()
        fig.add_bar(y=top["label"], x=top["excess"], orientation="h", marker_color=charts.BLUE,
                    text=[f"+{e:,.0f}  ·  {m.pct(r)}" for e, r in zip(top["excess"], top["rate"])],
                    textposition="outside", cliponaxis=False,
                    customdata=top[["leavers", "expected", "headcount"]].values,
                    hovertemplate=("<b>%{y}</b><br>%{customdata[0]:,} left vs %{customdata[1]:,.0f} expected"
                                   "<br>of %{customdata[2]:,} employees<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(showgrid=False, showticklabels=False,
                         range=[0, float(top["excess"].max()) * 1.6 if len(top) else 1])
        fig.update_layout(bargap=0.4)
        charts.show(charts.style(fig, 300, legend=False), "overview_excess")
        ui.footnote(f"Expected = segment headcount × the selection's turnover rate ({m.pct(h['rate'])}). "
                    f"Segments under {m.MIN_N} people are left out.")

    ui.table("Show the monthly numbers", mon.assign(
        monthly_rate=mon["monthly_rate"].map(m.pct), cumulative_rate=mon["cumulative_rate"].map(m.pct),
    )[["label", "voluntary", "involuntary", "leavers", "monthly_rate", "cumulative_rate"]].rename(columns={
        "label": "Month", "voluntary": "Voluntary", "involuntary": "Involuntary", "leavers": "Total",
        "monthly_rate": "Share of baseline", "cumulative_rate": "Cumulative turnover"}), key="overview_table")


ui.live(render, key="overview")

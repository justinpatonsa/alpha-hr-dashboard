"""Employee voice (SQ4): what do the survey and exit interviews say, and who do they cover?"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from lib import charts, metrics as m, ui
from lib.data import SCORE_COLUMNS

ui.page_header("Employee voice", "What do the December 2024 survey and the exit interviews say, and who do they cover?")


def render(df, snap):
    h = m.headline(df)
    leavers, stayers = df[df["left"]], df[~df["left"]]
    means = {label: df.loc[df["surveyed"], col].mean() for col, label in SCORE_COLUMNS.items()}
    lowest = min(means, key=lambda k: means[k] if not np.isnan(means[k]) else 9)
    reasons = m.reason_counts(df)
    top_reason = reasons.iloc[0] if len(reasons) else None
    vol_cov = df.loc[df["voluntary"], "interviewed"].mean()
    inv_cov = df.loc[df["involuntary"], "interviewed"].mean()

    ui.kpi_row([
        {"label": "Survey response", "value": m.pct(h["survey_rate"]), "hero": True,
         "note": f"{m.pct(leavers['surveyed'].mean(), 0)} of leavers · {m.pct(stayers['surveyed'].mean(), 0)} of stayers"},
        {"label": "Exit-interview coverage", "value": m.pct(h["interview_rate"]),
         "note": f"{m.pct(vol_cov, 0)} of voluntary · {m.pct(inv_cov, 0)} of involuntary leavers"},
        {"label": "Lowest-rated question", "value": f"{means[lowest]:.2f} / 5", "note": lowest},
        {"label": "Top reason for leaving", "value": m.pct(top_reason["share"]) if top_reason is not None else "–",
         "note": f"{top_reason['label']} · {top_reason['leavers']:,} leavers" if top_reason is not None else ""},
    ])

    # ---- turnover by survey answer (small multiples) ----
    ui.section("Turnover by survey answer", "Share of respondents who later left, by the score they gave (1 = worst, 5 = best)")
    sc = m.rate_by_score(df)
    questions = list(SCORE_COLUMNS.values())
    fig = make_subplots(rows=1, cols=4, shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=[q.replace(" ", "<br>", 1) for q in questions])  # two lines fit narrow screens
    for i, q in enumerate(questions, start=1):
        s = sc[sc["question"] == q]
        fig.add_bar(x=s["score"], y=s["rate"], marker_color=charts.BLUE, row=1, col=i, showlegend=False,
                    customdata=np.column_stack([s["leavers"], s["headcount"]]),
                    hovertemplate=f"<b>{q}</b>: score %{{x}}<br>%{{y:.1%}} left"
                                  "<br>%{customdata[0]:,} of %{customdata[1]:,}<extra></extra>")
    fig.update_layout(bargap=0.4)
    fig.update_xaxes(tickmode="array", tickvals=[1, 2, 3, 4, 5])
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_annotations(font_size=13)
    fig = charts.style(fig, 320, legend=False)
    fig.update_layout(margin=dict(t=52))
    charts.show(fig, "voice_scores")

    left, right = st.columns(2, gap="large")

    # ---- did the survey see it coming? ----
    with left:
        ui.section("Did the survey see it coming?",
                   "Voluntary leavers' score on the matching question: those who gave that reason vs the rest")
        al = m.reason_alignment(df)
        labels = [f"{r} → {q}" for r, q in zip(al["reason"], al["question"])]
        fig = go.Figure()
        fig.add_bar(y=labels, x=al["others"], orientation="h", name="Other voluntary leavers", marker_color=charts.BLUE,
                    text=[f"{v:.2f}" for v in al["others"]], textposition="outside", cliponaxis=False,
                    customdata=al["n_others"], hovertemplate="%{x:.2f} · %{customdata:,} leavers<extra></extra>")
        fig.add_bar(y=labels, x=al["cited"], orientation="h", name="Gave this reason", marker_color=charts.ORANGE,
                    text=[f"{v:.2f}" for v in al["cited"]], textposition="outside", cliponaxis=False,
                    customdata=al["n_cited"], hovertemplate="%{x:.2f} · %{customdata:,} leavers<extra></extra>")
        fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, hovermode="y unified")
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(range=[0, 5.4], dtick=1)
        charts.show(charts.style(fig, 340), "voice_alignment")
        ui.footnote("Mean survey score (1–5), among voluntary leavers who were both surveyed and interviewed. "
                    "A lower orange bar means the survey flagged the problem before they left.")

    # ---- coverage: whose voice is missing? ----
    with right:
        ui.section("Whose voice is missing?", "Survey response (everyone) and exit-interview coverage (leavers) by department")
        cov = df.groupby("department").agg(headcount=("employee_id", "size"), surveyed=("surveyed", "mean"))
        cov = cov.join(df[df["left"]].groupby("department").agg(leavers=("employee_id", "size"),
                                                                interviewed=("interviewed", "mean")))
        cov = cov.sort_values("surveyed", ascending=False)
        labels = [m.pretty(d) for d in cov.index]
        fig = go.Figure()
        fig.add_bar(y=labels, x=cov["surveyed"], orientation="h", name="Answered the survey", marker_color=charts.BLUE,
                    customdata=cov["headcount"], hovertemplate="%{x:.0%} of %{customdata:,} employees<extra></extra>")
        fig.add_bar(y=labels, x=cov["interviewed"], orientation="h", name="Leavers interviewed", marker_color=charts.ORANGE,
                    customdata=cov["leavers"].fillna(0), hovertemplate="%{x:.0%} of %{customdata:,.0f} leavers<extra></extra>")
        fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.06, hovermode="y unified")
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(tickformat=".0%", range=[0, 1])
        charts.show(charts.style(fig, charts.bar_rows_height(len(cov), row=34, extra=70)), "voice_coverage")
        ui.footnote("Low coverage means the survey and exit interviews say less about that group.")

    # ---- reasons by department (full width) ----
    ui.section("Reasons by department", "Share of each department's interviewed leavers giving each main reason")
    rb = m.reasons_by(df, "department")
    if len(rb):
        n = rb.pop("_n")
        cols = rb.sum().sort_values(ascending=False).index.tolist()
        rows = n.sort_values(ascending=False).index.tolist()
        rb = rb.loc[rows, cols]
        fig = go.Figure(go.Heatmap(
            z=rb.values, x=[m.pretty(c) for c in cols], y=[f"{m.pretty(r)} ({n[r]:,})" for r in rows],
            text=[[f"{v:.0%}" for v in row] for row in rb.values], texttemplate="%{text}",
            colorscale=charts.SEQUENTIAL, xgap=2, ygap=2, zmin=0,
            colorbar=dict(title="", tickformat=".0%", thickness=10, len=0.9),
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1%}<extra></extra>",
        ))
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(side="top", showgrid=False)
        charts.show(charts.style(fig, 40 * len(rows) + 70, legend=False), "voice_reasons")
    ui.footnote("Reasons are what leavers reported, not measured causes. Numbers in brackets are interviews.")

    ui.table("Show exit reasons", reasons.assign(share=reasons["share"].map(m.pct),
                                                  separation_type=reasons["separation_type"].map(m.pretty))[
        ["label", "separation_type", "leavers", "share"]].rename(columns={
        "label": "Reason", "separation_type": "Type", "leavers": "Leavers", "share": "Share of interviews"}),
        key="voice_table")


ui.live(render, key="voice")

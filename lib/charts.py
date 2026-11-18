"""Chart helpers with the dashboard's palette and chrome baked in (Plotly).

Colours are the validated dataviz defaults: categorical blue / orange / aqua, a one-hue blue
sequential ramp for rates, and blue <-> red with a grey midpoint for above / below.
"""
import plotly.graph_objects as go
import streamlit as st

BLUE = "#2a78d6"      # primary series · voluntary · stayed · "below"
ORANGE = "#eb6834"    # second series · involuntary · left
AQUA = "#1baf7a"      # third series
RED = "#e34948"       # "above the selection rate"
GREY = "#a9a8a0"      # "in line" / small samples
SEQUENTIAL = [[0.0, "#eef4fc"], [0.15, "#cde2fb"], [0.35, "#86b6ef"], [0.6, "#3987e5"], [0.8, "#1c5cab"], [1.0, "#0d366b"]]
GRID = "rgba(128, 128, 120, 0.18)"
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'


def style(fig: go.Figure, height: int, legend: bool = True) -> go.Figure:
    """Shared chrome. Fixed height so a refresh never changes the page layout."""
    fig.update_layout(
        height=height,
        margin=dict(l=4, r=16, t=34 if legend else 8, b=4),
        font=dict(family=FONT, size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend=dict(orientation="h", x=0, xanchor="left", y=1.0, yanchor="bottom", title_text="", font=dict(size=12.5),
                    traceorder="normal"),
        hoverlabel=dict(font=dict(family=FONT, size=13), align="left"),
        uirevision="keep",            # keep hover/legend state across refreshes
        transition=dict(duration=0),  # no animation on refresh
    )
    fig.update_xaxes(zeroline=False, showline=False, gridcolor=GRID, gridwidth=1, fixedrange=True, ticks="", automargin=True)
    fig.update_yaxes(zeroline=False, showline=False, gridcolor=GRID, gridwidth=1, fixedrange=True, ticks="", automargin=True)
    return fig


def bar_rows_height(n: int, row: int = 30, extra: int = 50) -> int:
    """Height for a horizontal bar chart: about 18 px bars with air between them."""
    return max(180, n * row + extra)


def show(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, key=key, width="stretch", theme="streamlit",
                    config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False})

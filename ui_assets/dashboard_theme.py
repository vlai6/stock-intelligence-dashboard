"""Consistent midnight-navy styling and page-header navigation for all three pages."""
from __future__ import annotations

from html import escape
import streamlit as st

BLUE_SERIES = ('#41A5FF', '#668BFF', '#36C1E8', '#268AD1', '#98BFFE', '#74C8F7')

PAGES = (
    ('stock', 'Stock Intelligence', 'pages/0_Stock_Intelligence.py', '📊'),
    ('sentiment', 'News Sentiment', 'pages/2_News_Sentiment.py', '📈'),
    ('general', 'General News Screen', 'pages/1_News_Screen.py', '📰'),
)


def style_blue_figure(figure):
    """Style Plotly charts without overwriting meaningful red/green series."""
    if figure is None:
        return figure
    figure.update_layout(
        template='plotly_dark',
        colorway=list(BLUE_SERIES),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, Segoe UI, Arial, sans-serif', color='#DEEAF7'),
        hoverlabel=dict(bgcolor='#101F32', font_color='#F4F9FF'),
        legend=dict(bgcolor='rgba(0,0,0,0)'),
    )
    figure.update_xaxes(gridcolor='rgba(69,120,176,.14)', zerolinecolor='#152A44')
    figure.update_yaxes(gridcolor='rgba(69,120,176,.14)', zerolinecolor='#152A44')
    for i, trace in enumerate(figure.data):
        color = BLUE_SERIES[i % len(BLUE_SERIES)]
        if trace.type == 'scatter':
            if trace.line.color is None:
                trace.line.color = color
            if trace.mode and 'markers' in trace.mode and trace.marker.color is None:
                trace.marker.color = color
        elif trace.type == 'bar' and trace.marker.color is None:
            trace.marker.color = color
    return figure


def apply_dashboard_theme():
    """Same background, font family, inputs, and controls for all three pages."""
    st.markdown('''
<style>
:root {
  --si-bg:#030711; --si-sidebar:#060C16; --si-card:#071321;
  --si-card-alt:#0B1A2D; --si-border:#172C43;
  --si-accent:#4EB7FF; --si-text:#E9F2FD; --si-muted:#A4B6CA;
}
html, body, [data-testid="stApp"], .stApp,
[data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background:var(--si-bg) !important;
}
html, body, .stApp, .stApp *, [data-testid="stSidebar"] * {
  font-family:Inter,"Segoe UI",Arial,sans-serif;
}
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {
  background:var(--si-sidebar) !important;
}
[data-testid="stMainBlockContainer"] {max-width:1900px;}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {color:#D9E7F4;}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {color:#EFF7FF; letter-spacing:-.02em;}
[data-testid="stCaptionContainer"] p {color:var(--si-muted) !important;}
.st-key-si_header_stock,
.st-key-si_header_sentiment,
.st-key-si_header_general {padding:0 0 .5rem;}
.si-page-title {font-family:Inter,"Segoe UI",Arial,sans-serif !important;
  margin:0 !important;padding:0 !important;font-size:2.05rem !important;
  font-weight:750 !important;letter-spacing:-.035em !important;
  line-height:1.24 !important;color:#F2F8FF !important;}
.si-page-subtitle {font-size:.93rem;line-height:1.42;color:#A5BBD0;margin:.36rem 0 .65rem;}
[class*="st-key-si_header_"] [data-testid="stPageLink"] a {
  display:flex;align-items:center;justify-content:center;min-height:44px;
  background:#091B2D;border:1px solid #21466D;border-radius:10px;
  color:#BDE3FF !important;text-decoration:none !important;
  font-size:.89rem !important;font-weight:650;padding:8px 9px;
  white-space:normal;text-align:center;
  transition:background .14s,border-color .14s;
}
[class*="st-key-si_header_"] [data-testid="stPageLink"] a:hover {
  background:#102B46;border-color:#4EB7FF;color:#FFFFFF !important;
}
[class*="st-key-si_header_"] [data-testid="stPageLink"] a * {color:inherit !important;}
[data-testid="stVerticalBlockBorderWrapper"]:has(> [data-testid="stVerticalBlock"]),
[data-testid="stForm"], [data-testid="stExpander"], [data-testid="stPopoverBody"] {
  border-color:var(--si-border) !important;border-radius:12px;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(> [data-testid="stVerticalBlock"]),
[data-testid="stForm"], [data-testid="stExpander"], [data-testid="stPopoverBody"] {
  background:rgba(8,20,35,.52);
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-baseweb="select"]>div,
[data-testid="stTextArea"] textarea {
  background:#0C1B2A !important;color:#EBF3FE !important;border-color:#254463 !important;
}
[data-testid="stWidgetLabel"] p {color:#C6DBED !important;}
[data-testid="stButton"] button,
[data-testid="stFormSubmitButton"] button,
[data-testid="stPopover"] button,
[data-testid="stDownloadButton"] button {
  border-color:#244664;border-radius:10px;font-weight:630;
}
[data-testid="stButton"] button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"] {
  background:#175C9B !important;color:white !important;border-color:#3084C8 !important;
}
[data-testid="stButton"] button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
  background:#1E79BC !important;border-color:#50B6FC !important;
}
[data-testid="stButton"] button[kind="secondary"],
[data-testid="stPopover"] button {color:#BBDFFD;background:rgba(10,28,48,.8);}
[data-testid="stButton"] button[kind="secondary"]:hover,
[data-testid="stPopover"] button:hover {color:white;border-color:#48A9ED;}
[data-testid="stMetric"] {background:rgba(7,23,40,.75);padding:12px;
  border:1px solid #1B344E;border-radius:11px;}
[data-testid="stMetricValue"] {color:#C4E8FF;}
[data-testid="stDataFrame"], [data-testid="stTable"] {border-color:#23445E;}
hr {border-color:#19324C !important;}
a {color:#7EC9FF;}
@media (max-width:760px){.si-page-title{font-size:1.7rem !important;}}
</style>
''', unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str = '', current: str = 'stock'):
    """Identical header row on every page, with the *other two* pages at right."""
    targets = [page for page in PAGES if page[0] != current]
    with st.container(key=f'si_header_{current}'):
        left, right = st.columns([1.25, 1.4], gap='large', vertical_alignment='center')
        with left:
            st.markdown(f'<h1 class="si-page-title">{escape(title)}</h1>', unsafe_allow_html=True)
            if subtitle:
                st.markdown(f'<div class="si-page-subtitle">{escape(subtitle)}</div>', unsafe_allow_html=True)
        with right:
            buttons = st.columns(2, gap='small', vertical_alignment='center')
            for col, (_slug, label, path, icon) in zip(buttons, targets):
                with col:
                    st.page_link(path, label=label, icon=icon, use_container_width=True)

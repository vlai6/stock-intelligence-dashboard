"""Consistent midnight-navy styling and page-header navigation for all three pages."""

from __future__ import annotations



from html import escape
from pathlib import Path
from functools import lru_cache
import base64

import streamlit as st



BLUE_SERIES = ('#41A5FF', '#668BFF', '#36C1E8', '#268AD1', '#98BFFE', '#74C8F7')



PAGES = (
    ('philosophy', 'Portfolio Analysis', 'pages/00_Investment_Philosophy.py', '📚'),
    ('general', 'News Screener', 'pages/1_News_Screen.py', '📰'),
    ('scanner', 'Regression Scanner', 'regression_scanner/app.py', '📉'),
    ('stock', 'Metrics & Competition', 'pages/0_Stock_Intelligence.py', '📊'),
    ('sentiment', 'Recent Sentiment', 'pages/2_News_Sentiment.py', '📈'),
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

        font=dict(family='Inter, Segoe UI, Arial, sans-serif', color='#DEEAF7', size=13),

        hoverlabel=dict(bgcolor='#101F32', font_color='#F4F9FF', font_size=14),

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





@lru_cache(maxsize=1)
def _earth_image_data_url() -> str:
    """Serve the bundled AI-enhanced Earth without external CDN requests.

    The optimized 1920x1080 WebP image is approximately 11 KB. Reusing a
    cached data URL makes Streamlit Cloud deploys deterministic and avoids
    static-file route configuration differences.
    """
    image = Path(__file__).resolve().parent / "assets" / "earth-enhanced-1920.webp"
    payload = image.read_bytes()
    if not payload.startswith(b"RIFF") or payload[8:12] != b"WEBP":
        raise ValueError("Invalid bundled Earth WebP background")
    return "data:image/webp;base64," + base64.b64encode(payload).decode("ascii")


def apply_dashboard_theme():

    """Same background, font family, inputs, and controls for all five pages."""

    st.markdown('''

<style>

:root {

  --si-bg:#030711; --si-sidebar:#060C16; --si-card:#071321;

  --si-card-alt:#0B1A2D; --si-border:#172C43;

  --si-accent:#4EB7FF; --si-text:#E9F2FD; --si-muted:#B9CDE0;
  /* Separate clickable actions from muted multi-select/chip states. */
  --si-action-bg:rgba(27,96,149,.92);
  --si-action-hover:rgba(40,119,173,.96);
  --si-action-border:#4A92BD;
  --si-selection-bg:rgba(13,38,57,.94);
  --si-selection-border:rgba(78,118,146,.42);
  /* Glassy surfaces reveal the Earth background without fading content. */
  --si-panel-glass:rgba(5,17,32,.65);
  --si-input-glass:rgba(7,22,39,.66);
  --si-popover-glass:rgba(7,21,39,.87);
  --si-glass-blur:blur(14px);
  --si-glass-border:rgba(87,145,190,.36);
  /* Shared type roles across every Streamlit section and embedded HTML card. */
  --si-type-page:2rem; --si-type-section:1.5rem;
  --si-type-subsection:1.3rem; --si-type-small-heading:1.12rem;
  --si-type-body:.95rem; --si-type-data:.9rem;
  --si-type-label:.875rem; --si-type-caption:.8rem;
  --si-type-nav:.85rem; --si-type-metric:1.4rem;
  --si-type-ticker:1.2rem;

}

html, body, [data-testid="stApp"], .stApp,

[data-testid="stAppViewContainer"], [data-testid="stHeader"] {

  background:var(--si-bg) !important;

}

/* Bundled AI-enhanced night-side Earth, based on the user-selected image.
   Keep the near-black fallback and let translucent glass cards reveal it. */
[data-testid="stAppViewContainer"] {
  background-color:var(--si-bg) !important;
  background-image:
    linear-gradient(180deg, rgba(3,7,17,.12) 0%, rgba(3,7,17,.22) 100%),
    url("__SI_EARTH_IMAGE_DATA_URI__") !important;
  background-position:center center !important;
  background-size:cover !important;
  background-repeat:no-repeat !important;
  background-attachment:fixed !important;
}
[data-testid="stMain"] {
  background:transparent !important;
}
@media (max-width:760px) {
  [data-testid="stAppViewContainer"] {
    background-attachment:scroll !important;
    background-position:center top !important;
  }
}

html, body, .stApp, [data-testid="stSidebar"] {

  font-family:Inter,"Segoe UI",Arial,sans-serif;

}

[data-testid="stSidebar"], [data-testid="stSidebarContent"] {

  background:var(--si-sidebar) !important;

}

[data-testid="stMainBlockContainer"] {max-width:1900px;}

/* Match size by semantic role, independent of which page renders it. */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
  color:#D9E7F4; font-size:var(--si-type-body); line-height:1.55;
}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {
  color:#EFF7FF; letter-spacing:-.02em; line-height:1.26; font-weight:720;
}
[data-testid="stMarkdownContainer"] h1 {font-size:var(--si-type-page);}
[data-testid="stMarkdownContainer"] h2 {font-size:var(--si-type-section);}
[data-testid="stMarkdownContainer"] h3 {font-size:var(--si-type-subsection);}
[data-testid="stMarkdownContainer"] h4 {font-size:var(--si-type-small-heading);}
[data-testid="stCaptionContainer"] p {
  color:var(--si-muted) !important;
  font-size:var(--si-type-caption) !important; line-height:1.45;
}
[data-testid="stWidgetLabel"] p,
label[data-testid="stWidgetLabel"] p,
[data-testid="stMetricLabel"] p {
  font-size:var(--si-type-label) !important; line-height:1.35 !important;
}
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-baseweb="select"] input,
[data-baseweb="select"] [role="combobox"] {
  font-size:var(--si-type-body) !important;
}
[data-testid="stButton"] button,
[data-testid="stFormSubmitButton"] button,
[data-testid="stDownloadButton"] button,
[data-testid="stPopover"] button,
[data-testid="stSegmentedControl"] button {
  font-size:var(--si-type-label) !important;
}
[data-testid="stDataFrame"], [data-testid="stTable"],
[data-testid="stDataEditor"] {font-size:var(--si-type-data);}
[data-testid="stMetricValue"] {
  font-size:var(--si-type-metric) !important; line-height:1.18 !important;
}

.st-key-si_header_stock,

.st-key-si_header_sentiment,

.st-key-si_header_general,
.st-key-si_header_philosophy,
.st-key-si_header_scanner {padding:0 0 .5rem;}

.si-page-title {font-family:Inter,"Segoe UI",Arial,sans-serif !important;

  margin:0 !important;padding:0 !important;font-size:var(--si-type-page) !important;

  font-weight:750 !important;letter-spacing:-.035em !important;

  line-height:1.24 !important;color:#F2F8FF !important;}

.si-page-subtitle {font-size:var(--si-type-body);line-height:1.45;color:#A5BBD0;margin:.36rem 0 .65rem;}

/* Remove only Streamlit's auto-generated heading permalink controls.
   Section headings and their deep-link IDs remain intact. Do not hide
   real article links, source citations, or deliberate page navigation. */
[data-testid="stHeaderActionElements"] {
  display: none !important;
  pointer-events: none !important;
}

/* Remove Streamlit's in-app top-right toolbar controls, but leave the header
   container itself intact: the sticky scroll navigator uses its height.
   Community Cloud chrome outside the app frame is controlled by the host. */
[data-testid="stToolbar"],
[data-testid="stAppToolbar"],
[data-testid="stMainMenu"],
[data-testid="stDeployButton"],
#MainMenu {
  display: none !important;
  pointer-events: none !important;
}


[class*="st-key-si_header_"] [data-testid="stPageLink"] a {

  display:flex;align-items:center;justify-content:center;min-height:44px;

  background:rgba(9,27,45,.48);border:1px solid #21466D;border-radius:10px;

  color:#BDE3FF !important;text-decoration:none !important;

  font-size:var(--si-type-label) !important;font-weight:650;padding:8px 9px;

  white-space:normal;text-align:center;

  transition:background .14s,border-color .14s;

}

[class*="st-key-si_header_"] [data-testid="stPageLink"] a:hover {

  background:rgba(16,43,70,.75);border-color:#4EB7FF;color:#FFFFFF !important;

}

[class*="st-key-si_header_"] [data-testid="stPageLink"] a * {color:inherit !important;}

[data-testid="stVerticalBlockBorderWrapper"]:has(> [data-testid="stVerticalBlock"]),

[data-testid="stForm"], [data-testid="stExpander"], [data-testid="stPopoverBody"] {

  border-color:var(--si-border) !important;border-radius:12px;

}

[data-testid="stVerticalBlockBorderWrapper"]:has(> [data-testid="stVerticalBlock"]),

[data-testid="stForm"], [data-testid="stExpander"], [data-testid="stPopoverBody"] {

  background:var(--si-panel-glass) !important;
  backdrop-filter:var(--si-glass-blur);
  -webkit-backdrop-filter:var(--si-glass-blur);
  border-color:var(--si-glass-border) !important;
}

[data-testid="stTextInput"] input,

[data-testid="stNumberInput"] input,

[data-baseweb="select"]>div,

[data-testid="stTextArea"] textarea {

  background:var(--si-input-glass) !important;color:#EBF3FE !important;border-color:#254463 !important;
  backdrop-filter:blur(5px);


}

/* Match the translucent General News cards for both chart canvases and
   the saved regression results. Plotly axes/series remain fully opaque. */
.st-key-stock_price_chart_glass,
.st-key-peer_chart_glass,
.st-key-regression_chart_glass,
.st-key-regression_results_surface {
  background:linear-gradient(150deg,rgba(8,20,34,.70),rgba(7,15,27,.61)) !important;
  backdrop-filter:blur(14px) !important;
  -webkit-backdrop-filter:blur(14px) !important;
  border:1px solid rgba(71,120,158,.27);
  border-radius:12px;
  padding:10px 12px;
}
.st-key-regression_results_surface {padding:14px 16px;}
@media(max-width:760px) {
  .st-key-stock_price_chart_glass,
  .st-key-peer_chart_glass,
  .st-key-regression_chart_glass,
  .st-key-regression_results_surface {padding:6px;}
}

[data-testid="stWidgetLabel"] p {color:#C6DBED !important;}

/* Clickable actions: Run Scan, Add Ticker, Analyze, Refresh, Save,
   Download, pagination and other ordinary buttons share a readable palette.
   Do not target expander summaries, selector triggers, chips or radio options. */
[data-testid="stButton"] button,
[data-testid="stFormSubmitButton"] button,
[data-testid="stDownloadButton"] button,
[data-testid="stPopover"] > button,
[data-testid="stLinkButton"] a {
  background:var(--si-action-bg) !important;
  color:#EDF7FF !important;
  border:1px solid var(--si-action-border) !important;
  border-radius:10px !important;
  font-size:var(--si-type-label) !important;
  font-weight:650 !important;
  line-height:1.35 !important;
  backdrop-filter:blur(6px);
  -webkit-backdrop-filter:blur(6px);
}
[data-testid="stButton"] button:hover:not(:disabled),
[data-testid="stFormSubmitButton"] button:hover:not(:disabled),
[data-testid="stDownloadButton"] button:hover:not(:disabled),
[data-testid="stPopover"] > button:hover:not(:disabled),
[data-testid="stLinkButton"] a:hover {
  background:var(--si-action-hover) !important;
  border-color:#77BBDD !important;
  color:#FFFFFF !important;
}
[data-testid="stButton"] button:focus-visible,
[data-testid="stFormSubmitButton"] button:focus-visible,
[data-testid="stDownloadButton"] button:focus-visible,
[data-testid="stPopover"] > button:focus-visible,
[data-testid="stLinkButton"] a:focus-visible {
  outline:2px solid #8ACAF0 !important;
  outline-offset:2px;
}
[data-testid="stButton"] button:disabled,
[data-testid="stFormSubmitButton"] button:disabled,
[data-testid="stDownloadButton"] button:disabled {
  opacity:.46 !important;
  cursor:not-allowed;
}
/* Expanders remain quiet and dark; they are not calls to action. */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary:hover {
  background:rgba(6,19,32,.52) !important;
  color:#C1D5E5 !important;
}

/* Selected competitors/metrics are information chips, not bright buttons.
   Target BaseWeb's real tag element AND its immediate children: Streamlit's
   generated theme styles can color the inner pill independently. */
[data-testid="stMultiSelect"] [data-baseweb="tag"],
[data-testid="stMultiSelect"] [data-baseweb="tag"] > span,
[data-baseweb="select"] [data-baseweb="tag"],
[data-baseweb="select"] [data-baseweb="tag"] > span,
[data-baseweb="tag"] {
  background:var(--si-selection-bg) !important;
  background-color:var(--si-selection-bg) !important;
  border-color:var(--si-selection-border) !important;
  color:#B5CBDD !important;
  box-shadow:none !important;
}
[data-baseweb="tag"] span,
[data-baseweb="tag"] svg,
[data-baseweb="tag"] [role="button"] {
  color:#B5CBDD !important;
  fill:#B5CBDD !important;
}
[data-baseweb="tag"]:hover {
  background:rgba(20,53,74,.95) !important;
}
/* Give the input background its own subdued color, including the tag tray. */
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  background:var(--si-input-glass) !important;
}

[data-testid="stMetric"] {
  background:var(--si-panel-glass) !important;
  backdrop-filter:var(--si-glass-blur);
  -webkit-backdrop-filter:var(--si-glass-blur);
  padding:12px;

  border:1px solid #1B344E;border-radius:11px;}

[data-testid="stMetricValue"] {color:#C4E8FF;}

[data-testid="stDataFrame"], [data-testid="stTable"] {border-color:#23445E;}

hr {border-color:#19324C !important;}

a {color:#7EC9FF;}

@media (max-width:760px){:root {--si-type-page:1.75rem;--si-type-section:1.35rem;--si-type-subsection:1.2rem;}}

/* SI icon font repair */

/* Restore Streamlit's Material Symbols font. A universal font override turns

   icons into raw ligatures like keyboard_double_arrow_left and expand_more. */

[data-testid="stIconMaterial"], [data-testid="stIconMaterial"] *,

.material-symbols-rounded, .material-icons, [class*="material-symbol"] {

  font-family:"Material Symbols Rounded","Material Icons" !important;

  font-weight:normal !important;font-style:normal !important;

  font-feature-settings:"liga" !important;letter-spacing:normal !important;

  white-space:nowrap !important;display:inline-block;

}




/* Portaled dropdowns and popovers are translucent too, but less transparent
   than large cards so typed values, menus and buttons remain clearly legible. */
div[data-baseweb="popover"] { z-index: 10000 !important; }
div[data-baseweb="popover"] > div,
div[data-baseweb="popover"] [data-testid="stPopoverBody"],
[data-testid="stPopoverBody"] {
  background:var(--si-popover-glass) !important;
  background-color:var(--si-popover-glass) !important;
  background-image:none !important;
  backdrop-filter:blur(16px) !important;
  -webkit-backdrop-filter:blur(16px) !important;
  border:1px solid #285075 !important;
  border-radius:12px !important;
  box-shadow:0 18px 48px rgba(0,0,0,.54) !important;
}
div[data-baseweb="popover"] [data-testid="stPopoverBody"] > div {
  background:transparent !important;
}
[data-testid="stPopoverBody"] [data-testid="stForm"] {
  background:rgba(13,34,56,.56) !important;
  border-color:#244968 !important;
}

/* Select menus and date pickers can render in separate portals. */
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="menu"],
[data-baseweb="popover"] [role="dialog"] {
  background:var(--si-popover-glass) !important;
  backdrop-filter:blur(14px);
}
[data-baseweb="popover"] [role="option"]:hover {
  background:rgba(35,85,123,.58) !important;
}
[data-testid="stPopoverBody"] [data-testid="stMarkdownContainer"] p,
[data-testid="stPopoverBody"] label { color: #E5F2FF !important; }

</style>

'''.replace("__SI_EARTH_IMAGE_DATA_URI__", _earth_image_data_url()), unsafe_allow_html=True)

    # si_compact_top_spacing_20261120
    # Reduce unused space beneath Streamlit native top navigation.
    st.markdown("""<style>
    [data-testid="stMainBlockContainer"], .stMainBlockContainer, .block-container {
        padding-top: 1.8rem !important;
    }
    [data-testid="stAppViewBlockContainer"] {
        padding-top: 0.6rem !important;
    }
    </style>""", unsafe_allow_html=True)





def render_page_header(title: str, subtitle: str = '', current: str = 'stock'):
    """Render each page title; native top navigation is owned by app.py."""
    with st.container(key=f'si_header_{current}'):
        st.markdown(f'<h1 class="si-page-title">{escape(title)}</h1>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<div class="si-page-subtitle">{escape(subtitle)}</div>',
                        unsafe_allow_html=True)


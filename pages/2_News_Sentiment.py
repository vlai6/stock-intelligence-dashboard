"""Independent sentiment page: name-matched headlines published within 7 days.
The old extracted page had missing helper definitions and swallowed the error.
This version retains the existing FinBERT/Gemini integrations, but isolates failures.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
PROJECT_ROOT=Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from dashboard_theme import apply_dashboard_theme, render_page_header, style_blue_figure
from news_shared import (
    fetch_company_news, yahoo_ticker_feed, clear_company_news_caches,
    gnews_key,
)
from news_ai_shared import scored_frame, group_company_news
try:
    from news_sentiment import fetch_stock_news as fetch_original_yahoo_news
except ImportError:
    # The older helper depends on VADER; broad Yahoo retrieval also works
    # without it, and event sentiment is always recalculated using FinBERT.
    fetch_original_yahoo_news = None
load_dotenv(PROJECT_ROOT/'.env')
MARKET_TZ=ZoneInfo('America/New_York')


def _event_detail_html(matching: pd.DataFrame, scored: pd.DataFrame) -> str:
    """Restore rich event details and clickable source links without a second AI call.

    Gemini provides title-to-event assignments but not URLs or explanations.
    Rejoin against the already-sourced headlines; never invent article URLs.
    """
    import html as _html
    from collections import Counter

    def norm(value):
        return str(value or '').strip().casefold()

    lookup = {}
    if isinstance(scored, pd.DataFrame) and 'Title' in scored.columns:
        for row in scored.to_dict('records'):
            lookup.setdefault(norm(row.get('Title')), row)

    records = []
    for item in matching['Title'].astype(str).head(100):
        source = lookup.get(norm(item))
        # The Gemini grouping adapter may shorten long titles to 350 characters.
        if source is None and len(item) >= 330:
            source = next((row for key, row in lookup.items() if key.startswith(norm(item))), None)
        records.append((item, source))

    mapped = [row for _title, row in records if row is not None]
    dates = pd.to_datetime([row.get('Date') for row in mapped], utc=True, errors='coerce') if mapped else []
    valid_dates = [dt for dt in dates if pd.notna(dt)]
    first = min(valid_dates).strftime('%b %d, %Y %I:%M %p UTC') if valid_dates else 'Not available'
    sentiments = [str(row.get('Sentiment') or '').strip().title()
                  for row in mapped if str(row.get('Sentiment') or '').strip().title()
                  in ('Positive', 'Neutral', 'Negative')]
    if sentiments:
        common = Counter(sentiments).most_common()
        top = common[0][1]
        label = common[0][0] if sum(count == top for _name, count in common) == 1 else 'Mixed'
    else:
        label = 'Unavailable'

    lines = [
        '<div class="si-event-meta"><p><strong>First observed:</strong> ' + _html.escape(first) + '</p>',
        '<p><strong>Headline sentiment:</strong> ' + _html.escape(label) + '</p>',
        '<p><strong>Report status:</strong> Reported in linked headlines (not independently verified)</p>',
        '<p><strong>Grouping rationale:</strong> Gemini grouped these headlines as coverage of the same event; '
        'no separate rationale was returned.</p></div>',
        '<ul class="si-event-articles">',
    ]
    for title, row in records:
        href = str(row.get('Link') or '').strip() if row is not None else ''
        try:
            parts = urlsplit(href)
            allowed = parts.scheme.lower() in ('http', 'https') and bool(parts.netloc)
        except ValueError:
            allowed = False
        safe_title = _html.escape(title)
        if allowed:
            label_html = (f'<a href="{_html.escape(href, quote=True)}" target="_blank" '
                          f'rel="noopener noreferrer">{safe_title}</a>')
        else:
            label_html = '<span>' + safe_title + '</span>'
        lines.append('<li>' + label_html + '</li>')
    lines.append('</ul>')
    return ''.join(lines)


apply_dashboard_theme()

# si_event_articles_original_style_v1
st.markdown("""<style>
.si-event-meta {font-size:var(--si-type-data);line-height:1.58;color:#B6C9D8;margin:0.35rem 0 0.8rem;}
.si-event-meta p {margin:0 0 0.52rem;}
.si-event-meta strong {color:#DEE9F3;font-weight:700;}
.si-event-articles {padding-left:1.22rem;margin:0.45rem 0 0.6rem;line-height:1.6;}
.si-event-articles li {padding-left:0.08rem;margin:0.65rem 0;overflow-wrap:anywhere;}
.si-event-articles a {color:#73BDFF;text-decoration:underline;text-underline-offset:2px;}
.si-event-articles a:hover {color:#C5E8FF;}
.si-event-articles span {color:#B0C2D1;}
/* Keep sentiment and event count cards small; do not affect other pages. */
.st-key-si_compact_sentiment_metrics [data-testid="stMetric"],
.st-key-si_compact_event_metric [data-testid="stMetric"] {
    min-height: 0 !important;
    padding: .4rem .7rem !important;
    margin: 0 !important;
}
.st-key-si_compact_sentiment_metrics [data-testid="stMetricValue"],
.st-key-si_compact_event_metric [data-testid="stMetricValue"] {
    font-size: var(--si-type-metric) !important;
    line-height: 1.1 !important;
}
.st-key-si_compact_sentiment_metrics [data-testid="stMetricLabel"] p,
.st-key-si_compact_event_metric [data-testid="stMetricLabel"] p {
    font-size: var(--si-type-caption) !important;
    line-height: 1.25 !important;
}
</style>""", unsafe_allow_html=True)
render_page_header('Recent Sentiment', 'FinBERT sentiment and Gemini events · company-name headlines from the last 7 days', current='sentiment')
# Regression scanner-based watchlist presets (not a synthetic market scan).
from regression_watchlists import (
    PRESETS, parse_scan_csv, read_local_scan, filtered, display_row, stale_report,
)

# si_compact_sentiment_controls_v1
si_stocklist_col, _si_stocklist_blank = st.columns([1, 1], gap='medium')
with si_stocklist_col:
    with st.container(border=True):
        news_list_mode = st.selectbox('News Sentiment stock list',
            ['Single stock'] + list(PRESETS), key='si_news_stock_list')
        scan_report = None
        if news_list_mode != 'Single stock':
            scan_report = read_local_scan()
            with st.expander('Regression Scanner CSV source', expanded=(scan_report is None)):
                st.caption('Uses Regression Stock Scanner results/latest_scan.csv. These presets filter actual '
                           'scanner output; they do not scan the entire stock market themselves.')
                uploaded = st.file_uploader('Or upload latest_scan.csv from your Regression Scanner',
                             type=['csv'], key='si_scan_import')
                if uploaded is not None:
                    try:
                        scan_report = parse_scan_csv(uploaded.getvalue(), uploaded.name)
                    except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
                        st.error(f'Invalid scanner CSV: {exc}')
                        scan_report = None
            if scan_report is None:
                st.info('The scanner report is not available here. Run your Regression Scanner, '
                        'then upload results/latest_scan.csv to populate this preset.')
                st.stop()
            else:
                qualifying = filtered(scan_report, news_list_mode)
                st.caption(f'{len(qualifying)} qualifying stock(s) in {len(scan_report.rows)} valid scanner records'
                           f' · Source: {scan_report.source}')
                if scan_report.modified_utc is None:
                    st.caption('The CSV has no verified scan timestamp. Confirm its session date in the Regression Scanner.')
                elif stale_report(scan_report):
                    st.warning('This scanner report is over 7 days old; the preset is not a current screening signal.')
                if qualifying.empty:
                    st.info('No stocks in the imported scanner report meet these thresholds.')
                    st.stop()
                else:
                    candidate = st.selectbox('Qualifying ticker', qualifying['ticker'].tolist(),
                        key=f'si_screened_ticker_{list(PRESETS).index(news_list_mode)}')
                    if candidate != str(st.session_state.get('primary') or 'NVDA').strip().upper():
                        st.session_state['primary'] = candidate
                        st.session_state['loaded'] = True
                        st.rerun()

selected_symbol=str(st.session_state.get('primary') or 'NVDA').strip().upper()
if news_list_mode == 'Single stock':
    si_ticker_col, _si_ticker_blank = st.columns([1, 1], gap='medium')
    with si_ticker_col:
        with st.form('sentiment_lookup'):
            left,right=st.columns([4,1], vertical_alignment='bottom')
            with left:
                wanted=st.text_input('Stock ticker', value=selected_symbol, max_chars=15)
            with right:
                go_now=st.form_submit_button('Analyze stock', type='primary', use_container_width=True)
    if go_now:
        candidate=wanted.strip().upper()
        if not candidate or not all(c.isalnum() or c in '.-^=' for c in candidate):
            st.error('Enter a valid ticker symbol.')
            st.stop()
        st.session_state['primary']=candidate
        st.session_state['loaded']=True
        st.rerun()
symbol=str(st.session_state.get('primary') or 'NVDA').strip().upper()

@st.cache_data(ttl=3600, show_spinner=False)
def ticker_name(t):
    try:
        info=yf.Ticker(t).info or {}
        return info.get('longName') or info.get('shortName') or t
    except Exception:
        return t

company=ticker_name(symbol)
control, refresh=st.columns([4,1], vertical_alignment='center')
with control:
    st.caption(f'{company} ({symbol}) · only headlines explicitly naming the company · past 7 days')
with refresh:
    if st.button('Refresh headlines', type='primary', use_container_width=True):
        clear_company_news_caches()
        # Updated articles can change event assignments: clear Gemini's
        # corresponding cache too, but do not remove saved groups/watchlists.
        from news_ai_shared import _events_cached
        _events_cached.clear()
        st.rerun()

with st.spinner('Retrieving relevant headlines...'):
    records=fetch_company_news(symbol, 60)
st.caption(
    'Headline sources: Yahoo Finance · Google News RSS · '
    + ('GNews' if gnews_key() else 'GNews not configured')
    + '. Coverage varies by provider; results are deduplicated and filtered.'
)
if not records:
    st.info('No dated headlines naming this company were found in the past week across the configured feeds.')
    st.stop()
try:
    with st.spinner('Scoring headlines with FinBERT...'):
        frame=scored_frame(records)
except Exception as exc:
    st.warning(f'FinBERT is temporarily unavailable: {exc}')
    frame=pd.DataFrame([{'Title':r['title'],'Date':r.get('date'),'Source':r.get('source',''),
                         'Link':r.get('link',''),'Sentiment':'Unavailable','Score':None} for r in records])

labels=['Positive','Neutral','Negative']
counts={label:int((frame['Sentiment']==label).sum()) for label in labels}

# The left chart should render regardless of Gemini availability.
left,right=st.columns([1,1], gap='large')
with left:
    with st.container(border=True):
        st.subheader('Recent Sentiment Analysis')
        st.caption(f'{len(frame)} distinct, name-matched headlines across the past 7 days. Headline sentiment does not establish price impact.')
        # Keep the three counts together, directly above the bar chart.
        # This is inside the left analysis panel, not a full-page-width row.
        with st.container(key='si_compact_sentiment_metrics'):
            positive_col, neutral_col, negative_col = st.columns(3, gap='small')
            positive_col.metric('Positive', counts['Positive'])
            neutral_col.metric('Neutral', counts['Neutral'])
            negative_col.metric('Negative', counts['Negative'])
        # Counts already appear in the three summary tiles above the graph.
        # Keep the bars uncluttered; tooltips and y-axis still show their values.
        fig=go.Figure(go.Bar(x=labels, y=[counts[k] for k in labels],
                             marker_color=['#2DBA9A','#8397AC','#EE7385']))
        fig.update_layout(height=310, xaxis_title='Headline sentiment', yaxis_title='Headlines',
                          margin=dict(l=8,r=8,t=10,b=8))
        st.plotly_chart(style_blue_figure(fig), use_container_width=True)
        dated=frame.copy()
        dated['Day']=pd.to_datetime(dated['Date'],utc=True,errors='coerce').dt.tz_convert(MARKET_TZ).dt.date
        daily=dated.groupby(['Day','Sentiment'],dropna=True).size().unstack(fill_value=0)
        if len(daily)>1:
            daily=daily.reindex(columns=labels,fill_value=0)
            fig_daily=go.Figure()
            for label,color in zip(labels,['#2DBA9A','#8397AC','#EE7385']):
                fig_daily.add_trace(go.Scatter(x=daily.index.astype(str),y=daily[label],
                                               mode='lines+markers',name=label,line=dict(color=color,width=2)))
            fig_daily.update_layout(height=265,xaxis_title='Published date (ET)',yaxis_title='Headlines',
                                    margin=dict(l=8,r=8,t=10,b=8))
            st.plotly_chart(style_blue_figure(fig_daily),use_container_width=True)

with right:
    with st.container(border=True):
        st.subheader('AI News Event Grouping')
        st.caption('Gemini groups sourced headlines into underlying news events. The minimum-article filter applies to events.')
        event_source=st.selectbox(
            'Headlines for event grouping',
            ['Strict company-name headlines (last 7 days)', 'All Mentioned Articles'],
            index=0,
            # New widget key resets the previous default to the stricter method once.
            key=f'si_event_headline_source_v2_{symbol}',
            help='Default: only articles explicitly naming the company from the past 7 days. All Mentioned Articles uses up to 40 Yahoo ticker-feed headlines, which can include older or indirectly related coverage.',
        )
        event_frame=frame
        if event_source == 'All Mentioned Articles':
            try:
                # Match the old app.py source: fetch_stock_news(symbol) returned
                # up to 40 Yahoo headlines, not just name-matched seven-day news.
                events_source_records=[]
                if fetch_original_yahoo_news is not None:
                    try:
                        broad=fetch_original_yahoo_news(symbol, count=40)
                        if isinstance(broad,pd.DataFrame):
                            for _,article in broad.head(40).iterrows():
                                title=str(article.get('Title') or '').strip()
                                if title:
                                    events_source_records.append({
                                        'title':title,
                                        'date':article.get('Date'),
                                        'source':str(article.get('Source') or ''),
                                        'link':str(article.get('URL') or ''),
                                    })
                    except Exception:
                        pass
                if not events_source_records:
                    # No new dependency: use the same raw Yahoo feed retrieved
                    # by news_shared if legacy VADER is unavailable.
                    events_source_records=yahoo_ticker_feed(symbol)[:40]
                if not events_source_records:
                    st.info('Yahoo did not return any ticker news; using the screened seven-day headlines instead.')
                else:
                    # Ignore legacy VADER scores: score the same headlines
                    # with the existing FinBERT pipeline for consistency.
                    event_frame=scored_frame(events_source_records)
            except Exception as exc:
                st.warning('Yahoo ticker-feed headlines are temporarily unavailable; using seven-day company-name headlines.')
        st.caption(
            f'Grouping {len(event_frame)} headlines. '
            + ('All Mentioned Articles may include older or indirectly related Yahoo coverage.'
               if event_source == 'All Mentioned Articles'
               else 'Default method: company-name-matched articles published in the past 7 days.')
        )
        min_articles=st.slider('Minimum articles per event',min_value=1,max_value=10,value=5,key=f'weekly_event_threshold_{symbol}')
        with st.spinner('Identifying distinct events...'):
            events_df, group_articles, group_error=group_company_news(symbol,event_frame)
        if group_error:
            from news_ai_shared import explain_gemini_error
            st.warning(explain_gemini_error(group_error))
            with st.expander('Technical detail'):
                st.code(group_error)
            # si_retry_gemini_grouping_20261120
            if st.button('Retry Gemini event grouping', key=f'si_gemini_retry_{symbol}'):
                from news_ai_shared import _events_cached
                _events_cached.clear()
                st.rerun()
        elif events_df.empty:
            st.info('No distinct events were identified from these headlines.')
        else:
            if 'Articles' in events_df.columns:
                article_counts=pd.to_numeric(events_df['Articles'],errors='coerce').fillna(0)
                qualified=events_df.loc[article_counts>=min_articles]
            else:
                qualified=events_df.iloc[0:0]
            # Do not stretch one event counter across the entire right panel.
            event_metric_col, _event_metric_space = st.columns([1.25, 2.5], gap='small')
            with event_metric_col:
                with st.container(key='si_compact_event_metric'):
                    st.metric('Total Events by Threshold', len(qualified))
            if qualified.empty:
                st.caption('No events meet this threshold. Try a lower minimum.')
            for _,e in qualified.iterrows():
                event_name=str(e.get('Event','AI event')).strip()
                count=e.get('Articles',0)
                eid=e.get('Event ID')
                with st.expander(f'{event_name} ({count} headlines)'):
                    matching=pd.DataFrame()
                    if isinstance(group_articles,pd.DataFrame) and 'Event ID' in group_articles.columns:
                        matching=group_articles[group_articles['Event ID'].astype(str)==str(eid)]
                    if 'Title' in matching.columns and not matching.empty:
                        details = _event_detail_html(matching, event_frame)
                        st.markdown(details, unsafe_allow_html=True)
                    else:
                        st.caption('Gemini returned this group without article-level assignments.')

st.divider()
st.subheader('Recent Headlines')
st.caption('Sorted newest first · each headline explicitly names the selected company · published within 7 days')
filter_choices=['All','Positive','Neutral','Negative']
col1,col2=st.columns([2,1])
with col1:
    sentiment_filter=st.segmented_control('Headline sentiment',filter_choices,default='All',key=f'weekly_headline_filter_{symbol}')
with col2:
    max_rows=st.selectbox('Headlines to display',[10,20,40,60],index=1)
visible=frame if sentiment_filter in (None,'All') else frame[frame['Sentiment']==sentiment_filter]
# One compact rendered block avoids a full Streamlit divider after every headline.
import html as _si_html
_compact_rows = []
for _, item in visible.head(max_rows).iterrows():
    dt = pd.to_datetime(item.get('Date'), utc=True, errors='coerce')
    date_str = dt.tz_convert(MARKET_TZ).strftime('%d %b %Y') if pd.notna(dt) else 'Date unavailable'
    url = str(item.get('Link') or '').strip()
    parts = urlsplit(url)
    safe_url = parts.scheme in ('http', 'https') and bool(parts.netloc)
    heading = _si_html.escape(str(item.get('Title', '')))
    title_html = (f'<a href="{_si_html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{heading}</a>'
                  if safe_url else f'<span>{heading}</span>')
    meta = ' · '.join((date_str, str(item.get('Source') or 'Unknown'),
                       str(item.get('Sentiment') or 'Unavailable')))
    _compact_rows.append(
        '<div class="si-compact-row"><div class="si-compact-title">' + title_html + '</div>'
        '<div class="si-compact-meta">' + _si_html.escape(meta) + '</div></div>'
    )
if _compact_rows:
    st.markdown(
        '<style>'
        '.si-compact-headlines{border:1px solid #18314B;border-radius:10px;overflow:hidden}'
        '.si-compact-row{padding:9px 14px;border-bottom:1px solid #142739;line-height:1.35}'
        '.si-compact-row:last-child{border-bottom:0}'
        '.si-compact-title{font-size:var(--si-type-data);font-weight:550;margin-bottom:3px}'
        '.si-compact-title a{color:#8DD3FF;text-decoration:none}'
        '.si-compact-title a:hover{text-decoration:underline;color:#CBEBFF}'
        '.si-compact-meta{font-size:var(--si-type-caption);color:#91A9C0}'
        '</style><div class="si-compact-headlines">' + ''.join(_compact_rows) + '</div>',
        unsafe_allow_html=True,
    )
if visible.empty:
    st.info('No headlines match the selected sentiment filter.')

# si_20261120_refinements_v2

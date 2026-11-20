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
from news_shared import fetch_company_news
from news_ai_shared import scored_frame, group_company_news
load_dotenv(PROJECT_ROOT/'.env')
MARKET_TZ=ZoneInfo('America/New_York')

apply_dashboard_theme()
render_page_header('News Sentiment', 'FinBERT sentiment and Gemini events · company-name headlines from the last 7 days', current='sentiment')
selected_symbol=str(st.session_state.get('primary') or 'NVDA').strip().upper()
with st.form('sentiment_lookup'):
    left,right=st.columns([4,1], vertical_alignment='bottom')
    with left:
        wanted=st.text_input('Stock ticker', value=selected_symbol, max_chars=15)
    with right:
        go_now=st.form_submit_button('Analyze stock', use_container_width=True)
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
    if st.button('Refresh headlines', use_container_width=True):
        fetch_company_news.clear()
        # Refresh data, but do not destroy the user's other-page watchlists.
        st.rerun()

with st.spinner('Retrieving relevant headlines...'):
    records=fetch_company_news(symbol, 60)
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
a,b,c=st.columns(3)
a.metric('Positive', counts['Positive'])
b.metric('Neutral', counts['Neutral'])
c.metric('Negative', counts['Negative'])

# The left chart should render regardless of Gemini availability.
left,right=st.columns([1,1], gap='large')
with left:
    with st.container(border=True):
        st.subheader('Recent Sentiment Analysis')
        st.caption(f'{len(frame)} distinct, name-matched headlines across the past 7 days. Headline sentiment does not establish price impact.')
        fig=go.Figure(go.Bar(x=labels, y=[counts[k] for k in labels], text=[counts[k] for k in labels],
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
        st.caption('Gemini groups only the same screened seven-day headlines. The minimum-article filter applies to events, not the source headlines.')
        min_articles=st.slider('Minimum articles per event',min_value=1,max_value=10,value=5,key=f'weekly_event_threshold_{symbol}')
        with st.spinner('Identifying distinct events...'):
            events_df, group_articles, group_error=group_company_news(symbol,frame)
        if group_error:
            st.warning('Gemini event grouping is unavailable. Headlines and sentiment remain available.')
            with st.expander('Technical detail'):
                st.code(group_error)
        elif events_df.empty:
            st.info('No distinct events were identified from these headlines.')
        else:
            if 'Articles' in events_df.columns:
                article_counts=pd.to_numeric(events_df['Articles'],errors='coerce').fillna(0)
                qualified=events_df.loc[article_counts>=min_articles]
            else:
                qualified=events_df.iloc[0:0]
            k1,k2=st.columns(2)
            k1.metric('All Events',len(events_df))
            k2.metric('Meeting Threshold',len(qualified))
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
                    if 'Title' in matching.columns:
                        for title in matching['Title'].astype(str).head(20):
                            st.markdown('• '+title)
                    else:
                        st.caption('Gemini returned this group without article-level assignments.')

st.divider()
st.subheader('Recent Headlines')
st.caption('Sorted newest first · each headline explicitly names the selected company · published within 7 days')
filter_choices=['All','Positive','Neutral','Negative','Unavailable']
col1,col2=st.columns([2,1])
with col1:
    sentiment_filter=st.segmented_control('Headline sentiment',filter_choices,default='All',key=f'weekly_headline_filter_{symbol}')
with col2:
    max_rows=st.selectbox('Headlines to display',[10,20,40,60],index=1)
visible=frame if sentiment_filter in (None,'All') else frame[frame['Sentiment']==sentiment_filter]
for _,item in visible.head(max_rows).iterrows():
    dt=pd.to_datetime(item.get('Date'),utc=True,errors='coerce')
    date_str=dt.tz_convert(MARKET_TZ).strftime('%d %b %Y') if pd.notna(dt) else 'Date unavailable'
    url=str(item.get('Link') or '').strip()
    is_link=urlsplit(url).scheme in ('http','https') and bool(urlsplit(url).netloc)
    heading=str(item.get('Title',''))
    if is_link:
        st.markdown(f'**[{heading.replace("[", "\\[").replace("]", "\\]")}]({url})**')
    else:
        st.markdown(f'**{heading}**')
    st.caption(f"{date_str}  ·  {item.get('Source','Unknown')}  ·  {item.get('Sentiment','Unavailable')}")
    st.divider()
if visible.empty:
    st.info('No headlines match the selected sentiment filter.')

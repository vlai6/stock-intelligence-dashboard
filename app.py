"""Stock Intelligence: navigation-only entrypoint for Streamlit Cloud."""

import streamlit as st



# stock_intelligence_ui_router_v1

st.set_page_config(page_title='Stock Intelligence',

                   layout='wide', initial_sidebar_state='collapsed')



# The continuous dashboard is the default. Keep the original individual pages
# registered as deep-link fallbacks (and for existing st.page_link references).
page = st.navigation([
    st.Page('scroll_dashboard.py', title='Dashboard', default=True),
    st.Page('pages/00_Investment_Philosophy.py', title='Portfolio Analysis'),
    st.Page('pages/1_News_Screen.py', title='News Screener'),
    st.Page('regression_scanner/app.py', title='Regression Scanner'),
    st.Page('pages/0_Stock_Intelligence.py', title='Metrics & Competition'),
    st.Page('pages/2_News_Sentiment.py', title='Recent Sentiment'),
], position='hidden')


if page.title != 'Dashboard':
    st.page_link('scroll_dashboard.py', label='Back to continuous dashboard', icon='↩️')

page.run()


# si_five_page_investment_philosophy_v1

"""Stock Intelligence: navigation-only entrypoint for Streamlit Cloud."""

import streamlit as st



# stock_intelligence_ui_router_v1

st.set_page_config(page_title='Stock Intelligence', page_icon='📊',

                   layout='wide', initial_sidebar_state='collapsed')



page = st.navigation([
    st.Page('pages/00_Investment_Philosophy.py', title='Investment Philosophy', icon='📚', default=True),
    st.Page('pages/1_News_Screen.py', title='General News Screen', icon='📰'),
    st.Page('regression_scanner/app.py', title='Regression Scanner', icon='📉'),
    st.Page('pages/0_Stock_Intelligence.py', title='Stock Intelligence', icon='📊'),
    st.Page('pages/2_News_Sentiment.py', title='Recent Sentiment', icon='📈'),
], position='top')


page.run()


# si_five_page_investment_philosophy_v1

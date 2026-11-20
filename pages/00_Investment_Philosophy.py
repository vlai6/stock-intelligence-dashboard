"""Investment Philosophy: static, research-backed Streamlit landing page.

No API keys, new dependencies, live data sources, or trading actions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard_theme import apply_dashboard_theme, render_page_header

apply_dashboard_theme()
render_page_header(
    "Investment Philosophy",
    "Evidence-based long-term investing with selective individual-stock opportunities.",
    current="philosophy",
)

st.markdown("### OUR OBJECTIVE")
st.markdown(
    "Our goal is to build long-term wealth by investing in a wide range of companies "
    "and using financial research to find additional opportunities. We believe "
    "most of our money should go into diversified funds with strong historical "
    "evidence behind them. A smaller portion can be used for individual companies "
    "that our research suggests may be attractive investments."
)
st.markdown(
    "**Our goal is not just to make money on individual trades. It is to make "
    "decisions worth the risk compared with simply owning the S&P 500.**"
)

st.markdown("### ABOUT THIS DASHBOARD")
st.markdown(
    "**Stock Intelligence** helps us find stocks worth researching and understand "
    "the companies behind them. It brings together price history, financial "
    "information, competitors, and recent news to make research faster and more "
    "organized. The dashboard is mainly designed to identify stocks that have "
    "fallen unusually far below their historical price trends."
)
st.markdown(
    "**It helps us decide what to investigate, not what to automatically buy.** "
    "A complete investment decision still requires deeper research."
)
st.divider()

st.markdown("## INVESTMENT FOUNDATION")
st.markdown("""
<style>
.si-allocation-row { display:flex; flex-wrap:wrap; gap:10px; margin:.45rem 0 .35rem; }
.si-allocation-chip {
  min-width:130px; max-width:165px; border:1px solid #19334d;
  border-radius:9px; background:#071321; padding:7px 11px;
}
.si-allocation-label { color:#a8c3db; font-size:.73rem; line-height:1.3; }
.si-allocation-number { color:#c3e7ff; font-size:1.4rem; line-height:1.3; font-weight:700; }
</style>
<div class="si-allocation-row">
  <div class="si-allocation-chip">
    <div class="si-allocation-label">Diversified ETFs</div>
    <div class="si-allocation-number">90–95%</div>
  </div>
  <div class="si-allocation-chip">
    <div class="si-allocation-label">Individual stocks</div>
    <div class="si-allocation-number">5–10%</div>
  </div>
</div>
""", unsafe_allow_html=True)
st.caption(
    "Targets are shares of money invested in stocks and stock ETFs. Cash and "
    "lower-risk fixed-income investments are managed separately."
)
st.markdown(
    "An **ETF (exchange-traded fund)** lets us own many companies through one "
    "investment. For example, VOO and SPY track the S&P 500, an index of about "
    "500 leading U.S. companies. Our approach is to keep a strong broad-market "
    "foundation alongside funds that emphasize investment characteristics "
    "associated with stronger returns in historical research."
)
st.markdown("#### What research says about different investing styles")
st.markdown("""
| Investing style | What it means | Why we consider it |
|:--|:--|:--|
| **Market** | Owning many companies through funds such as VOO or SPY. | Spreads investments across businesses and participates in long-term stock-market growth. |
| **Momentum** | Buying stocks that have already been performing well. | Past winners have sometimes kept outperforming over the following months. |
| **Value** | Buying stocks that look inexpensive compared with earnings, assets, or cash flow. | Cheaper stocks have historically offered higher returns over some long periods. |
| **Size** | Investing in smaller companies. | Smaller companies have sometimes outperformed, especially when well-priced and financially strong. |
| **Profitability & quality** | Favoring companies that earn healthy profits and manage their money responsibly. | Strong finances can help a business grow and survive difficult periods. |
""")
st.markdown(
    "**Our approach:** Keep a substantial S&P 500 foundation while adding "
    "momentum, value, and selected smaller-company investments. "
    "We combine styles instead of depending on one because **none wins all the time**."
)
st.caption(
    "Research: [Fama & French (2015)](https://doi.org/10.1016/j.jfineco.2014.10.010) · "
    "[Value and Momentum Everywhere (2013)](https://doi.org/10.1111/jofi.12021) · "
    "[Size Matters, If You Control Your Junk (2018)](https://doi.org/10.1016/j.jfineco.2018.05.006)"
)

with st.expander("Further research: what do the numbers show?", expanded=False):
    st.markdown("""
| Research finding | What it means in plain English |
|:--|:--|
| **Fama–French (2015): 71–94%** | Their model explained much of the difference in average returns between the groups of stocks they studied. This **does not** mean investors earn 71–94%. |
| **Momentum: up to 150 years of evidence** | Researchers found momentum patterns over many periods, not only during the recent technology boom. These are research portfolio results, not guaranteed ETF returns. |
| **AQR's 2026 estimates: +0.5 to +1.0 percentage points/year** | AQR modeled potential extra annual returns from certain factor-based portfolios. These are forecasts, **not guaranteed or achieved results**. |
| **SPIVA (2025): 79%** | About 79% of active U.S. large-company stock funds earned less than the S&P 500 that year. |

**What we take from this:** Beating the overall market is difficult, even for professionals. That supports keeping most money in diversified ETFs while cautiously adding research-backed investment styles.

**Smaller companies:** The historical advantage of small-cap stocks has not been consistent. Research suggests it is more convincing when we also favor reasonable prices and healthier businesses.

**Sources:** [CFA Institute on Fama–French](https://rpc.cfainstitute.org/research/cfa-digest/2015/04/a-five-factor-asset-pricing-model-digest-summary) · [Baltussen et al., momentum (2026)](https://pure.eur.nl/en/publications/momentum-factor-investing-evidence-and-evolution/) · [AQR, 2026 assumptions](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---2026-Capital-Market-Assumptions.pdf?sc_lang=en) · [S&P SPIVA (2025)](https://www.spglobal.com/spdji/en/spiva/article/spiva-us-year-end-2025/) · [Size and quality research](https://www.aqr.com/Insights/Research/Working-Paper/Size-Matters-If-You-Control-Your-Junk)
""")

st.divider()
st.markdown("## INDIVIDUAL-STOCK STRATEGIES")
st.markdown(
    "We study three different ways to find individual stocks worth buying. "
    "All three are **long-only**: we buy shares when we expect them to rise, "
    "rather than betting on falling prices. Each strategy needs a reason "
    "to buy, a reason to sell, and a comparison with the S&P 500."
)
regression, momentum, event = st.tabs(
    ["Regression Recovery", "Momentum Swing", "Event-Driven"]
)

with regression:
    st.markdown(
        "**The idea: A stock that has fallen unusually far may be worth investigating.**"
    )
    st.markdown(
        "Stocks sometimes fall because investors become too pessimistic. "
        "Other times, the business is truly getting worse. Our regression scanner "
        "measures how far a stock is below its historical price trend. "
        "A **standard deviation (σ)** measures how unusual the gap is compared "
        "with the variations in the model's historical data."
    )
    st.markdown("""
| Company size (market value) | Experimental screening level |
|:--|--:|
| <code>At least $50B</code> | −3σ |
| <code>$25B to below $50B</code> | −3.5σ |
| <code>$2B to below $25B</code> | −4σ |
""")
    st.markdown(
        "**The important distinction:** These are experimental screening levels, "
        "**not buy signals**. A share price can fall far below a historical trend "
        "because the company's financial outlook has permanently changed."
    )
    st.markdown("#### WHAT OUR BACKTEST ACTUALLY FOUND")
    st.markdown(
        "We reviewed **30 completed trades** from the QuantConnect "
        "large-company (50B+) −3σ experiment and compared each trade with "
        "**dividend-adjusted SPY over the same entry and exit dates**."
    )
    st.markdown("""
<style>
.si-backtest-results { display:flex; gap:9px; flex-wrap:wrap; margin:.3rem 0 .65rem; }
.si-backtest-chip {
    min-width:120px; max-width:162px; flex:0 0 auto;
    padding:9px 11px; border:1px solid #1d3854;
    border-radius:9px; background:#091726;
}
.si-backtest-chip .label { font-size:.71rem; color:#A9C2D8; line-height:1.35; }
.si-backtest-chip .value { font-weight:700; font-size:1.24rem; color:#DAEBFF; }
</style>
<div class="si-backtest-results">
  <div class="si-backtest-chip"><div class="label">Profitable trades</div><div class="value">26 / 30</div></div>
  <div class="si-backtest-chip"><div class="label">Beat matched SPY</div><div class="value">17 / 30</div></div>
  <div class="si-backtest-chip"><div class="label">Average vs. SPY</div><div class="value">−4.5 pp</div></div>
  <div class="si-backtest-chip"><div class="label">Median vs. SPY</div><div class="value">+6.3 pp</div></div>
</div>
""", unsafe_allow_html=True)
    st.markdown(
        "**What looks promising:** Most of the stocks eventually made money, "
        "and the median trade beat SPY by about 6.3 percentage points. "
        "Some recovered dramatically. "
        "**What looks unfavorable:** Only 17 of 30 outperformed SPY, "
        "and the **average** stock trade underperformed SPY by 4.5 percentage points. "
        "A few very large relative losers hurt the results."
    )
    st.markdown(
        "**Our conclusion:** The scanner may be a useful way to **find candidates "
        "for further research**, but the current test **does not demonstrate a "
        "repeatable market-beating trading strategy**. Its high win rate alone "
        "is not enough to establish an advantage over buying and holding SPY."
    )
    st.caption(
        "Provisional trade-level comparison, not a portfolio backtest. "
        "Original trade prices and the SPY dividend-adjusted series are not "
        "fully like-for-like, and some historical ticker/corporate-action "
        "prices require checking. Overlapping trade periods, unused cash, "
        "taxes and costs are not modeled as a complete portfolio."
    )

    st.markdown("#### WHERE COULD AN ADDITIONAL EDGE COME FROM?")
    st.markdown(
        "**Our hypothesis:** The scanner may find unusually depressed stocks, "
        "but the real advantage, if one exists, may come from deciding "
        "**which businesses deserve investment and when to exit**. "
        "Understanding the company could help distinguish a temporary "
        "setback from lasting damage; this has **not yet been proven "
        "in our backtest**."
    )
    st.markdown("""
| Candidate advantage to test | What we would look for |
|:--|:--|
| **Financial strength** | Sustainable profits and free cash flow, manageable debt, adequate cash, and limited dilution. |
| **Real undervaluation** | A conservative estimate of future cash flows supports a higher value than today's price. |
| **Temporary rather than lasting damage** | The core product, customer relationships, and competitive position remain intact. |
| **Clear recovery catalyst** | Evidence of improving sales, margins, earnings, contracts, or industry conditions. |
| **Better exit discipline** | Recoveries can happen without returning to the old trend; earlier exits might reduce idle capital and large relative losses. |
""")
    st.markdown(
        "**When to sell:** Reconsider the investment when the stock approaches "
        "a defensible estimate of fair value, the recovery becomes less likely, "
        "or its expected return is no longer attractive compared with SPY. "
        "**Reaching the regression line is not automatically reaching fair value.**"
    )

    with st.expander("Detailed evidence: the 30 trades and academic studies", expanded=False):
        st.markdown("""
**The benchmark comparison (completed trades, before investor-level taxes)**

| Statistic | Stock trades | Matched SPY |
|:--|--:|--:|
| **Average trade return** | +29.4% | +33.9% |
| **Median time held** | 579 days | Same dates |
| **Profitable stock trades** | 26 of 30 | Not a separate SPY win-count test |
| **Beat SPY** | 17 of 30 | Reference benchmark |

The **average excess return was −4.5 percentage points** per trade, while the **median was +6.3 percentage points**. These averages do not represent a fully invested strategy's return.

**Examples showing the difference between winning and outperforming**

| Stock | Stock return | SPY over same dates | Difference |
|:--|--:|--:|--:|
| **NFLX** | +167.0% | +17.9% | +149.1 pp |
| **WFC** | +92.9% | +33.7% | +59.2 pp |
| **UPS** | +56.3% | +7.5% | +48.8 pp |
| **IBM** | +25.3% | +92.9% | −67.6 pp |
| **MMM** | −7.5% | +96.7% | −104.2 pp |

This shows why **the ability to find a recovering stock is not the same as the ability to beat the market**.

**How sensitive are the averages?** Excluding the questionable DOW trade alone leaves the mean relative return at about **−1.8 percentage points** across 29 trades. Excluding both DOW and MMM moves it to about **+1.9 percentage points** across 28 trades. That does **not** justify dropping those losing trades after seeing the results; it shows that this small sample is strongly affected by a few outliers and needs proper historical-data validation.

**Research outside our test**

- **De Bondt & Thaler (1985):** In their historical study, portfolios of extreme losers beat the market by roughly **19.6 percentage points over the following 36 months**. Their methodology was *not* our regression-Z-score scanner.
- **Piotroski (2000):** Selecting financially stronger companies within a cheap-stock universe improved average annual returns by **at least 7.5 percentage points** in his historical sample. This supports testing business quality, **not** assuming it improves our own screen by that amount.
- **Fama & French (1996):** Part of long-term stock-return reversal can be related to other characteristics such as company size and value exposure rather than a pure price-reversal effect.

**Sources:** [De Bondt & Thaler (1985)](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x) · [Piotroski (2000)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=249455) · [Fama & French (1996)](https://doi.org/10.1111/j.1540-6261.1996.tb05202.x)

**Data-quality warning:** The original QuantConnect export includes a suspicious DOW trade recorded with an April 2019 entry price of 341.73, inconsistent with Dow Inc.'s historical trading range. Corporate actions, historical symbol identity, and adjusted prices need to be audited. The figures here are therefore **provisional research**, not verified live-trading performance.
""")

    with st.expander("Next research: what could prove or disprove an edge?", expanded=False):
        st.markdown("""
**Separate two experiments rather than changing many things at once:**

**1. Better company selection.** Hold the regression entry signal constant, then compare all screened candidates with a version that also uses information available **at entry**: profitability, debt, free cash flow, valuation, and a documented recovery catalyst. Require better returns **relative to SPY**, not just a higher percentage of profitable trades.

**2. Better exits with Backtrader.** Keep entries and the investable stock universe fixed. Compare exits at the regression line, −2σ, −1.5σ, and −1σ. Measure whole-portfolio growth, drawdowns, holding time, unused capital, transaction costs, taxes where relevant, and returns versus SPY over identical dates.

**Avoid hindsight:** Do not choose filters because they exclude known losing trades. Validate on a fresh period and include companies that disappeared, merged, or went bankrupt. Use historical market capitalization and financial statements as they would have been known on the original screening date.

**What would change our conclusion?** Repeated out-of-sample outperformance after costs, with realistic capital deployment and acceptable downside risk. Until then, a −3σ/−4σ alert is an **idea generator**, not a validated trading edge.
""")
    st.page_link(
        "regression_scanner/app.py",
        label="Open Regression Scanner",
        icon="📉",
    )

with momentum:
    st.markdown(
        "**The idea: Strong stocks sometimes continue getting stronger.**"
    )
    st.markdown(
        "Momentum investing means looking at companies whose shares have "
        "already been doing well. For example, a company with rising demand, "
        "strong earnings, and a leading position in its industry may attract "
        "investors for months. Unlike regression recovery, this strategy "
        "**follows strength rather than looking for unusually depressed stocks**."
    )
    st.markdown(
        "**Our approach:** Look for stocks doing well compared with the market, "
        "improving business results, strong industries, and supportive market "
        "conditions. Positive news and a rising overall market can help, "
        "but neither guarantees the trend will continue."
    )
    st.markdown(
        "**When to sell:** Reconsider when the upward trend weakens, the "
        "business outlook worsens, the stock price looks too high relative "
        "to likely future results, or our risk limit is reached."
    )
    st.caption(
        "Research: [CFA Institute Momentum Review (2025)]"
        "(https://rpc.cfainstitute.org/blogs/enterprising-investor/2025/momentum-investing-a-stronger-more-resilient-framework-for-long-term-allocators) · "
        "[International Momentum Research (2025)]"
        "(https://doi.org/10.1093/rof/rfae038)"
    )
    with st.expander("Further research: why can momentum work?", expanded=False):
        st.markdown("""
Researchers have found momentum patterns across **up to 150 years** of stock-market history.

A **2025 CFA Institute review** also examines using more than stock-price strength alone—for example, whether the industry is doing well and whether analysts are raising their profit expectations.

**Why this still requires caution:** Much academic momentum research uses portfolios of many stocks, sometimes including bets against falling stocks. It does **not** prove buying a handful of popular stocks will outperform.

Momentum can reverse suddenly. Even a company doing well can have an overly expensive stock if investors expect too much growth.

**Our goal** is to find strong, durable trends without blindly chasing stocks that have already risen.

**Sources:** [Baltussen et al. (2026)](https://pure.eur.nl/en/publications/momentum-factor-investing-evidence-and-evolution/) · [CFA Institute (2025)](https://rpc.cfainstitute.org/blogs/enterprising-investor/2025/momentum-investing-a-stronger-more-resilient-framework-for-long-term-allocators)
""")

with event:
    st.markdown(
        "**The idea: Important news can create opportunities when investors "
        "react too strongly—or too slowly.**"
    )
    st.markdown(
        "We look at events such as earnings reports, partnerships, product "
        "problems, and controversies. Two different patterns may occur:"
    )
    st.markdown(
        "**Overreaction:** Bad news makes investors more pessimistic than "
        "the likely lasting damage to the business justifies.\n\n"
        "**Underreaction:** Important positive news takes time to be fully "
        "reflected in the stock price, so shares may continue rising."
    )
    st.markdown(
        "**Our approach:** Ask what the event changes about future sales, "
        "profits, cash flow, or competition. A temporary controversy may be "
        "very different from permanently losing a major customer. "
        "A negative headline alone is **not** a reason to buy."
    )
    st.markdown(
        "**When to sell:** Reconsider after the event plays out, investors "
        "have adjusted their expectations, or new facts change our view."
    )
    st.caption(
        "Research: [Hirshleifer, Peng & Wang (2025)]"
        "(https://doi.org/10.1093/rfs/hhae025) · "
        "[Chan (2003)]"
        "(https://doi.org/10.1016/S0304-405X(03)00146-6)"
    )
    with st.expander("Further research: does the market react efficiently to news?", expanded=False):
        st.markdown("""
A **2025 study in the Review of Financial Studies** found that when earnings news spread more effectively, prices moved more immediately and tended to move less afterward.

A **2025 Journal of Financial Economics study** found that results from one earnings-related trading approach were consistent with more efficient stock pricing in recent years.

**The lesson:** By the time we read a headline, other investors may already have reacted. Finding news is not itself an investing advantage. We would need to understand its real business impact better than what the current price seems to reflect.

**Sources:** [News diffusion (2025)](https://academic.oup.com/rfs/article-abstract/38/3/883/7698199) · [Warp Speed Price Moves (2025)](https://www.sciencedirect.com/science/article/pii/S0304405X25000182)
""")

st.divider()
st.markdown("## INVESTMENT DISCIPLINE & EXITS")
st.markdown(
    "**Knowing when to sell matters as much as knowing when to buy.** "
    "Different investments need different exit rules because we purchased "
    "them for different reasons."
)
st.markdown("""
| Strategy | When we consider selling |
|:--|:--|
| **Regression recovery** | The stock reaches a reasonable value, or the recovery seems unlikely. |
| **Momentum swing** | The upward trend weakens or risk becomes too high. |
| **Event-driven** | The event plays out, or new facts change our expectations. |
| **Valuation-based reallocation** | The stock price becomes too high compared with the business's current and expected results. |
""")
st.markdown(
    "We also compare the expected benefit of continuing to hold a stock with "
    "the alternative of owning a diversified ETF, after considering risk, "
    "taxes, and trading costs."
)
with st.expander("Example: when stock prices rise faster than sales", expanded=False):
    st.markdown(
        "Imagine a stock rises **60%**, while the company's revenue "
        "(money it earns from sales) rises only **20%**. The "
        "**price-to-sales ratio**—how expensive the company is relative "
        "to its sales—has increased about **33%** (1.60 ÷ 1.20 − 1). "
        "That does **not** automatically mean the stock is overpriced. "
        "The company might be improving profits or growing faster in the future. "
        "But it gives us a reason to investigate whether expectations have "
        "gotten ahead of reality.\n\n"
        "**Our principle: A good company is not always a good investment at every price.**"
    )

st.divider()
st.markdown("## LIQUIDITY & CAPITAL PRESERVATION")
st.markdown(
    "We don't believe every available dollar must always be invested in stocks. "
    "Keeping some money in lower-risk investments can provide stability and "
    "flexibility when opportunities appear."
)
st.markdown("#### Liquidity options & best-suited purpose")
st.markdown("""
| Investment | Best use | What to know |
|:--|:--|:--|
| **Savings / money market** | Money needed quickly | Easy access, but interest can change. Money-market funds are different from insured savings accounts. |
| **Treasury bills** | Money reserved for future stock purchases | Short-term U.S. government debt with predictable repayment if held to maturity. |
| **CD ladder** | Money needed on planned future dates | Bank certificates of deposit with staggered maturities; early withdrawal may be restricted. |
| **Municipal money market** | Short-term cash reserves with potential tax savings | Often federally tax-exempt income, but fund and personal tax details matter. |
| **VTES — short-term municipal bonds** | Tax-efficient income for money not needed immediately | Bond prices can change when interest rates move. |
| **VTEB — intermediate municipal bonds** | Longer-term tax-efficient bond investing | More price fluctuations; **not the same as cash**. |
""")
st.markdown("### OUR APPROACH: ADJUSTING TO MARKET CONDITIONS")
st.markdown(
    "When stocks become very expensive compared with the underlying businesses, "
    "we may decide to hold somewhat more money in lower-risk investments. "
    "This doesn't mean selling everything or predicting a crash. We can "
    "keep participating through diversified ETFs, including momentum funds, "
    "while holding additional money for future opportunities."
)
st.markdown(
    "**We keep additional investment cash within a predetermined range**, "
    "rather than making big changes based on a guess about where the market goes next."
)
with st.expander("Further research: what does Vanguard say?", expanded=False):
    st.markdown("""
In its outlook for **2026**, Vanguard highlighted expensive stock valuations and relatively attractive bond yields. Under the assumptions in its **time-varying model**, Vanguard preferred a portfolio with **40% stocks / 60% bonds** over a traditional 60% stocks / 40% bonds mix, expecting similar long-term returns with less risk.

That was a **model forecast**, not a recommendation that every investor should hold 60% bonds.

Vanguard also emphasized in **October 2026** that expensive markets do **not** reliably tell us when stock prices will fall. Markets can remain expensive and continue rising.

**What this means for us:** We can consider valuations, interest rates, business growth, bond yields, and our need for liquidity when choosing a cash allocation, but we should not try to predict an exact market top.

Extra cash can reduce losses during a downturn—but may cause us to miss gains if stocks continue rising.

**Sources:** [Vanguard — Why We're Underweight in Stocks](https://corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/why-were-underweight-stocks.html) · [Vanguard — Capital Markets Model Forecasts (Oct. 2026)](https://corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/vemo-return-forecasts.html)
""")

st.divider()
st.markdown("### OUR GUIDING PRINCIPLE")
st.markdown(
    "**Invest most of our money through diversified, research-backed strategies.** "
    "Use individual-company research to seek additional opportunities, "
    "stay disciplined about risk and price, and measure our decisions "
    "against the broader market."
)
st.caption(
    "Historical returns, research findings, and backtests provide useful evidence, "
    "but none guarantees future investment performance."
)

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

st.markdown("### OUR APPROACH")
st.markdown(
    "**Keep most of our investments diversified.** Use our dashboards to find "
    "unusual stock opportunities, study the underlying businesses, and invest "
    "selectively when the expected return justifies the risk versus SPY."
)
st.markdown("""
<style>
.si-simple-chips {display:flex;flex-wrap:wrap;gap:9px;margin:.45rem 0 .4rem;}
.si-simple-chip {flex:0 0 auto;min-width:125px;max-width:155px;padding:8px 11px;
  border:1px solid #1d3854;border-radius:9px;background:#091726;}
.si-simple-chip .label {font-size:.72rem;color:#a7c1d6;line-height:1.3;}
.si-simple-chip .value {font-size:1.26rem;font-weight:700;color:#d9ecff;line-height:1.5;}
</style>
<div class="si-simple-chips">
  <div class="si-simple-chip"><div class="label">Diversified ETFs</div><div class="value">90–95%</div></div>
  <div class="si-simple-chip"><div class="label">Individual stocks</div><div class="value">5–10%</div></div>
</div>
""", unsafe_allow_html=True)
st.caption(
    "Illustrative stock-portfolio allocation; cash and bonds are managed separately. "
    "SPY and VOO track the S&P 500, our main benchmark."
)

with st.expander("Why ETFs, momentum, value and quality?", expanded=False):
    st.markdown("""
Broad-market ETFs are our foundation. We may add **momentum** (stocks already performing well), **value** (stocks priced inexpensively relative to business fundamentals), and **quality** (healthy, profitable companies). These styles have historical research support, but none consistently outperforms.

**Research:** [Fama & French (2015)](https://doi.org/10.1016/j.jfineco.2014.10.010) · [Value and Momentum Everywhere](https://doi.org/10.1111/jofi.12021) · [Quality and Small Companies](https://doi.org/10.1016/j.jfineco.2018.05.006) · [SPIVA (2025)](https://www.spglobal.com/spdji/en/spiva/article/spiva-us-year-end-2025/)
""")

st.divider()
st.markdown("## INDIVIDUAL-STOCK STRATEGIES")
regression, momentum, event = st.tabs(
    ["Regression Recovery", "Momentum Swing", "Event-Driven"]
)

with regression:
    st.markdown(
        "**Regression identifies unusually large price declines—not necessarily "
        "cheap stocks.** A −3σ or −4σ signal means the price sits far below "
        "a fitted historical trend relative to past model variation. "
        "It triggers research, **not an automatic purchase**."
    )
    st.markdown(
        "**Our preferred use:** Stay invested in SPY, temporarily rotate a "
        "small amount into a stock only after confirming business quality, "
        "financial strength, reasonable valuation and a realistic recovery path."
    )
    st.markdown("#### WHAT OUR RESEARCH FOUND")
    st.markdown("""
<div class="si-simple-chips">
  <div class="si-simple-chip"><div class="label">Beat SPY before tax</div><div class="value">32 / 32</div></div>
  <div class="si-simple-chip"><div class="label">Beat SPY after tax</div><div class="value">11 / 32</div></div>
  <div class="si-simple-chip"><div class="label">Best after-tax edge</div><div class="value">~$4.7K</div></div>
</div>
""", unsafe_allow_html=True)
    st.markdown(
        "In our **historical SPY-funded rotation simulations**, every tested "
        "entry/exit combination beat SPY before modeled taxes, but most did "
        "**not** beat it after estimated taxes. The best reported after-tax "
        "portfolio ended near **USD 374,922**, versus **USD 370,264** for SPY "
        "from USD 100,000 over nearly 11 years."
    )
    st.caption(
        "Historical, in-sample research using a current-survivor stock universe. "
        "The results are not independently audited or proof of a future advantage."
    )
    st.markdown("#### OUR RECOVERY CHECK")
    st.markdown("""
| Question | What matters |
|:--|:--|
| **Strong business?** | Core product, customers, competitive advantage and profitability |
| **Resilient leadership and finances?** | Cash, debt, management execution and survival through setbacks |
| **Attractive investment?** | Conservative valuation, recovery catalyst, time and expected return versus SPY |
""")
    st.markdown(
        "We distinguish **temporary disruptions** (possible faster recoveries) "
        "from **genuine but repairable business problems** (possibly multi-year "
        "value investments). Neither recovery timeframe nor the management "
        "checklist is a proven trading rule."
    )
    st.page_link(
        "regression_scanner/app.py",
        label="Open Regression Scanner",
        icon="📉",
    )

    with st.expander("Backtest details and limitations", expanded=False):
        st.markdown("""
**Study setup:** Around 304 companies selected from a *current* USD 50B+ universe; ~2,500 trading days of regression history; entries at −3σ to −4.5σ; eight recovery exits and a 52-week maximum hold. The event study evaluated **509 entry-threshold-specific episodes** under eight exits (**4,072 records, not independent trades**).

| Selected trade rule | Episodes | Average excess vs. SPY | Beat SPY |
|:--|--:|--:|--:|
| −3σ → −2σ | 215 | +4.83 pp | 73.0% |
| −3σ → −0.5σ | 215 | +7.61 pp | 65.6% |
| −4σ → −1σ | 92 | +10.88 pp | 68.5% |
| −4.5σ → +1σ | 61 | +22.84 pp | 72.1% |

Those are **trade-level returns before taxes**, not full-portfolio gains. The −3σ → −2σ mean excess was +3.50 pp after excluding both 2020 and 2022, but only +0.40 pp for 2023–2025 entrants.

**Portfolio model:** Begin with USD 100,000 in SPY, transfer 1% per new qualifying stock, return proceeds to SPY at exit, and allow up to 20% satellite exposure (a test setting, not our 5–10% equity-allocation preference). Reported best *pretax* portfolio: USD 458,879 vs USD 423,602 SPY. Best *after-tax*: USD 374,922 vs USD 370,264 SPY, or roughly 12.92% versus 12.79% annualized. Pretax and after-tax winners may use different parameters.

Trading costs, dividends, settlement and estimated federal taxes (35% short-term, 15% long-term) were modeled. A separate cash/Treasury-funded portfolio failed to beat SPY after estimated taxes under all 32 tested configurations; idle cash alone is **not proven** to explain its failure.

**Major cautions:** Survivorship bias from the current company list; unusually many 2020–2022 signals; multiple-tested parameters; 52-week censoring; simplified taxes; incomplete or questionable historical prices; no systematic fundamental-quality selection test. The simulation outputs were reported in prior research and have **not been independently reproduced for this page**.
""")

    with st.expander("Management, business quality and academic research", expanded=False):
        st.markdown("""
**Core business:** We investigate customer loyalty, competitive advantage, pricing power, cash flow and debt. A low price can be a value trap if the business's long-term earnings power is deteriorating.

**Management:** We assess whether leaders have met commitments, allocated capital responsibly, maintained liquidity and demonstrated relevant turnaround experience. A famous CEO or strong résumé is not sufficient.

**What independent research adds:**

- **Demerjian, Lev & McVay (2012)** examined managerial ability through the efficiency of turning resources into revenue.
- **Piotroski (2000)** found that historical financial-strength measures helped select winners among cheap stocks; the result was *not* a direct SPY comparison.
- **Asness, Frazzini & Pedersen (2019)** studied profitability, safety and other quality characteristics.
- **Campbell, Hilscher & Szilagyi (2008)** showed why financially distressed stocks can remain poor investments despite large price declines.
- Research on **crisis leadership, governance and employee satisfaction** offers additional clues about operational resilience, but does not validate our specific strategy.

**Sources:** [Managerial Ability](https://doi.org/10.1287/mnsc.1110.1487) · [Piotroski](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=249455) · [Quality Minus Junk](https://link.springer.com/article/10.1007/s11142-018-9470-2) · [Distress Risk](https://doi.org/10.1111/j.1540-6261.2008.01416.x) · [Employee Satisfaction](https://doi.org/10.1016/j.jfineco.2011.03.021) · [Corporate Governance](https://doi.org/10.1093/rfs/hhn099)

**Limit:** We have not shown that any of these quality measures raises the **after-tax SPY-funded portfolio return** when added to regression screening.
""")

    with st.expander("Standard deviations, reversals and future tests", expanded=False):
        st.markdown("""
**Our Z-score** = (current price − fitted trend price) ÷ standard deviation of historical regression residuals. It is **not** the same as a −3σ *one-day return*. Bell-curve tail probabilities are not reliable probabilities that a stock will recover.

**Other research:** Studies of extreme daily losses, **Gatev et al.'s pairs trading**, and statistical arbitrage have documented some reversals, while Bollinger Band findings are mixed after trading costs. These methods do **not** directly validate our long-horizon price-trend screen.

**Sources:** [Extreme Losses (2024)](https://digitalcommons.newhaven.edu/americanbusinessreview/vol27/iss1/7/) · [Statistical Arbitrage](https://doi.org/10.1080/14697680903124632) · [Pairs Trading](https://doi.org/10.1093/rfs/hhj020) · [Bollinger Bands](https://doi.org/10.1080/17446540701206576)

**Research questions:** Would market- or industry-adjusted deviations, stronger businesses, better management, genuinely cheap valuations, or different recovery periods improve results?

We should freeze new rules *before* evaluating outcomes, use point-in-time company and financial data, include delistings, and compare full portfolios against dividend-reinvested SPY after comparable costs and taxes. Testing many variations creates overfitting risk. [Harvey, Liu & Zhu (2016)](https://doi.org/10.1093/rfs/hhv059)

**Conclusion:** The regression signal is promising for **finding research candidates**. A repeatable market-beating edge remains unproven.
""")

with momentum:
    st.markdown(
        "**Momentum means investing in stocks already performing well.** "
        "We look for strong relative performance, improving earnings and healthy "
        "industry conditions rather than trying to buy every price decline."
    )
    st.markdown(
        "**When to sell:** Reevaluate if the trend weakens, business expectations "
        "deteriorate, or the price becomes difficult to justify. "
        "Momentum can reverse suddenly."
    )
    with st.expander("Evidence and limitations", expanded=False):
        st.markdown("""
Momentum patterns have been documented over long periods, but research portfolios are not the same as successfully picking a few individual stocks. High valuations, crowding and sudden reversals remain important risks.

**Research:** [Long-term Momentum Evidence (2026)](https://pure.eur.nl/en/publications/momentum-factor-investing-evidence-and-evolution/) · [CFA Institute Review (2025)](https://rpc.cfainstitute.org/blogs/enterprising-investor/2025/momentum-investing-a-stronger-more-resilient-framework-for-long-term-allocators)
""")

with event:
    st.markdown(
        "**Event-driven investing examines whether news changes a company's "
        "long-term value more or less than its stock price suggests.** "
        "A temporary controversy may be very different from lasting customer "
        "losses or a product failure."
    )
    st.markdown(
        "**When to sell:** Reevaluate when the news has been absorbed, "
        "the catalyst has played out, or new information changes the thesis. "
        "Headlines alone do not establish an advantage."
    )
    with st.expander("Evidence and limitations", expanded=False):
        st.markdown("""
Studies of news diffusion and post-earnings price reactions suggest that prices can adjust over time, but the opportunity can shrink rapidly as information spreads. Understanding the *economic effect* of news matters more than simply detecting sentiment.

**Research:** [News Diffusion (2025)](https://academic.oup.com/rfs/article-abstract/38/3/883/7698199) · [Earnings-related Market Efficiency (2025)](https://www.sciencedirect.com/science/article/pii/S0304405X25000182)
""")

st.divider()
st.markdown("## DISCIPLINE & CAPITAL")
st.markdown(
    "**Sell when the original reason to own a stock weakens, its valuation "
    "no longer supports attractive returns, or a better risk-adjusted "
    "alternative exists.** Include taxes and trading costs in that decision."
)
st.markdown(
    "Maintain separate liquid reserves for near-term needs and opportunities. "
    "Cash, money-market funds and short-term Treasuries serve different purposes "
    "from longer-duration municipal bond funds. "
    "**VTEB is not a cash substitute.**"
)
with st.expander("Liquidity options and valuation context", expanded=False):
    st.markdown("""
| Instrument | Typical purpose | Main caution |
|:--|:--|:--|
| Savings / money-market holdings | Immediate liquidity | Money-market funds are not insured deposits |
| Treasury bills / CD ladder | Planned short-term needs | Maturity and early-withdrawal considerations |
| Municipal money market | Potential tax-efficient short-term reserves | Tax treatment and fund risk vary |
| VTES short-term municipal ETF | Short-duration tax-aware bond allocation | Prices can move with rates |
| VTEB intermediate municipal ETF | Longer-duration bond allocation | Greater interest-rate sensitivity |

Extra cash may provide resilience, but also creates opportunity cost when stocks rise. Valuation is not a reliable short-term market-timing signal. A 2026 Vanguard model favored bonds under particular assumptions; its forecasts are **not** universal allocations.

**Research:** [Vanguard Valuation Perspective](https://corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/why-were-underweight-stocks.html) · [Vanguard Return Forecasts](https://corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/vemo-return-forecasts.html)
""")

st.caption(
    "**Guiding principle:** Regression tells us where to look. Business quality, "
    "management, financial strength and valuation help us decide whether to "
    "invest. We judge the outcome against the S&P 500, not just whether "
    "an individual stock made money."
)

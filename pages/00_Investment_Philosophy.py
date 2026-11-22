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

st.markdown("### INVESTMENT APPROACH")
st.markdown(
    "**Most investments remain diversified.** The dashboards help identify "
    "unusual stock opportunities and evaluate the underlying businesses. "
    "Individual stocks are considered only when their expected return justifies the risk relative to SPY."
)
st.markdown("""
<style>
.si-simple-chips {display:flex;flex-wrap:wrap;gap:9px;margin:.45rem 0 .4rem;}
.si-simple-chip {flex:0 0 auto;min-width:125px;max-width:155px;padding:8px 11px;
  border:1px solid #1d3854;border-radius:9px;background:rgba(9,23,38,.54);
  backdrop-filter:blur(7px);-webkit-backdrop-filter:blur(7px);}
.si-simple-chip .label {font-size:var(--si-type-caption);color:#a7c1d6;line-height:1.3;}
.si-simple-chip .value {font-size:var(--si-type-metric);font-weight:700;color:#d9ecff;line-height:1.5;}
</style>
<div class="si-simple-chips">
  <div class="si-simple-chip"><div class="label">Diversified ETFs</div><div class="value">90–95%</div></div>
  <div class="si-simple-chip"><div class="label">Individual stocks</div><div class="value">5–10%</div></div>
</div>
""", unsafe_allow_html=True)
st.caption(
    "Illustrative stock-portfolio allocation; cash and bonds are managed separately. "
    "SPY and VOO track the S&P 500, the main benchmark."
)

with st.expander("Why ETFs, momentum, value and quality?", expanded=False):
    st.markdown("""
Broad-market ETFs provide the foundation. Factor tilts may include **momentum** (stocks already performing well), **value** (stocks priced inexpensively relative to business fundamentals), and **quality** (healthy, profitable companies). These styles have historical research support, but none consistently outperforms.

**Research:** [Fama & French (2015)](https://doi.org/10.1016/j.jfineco.2014.10.010) · [Value and Momentum Everywhere](https://doi.org/10.1111/jofi.12021) · [Quality and Small Companies](https://doi.org/10.1016/j.jfineco.2018.05.006) · [SPIVA (2025)](https://www.spglobal.com/spdji/en/spiva/article/spiva-us-year-end-2025/)
""")

st.markdown("#### FEATURED ETF FACTORS")
st.caption(
    "Momentum and value are the two factor tilts emphasized here. "
    "Evidence and risks come first; ETF examples appear at the end of each factor section."
)

with st.expander("Momentum factor — research, evidence and risks", expanded=False):
    st.markdown("""
**What is momentum?** Cross-sectional momentum ranks stocks by their *relative* performance over an intermediate horizon and favors recent winners. A commonly studied implementation uses roughly 12 months of returns **excluding the most recent month** (12–2 momentum), to reduce short-term reversal effects. This does **not** mean buying an individual stock simply because its price is up.

**What the historical data show**

| Study and sample | Finding | Important interpretation |
|:--|:--|:--|
| **Jegadeesh & Titman (1993)** · U.S. equities, 1965–1989 | Past winners tended to outperform past losers over **3–12-month** holding periods. | The original tests study **winner-minus-loser portfolios**, not guaranteed excess returns for a long-only ETF versus SPY. |
| **Daniel & Moskowitz (2016)** · U.S. equities, 1927–2013 | During the **March–May 2009** rebound, the past-loser decile gained **163%**, versus **8%** for the past-winner decile. | A severe **momentum-crash episode**, not the return of SPMO or a long-only investor. |
| **Asness, Moskowitz & Pedersen (2013)** · Eight markets and asset classes | Momentum premia appeared across multiple markets, with a tendency to be **negatively related to value**. | Evidence extends beyond one U.S. stock sample, but the relationship varies over time. |

**Why might it exist?** Slow information diffusion, gradual earnings revisions, investor underreaction and trend-following demand are proposed explanations. None is a complete or settled causal proof.

**What can go wrong?** Abrupt market rebounds can punish previous winners; sector concentration, high valuation, turnover and rebalancing costs can reduce returns. Standard factor papers often use idealized long–short portfolios, whereas diversified momentum ETFs are normally **long-only** and have implementation costs.

**What to evaluate:** Momentum methodology (lookback and weighting), drawdowns, sector/mega-cap concentration, turnover, after-tax results, fees and overlap with SPY/VOO.

**ETF examples** — these describe different forms of factor exposure, not forecasts of outperformance:

- **[SPMO](https://www.invesco.com/us/en/financial-products/etfs/invesco-sp-500-momentum-etf.html)** — an ETF tracking momentum-selected **U.S. large-cap stocks** from the S&P 500.
- **[XMMO](https://www.invesco.com/us/en/financial-products/etfs/invesco-sp-midcap-momentum-etf.html)** — an ETF tracking momentum-selected **U.S. mid-cap stocks** from the S&P MidCap 400.

**Primary research:** [Jegadeesh & Titman (1993)](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x) · [Daniel & Moskowitz (2016)](https://doi.org/10.1016/j.jfineco.2015.12.002) · [Value and Momentum Everywhere (2013)](https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere)
""")

with st.expander("Value factor — research, evidence and risks", expanded=False):
    st.markdown("""
**What is value?** Value strategies favor stocks priced cheaply *relative to fundamentals*, such as book equity, earnings or cash flow. Value is a **relative ranking**, not proof a company is intrinsically undervalued or safe from further losses.

**What the historical data show**

| Study and sample | Finding | Important interpretation |
|:--|:--|:--|
| **Fama & French (1993)** · U.S. equity portfolios from 1963 onward | The **HML (high minus low book-to-market)** factor captures historical return differences between value and growth portfolios. | An influential historical value premium, **not** a reliable annual outperformance forecast. |
| **Fama & French (2015)** · five-factor stock-return model | Adding **profitability** and **investment** improved the explanation of average portfolio returns beyond the original three factors. | A cheap company with weak profits is not necessarily an attractive value investment. |
| **Asness, Moskowitz & Pedersen (2013)** · eight markets and asset classes | Found value premia across multiple markets and an overall **negative relationship with momentum**. | Diversification is possible, but neither factor is a guaranteed hedge for the other. |

**Why might it exist?** Investors may extrapolate high growth too far, neglect unpopular industries or demand higher expected returns for distressed and less fashionable businesses. Risk-based and behavioral explanations both have supporting literature.

**What can go wrong?** A low multiple can reflect falling earnings, leverage, obsolete products or structural decline. Value may trail growth for many years, and sector tilts can be substantial. **Value ≠ buying every stock after a −4σ regression drop.**

**What to evaluate:** Valuation ratios alongside profitability and balance-sheet strength, value methodology, sector exposure, expense ratio, turnover and after-tax returns versus the same-period broad-market benchmark.

**ETF examples:**

- **[AVLV](https://www.avantisinvestors.com/avantis-investments/en-us/avantis-us-large-cap-value-etf/)** — an actively managed **U.S. large-cap value ETF** considering valuations and profitability.
- **[VTV](https://advisors.vanguard.com/investments/products/vtv/vanguard-value-etf)** — an index-tracking **U.S. large-cap value ETF** with broad exposure to value stocks.
- **[AVUV](https://www.avantisinvestors.com/avantis-investments/en-us/avantis-us-small-cap-value-etf/)** — an actively managed **U.S. small-cap value ETF** considering valuations and profitability.

**Primary research:** [Fama & French (1993)](https://doi.org/10.1016/0304-405X(93)90023-5) · [Fama & French (2015)](https://doi.org/10.1016/j.jfineco.2014.10.010) · [Kenneth French factor definitions](https://mba.tuck.dartmouth.edu/pages/Faculty/ken.french/Data_Library/f-f_factors.html) · [Value and Momentum Everywhere (2013)](https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere)
""")

st.caption(
    "Momentum and value can diversify one another because they select stocks differently, "
    "but they are not guaranteed to move in opposite directions or outperform SPY. "
    "Evaluate the combined portfolio after fees and taxes."
)

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
        "It is a research alert, **not an automatic purchase**."
    )
    st.markdown("#### HOW THE ROTATING STRATEGY WORKED")
    st.markdown(
        "Our historical test used a **SPY-funded regression rotation**, rather than "
        "holding a separate pool of cash for stock picking. The model began with "
        "**$100,000 invested in SPY**, an S&P 500 ETF. When an individual stock "
        "crossed a selected negative regression-deviation threshold (−3σ to −4.5σ), "
        "it **shifted 1% of portfolio capital from SPY into that stock**, with "
        "a maximum of 20% allocated to these temporary positions. At the "
        "specified recovery exit or 52-week holding limit, proceeds **returned "
        "to SPY**. We compared the entire rotating portfolio against buying "
        "and holding SPY over the same period."
    )
    st.caption(
        "The 20% satellite cap was a backtest setting, not the recommended "
        "long-term allocation. These historical trades were triggered by "
        "regression rules, **without** a management, valuation or business-quality "
        "filter."
    )
    st.markdown("#### BACKTEST FINDINGS")
    st.markdown("""
<div class="si-simple-chips">
  <div class="si-simple-chip"><div class="label">Rules ahead · before tax</div><div class="value">32 / 32</div></div>
  <div class="si-simple-chip"><div class="label">Rules ahead · after tax</div><div class="value">11 / 32</div></div>
  <div class="si-simple-chip"><div class="label">Best after-tax lead</div><div class="value">~$4.7K</div></div>
</div>
""", unsafe_allow_html=True)
    st.markdown(
        "All 32 tested SPY-funded configurations beat SPY **before taxes**, but "
        "only **11 of 32** did **after taxes**. The best after-tax portfolio ended "
        "at **$374,922 vs. $370,264 for SPY** from $100,000 over nearly 11 years. "
        "These are **portfolio-level, in-sample** results—not proof of a repeatable edge."
    )
    st.markdown(
        "**Recovery-timing clue:** In our separate **52-week-capped** −3σ → −0.5σ "
        "test, trades reaching the target (median **208 days**) averaged "
        "**+20.44 percentage points vs. SPY**; one-year timeouts averaged "
        "**−11.00 points**. The 52-week cap was imposed, **not proven optimal**."
    )
    st.markdown("#### WHY THE SCREEN IS STILL WORTH RESEARCHING")
    st.markdown(
        "**Regression flags unusual declines; it cannot tell a temporary setback "
        "from permanent business damage.** Research on long-term reversals "
        "([De Bondt & Thaler (1985)](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x)), "
        "financial strength ([Piotroski (2000)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=249455); "
        "[Fama & French (2015)](https://doi.org/10.1016/j.jfineco.2014.10.010)), "
        "and management and distress ([Demerjian, Lev & McVay (2012)](https://doi.org/10.1287/mnsc.1110.1487); "
        "[Campbell et al. (2008)](https://doi.org/10.1111/j.1540-6261.2008.01416.x)) "
        "supports examining the underlying business—not this exact regression rule."
    )
    st.markdown(
        "**Next step:** Evaluate the decline's cause, business quality, management, "
        "financial resilience and valuation. Only rotate out of SPY when expected "
        "**after-tax returns** justify it. **This combined screening process is "
        "not yet validated.**"
    )
    st.caption(
        "Historical current-survivor sample; survivorship and regime biases, "
        "simplified taxes and unaudited results limit confidence."
    )
    st.markdown("#### RECOVERY CHECKLIST")
    st.markdown("""
| Question | What matters |
|:--|:--|
| **Strong business?** | Core product, customers, competitive advantage and profitability |
| **Resilient leadership and finances?** | Cash, debt, management execution and survival through setbacks |
| **Attractive investment?** | Conservative valuation, recovery catalyst, time and expected return versus SPY |
""")
    st.markdown(
        "The framework distinguishes **temporary disruptions** (possible faster recoveries) "
        "from **genuine but repairable business problems** (possibly multi-year "
        "value investments). Neither recovery timeframe nor the management "
        "checklist is a proven trading rule."
    )
    with st.expander("Backtest details and limitations", expanded=False):
        st.markdown("""
**Study setup:** Around 304 companies selected from a *current* USD 50B+ universe; ~2,500 trading days of regression history; entries at −3σ to −4.5σ; eight recovery exits and a 52-week maximum hold. The event study evaluated **509 entry-threshold-specific episodes** under eight exits (**4,072 records, not independent trades**).

**Selected trade rules (trade-level observations, before modeled taxes)**

| Selected trade rule | Episodes | Average excess vs. SPY | Beat SPY |
|:--|--:|--:|--:|
| −3σ → −2σ | 215 | +4.83 pp | 73.0% |
| −3σ → −0.5σ | 215 | +7.61 pp | 65.6% |
| −4σ → −1σ | 92 | +10.88 pp | 68.5% |
| −4.5σ → +1σ | 61 | +22.84 pp | 72.1% |

The −3σ → −2σ mean excess was +3.50 pp after excluding both 2020 and 2022, but only +0.40 pp for 2023–2025 entrants.

**Recovery timing (separate −3σ → −0.5σ trade ledger):** Among **134 closed trades**, **72 hit the recovery target** (median **208 holding days**, mean **+20.44 pp vs. SPY**); **62 reached the 52-week timeout** (**364 days**, mean **−11.00 pp vs. SPY**). These are *outcome-conditioned, trade-level* results (stock return after estimated execution costs versus SPY gross return, before capital-gains taxes). The 52-week limit was a **test assumption**, not evidence that holding longer would be worse, nor a signal that can predict fast recoveries at entry. The ledger covers one entry/exit variation and is not the same denominator as the 509 threshold-specific episodes reported above.

**Full-portfolio results, including estimated taxes**

| Portfolio comparison | Configurations ahead of SPY | Best rotation value | SPY benchmark | Best reported lead |
|:--|--:|--:|--:|--:|
| Before modeled federal taxes | 32 / 32 | $458,879 | $423,602 | +$35,277 |
| After estimated federal taxes | 11 / 32 | $374,922 | $370,264 | +$4,658 |

**Portfolio model:** Begin with $100,000 invested in SPY, temporarily transfer 1% per qualifying stock, return proceeds to SPY at exit, and allow up to 20% satellite exposure (a test setting, not the preferred 5–10% individual-stock allocation). The best pretax and after-tax configurations can use **different parameters**, so each row reports its own corresponding SPY benchmark. The reported best after-tax comparison was approximately **12.92% versus 12.79% annualized**.

**Interpretation:** The before/after-tax table reflects **complete portfolio outcomes** across 32 tested configurations, not taxes applied separately to the four selected trade-rule rows. Rule-specific after-tax excess returns and hit rates were **not available** in the reported study and should not be inferred from the portfolio totals.

Trading costs, dividends, settlement and estimated federal taxes (35% short-term, 15% long-term) were modeled. A separate cash/Treasury-funded portfolio failed to beat SPY after estimated taxes under all 32 tested configurations; idle cash alone is **not proven** to explain its failure.

**Major cautions:** Survivorship bias from the current company list; unusually many 2020–2022 signals; multiple-tested parameters; 52-week censoring; simplified taxes; incomplete or questionable historical prices; no systematic fundamental-quality selection test. The simulation outputs were reported in prior research and have **not been independently reproduced for this page**.
""")

    with st.expander("Management, business quality and academic research", expanded=False):
        st.markdown("""
**Core business:** Review customer loyalty, competitive advantage, pricing power, cash flow and debt. A low price can be a value trap if the business's long-term earnings power is deteriorating.

**Management:** Assess whether leaders have met commitments, allocated capital responsibly, maintained liquidity and demonstrated relevant turnaround experience. A famous CEO or strong résumé is not sufficient.

**What independent research adds:**

- **Demerjian, Lev & McVay (2012)** examined managerial ability through the efficiency of turning resources into revenue.
- **Piotroski (2000)** found that historical financial-strength measures helped select winners among cheap stocks; the result was *not* a direct SPY comparison.
- **De Bondt & Thaler (1985)** documented long-term loser/winner return reversals. Their return-ranked portfolios are **not** equivalent to a regression Z-score strategy.
- **Asness, Frazzini & Pedersen (2019)** studied profitability, safety and other quality characteristics.
- **Campbell, Hilscher & Szilagyi (2008)** showed why financially distressed stocks can remain poor investments despite large price declines.
- Research on **crisis leadership, governance and employee satisfaction** offers additional clues about operational resilience, but does not validate this particular regression strategy.

**Sources:** [Long-term Reversals](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x) · [Managerial Ability](https://doi.org/10.1287/mnsc.1110.1487) · [Piotroski](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=249455) · [Quality Minus Junk](https://link.springer.com/article/10.1007/s11142-018-9470-2) · [Distress Risk](https://doi.org/10.1111/j.1540-6261.2008.01416.x) · [Employee Satisfaction](https://doi.org/10.1016/j.jfineco.2011.03.021) · [Corporate Governance](https://doi.org/10.1093/rfs/hhn099)

**Limit:** It has not been shown that these quality measures improve **after-tax SPY-funded portfolio returns** when added to regression screening.
""")

    with st.expander("Standard deviations, reversals and future tests", expanded=False):
        st.markdown("""
**Regression Z-score** = (current price − fitted trend price) ÷ standard deviation of historical regression residuals. It is **not** the same as a −3σ *one-day return*. Bell-curve tail probabilities are not reliable probabilities that a stock will recover.

**Other research:** Studies of extreme daily losses, **Gatev et al.'s pairs trading**, and statistical arbitrage have documented some reversals, while Bollinger Band findings are mixed after trading costs. These methods do **not** directly validate this long-horizon price-trend screen.

**Sources:** [Extreme Losses (2024)](https://digitalcommons.newhaven.edu/americanbusinessreview/vol27/iss1/7/) · [Statistical Arbitrage](https://doi.org/10.1080/14697680903124632) · [Pairs Trading](https://doi.org/10.1093/rfs/hhj020) · [Bollinger Bands](https://doi.org/10.1080/17446540701206576)

**Research questions:** Would market- or industry-adjusted deviations, stronger businesses, better management, genuinely cheap valuations, or different recovery periods improve results?

New rules should be defined *before* evaluation, using point-in-time company and financial data, including delistings, and comparing full portfolios with dividend-reinvested SPY after comparable costs and taxes. Testing many variations creates overfitting risk. [Harvey, Liu & Zhu (2016)](https://doi.org/10.1093/rfs/hhv059)

**Conclusion:** The regression signal is promising for **finding research candidates**. A repeatable market-beating edge remains unproven.
""")

with momentum:
    st.markdown(
        "**Momentum investing focuses on stocks already performing well.** "
        "Selection emphasizes strong relative performance, improving earnings and healthy "
        "industry conditions rather than trying to buy every price decline."
    )
    st.markdown(
        "**When to sell:** Reassess if the trend weakens, business expectations "
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
        "**When to sell:** Reassess when the news has been absorbed, "
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
    "**Selling discipline:** Reassess a position when its investment thesis weakens, valuation "
    "no longer supports attractive returns, or a better risk-adjusted "
    "alternative exists.** Taxes and trading costs also matter."
)
st.markdown(
    "Separate liquid reserves provide flexibility for near-term needs and opportunities. "
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
    "**Guiding principle:** Regression identifies opportunities. Business quality, "
    "management, financial strength and valuation help determine whether to "
    "invest. Performance is judged against the S&P 500, not just whether "
    "an individual stock made money."
)

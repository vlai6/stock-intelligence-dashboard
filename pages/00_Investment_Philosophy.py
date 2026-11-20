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

st.markdown("### ABOUT OUR DASHBOARDS")
st.markdown(
    "**Our dashboards** help us find stocks worth researching and understand "
    "the businesses behind them. They bring together historical prices, "
    "financial results, competitors, and recent news. The regression scanner "
    "flags unusually large declines so we can research whether a company's "
    "long-term value may be stronger than its current stock price suggests."
)
intro_a, intro_b, intro_c = st.columns(3, gap="small")
with intro_a:
    st.markdown("**Find opportunities**")
    st.caption("Use regression to flag unusually large price declines.")
with intro_b:
    st.markdown("**Understand the business**")
    st.caption("Check the reasons for the decline and the company's financial health.")
with intro_c:
    st.markdown("**Make informed decisions**")
    st.caption("Compare realistic upside, downside, and recovery time with SPY.")
st.markdown(
    "**Statistical signals tell us where to investigate. Fundamental analysis "
    "helps us decide whether to invest.**"
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
    st.markdown("#### REGRESSION-BASED INVESTING")
    st.markdown(
        "**The idea:** A company whose shares have fallen unusually far below their "
        "historical price trend may be worth studying. Regression measures that "
        "price gap; **standard deviations (σ)** indicate how unusual it is compared "
        "with past variation. An extreme reading is **not proof of undervaluation**."
    )
    st.markdown(
        "This approach might work because investors sometimes react too strongly "
        "to bad news, uncertainty, or temporary business problems. But sometimes "
        "the fall is justified: future profits may genuinely be lower. "
        "**We invest only when our estimate of the business's sustainable value "
        "is more favorable than expectations already reflected in the stock price.**"
    )
    st.markdown("""
| Company size | Experimental screening level |
|:--|--:|
| At least USD 50 billion | −3σ |
| USD 25B to below USD 50B | −3.5σ |
| USD 2B to below USD 25B | −4σ |
""")
    st.caption(
        "These market-cap levels and Z-score cutoffs are experimental candidate "
        "filters. They are not research-proven trading thresholds."
    )

    st.markdown("#### TWO TYPES OF REGRESSION OPPORTUNITIES")
    short_col, value_col = st.columns(2, gap="small")
    with short_col:
        with st.container(border=True):
            st.markdown("**Recovery Investing**")
            st.caption("Temporary setbacks · Potentially healthier underlying business")
            st.markdown(
                "We investigate a sharp decline caused by temporary bad publicity, "
                "market panic, short-lived earnings weakness, or disruptions that "
                "do not permanently damage the business."
            )
            st.markdown("**Research horizon:** roughly 3–12 months (illustrative, not a tested optimal period).")
            st.markdown(
                "**Key question:** Did the price fall more than the company's "
                "long-term outlook justifies?"
            )
    with value_col:
        with st.container(border=True):
            st.markdown("**Regression-Assisted Value Investing**")
            st.caption("Real but recoverable business problems · Longer-term valuation")
            st.markdown(
                "We investigate lost contracts, declining revenue that may stabilize, "
                "restructuring, margin pressure, or a multi-year turnaround where "
                "future cash flows might still justify a higher valuation."
            )
            st.markdown("**Research horizon:** roughly 1–3 years or longer (illustrative, not a proven holding rule).")
            st.markdown(
                "**Key question:** Does today's price compensate us for the "
                "risks and time needed for recovery?"
            )
    st.caption(
        "These categories are research frameworks, not guaranteed patterns. "
        "A stock can rise before reported earnings recover because prices reflect "
        "expectations about the future."
    )

    st.markdown("#### HOW WE TRY TO AVOID VALUE TRAPS")
    st.markdown(
        "A **value trap** is a stock that looks cheap but keeps disappointing "
        "because its business is deteriorating. We aim to separate a temporary "
        "price decline from a lasting decline in business value."
    )
    st.markdown("""
| What we examine | Encouraging signs | Warning signs |
|:--|:--|:--|
| **Business quality** | Customers still want the product; durable advantages | Lost customers, weakening competitiveness |
| **Financial health** | Manageable debt; enough cash; reliable or recoverable free cash flow | Debt pressure, cash burn, possible new-share dilution |
| **Underlying business** | Sales and profit margins can stabilize | Repeated guidance cuts or worsening economics |
| **Fair value** | Conservatively estimated future earnings/cash flows exceed what today's price implies | Business value may have fallen even more than the stock |
| **Recovery catalyst & time** | A realistic path through contracts, cost savings, or improving demand | No credible turnaround or a wait that makes SPY more attractive |
""")
    st.markdown(
        "**The goal is not to buy every stock that falls. It is to identify "
        "businesses whose long-term value may be greater than the market currently expects.**"
    )

    st.markdown("#### WHAT OUR BACKTRADER TESTING HAS SHOWN")
    st.markdown(
        "We judge the strategy by **how the full investment portfolio performed "
        "against buying and holding SPY over the same dates**. A high number "
        "of profitable individual trades is not enough to show an advantage."
    )
    st.markdown("""
<style>
.si-backtest-results { display:flex; flex-wrap:wrap; gap:9px; margin:.4rem 0 .65rem; }
.si-backtest-chip {
    flex:0 0 auto; min-width:121px; max-width:164px;
    padding:9px 11px; border:1px solid #1d3854;
    border-radius:9px; background:#091726;
}
.si-backtest-chip .label { font-size:.71rem; color:#A9C2D8; line-height:1.35; }
.si-backtest-chip .value { font-weight:700; font-size:1.24rem; color:#DAEBFF; }
</style>
<div class="si-backtest-results">
  <div class="si-backtest-chip"><div class="label">Backtrader CAGR</div><div class="value">12.40%</div></div>
  <div class="si-backtest-chip"><div class="label">SPY CAGR</div><div class="value">12.79%</div></div>
  <div class="si-backtest-chip"><div class="label">Ending gap vs. SPY</div><div class="value">−$13,898</div></div>
  <div class="si-backtest-chip"><div class="label">Max strategy drawdown</div><div class="value">−35.65%</div></div>
</div>
""", unsafe_allow_html=True)
    st.markdown("""
**Reported Backtrader full-portfolio result (January 4, 2016 – November 19, 2026)**

| Portfolio measure | Regression strategy | Buy-and-hold SPY |
|:--|--:|--:|
| Starting portfolio | $100,000 | $100,000 |
| Ending portfolio | **$356,374** | **$370,272** |
| Annualized compound growth (CAGR) | **12.40%** | **12.79%** |

The best reported after-tax variant from this set used **−3σ entries and −0.5σ exits**. It finished around **$13,898 below SPY**, even though the portfolio grew substantially.

**The result is negative relative to the benchmark**, not a loss of invested principal. The strategy grew but did not beat simply holding SPY in this test.
""")
    st.markdown(
        "**What looks promising:** The statistical screen generated many "
        "potential recovery investments, and the tested portfolio grew over "
        "the long sample. **What is not established:** An advantage over SPY "
        "after the modeled taxes, trading costs, and capital deployment. "
        "That is a more demanding and useful test than counting winning trades."
    )
    st.markdown(
        "**Our conclusion:** Regression remains a reasonable **idea-generation "
        "indicator**, not a proven profitable trading edge relative to SPY. "
        "A potential additional advantage might come from understanding "
        "the business, avoiding financial distress, estimating fair value, "
        "identifying recovery catalysts, or improving position exits. "
        "None has yet been demonstrated as a repeatable advantage "
        "within our strategy."
    )
    st.caption(
        "Figures above were reported in our earlier Backtrader discussion; "
        "the complete raw run and settings have not been independently re-run "
        "for this website update. This is a historical, in-sample comparison, "
        "not a forecast."
    )

    with st.expander("Backtrader assumptions and why the result needs validation", expanded=False):
        st.markdown("""
**Reported full-portfolio model:** weekly signals, approximately 2,500 historical trading days for the regression, an entry around −3σ, an exit at −0.5σ in the best reported variant, positions sized at up to **10% each** with no more than **10 positions**, and a roughly **52-week holding limit**. The simulation included assumed 0.15% one-way trading costs, a short-term Treasury cash-yield proxy, modeled capital-gains taxes, and SPY dividend reinvestment.

The earlier report recorded **100 completed trades** and a maximum strategy drawdown around **−35.65%**. This is a portfolio-level model, unlike individual trade averages.

**Why results may not repeat:**

- **Survivorship bias:** The current $50B+ company universe can omit firms that previously qualified but later failed or shrank.
- **COVID-era effects:** The extraordinary 2020–2022 market environment may have contributed disproportionately to recoveries.
- **Historical data:** Tickers, stock splits, dividends, mergers, and delistings require point-in-time verification.
- **Overfitting:** Choosing the best exit after examining many historical settings may overstate future performance.
- **Taxes and cash:** Realized gains, idle capital, position sizing, and benchmark dividends materially affect results.

The figures are **reported outputs, not independently reproduced audited performance**. The best variant from a historical search is not necessarily the best future trading rule.
""")

    with st.expander("Separate research: smaller SPY-funded stock rotations", expanded=False):
        st.markdown("""
Another historical analysis considered a portfolio invested mainly in SPY, reallocating approximately **1% of capital per qualifying stock**, subject to an aggregate satellite limit. This model is **different from the Backtrader full-portfolio test above**.

| Reported historical simulation results | Outcome |
|:--|--:|
| Rule combinations beating SPY before modeled taxes | 32 of 32 |
| Rule combinations beating SPY after estimated taxes | 11 of 32 |
| Best estimated after-tax advantage | About $4,659 on $100,000 over nearly 11 years |

**Interpretation:** Under the simplified assumptions, certain limited-allocation rules modestly outperformed SPY after taxes. But most of the tested combinations did not; the selected best result is exposed to hindsight and multiple-testing bias.

These 32-combination figures come from a **separate re-aggregation summarized in earlier research**, not an independently rerun Backtrader simulation. We have not reprocessed its underlying results here. Its estimated tax treatment, historical stock universe, and 52-week time limits also need further validation.

**Do not combine these figures with the 10%-per-position Backtrader test or interpret them as independently confirmed profitability.**
""")

    with st.expander("Academic research: where an additional edge might come from", expanded=False):
        st.markdown("""
A regression deviation measures unusual **price movement**, not a company's true business value. Research suggests several possible methods for improving the **next stage of selecting investments**:

- **De Bondt & Thaler (1985):** Some extreme historical stock losers subsequently experienced return reversals. This is not the same as testing −3σ or −4σ rules.
- **Benou & Richie (2003):** Studied subsequent returns following large declines in large firms, providing context for the recovery hypothesis.
- **Piotroski (2000):** Financial strength helped distinguish higher-quality investments within cheap-stock portfolios.
- **Asness, Frazzini & Pedersen (2019):** Quality Minus Junk examines differences in returns associated with business quality.
- **Campbell, Hilscher & Szilagyi (2008):** Financial distress can make apparently cheap or badly beaten-down stocks dangerous.

**What we would test:** Whether knowing a company's profitability, cash flow, debt, competitive situation, valuation, and plausible recovery event *before purchasing* improves future portfolio returns relative to SPY.

**Sources:** [De Bondt & Thaler](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x) · [Benou & Richie](https://ideas.repec.org/a/spr/jecfin/v27y2003i1p19-38.html) · [Piotroski](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=249455) · [Quality Minus Junk](https://link.springer.com/article/10.1007/s11142-018-9470-2) · [In Search of Distress Risk](https://doi.org/10.1111/j.1540-6261.2008.01416.x)

**Key limitation:** These studies support the research direction. They do **not** independently validate our particular scanner or prove business analysis can reliably add alpha.
""")

    with st.expander("Why we avoid continually optimizing historical results", expanded=False):
        st.markdown("""
**Overfitting** means creating rules that explain past winners and losers very well but do not predict new outcomes.

We have tested numerous regression entry and exit conditions. Choosing rules because they keep historical winners while excluding historical losers risks making the apparent edge disappear in live investing.

A better evaluation records **the rules and fundamental decision before knowing the outcome**, includes stocks that disappeared from the market, uses financial statements available on the original signal date, and measures new results against a dividend-reinvested SPY benchmark.

Our next Backtrader experiments should assess **whole-portfolio compound growth, drawdowns, taxes, turnover, and unused capital**—not just successful trades. Any genuine improvement must survive out-of-sample testing.
""")

    st.markdown("#### OUR RESEARCH PROCESS")
    st.markdown(
        "**Regression alert → Understand the business → Check financial health "
        "→ Estimate fair value → Identify recovery path → Decide whether to invest**"
    )
    st.markdown("""
| Research outcome | What it means |
|:--|:--|
| **Recovery candidate** | Healthy underlying company with a potentially temporary setback |
| **Long-term value candidate** | Real but potentially recoverable problems and an attractive conservative valuation |
| **Watchlist** | Interesting business, but insufficient evidence or margin of safety so far |
| **Rejected** | Excessive risk, worsening finances, or unattractive expected return versus SPY |
""")
    st.markdown("**No investment is required simply because a regression signal appears.**")
    st.markdown(
        "SPY remains the default alternative. In some experiments we considered "
        "moving only a small portion of the existing SPY portfolio into a "
        "qualified opportunity while limiting total individual-stock exposure. "
        "That position-sizing approach is still a hypothesis to test."
    )
    st.markdown(
        "**Exit discipline:** Reassess fair value, new business information, "
        "recovery time, and expected performance relative to SPY. "
        "A return to the regression line is not automatically a fair-value signal."
    )

    with st.expander("Next steps: validating exits and fundamental selection", expanded=False):
        st.markdown("""
**Separate the tests so we can learn what helps:**

1. **Selection:** Keep the regression screen fixed. Test whether financial strength, conservative valuation, or a documented recovery catalyst improves results using information available at the time.
2. **Exit:** Compare the historical regression line, −2σ, −1.5σ, and −1σ as exit candidates using consistent entry rules.
3. **Full portfolio:** Compare total portfolio growth, drawdowns, unused capital, costs, and (where modeled) taxes with a dividend-reinvested SPY investment over the exact same period.
4. **Out-of-sample evaluation:** Freeze the chosen rules before testing an untouched period or new alerts. Keep delisted, bankrupt, and acquired companies in the historical universe where applicable.

**The result we need:** Repeated outperformance after realistic costs and risk, not a high win rate or one impressive historical trade. Until that is demonstrated, regression is a **screening indicator**, not a proven trading advantage.
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
    "**Our goal is not to predict every market recovery.** We want to find "
    "situations where a company's long-term value may be stronger than its "
    "depressed share price suggests. Regression tells us where to look; "
    "financial strength, business understanding, valuation, and disciplined "
    "decisions help us decide whether an opportunity is worth pursuing."
)
st.markdown(
    "We keep most of our investments diversified and judge individual-stock "
    "decisions against a simple alternative: owning the S&P 500."
)
st.caption(
    "Historical returns, research findings, and backtests provide useful evidence, "
    "but none guarantees future investment performance."
)

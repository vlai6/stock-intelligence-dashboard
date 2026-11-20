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
    "Build long-term wealth through diversified, research-informed investing. "
    "Our foundation is broad-market and factor-based ETFs; statistical screening "
    "and fundamental analysis help us investigate selective individual-stock ideas. "
    "**Success means attractive risk-adjusted outcomes relative to alternatives, "
    "not merely making profitable trades.**"
)

st.markdown("### ABOUT THIS DASHBOARD")
st.markdown(
    "**Stock Intelligence** is a research dashboard, not a full equity valuation "
    "or automated trading system. It primarily supports regression-based recovery "
    "screening and organizes price history, financial metrics, competitor "
    "comparisons, and news sentiment to save preliminary research time. "
    "The other strategies below are part of our broader philosophy, not "
    "systems validated by this dashboard."
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
    "Targets are shares of invested equity capital. Liquidity and fixed-income reserves are managed separately."
)
st.markdown(
    "Maintain a broad-market core (such as VOO or SPY) with deliberate exposure "
    "to factors supported by long-run research. No factor consistently outperforms."
)
st.markdown("""
| Factor | Research-based principle |
|:--|:--|
| **Market** | Diversified participation in long-run equity growth and a benchmark for decisions. |
| **Momentum** | Intermediate-term relative winners have historically tended to outperform. |
| **Value** | Cheaper valuations have historically earned a premium, but not consistently. |
| **Size** | A historical small-cap premium exists, but is unreliable in some periods; value and quality can refine exposure. |
| **Profitability & investment** | Robust profitability and disciplined investment add information beyond price alone. |
""")
st.caption(
    "Research: [Fama & French, five-factor model (2015)](https://doi.org/10.1016/j.jfineco.2014.10.010) · "
    "[Asness et al., value and momentum (2013)](https://doi.org/10.1111/jofi.12021) · "
    "[Asness et al., size and quality (2018)](https://doi.org/10.1016/j.jfineco.2018.05.006)"
)


with st.expander("Research evidence: factors and the S&P 500 benchmark", expanded=False):
    st.markdown("""
| Finding | Interpretation |
|:--|:--|
| **Fama–French (2015): 71–94%** | Share of cross-sectional average-return variation explained in portfolios examined by the five-factor model, **not** an investor return. |
| **Momentum (Baltussen et al., 2026): up to 150 years** | Evidence across long historical equity samples and many specifications. These are factor results, not SPMO or swing-trade profits. |
| **AQR's 2026 assumptions: +0.5 to +1.0 percentage points/year** | *Modeled* expected net active return for diversified value and combined factor tilts, respectively—not achieved returns or guarantees. |
| **SPIVA 2025: 79%** | Proportion of U.S. active large-cap equity funds that underperformed the S&P 500 that year. |

The historical **size premium is inconsistent**; controlling for low-quality small firms strengthens the evidence. That supports examining small-cap value and quality, not buying small stocks indiscriminately.

**Sources:** [CFA Institute on Fama–French (2015)](https://rpc.cfainstitute.org/research/cfa-digest/2015/04/a-five-factor-asset-pricing-model-digest-summary) · [Baltussen et al., *Journal of Portfolio Management* (2026)](https://pure.eur.nl/en/publications/momentum-factor-investing-evidence-and-evolution/) · [AQR, 2026 Capital Market Assumptions](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---2026-Capital-Market-Assumptions.pdf?sc_lang=en) · [S&P SPIVA 2025](https://www.spglobal.com/spdji/en/spiva/article/spiva-us-year-end-2025/) · [Asness et al., quality-adjusted size (2018)](https://www.aqr.com/Insights/Research/Working-Paper/Size-Matters-If-You-Control-Your-Junk)
""")

st.divider()
st.markdown("## INDIVIDUAL-STOCK STRATEGIES")
st.markdown(
    "Three **independent, long-only** strategies. Each requires a clear thesis "
    "and comparison with a diversified ETF alternative."
)
regression, momentum, event = st.tabs(
    ["Regression Recovery", "Momentum Swing", "Event-Driven"]
)

with regression:
    st.markdown(
        "**Thesis.** Extreme negative deviations from a historical price trend may "
        "identify potential temporary mispricing. A regression deviation is "
        "**not evidence of intrinsic undervaluation**."
    )
    st.markdown("""
| Market capitalization | Experimental threshold |
|:--|--:|
| `≥$50B` | −3σ |
| `$25B–<$50B` | −3.5σ |
| `$2B–<$25B` | −4σ |
""")
    st.markdown(
        "**Our hypothesis.** The potential advantage may lie **beyond the numerical "
        "signal**. Business understanding, financial strength, competitive positioning, "
        "valuation, and recovery catalysts may distinguish temporary setbacks from "
        "permanent deterioration. We have not yet demonstrated consistent outperformance."
    )
    st.markdown(
        "**Exit.** Reassess as estimated intrinsic value is approached, the recovery "
        "thesis weakens, or better risk-adjusted opportunities emerge. "
        "Returning to the regression line is not automatically reaching fair value."
    )
    st.caption(
        "**Backtrader research planned:** compare regression-line, −2σ, −1.5σ, "
        "and −1σ exits with consistent entry rules, total-return SPY comparisons, "
        "capital usage, costs, drawdowns, and out-of-sample validation."
    )
    st.caption(
        "Research: [De Bondt & Thaler, long-horizon reversals (1985)]"
        "(https://doi.org/10.1111/j.1540-6261.1985.tb05004.x) · "
        "[Piotroski, financial strength in value stocks (2000)]"
        "(https://papers.ssrn.com/sol3/papers.cfm?abstract_id=249455). "
        "Neither paper validates these exact regression thresholds."
    )

    with st.expander("Research evidence and our preliminary backtest", expanded=False):
        st.markdown("""
| Evidence | What it demonstrates |
|:--|:--|
| **De Bondt & Thaler (1985): +19.6 percentage points** | Prior-loser portfolios' cumulative *market-adjusted* return over the following **36 months** in a historical sample; not this scanner's Z-score rules. |
| **Piotroski (2000): at least +7 percentage points annually** | Historical improvement in mean return from identifying financially strong companies *within a cheap book-to-market universe*. Not a predicted return for our strategy. |
| **Our experiment: 26 of 30 profitable trades** | An earlier provisional matched-date analysis found **17 of 30** beat SPY and mean relative performance of **−4.5 percentage points per trade**. |

**Limitations:** Our 30-trade export is not a portfolio backtest. Historical price and corporate-action data require reconciliation (including DOW), and stock-dividend adjustments may differ from SPY. **These results do not establish an exploitable edge.**

**Planned Backtrader test:** Hold entries constant and compare exits at the regression line, −2σ, −1.5σ, and −1σ. Measure portfolio CAGR, drawdown, turnover, idle cash, and dividend-adjusted SPY on identical dates; reserve untouched out-of-sample data.

**Sources:** [De Bondt & Thaler (1985)](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1985.tb05004.x) · [Piotroski (2000)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=249455)
""")
    st.page_link("regression_scanner/app.py", label="Open Regression Scanner", icon="📉")

with momentum:
    st.markdown(
        "**Thesis.** Stocks with sustained relative strength may continue "
        "outperforming over intermediate horizons. This is separate from buying "
        "statistically depressed stocks."
    )
    st.markdown(
        "**Our approach.** Examine price momentum alongside industry leadership, "
        "earnings developments, valuations, and broader market conditions. "
        "Bull markets and positive sentiment may help, but are not prerequisites."
    )
    st.markdown(
        "**Exit.** Hold while the trend and thesis remain favorable; reassess if "
        "relative strength fades, valuations become difficult to justify, or "
        "a defined risk limit is breached. The specific rules still require testing."
    )
    st.caption(
        "Research: [CFA Institute, momentum evidence and multi-signal methods (2025)]"
        "(https://rpc.cfainstitute.org/blogs/enterprising-investor/2025/momentum-investing-a-stronger-more-resilient-framework-for-long-term-allocators) · "
        "[Review of Finance, international momentum determinants (2025)]"
        "(https://doi.org/10.1093/rof/rfae038). "
        "Factor evidence does not automatically validate discretionary long-only swing trading."
    )

    with st.expander("Recent momentum research", expanded=False):
        st.markdown("""
**Baltussen et al. (2026, *Journal of Portfolio Management*)** examine equity momentum in samples spanning **up to 150 years** and across many implementation choices. This is evidence for persistent factor behavior, **not** proof that our long-only swing entries will beat SPY.

A **2025 CFA Institute research review** emphasizes that price strength alone is incomplete. We may test industry-relative strength, earnings revisions, and trend persistence independently rather than assuming that a bull market or positive sentiment is required.

**Counterpoint:** Momentum can suffer abrupt reversals, and recent winners can become expensive or crowded. We should evaluate prospective upside and valuation rather than chase a stock because it has risen.

**Sources:** [Baltussen et al. (2026)](https://pure.eur.nl/en/publications/momentum-factor-investing-evidence-and-evolution/) · [CFA Institute (2025)](https://rpc.cfainstitute.org/blogs/enterprising-investor/2025/momentum-investing-a-stronger-more-resilient-framework-for-long-term-allocators)
""")

with event:
    st.markdown(
        "**Thesis.** An important event may trigger **overreaction** to temporary "
        "damage or **underreaction** to new information. Neither is an automatic buy signal."
    )
    st.markdown(
        "**Our approach.** Assess what the event changes about future cash flows, "
        "competition, and expectations. Headline sentiment is a research clue, "
        "not a substitute for assessing fundamental impact."
    )
    st.markdown(
        "**Exit.** Reassess when the catalyst resolves, market expectations adjust, "
        "or new facts invalidate the original investment thesis."
    )
    st.caption(
        "Research: [Hirshleifer, Peng & Wang, news diffusion (2025)]"
        "(https://doi.org/10.1093/rfs/hhae025) · "
        "[Chan, reactions to news and no-news (2003)]"
        "(https://doi.org/10.1016/S0304-405X(03)00146-6). "
        "Bad headlines do not imply a reliable rebound."
    )


    with st.expander("Recent event-driven research", expanded=False):
        st.markdown("""
**Hirshleifer, Peng & Wang (2025, *Review of Financial Studies*)** find that earnings information diffusing through more connected communities generates **stronger initial stock-price reactions and weaker subsequent drift**. This is consistent with the opportunity shrinking as information becomes widespread.

A **2025 *Journal of Financial Economics*** study of price jumps around earnings announcements finds that returns from one post-announcement strategy were consistent with **efficient price formation after 2016**. Thus, a predictable post-news profit should not be assumed.

**Implication:** An event must be evaluated for what it changes about future cash flows and market expectations; a strong positive/negative sentiment reading alone is not an edge.

**Sources:** [News diffusion (2025)](https://academic.oup.com/rfs/article-abstract/38/3/883/7698199) · [Warp speed price moves (2025)](https://www.sciencedirect.com/science/article/pii/S0304405X25000182)
""")

st.divider()
st.markdown("## INVESTMENT DISCIPLINE & EXITS")
st.markdown("""
| Strategy | Primary reason to reduce or exit |
|:--|:--|
| **Regression recovery** | Fair value approached or recovery thesis deteriorated. |
| **Momentum swing** | Relative strength/trend deteriorated or risk limit reached. |
| **Event-driven** | Catalyst resolved or expected economics changed. |
| **Valuation-based reallocation** | Price rose faster than revenue, earnings, cash flow, and future growth expectations can justify. |
""")
st.markdown(
    "Rising valuation multiples prompt **reassessment, not automatic selling**: "
    "improving margins or stronger expected growth may justify them. "
    "Assess risk, taxes, transaction costs, and opportunity cost versus ETFs."
)


with st.expander("Valuation example: price outpacing fundamentals", expanded=False):
    st.markdown(
        "If a stock gains **60%** while its revenue grows **20%**, its "
        "price-to-sales multiple increases by roughly **33%** "
        "(1.60 ÷ 1.20 − 1). This may justify a reassessment, "
        "**not automatic selling**. Higher expected margins, earnings, "
        "and cash flow could still support the price. "
        "Consider next-year earnings expectations, business durability, "
        "and the risk-adjusted return available from VOO or another ETF."
    )

st.divider()
st.markdown("## LIQUIDITY & CAPITAL PRESERVATION")
st.markdown("""
| Vehicle | Best-suited purpose | Main trade-off |
|:--|:--|:--|
| **Savings / money market** | Immediate reserves | Variable yield; funds differ from insured deposits. |
| **Treasury bills / short ladder** | Dry powder for opportunities | Maturity timing; prices can fluctuate before maturity. |
| **CD ladder** | Known future cash needs | Early withdrawal restrictions; insurance limits. |
| **Municipal money market** | Tax-efficient short-term reserves | Variable yield and investor-dependent taxes. |
| **VTES — short-term munis** | Tax-efficient income with some flexibility | Interest-rate and market-price risk. |
| **VTEB — intermediate munis** | Longer-term tax-efficient fixed income | Greater duration risk; not a cash equivalent. |
""")
st.markdown(
    "**Our market-dependent approach.** When equity valuations and prospective "
    "returns appear unattractive relative to risks and bond/cash yields, we may "
    "hold additional liquid capital while maintaining meaningful diversified "
    "equity and momentum exposure. Discretionary liquidity stays **within a "
    "predetermined allocation range**, separately from emergency reserves. "
    "We do not automatically raise cash whenever prices look expensive."
)
st.markdown(
    "**Vanguard's research:** In its 2026 outlook, Vanguard's *time-varying "
    "allocation model* favored **40% stocks / 60% bonds** over the traditional "
    "60/40 approach, based on stretched equity valuations and more attractive "
    "bond yields. Vanguard also cautioned in October 2026 that valuations "
    "are **poor predictors of short- and intermediate-term returns** and should "
    "not be the main reason for adjusting allocations. That model is not a "
    "recommended allocation for this portfolio."
)
st.caption(
    "Sources: [Vanguard — Why we're underweight in stocks (Dec. 2025)]"
    "(https://corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/why-were-underweight-stocks.html) · "
    "[Vanguard — Capital Markets Model forecasts (Oct. 2026)]"
    "(https://corporate.vanguard.com/content/corporatesite/us/en/corp/vemo/vemo-return-forecasts.html)"
)
st.caption(
    "Research and educational context only. Historical premiums and backtests "
    "do not guarantee future results."
)

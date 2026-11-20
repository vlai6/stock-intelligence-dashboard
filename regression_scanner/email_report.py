"""Readable plain-text and HTML digests for scheduled regression signals.

Presentation only: never changes signal selection, regression or DCF calculations.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import urlsplit


def _money(value) -> str:
    if value is None or value == "":
        return "N/A"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _percent(value) -> str:
    if value is None or value == "":
        return "N/A"
    try:
        return f"{float(value):+.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _z(value) -> str:
    return f"{float(value):+.2f}σ".replace("-", "−")


def _zone(row: dict) -> str:
    z = float(row["z_score"])
    if z <= -4.0:
        return "BELOW −4σ"
    if z <= -3.0:
        return "BETWEEN −3σ AND −4σ"
    return "BETWEEN −2.75σ AND −3σ" if row.get("bucket") == "50B+" else "ABOVE −3σ"


def _extra_threshold(row: dict) -> str | None:
    if row.get("bucket") != "50B+":
        return None
    try:
        line = float(row["regression"])
        if row.get("sigma") is not None:
            sigma = float(row["sigma"])
        else:
            sigma = (line - float(row["lower_3"])) / 3.0
        if sigma <= 0:
            return None
        return _money(line - 2.75 * sigma)
    except (ValueError, TypeError, KeyError, ZeroDivisionError):
        return None


def _safe_link(value: str) -> str:
    """Reject non-web schemes; escape the result separately for HTML attributes."""
    url = str(value or "").strip()
    parts = urlsplit(url)
    return url if parts.scheme in ("http", "https") and parts.netloc else ""


BUCKET_ORDER = ("50B+", "25-50B", "10-25B", "5-10B", "2-5B")


def grouped_signals(signals: list[dict]) -> list[tuple[str, list[dict]]]:
    """Large-cap first; strongest (most negative) Z-score first within a bucket."""
    groups = []
    for bucket in BUCKET_ORDER:
        members = sorted(
            (row for row in signals if row.get("bucket") == bucket),
            key=lambda row: float(row["z_score"]),
        )
        if members:
            groups.append((bucket, members))
    # Retain any unfamiliar bucket instead of silently dropping its alerts.
    extras = sorted({str(row.get("bucket", "Other")) for row in signals} - set(BUCKET_ORDER))
    for bucket in extras:
        members = sorted((row for row in signals if str(row.get("bucket", "Other")) == bucket),
                         key=lambda row: float(row["z_score"]))
        groups.append((bucket, members))
    return groups


def formatted_signal(row: dict) -> str:
    """Plain-text presentation of one signal (usable outside the email digest too)."""
    zone = _zone(row)
    z = _z(row["z_score"])
    lines = [
        f"{row['ticker']} — {row.get('name', '')}  |  Market cap: {row.get('bucket', '')}",
        f"  SIGNAL: {zone}  |  Z-score: {z}",
        f"  Share price: {_money(row.get('close'))}  |  Regression trend: {_money(row.get('regression'))}",
        f"  Thresholds: −3σ = {_money(row.get('lower_3'))}  |  −4σ = {_money(row.get('lower_4'))}",
    ]
    if row.get("bucket") == "50B+" and float(row["z_score"]) <= -3.0:
        lines.insert(1, "  PRIME RESEARCH SIGNAL: $50B+ at/below −3σ. Verify fundamentals before buying.")
    if row.get("bucket") == "50B+":
        threshold = _extra_threshold(row)
        if threshold:
            lines.append(f"  −2.75σ alert threshold: {threshold}")
    value = row.get("intrinsic_value")
    if value is None or value == "":
        lines.append(f"  Intrinsic value: N/A — {row.get('valuation_note') or 'Financial data unavailable'}")
    else:
        lines += [
            f"  Intrinsic value (DCF): {_money(value)}/share",
            f"  DCF upside/downside: {_percent(row.get('upside_downside_pct'))}"
            f"  |  Margin of safety: {_percent(row.get('margin_of_safety_pct'))}",
        ]
    link = _safe_link(row.get("tradingview", ""))
    if link:
        lines.append(f"  Chart: {link}")
    return "\n".join(lines)


def _session_label(signals: list[dict], reports: list[dict]) -> str:
    for row in signals + reports:
        value = row.get("session")
        if value:
            return str(value)
    return "not available"


def _coverage_text(failed: list[str]) -> str:
    if failed:
        return "PARTIAL SCAN — missing data in: " + ", ".join(failed) + ". Some signals may be missing."
    return "Coverage: all five buckets completed without reported data errors."


def plain_report(*, started: datetime, signals: list[dict], alerts: list[dict], failed: list[str],
                 reports: list[dict], years: float, assumptions=None, ai_summary: str | None = None) -> str:
    new = {row["ticker"] for row in alerts}
    at_four = sum(float(row["z_score"]) <= -4 for row in signals)
    at_275_or_lower = sum(row.get("bucket") == "50B+" and float(row["z_score"]) <= -2.75 for row in signals)
    lines = [
        "POTENTIALLY UNDERVALUED STOCKS — REGRESSION SCANNER",
        f"Run: {started:%b %d, %Y at %I:%M %p} Eastern",
        f"Stock prices through: {_session_label(signals, reports)}",
        "=" * 52,
        f"{len(signals)} ACTIVE SIGNALS  |  {at_four} below −4σ  |  {at_275_or_lower} $50B+ at or below −2.75σ",
        f"{len(alerts)} NEW OR WORSENED  |  {years:g}-year regression",
        _coverage_text(failed),
        "",
        "HOW TO READ THE SIGNAL",
        "−3σ = stock price is at least 3 historical residual standard deviations below its regression trend.",
        "−4σ = stock price is at least 4 historical residual standard deviations below its regression trend.",
        "Alert threshold: $2–50B at −3σ or lower; $50B+ at −2.75σ or lower.",
        "A $50B+ stock below −3σ could be a prime buying opportunity for further research, not an automatic buy.",
        "The −3σ/−4σ prices are threshold lines, not forecast prices or buy targets.",
        "",
        "STOCKS — LARGEST MARKET CAP FIRST; MOST NEGATIVE Z-SCORE WITHIN EACH GROUP",
        "-" * 52,
    ]
    if not signals:
        lines.append("No active qualifying deviation signals found in the successfully checked symbols.")
    shown = 0
    for bucket, bucket_rows in grouped_signals(signals):
        if shown >= 100:
            break
        lines.extend(["", f"{bucket} STOCKS", "=" * 52])
        for row in bucket_rows:
            if shown >= 100:
                break
            shown += 1
            lines.append(f"{shown}. {'NEW / WORSENED' if row['ticker'] in new else 'EXISTING'}")
            lines.append(formatted_signal(row))
            lines.append("-" * 52)
    if len(signals) > 100:
        lines.append(f"Only the first 100 of {len(signals)} signals are shown; the full CSV is saved locally.")
    lines += [
        "",
        "MODEL NOTES",
        f"Regression: {years:g} years, 250 trading sessions/year, regular-session closing prices.",
        "Intrinsic values use a scenario-based five-year cash-flow DCF, where financial data permits.",
        "Valuation does not affect which stocks qualify for this report.",
    ]
    if assumptions is not None:
        lines.append(
            f"DCF assumptions: FCFF growth {assumptions.growth:.1%}; "
            f"WACC {assumptions.wacc:.1%}; terminal growth {assumptions.terminal_growth:.1%}."
        )
    if ai_summary:
        lines += ["", "QUANTITATIVE RESEARCH SUMMARY", ai_summary]
    lines += [
        "",
        "A statistical deviation or model valuation is not an investment recommendation.",
        "Review financial statements, catalysts and data quality before acting.",
    ]
    return "\n".join(lines)


def html_report(*, started: datetime, signals: list[dict], alerts: list[dict], failed: list[str],
                reports: list[dict], years: float, assumptions=None, ai_summary: str | None = None) -> str:
    """Gmail-friendly inline CSS. Every dynamic company name/link is escaped."""
    new = {row["ticker"] for row in alerts}
    at_four = sum(float(row["z_score"]) <= -4 for row in signals)
    at_275_or_lower = sum(row.get("bucket") == "50B+" and float(row["z_score"]) <= -2.75 for row in signals)
    e = escape
    session = _session_label(signals, reports)
    blocks: list[str] = []
    blocks.append('''<!doctype html><html><head><meta charset="utf-8"><meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark"></head>
<body bgcolor="#050912" style="margin:0;padding:0;background:#050912;color:#e4edf7;font-family:Arial,Helvetica,sans-serif;color-scheme:dark;">
<div style="max-width:700px;margin:0 auto;padding:28px 14px;">
<div style="background:#0b1420;border:1px solid #22364a;border-top:3px solid #368dbb;border-radius:12px;padding:24px;">
<div style="font-size:12px;letter-spacing:1.5px;font-weight:bold;color:#66b7e5;">REGRESSION STOCK SCANNER</div>''')
    blocks.append(f'<h1 style="font-size:24px;line-height:1.25;margin:10px 0 8px;color:#f1f7fd;">Potentially Undervalued Stocks — {len(signals)} signals</h1>')
    blocks.append(f'<div style="color:#99aec4;font-size:13px;">{e(started.strftime("%b %d, %Y • %I:%M %p"))} ET &nbsp;·&nbsp; Prices through {e(session)} &nbsp;·&nbsp; {years:g}-year lookback</div>')
    blocks.append('<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;margin:19px 0 16px;border-collapse:collapse;"><tr>')
    for value,label in ((at_four,"BELOW −4σ"),(at_275_or_lower,"$50B+ AT OR BELOW −2.75σ"),(len(alerts),"NEW / WORSENED")):
        blocks.append(f'<td style="width:33.3%;border:1px solid #29435c;background:#101f30;padding:15px 7px;text-align:center;vertical-align:top;">'
                      f'<div style="font-size:26px;font-weight:bold;color:#f2f9ff;">{value}</div>'
                      f'<div style="font-size:10px;font-weight:bold;color:#a6c1d8;letter-spacing:0.4px;line-height:1.45;">{label}</div></td>')
    blocks.append('</tr></table>')
    if failed:
        blocks.append('<div style="background:#342719;border:1px solid #9c7139;border-radius:8px;'
                      'padding:13px 15px;margin-bottom:16px;color:#ffdfaa;font-size:13px;line-height:1.5;">'
                      '<strong>PARTIAL SCAN — some opportunities may be missing.</strong><br>'
                      f'Incomplete buckets: {e(", ".join(failed))}</div>')
    else:
        blocks.append('<div style="font-size:12px;color:#9fb5c7;margin-bottom:14px;">'
                      'All five market-cap buckets completed without reported data errors.</div>')
    blocks.append('<div style="background:#10263a;border:1px solid #244965;border-left:4px solid #3e9bcc;color:#d2e3f1;padding:12px 14px;'
                  'border-radius:6px;font-size:13px;line-height:1.55;margin:0 0 20px;">'
                  '<strong>What does the standard deviation mean?</strong><br>'
                  '<strong>−3σ:</strong> Price is at least 3 historical residual standard deviations below its regression trend.<br>'
                  '<strong>−4σ:</strong> Price is at least 4 below that trend (a more extreme deviation).<br>'
                  '<strong>Alert rules:</strong> $2–50B at −3σ or lower; $50B+ at −2.75σ or lower.<br>'
                  '<strong>Prime opportunity note:</strong> $50B+ at −3σ could be a prime buying opportunity for further fundamental research—not an automatic buy.<br>'
                  '<span style="color:#a3bdd2;">Threshold prices are boundary lines—not price targets or forecasts.</span>'
                  '</div>')
    blocks.append('<h2 style="font-size:16px;margin:10px 0 14px;color:#e9f4fd;">Qualifying stocks <span style="font-size:12px;color:#9bb2c8;font-weight:normal;">· largest market cap first, most negative Z-score within each group</span></h2>')
    if not signals:
        blocks.append('<p style="font-size:14px;color:#bcd0e2;">No qualifying stocks identified in the covered symbols.</p>')
    shown = 0
    for bucket_name, bucket_rows in grouped_signals(signals):
        if shown >= 100:
            break
        blocks.append('<div style="background:#102a40;border:1px solid #254d6c;border-left:5px solid #429fd0;'
                      'padding:12px 14px;margin:24px 0 12px;border-radius:5px;">'
                      f'<strong style="font-size:19px;color:#f1f9ff;">${e(bucket_name)} Stocks</strong>'
                      f'<span style="margin-left:9px;font-size:12px;color:#a9c2d8;">{len(bucket_rows)} qualifying</span>'
                      '</div>')
        for row in bucket_rows:
            if shown >= 100:
                break
            shown += 1
            index = shown
            is_four = float(row["z_score"]) <= -4.0
            badge_text = _zone(row)
            badge_bg = "#4a2833" if is_four else "#493619"
            badge_fg = "#ffc5d2" if is_four else "#ffe1a3"
            ticker = e(str(row.get("ticker", "")))
            company = e(str(row.get("name", "")))
            bucket = e(str(row.get("bucket", "")))
            current_label = "NEW / WORSENED" if row.get("ticker") in new else "EXISTING"
            blocks.append('<div style="background:#0e1a28;border:1px solid #274057;border-radius:10px;padding:17px;margin:0 0 13px;">')
            blocks.append('<div style="margin-bottom:10px;color:#f2f8fd;">'
                          f'<span style="font-size:18px;font-weight:bold;">{index}. {ticker}</span>'
                          f'<span style="margin-left:9px;font-size:13px;color:#b6cbdc;">{company}</span>'
                          f'<strong style="display:inline-block;margin-left:9px;font-size:13px;color:#e1edf9;">'
                          f'Market cap: ${bucket}</strong></div>')
            if row.get("bucket") == "50B+" and float(row["z_score"]) <= -3.0:
                blocks.append(
                    '<div style="display:block;background:#102e29;border:1px solid #307b5e;'
                    'border-left:4px solid #34bf82;border-radius:6px;padding:9px 11px;'
                    'margin:3px 0 12px;font-size:13px;line-height:1.5;'
                    'font-weight:bold;color:#b3f5d0;">'
                    'Prime opportunity research signal: $50B+ below −3σ. '
                    'Verify fundamentals before buying.'
                    '</div>'
                )
            blocks.append(f'<div style="margin-bottom:13px;font-size:11px;">'
                          f'<span style="display:inline-block;background:{badge_bg};color:{badge_fg};padding:5px 9px;'
                          f'border-radius:5px;font-weight:bold;">{badge_text}</span>'
                          f'<span style="margin-left:8px;color:#a3b8cc;">{current_label}</span></div>')
            blocks.append('<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;margin-bottom:11px;"><tr>')
            for label,val in (("CLOSING PRICE",_money(row.get("close"))),
                              ("Z-SCORE",_z(row.get("z_score"))),
                              ("REGRESSION TREND",_money(row.get("regression")))):
                blocks.append(f'<td style="border-top:1px solid #29425a;border-bottom:1px solid #29425a;background:#112134;'
                              f'padding:10px 5px;vertical-align:top;width:33.3%;">'
                              f'<div style="font-size:10px;color:#9db8cf;font-weight:bold;">{label}</div>'
                              f'<div style="font-size:17px;font-weight:bold;margin-top:4px;color:#f0f8ff;">{e(val)}</div></td>')
            blocks.append('</tr></table>')
            blocks.append('<div style="font-size:13px;line-height:1.7;color:#d2e2f0;">'
                          f'<strong>−3σ price threshold:</strong> {e(_money(row.get("lower_3")))} '
                          '&nbsp;&nbsp;|&nbsp;&nbsp; '
                          f'<strong>−4σ price threshold:</strong> {e(_money(row.get("lower_4")))}'
                          '</div>')
            trigger = _extra_threshold(row)
            if trigger:
                blocks.append(f'<div style="font-size:13px;line-height:1.7;color:#d2e2f0;"><strong>−2.75σ alert threshold:</strong> {e(trigger)}</div>')
            intrinsic = row.get("intrinsic_value")
            if intrinsic is None or intrinsic == "":
                blocks.append(f'<div style="font-size:13px;line-height:1.6;color:#a8bed2;">'
                              f'<strong>Intrinsic value:</strong> N/A — {e(str(row.get("valuation_note") or "financial data unavailable"))}</div>')
            else:
                blocks.append('<div style="margin:8px 0 3px;padding:11px 12px;background:#14263b;border:1px solid #2b4562;border-radius:6px;color:#dfedfa;'
                              'font-size:13px;line-height:1.7;">'
                              f'<strong>DCF intrinsic value:</strong> {e(_money(intrinsic))}/share<br>'
                              f'<strong>Upside / downside:</strong> {e(_percent(row.get("upside_downside_pct")))}'
                              '&nbsp;&nbsp;|&nbsp;&nbsp;'
                              f'<strong>Margin of safety:</strong> {e(_percent(row.get("margin_of_safety_pct")))}'
                              '</div>')
            link = _safe_link(row.get("tradingview", ""))
            if link:
                blocks.append(f'<a href="{e(link, quote=True)}" style="display:inline-block;margin-top:11px;'
                              'font-size:13px;font-weight:bold;color:#66c2fa;text-decoration:underline;">View TradingView chart</a>')
            blocks.append('</div>')
    if len(signals) > 100:
        blocks.append(f'<p style="font-size:12px;color:#9fb5c8;">Only 100 of {len(signals)} displayed. Full CSV saved locally.</p>')
    blocks.append('<div style="border-top:1px solid #293e54;padding-top:16px;margin-top:17px;'
                  'font-size:12px;color:#a6bbce;line-height:1.6;">'
                  f'<strong>Method:</strong> {years:g}-year linear regression using 250 trading sessions/year and regular-session closes.<br>'
                  'Intrinsic values are indicative five-year discounted cash-flow scenarios and are not screening filters.<br>')
    if assumptions is not None:
        blocks.append(f'DCF scenario: {assumptions.growth:.1%} annual cash-flow growth; '
                      f'{assumptions.wacc:.1%} discount rate; {assumptions.terminal_growth:.1%} terminal growth.<br>')
    blocks.append('These signals do not establish a buying opportunity. Confirm news, financials, data quality and model assumptions.</div>')
    if ai_summary:
        blocks.append('<div style="margin-top:19px;padding:15px;background:#14263b;border:1px solid #2b4562;border-radius:8px;color:#dfedfa;">'
                      '<strong style="font-size:14px;">Quantitative research summary</strong>'
                      f'<div style="white-space:pre-line;font-size:13px;line-height:1.7;margin-top:8px;">{e(ai_summary)}</div></div>')
    blocks.append('</div></div></body></html>')
    return "".join(blocks)

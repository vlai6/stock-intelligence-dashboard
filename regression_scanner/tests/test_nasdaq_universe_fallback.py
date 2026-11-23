"""Offline tests for the Yahoo screener 401 -> Nasdaq stock-discovery fallback.

Never publish a partial market universe as a complete Top-N scan.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import nasdaq_universe
import universe


class Response:
    def __init__(self, rows, *, total=None, status=200):
        self.rows, self.total, self.status_code = rows, total, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return {"data": {"rows": self.rows, "totalrecords": self.total}}


def quote(symbol, cap, name=None, country="United States"):
    return {
        "symbol": symbol, "name": name or (symbol + " Corporation Common Stock"),
        "country": country, "marketCap": str(cap),
    }


class HttpStub:
    def __init__(self, by_exchange):
        self.by_exchange = by_exchange
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        assert url == nasdaq_universe.API
        assert params["tableonly"] == "true"
        assert params["limit"] == nasdaq_universe.PAGE_SIZE
        assert "Mozilla" in headers["User-Agent"]
        self.calls.append((params["exchange"], params["offset"]))
        return self.by_exchange[params["exchange"]][params["offset"]]


def test_nasdaq_fallback_filters_and_global_top_n(monkeypatch):
    source = HttpStub({
        "NASDAQ": {0: Response([
            quote("NVDA", "5000000000000"),
            quote("QQQ", "700000000000", name="Invesco QQQ ETF"),
            quote("ADR", "900000000000", name="Foreign ADR"),
            quote("FOREIGN", "800000000000", country="Canada"),
            quote("LOW", "600000000"),
        ], total=5)},
        "NYSE": {0: Response([
            quote("BRK/B", "900000000000"),
            quote("MAIN", "230000000000"),
        ], total=2)},
        "AMEX": {0: Response([quote("MINI", "5000000000")], total=1)},
    })
    monkeypatch.setattr(nasdaq_universe.time, "sleep", lambda *_: None)
    monkeypatch.setattr(universe.yf, "screen", lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(RuntimeError("HTTP Error 401: Invalid Crumb"))
    ))
    monkeypatch.setattr(nasdaq_universe.requests, "get", source.get)
    monkeypatch.setattr(universe.time, "sleep", lambda *_: None)
    selected = universe.large_cap_stocks(50, None, limit=3)
    assert [s.symbol for s in selected] == ["NVDA", "BRK-B", "MAIN"]
    assert selected[0].source.startswith("Nasdaq public screener")
    assert selected[1].exchange == "NYQ"
    assert set(source.calls) == {("NASDAQ", 0), ("NYSE", 0), ("AMEX", 0)}


def test_yahoo_unauthorized_does_not_retry_three_times(monkeypatch):
    n = []
    def fail(*_args, **_kwargs):
        n.append(1)
        raise RuntimeError("401 Client Error: Unauthorized")
    monkeypatch.setattr(universe.yf, "screen", fail)
    monkeypatch.setattr(universe, "_nasdaq_fallback",
                        lambda *args: [universe.Stock("AAPL", "Apple", "NMS", 10**12)])
    out = universe.large_cap_stocks(50, limit=1)
    assert [x.symbol for x in out] == ["AAPL"]
    assert len(n) == 1


def test_yahoo_success_still_uses_original_source(monkeypatch):
    def succeeds(*_args, **_kwargs):
        return {"quotes": [{
            "symbol": "AAPL", "longName": "Apple Inc.",
            "exchange": "NMS", "quoteType": "EQUITY",
            "marketCap": 3_000_000_000_000,
        }]}
    monkeypatch.setattr(universe.yf, "screen", succeeds)
    monkeypatch.setattr(universe, "_nasdaq_fallback",
                        lambda *args: (_ for _ in ()).throw(AssertionError("fallback used")))
    out = universe.large_cap_stocks(50, limit=1)
    assert out[0].symbol == "AAPL"
    assert out[0].source == "Yahoo Finance screener"


def test_nasdaq_discovery_rejects_incomplete_exchange(monkeypatch):
    fake = HttpStub({
        "NASDAQ": {0: Response([quote("NVDA", "5000000000000")], total=2),
                   1: Response([], total=2)},
        "NYSE": {0: Response([quote("MAIN", "600000000000")], total=1)},
        "AMEX": {0: Response([quote("MINI", "5000000000")], total=1)},
    })
    monkeypatch.setattr(nasdaq_universe.requests, "get", fake.get)
    monkeypatch.setattr(nasdaq_universe.time, "sleep", lambda *_: None)
    with pytest.raises(RuntimeError, match="truncated.*pagination"):
        nasdaq_universe.fetch_nasdaq_universe(50_000_000_000, None)


def test_fallback_refuses_unavailable_second_provider(monkeypatch):
    monkeypatch.setattr(
        nasdaq_universe, "fetch_nasdaq_universe",
        lambda *_: (_ for _ in ()).throw(RuntimeError("Nasdaq unavailable")),
    )
    with pytest.raises(RuntimeError, match="Previous successful scan results"):
        universe._nasdaq_fallback(50_000_000_000, None, 25,
                                  RuntimeError("HTTP Error 401"))


def test_nasdaq_market_cap_robust_parsing():
    assert nasdaq_universe._market_cap("$1.50T") == 1_500_000_000_000
    assert nasdaq_universe._market_cap("2,000,000,000") == 2_000_000_000
    assert nasdaq_universe._market_cap("N/A") is None
    assert nasdaq_universe._market_cap("-1000") is None

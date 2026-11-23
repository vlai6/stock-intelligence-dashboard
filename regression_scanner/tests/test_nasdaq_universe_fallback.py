"""Offline tests for Yahoo 401 -> complete Nasdaq exchange-export fallback."""
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
        return {
            "status": {"rCode": 200},
            "data": {"rows": self.rows, "totalrecords": self.total},
        }


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
        assert params["download"] == "true"
        assert params["offset"] == 0
        assert "Mozilla" in headers["User-Agent"]
        self.calls.append(params["exchange"])
        return self.by_exchange[params["exchange"]]


@pytest.fixture
def small_export(monkeypatch):
    monkeypatch.setattr(nasdaq_universe, "MIN_FULL_EXPORT_RECORDS",
                        {"NASDAQ": 3, "NYSE": 3, "AMEX": 2})


def test_nasdaq_complete_export_filters_and_global_top_n(monkeypatch, small_export):
    source = HttpStub({
        "NASDAQ": Response([
            quote("ADR", "900000000000", name="Foreign ADR"),
            quote("FOREIGN", "800000000000", country="Canada"),
            quote("LOW", "600000000"),
            quote("NVDA", "5000000000000.00"),
            quote("QQQ", "700000000000", name="Invesco QQQ ETF"),
            quote("ZZZ", "1000000"),
        ], total=6),
        "NYSE": Response([
            quote("AAA", "2000000000"),
            quote("BRK/B", "900000000000"),
            quote("MAIN", "230000000000"),
            quote("ZZZZ", "1000000"),
        ], total=4),
        "AMEX": Response([
            quote("AA", "5000000000"),
            quote("ZAAA", "1000000"),
        ], total=2),
    })
    monkeypatch.setattr(universe.yf, "screen", lambda *_args, **_kwargs: (
        (_ for _ in ()).throw(RuntimeError("HTTP Error 401: Invalid Crumb"))
    ))
    monkeypatch.setattr(nasdaq_universe.requests, "get", source.get)
    selected = universe.large_cap_stocks(50, None, limit=3)
    assert [s.symbol for s in selected] == ["NVDA", "BRK-B", "MAIN"]
    assert selected[0].source.startswith("Nasdaq public screener")
    assert selected[1].exchange == "NYQ"
    assert source.calls == ["NASDAQ", "NYSE", "AMEX"]


def test_full_download_can_exceed_previous_page_size(monkeypatch):
    # Real Nasdaq download=true exports can have several thousand rows even
    # when the query contains limit=25 or limit=1000.
    many = [
        quote(f"A{i:04}", "2000000000")
        for i in range(1400)
    ] + [quote("ZMAX", "5000000000000")]
    fake = HttpStub({
        "NASDAQ": Response(many, total=None),
        "NYSE": Response([
            quote(f"A{i:04}", "1500000000") for i in range(900)
        ] + [quote("ZEND", "900000000000")], total=None),
        "AMEX": Response([
            quote(f"A{i:04}", "1500000000") for i in range(100)
        ] + [quote("ZEND", "1000000")], total=None),
    })
    monkeypatch.setattr(nasdaq_universe.requests, "get", fake.get)
    result = nasdaq_universe.fetch_nasdaq_universe(50_000_000_000, None)
    assert [r["symbol"] for r in result] == ["ZMAX", "ZEND"]
    assert fake.calls == ["NASDAQ", "NYSE", "AMEX"]


def test_yahoo_unauthorized_does_not_retry_three_times(monkeypatch):
    attempts = []
    def reject(*_args, **_kwargs):
        attempts.append(1)
        raise RuntimeError("401 Client Error: Unauthorized")
    monkeypatch.setattr(universe.yf, "screen", reject)
    monkeypatch.setattr(universe, "_nasdaq_fallback",
                        lambda *args: [universe.Stock("AAPL", "Apple", "NMS", 10**12)])
    out = universe.large_cap_stocks(50, limit=1)
    assert [x.symbol for x in out] == ["AAPL"]
    assert len(attempts) == 1


def test_yahoo_success_uses_original_source(monkeypatch):
    monkeypatch.setattr(universe.yf, "screen", lambda *_a, **_k: {"quotes": [{
        "symbol": "AAPL", "longName": "Apple Inc.",
        "exchange": "NMS", "quoteType": "EQUITY", "marketCap": 3_000_000_000_000,
    }]})
    monkeypatch.setattr(universe, "_nasdaq_fallback",
                        lambda *args: (_ for _ in ()).throw(AssertionError("fallback used")))
    assert universe.large_cap_stocks(50, limit=1)[0].source == "Yahoo Finance screener"


def test_nasdaq_rejects_short_or_partial_download(monkeypatch, small_export):
    fake = HttpStub({
        "NASDAQ": Response([
            quote("AAPL", "5000000000000"),
            quote("ZZZZ", "1000000"),
        ], total=500),
    })
    monkeypatch.setattr(nasdaq_universe.requests, "get", fake.get)
    with pytest.raises(RuntimeError, match="potentially truncated"):
        nasdaq_universe.fetch_nasdaq_universe(50_000_000_000, None)


def test_nasdaq_rejects_wrong_full_download_total(monkeypatch, small_export):
    fake = HttpStub({
        "NASDAQ": Response([
            quote("AAPL", "5000000000000"),
            quote("MSFT", "4000000000000"),
            quote("ZZZ", "1000000"),
        ], total=800),
    })
    monkeypatch.setattr(nasdaq_universe.requests, "get", fake.get)
    with pytest.raises(RuntimeError, match="reported rows"):
        nasdaq_universe.fetch_nasdaq_universe(50_000_000_000, None)


def test_fallback_refuses_unavailable_second_provider(monkeypatch):
    monkeypatch.setattr(
        nasdaq_universe, "fetch_nasdaq_universe",
        lambda *_: (_ for _ in ()).throw(RuntimeError("Nasdaq unavailable")),
    )
    with pytest.raises(RuntimeError, match="Previous successful scan results"):
        universe._nasdaq_fallback(50_000_000_000, None, 25,
                                  RuntimeError("HTTP Error 401"))


def test_market_cap_and_country_parsing():
    assert nasdaq_universe._market_cap("$1.50T") == 1_500_000_000_000
    assert nasdaq_universe._market_cap("5074783276220.00") == 5_074_783_276_220
    assert nasdaq_universe._market_cap("2,000,000,000") == 2_000_000_000
    assert nasdaq_universe._market_cap("N/A") is None
    assert nasdaq_universe._market_cap("-1000") is None

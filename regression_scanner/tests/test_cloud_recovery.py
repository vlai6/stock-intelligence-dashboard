"""Offline regression tests for Yahoo bulk download failures on Streamlit Cloud."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest

import scanner
from universe import Stock


def stock(symbol: str) -> Stock:
    return Stock(symbol=symbol, name=symbol, exchange="NMS", cap=100_000_000_000)


def test_bulk_failure_recovers_a_valid_single_ticker(monkeypatch):
    monkeypatch.setattr(scanner, "_read_cache", lambda *_: None)
    written = []
    monkeypatch.setattr(scanner, "_write_cache", lambda *args: written.append(args))
    monkeypatch.setattr(scanner.time, "sleep", lambda _: None)

    def fail_download(**kwargs):
        raise RuntimeError("test bulk error")
    monkeypatch.setattr(scanner.yf, "download", fail_download)

    history = pd.DataFrame(
        {"Close": [100., 101., 102.]},
        index=pd.to_datetime(["2026-11-18", "2026-11-19", "2026-11-20"]),
    )

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol
        def history(self, **kwargs):
            assert kwargs["end"] == "2026-11-21"  # exclusive end
            return history if self.symbol == "AAPL" else pd.DataFrame()
    monkeypatch.setattr(scanner.yf, "Ticker", FakeTicker)

    values, cache_hits = scanner._download_batch(
        [stock("AAPL"), stock("MSFT")], "2026-11-01", "2026-11-20"
    )
    assert cache_hits == 0
    assert len(values["AAPL"]) == 3
    assert values["MSFT"].empty
    assert [call[0] for call in written] == ["AAPL"]


def test_rate_limited_individual_probes_stop_without_fabricating_prices(monkeypatch):
    monkeypatch.setattr(scanner, "_read_cache", lambda *_: None)
    monkeypatch.setattr(scanner.time, "sleep", lambda _: None)
    symbols = [f"T{i}" for i in range(25)]
    columns = pd.MultiIndex.from_product([symbols, ["Close"]])
    # Yahoo can return a formally nonempty frame containing only NaN prices.
    bulk = pd.DataFrame(np.nan, index=pd.to_datetime(["2026-11-20"]),
                        columns=columns)
    monkeypatch.setattr(scanner.yf, "download", lambda **_: bulk)

    probes = []
    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol
        def history(self, **kwargs):
            probes.append(self.symbol)
            return pd.DataFrame()
    monkeypatch.setattr(scanner.yf, "Ticker", FakeTicker)

    results, hits = scanner._download_batch(
        [stock(f"T{i}") for i in range(25)], "2021-01-01", "2026-11-20"
    )
    assert hits == 0
    assert all(series.empty for series in results.values())
    assert len(probes) == 5  # capped, no retry storm


def test_failed_bulk_and_single_probes_raise_actionable_error(monkeypatch):
    monkeypatch.setattr(scanner, "_read_cache", lambda *_: None)
    monkeypatch.setattr(scanner.time, "sleep", lambda _: None)
    monkeypatch.setattr(scanner.yf, "download", lambda **_: (_ for _ in ()).throw(ValueError("rate limited")))

    count = []
    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol
        def history(self, **kwargs):
            count.append(self.symbol)
            raise ValueError("single rate limited")
    monkeypatch.setattr(scanner.yf, "Ticker", FakeTicker)

    with pytest.raises(RuntimeError, match="Yahoo Finance returned no prices"):
        scanner._download_batch([stock(f"T{i}") for i in range(25)],
                                "2021-01-01", "2026-11-20")
    assert count == ["T0", "T1"]  # stop probing a blocked provider


def test_field_first_multiindex_history_is_supported(monkeypatch):
    monkeypatch.setattr(scanner, "_read_cache", lambda *_: None)
    monkeypatch.setattr(scanner, "_write_cache", lambda *_: None)
    idx = pd.to_datetime(["2026-11-19", "2026-11-20"])
    cols = pd.MultiIndex.from_tuples([("Close", "AAPL"), ("Close", "MSFT")])
    bulk = pd.DataFrame([[100., 200.], [101., 201.]], index=idx, columns=cols)
    monkeypatch.setattr(scanner.yf, "download", lambda **kwargs: bulk)
    values, hits = scanner._download_batch(
        [stock("AAPL"), stock("MSFT")], "2026-11-01", "2026-11-20"
    )
    assert hits == 0
    assert values["AAPL"].iloc[-1] == pytest.approx(101.)
    assert values["MSFT"].iloc[-1] == pytest.approx(201.)


def test_daily_history_does_not_invent_missing_target_session():
    idx = pd.to_datetime(["2026-11-18", "2026-11-19"])
    history = pd.DataFrame({"Close": [100., 105.]}, index=idx)
    closes = scanner._clean_daily_closes(history, "2026-11-20")
    assert closes.index[-1].strftime("%Y-%m-%d") == "2026-11-19"

"""Scheduled scanner worker for the entire price-processing batch.

The parent hard-kills this process on timeout. Cache reads, Yahoo download,
cache writes, and result serialization all run within that wall-clock limit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Read the same local automation configuration before importing scanner, which
# selects the cache directory when the module is first imported.
load_dotenv(Path(__file__).with_name(".env"))


def main() -> None:
    if len(sys.argv) in (4, 5) and sys.argv[1] == "--full-batch":
        request_file, output_file = Path(sys.argv[2]), Path(sys.argv[3])
        info = json.loads(request_file.read_text(encoding="utf-8"))
        from scanner import _download_batch
        from universe import Stock
        stocks = [Stock(**record) for record in info["stocks"]]
        if not stocks or len(stocks) > 25:
            raise ValueError("Full-batch watchdog expects 1 to 25 stocks")
        prices, hits = _download_batch(
            stocks, info["start"], info["target"],
            bypass_cache=bool(info.get("bypass_cache", False)),
            recover_individual=False,  # Preserve strict 20-second scheduled watchdog
        )
        pd.to_pickle((prices, hits), output_file, compression="gzip")
        return

    # Compatible with the previous version of the worker. The old helper is
    # not called by the scheduled scanning path after this patch.
    if len(sys.argv) == 2:
        import yfinance as yf
        request = json.load(sys.stdin)
        symbols = request["symbols"]
        data = yf.download(
            tickers=symbols, start=request["start"], interval="1d",
            auto_adjust=False, group_by="ticker", multi_level_index=True,
            progress=False, threads=int(request.get("download_threads", 4)),
            timeout=20,
        )
        if data is None or data.empty:
            raise RuntimeError("Yahoo returned no price history for the batch")
        data.to_pickle(Path(sys.argv[1]), compression="gzip")
        return

    raise ValueError("Invalid price batch worker invocation")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Parent passes an optional error path. Open only upon failure, then
        # immediately close it; no Windows-inherited stderr file handle.
        if len(sys.argv) == 5 and sys.argv[1] == "--full-batch":
            try:
                Path(sys.argv[4]).write_text(
                    f"{type(exc).__name__}: {str(exc)[:180]}", encoding="utf-8"
                )
            except OSError:
                pass
        raise SystemExit(1)

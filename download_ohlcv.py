"""Download OHLCV data for all KOSPI and KOSDAQ tickers.

This script uses the ``pykrx`` library to download approximately 400
trading days of OHLCV data for every stock listed on the KOSPI and
KOSDAQ markets. Each stock's data is saved as a CSV file in the ``data``
directory.

Usage:
    python3 download_ohlcv.py

The script will attempt to install ``pykrx`` if it is not available.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta


def ensure_pykrx() -> None:
    """Ensure that the ``pykrx`` package is installed."""
    try:
        import pykrx  # type: ignore  # noqa: F401
    except ImportError:
        print("pykrx not found. Attempting to install...")
        subprocess.check_call([
            "python3",
            "-m",
            "pip",
            "install",
            "pykrx",
        ])


def get_tickers() -> list[str]:
    """Return a list of all KOSPI and KOSDAQ tickers."""
    from pykrx import stock

    tickers = stock.get_market_ticker_list(market="KOSPI")
    tickers += stock.get_market_ticker_list(market="KOSDAQ")
    return tickers


def save_ohlcv(ticker: str, start: datetime, end: datetime) -> None:
    """Fetch and save OHLCV data for ``ticker`` between ``start`` and ``end``."""
    from pykrx import stock

    df = stock.get_market_ohlcv_by_date(
        start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), ticker
    )
    if df.empty:
        print(f"No data for {ticker}")
        return

    os.makedirs("data", exist_ok=True)
    csv_path = os.path.join("data", f"{ticker}.csv")
    df.to_csv(csv_path)
    print(f"Saved {ticker} -> {csv_path}")


def main() -> None:
    ensure_pykrx()

    end = datetime.today()
    # Roughly 400 trading days ~ about 560 calendar days.
    start = end - timedelta(days=560)

    tickers = get_tickers()
    print(f"Found {len(tickers)} tickers")

    for ticker in tickers:
        try:
            save_ohlcv(ticker, start, end)
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to fetch {ticker}: {exc}")


if __name__ == "__main__":
    main()

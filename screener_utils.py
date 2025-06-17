from __future__ import annotations

"""Utility helpers for stock screeners."""

import subprocess
from datetime import datetime
from typing import Dict


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


def load_market_caps(date: datetime) -> Dict[str, float]:
    """Return market caps for all tickers on ``date``."""
    from pykrx import stock

    df = stock.get_market_cap_by_ticker(date.strftime("%Y%m%d"))
    caps = df["시가총액"].to_dict()
    return {str(k): float(v) for k, v in caps.items()}


import pandas as pd


def relative_strength(df: pd.DataFrame) -> float:
    """Compute a simple 52-week relative strength measure."""
    last_price = df["종가"].iloc[-1]
    high52 = df["종가"].rolling(252).max().iloc[-1]
    low52 = df["종가"].rolling(252).min().iloc[-1]
    if high52 == low52:
        return 0.0
    return 100 * (last_price - low52) / (high52 - low52)

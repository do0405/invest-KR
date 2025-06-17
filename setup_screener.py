from __future__ import annotations

"""Run the setup-style stock screener."""

import os
from datetime import datetime
from typing import Any

import pandas as pd

from screener_utils import ensure_pykrx, load_market_caps, relative_strength


DATA_DIR = "data"
RESULT_DIR = "result"


def setup_screener(df: pd.DataFrame, cap: float) -> bool:
    """Return ``True`` if ``df`` satisfies the setup screener criteria."""
    if df.empty:
        return False

    price = df["종가"].iloc[-1]
    if price <= 1500:
        return False

    if cap <= 60_000_000_000:
        return False

    volume = df["거래량"].iloc[-1]
    if volume <= 100_000:
        return False

    vol60 = df["거래량"].rolling(60).mean().iloc[-1]
    if vol60 <= 250_000:
        return False

    perf1w = df["종가"].pct_change(5).iloc[-1]
    if not (-0.25 < perf1w < 0.25):
        return False

    perf1m = df["종가"].pct_change(21).iloc[-1]
    if perf1m <= 0.10:
        return False

    adr = ((df["고가"] - df["저가"]) / df["종가"]).rolling(20).mean().iloc[-1] * 100
    if adr <= 3:
        return False

    ema10 = df["종가"].ewm(span=10).mean().iloc[-1]
    ema20 = df["종가"].ewm(span=20).mean().iloc[-1]
    ema50 = df["종가"].ewm(span=50).mean().iloc[-1]

    if not (ema50 < ema20 < ema10):
        return False

    ma20 = df["종가"].rolling(20).mean().iloc[-1]
    std20 = df["종가"].rolling(20).std().iloc[-1]
    bb_upper = ma20 + 2 * std20
    if bb_upper <= price:
        return False

    return True


def run() -> None:
    """Execute the setup screener and save results."""
    ensure_pykrx()

    today = datetime.today()
    caps = load_market_caps(today)

    rows: list[dict[str, Any]] = []

    if not os.path.isdir(DATA_DIR):
        print("data directory not found. Run download_ohlcv.py first.")
        return

    for file in os.listdir(DATA_DIR):
        if not file.endswith(".csv"):
            continue
        ticker = os.path.splitext(file)[0]
        path = os.path.join(DATA_DIR, file)
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if df.empty:
            continue

        cap = caps.get(ticker, 0.0)

        if setup_screener(df, cap):
            rows.append({"ticker": ticker, "relative_strength": relative_strength(df)})

    os.makedirs(RESULT_DIR, exist_ok=True)

    result_df = pd.DataFrame(rows).sort_values("relative_strength", ascending=False)
    result_df.to_csv(os.path.join(RESULT_DIR, "setup_screener.csv"), index=False)
    result_df.to_json(os.path.join(RESULT_DIR, "setup_screener.json"), orient="records", force_ascii=False)


if __name__ == "__main__":
    run()

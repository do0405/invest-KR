from __future__ import annotations

"""Run the Mark Minervini style stock screener."""

import os
from datetime import datetime
from typing import Any

import pandas as pd

from screener_utils import ensure_pykrx, load_market_caps, relative_strength

DATA_DIR = "data"
RESULT_DIR = "result"


def minervini_screener(df: pd.DataFrame) -> bool:
    """Return ``True`` if ``df`` meets Mark Minervini criteria."""
    if len(df) < 252:
        return False

    price = df["종가"].iloc[-1]

    ma50 = df["종가"].rolling(50).mean()
    ma150 = df["종가"].rolling(150).mean()
    ma200 = df["종가"].rolling(200).mean()

    conds = [
        price > ma150.iloc[-1] and price > ma200.iloc[-1],
        ma150.iloc[-1] > ma200.iloc[-1],
        ma200.iloc[-1] > ma200.shift(21).iloc[-1],
        ma50.iloc[-1] > ma150.iloc[-1] and ma50.iloc[-1] > ma200.iloc[-1],
        price > ma50.iloc[-1],
    ]
    if not all(conds):
        return False

    low52 = df["종가"].rolling(252).min().iloc[-1]
    high52 = df["종가"].rolling(252).max().iloc[-1]

    if price <= low52 * 1.30:
        return False

    if price < high52 * 0.75:
        return False

    if relative_strength(df) < 70:
        return False

    return True


def run() -> None:
    """Execute the Minervini screener and save results."""
    ensure_pykrx()

    today = datetime.today()
    caps = load_market_caps(today)  # not strictly needed but maybe useful

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

        if minervini_screener(df):
            rows.append({"ticker": ticker, "relative_strength": relative_strength(df)})

    os.makedirs(RESULT_DIR, exist_ok=True)

    result_df = pd.DataFrame(rows).sort_values("relative_strength", ascending=False)
    result_df.to_csv(os.path.join(RESULT_DIR, "minervini_screener.csv"), index=False)
    result_df.to_json(os.path.join(RESULT_DIR, "minervini_screener.json"), orient="records", force_ascii=False)


if __name__ == "__main__":
    run()

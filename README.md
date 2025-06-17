# invest-KR

This repository contains utilities for downloading historical OHLCV data
from the Korean stock markets (KOSPI and KOSDAQ).

## Downloading data

The script `download_ohlcv.py` fetches approximately 400 trading days of
OHLCV data for every listed KOSPI and KOSDAQ stock and stores each
stock's data as a CSV file inside the `data` directory.

### Usage

```bash
python3 download_ohlcv.py
```

The script requires the [`pykrx`](https://github.com/sharebook-kr/pykrx)
package. If the package is not installed, the script will attempt to
install it using `pip`.

## Running screeners

After downloading data you can execute each screener separately. The
results are written to the `result` directory in both CSV and JSON format.

Run the setup screener:

```bash
python3 setup_screener.py
```

Run the Mark Minervini screener:

```bash
python3 minervini_screener.py
```

You can also run both at once using `run_screeners.py`:

```bash
python3 run_screeners.py
```

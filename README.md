# invest-KR

This repository contains utilities for downloading historical OHLCV data
from the Korean stock markets (KOSPI and KOSDAQ) and running various stock screeners.

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

Run the Advanced Mark Minervini screener (with financial statement criteria):

```bash
python3 advanced_minervini_screener.py
```

You can also run all screeners at once using `main.py`:

```bash
python3 main.py
```

## Advanced Mark Minervini Screener

The Advanced Mark Minervini Screener combines technical analysis criteria with financial statement analysis. It requires the `dart-fss` library to fetch financial data from the DART (Data Analysis, Retrieval and Transfer) system.

### Prerequisites

1. Install required packages:

```bash
pip install -r requirements.txt
```

2. Obtain an API key from [Open DART](https://opendart.fss.or.kr)

3. Set your API key as an environment variable:

```bash
# Windows
set DART_API_KEY=your_api_key_here

# macOS/Linux
export DART_API_KEY=your_api_key_here
```

Alternatively, you can enter your API key when prompted during execution.

### Financial Criteria

The Advanced Mark Minervini Screener applies the following financial criteria in addition to the technical criteria:

- Quarterly EPS growth rate: Minimum 25% or higher, with acceleration for at least 2 consecutive quarters
- Annual EPS growth rate: Minimum 15% or higher for the past 3 years
- Quarterly revenue growth rate: Minimum 25% or higher, with acceleration for at least 2 consecutive quarters
- Annual revenue growth rate: Minimum 15% or higher for the past 3 years
- Operating profit growth rate: 30-40% or higher, with solid operating profit for 4-6 consecutive quarters
- Debt-to-equity ratio: 150% or lower

from __future__ import annotations

"""Run both stock screeners."""

import setup_screener
import minervini_screener


def main() -> None:
    setup_screener.run()
    minervini_screener.run()


if __name__ == "__main__":
    main()

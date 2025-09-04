import time
import yfinance as yf
import logging
from typing import Tuple

logger = logging.getLogger("stock-alerts")


def get_open_and_last(ticker: str) -> Tuple[float, float]:
    """
    Retrieve today's opening price and the latest available price for a ticker.

    Strategy:
      1. Try intraday data with finer intervals ("1m", "5m", "15m").
         - Use the very first "Open" of the day.
         - Use the most recent "Close" (last candle).
         - Retry once per interval in case Yahoo delivers empty DataFrames.
      2. If no intraday data is available (e.g., market closed),
         fall back to daily interval ("1d").
    """
    # DONE: Loop over intraday intervals ("1m", "5m", "15m")
    for interval in ("1m", "5m", "15m"):

        # DONE: For each interval, attempt up to two retries
        for attempt in range(2):
            try:
                df = yf.Ticker(ticker).history(
                    period="1d", interval=interval, auto_adjust=False
                )
                # if not df.empty:
                if not df.empty and "Open" in df.columns and "Close" in df.columns:
                    open_today = float(df.iloc[0]["Open"])
                    last_price = float(df.iloc[-1]["Close"])
                    logger.debug(
                        "Intraday %s: interval=%s open=%.4f last=%.4f",
                        ticker, interval, open_today, last_price,
                    )
                    # print("df[0]: ", df[0])
                    # print("df[-1]: ", df[-1])
                    return open_today, last_price
                else:
                    logger.debug(
                        "No intraday %s data for %s (attempt %d) — market may be closed",
                        ticker, interval, attempt + 1,
                    )
            except Exception as e:
                logger.warning(
                    "Intraday fetch error for %s (interval=%s, attempt=%d): %s",
                    ticker, interval, attempt + 1, repr(e),
                )
            
            time.sleep(0.4)

    # DONE: Fallback to daily data ("1d" interval)
    try:
        df = yf.Ticker(ticker).history(period="1d", interval="1d", auto_adjust=False)
        if not df.empty and "Open" in df.columns and "Close" in df.columns:
            row = df.iloc[-1]
            open_today, last_price = float(row["Open"]), float(row["Close"])
            logger.debug(
                "Fallback daily data %s: open=%.4f last=%.4f (market likely closed)",
                ticker, open_today, last_price,
            )
            return open_today, last_price
        else:
            logger.warning("Primary daily fallback empty for %s → trying 5d", ticker)

    except Exception as e:
        logger.warning("Fallback daily fetch failed for %s: %r  → will try 5d next", ticker, repr(e))

    # DONE: Second fallback to "5d" data
    try:
        df = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
        if not df.empty and "Open" in df.columns and "Close" in df.columns:
            row = df.iloc[-1]
            open_today, last_price = float(row["Open"]), float(row["Close"])
            logger.debug(
                "Fallback 5-day data for %s: open=%.4f last=%.4f (using last trading day)",
                ticker, open_today, last_price,
            )
            return open_today, last_price
        else:
            raise RuntimeError(f"No usable 5d data for {ticker}")

    except Exception as e:
        logger.error("Second fallback (5d) fetch failed for %s: %r", ticker, repr(e))
        raise RuntimeError(f"Could not retrieve price data for {ticker}") from e

    # pass  # Remove once implemented

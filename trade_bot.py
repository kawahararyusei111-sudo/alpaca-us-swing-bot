"""Alpaca paper trading bot: SMA(20/50) crossover on a fixed US stock watchlist.

Runs once per invocation (intended to be fired on a schedule by GitHub Actions).
All state (positions, cash) lives in the Alpaca paper account itself, so each
run is independent and stateless on this side.

Safety: PAPER_BASE / DATA_BASE are hardcoded to Alpaca's paper endpoints.
Switching to live trading requires deliberately editing those two constants.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

PAPER_BASE = "https://paper-api.alpaca.markets"
DATA_BASE = "https://data.alpaca.markets"

WATCHLIST = ["MU", "NVDA", "MSFT", "PLTR", "CRWV", "NBIS", "QQQ", "AAPL", "SPY", "JNJ", "JPM"]
SHORT_WINDOW = 20
LONG_WINDOW = 50
POSITION_PCT = 0.30  # fraction of equity to put into a single new position
MAX_POSITIONS = 3
STOP_LOSS_PCT = -0.05  # unrealized P/L fraction that forces an exit
# Runs fire only a few times a day, so a cross that happened between runs
# would be missed if we only looked at the latest bar. Treat a cross within
# the last CROSS_LOOKBACK bars as valid, as long as the trend still holds now.
CROSS_LOOKBACK = 8
HISTORY_DAYS = 30  # calendar days of hourly bars to request


def _headers():
    key = os.environ.get("ALPACA_API_KEY_ID")
    secret = os.environ.get("ALPACA_API_SECRET_KEY")
    if not key or not secret:
        sys.exit("ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY が環境変数に設定されていません。")
    return {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Content-Type": "application/json",
    }


def req(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} on {url}: {e.read().decode()}")
        raise


def get_clock():
    return req(f"{PAPER_BASE}/v2/clock")


def get_account():
    return req(f"{PAPER_BASE}/v2/account")


def get_positions():
    return {p["symbol"]: p for p in req(f"{PAPER_BASE}/v2/positions")}


def get_closes(symbol, limit):
    # Without `start`, Alpaca only returns bars from the current day, which is
    # never enough for SMA50 on hourly bars. Request a wider window explicitly.
    start = (datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    closes = []
    page_token = None
    while True:
        url = (f"{DATA_BASE}/v2/stocks/{symbol}/bars?timeframe=1Hour&start={start}"
               f"&limit=10000&adjustment=raw&feed=iex")
        if page_token:
            url += f"&page_token={page_token}"
        resp = req(url)
        closes += [b["c"] for b in resp.get("bars") or []]
        page_token = resp.get("next_page_token")
        if not page_token:
            break
    return closes[-limit:]


def sma(values, window):
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def place_order(symbol, side, notional):
    body = {
        "symbol": symbol,
        "notional": round(notional, 2),
        "side": side,
        "type": "market",
        "time_in_force": "day",
    }
    result = req(f"{PAPER_BASE}/v2/orders", method="POST", body=body)
    print(f"  -> order submitted: {side} {symbol} ${notional:.2f} (id={result.get('id')})")


def main():
    now = datetime.now(timezone.utc).isoformat()
    clock = get_clock()
    if not clock["is_open"]:
        print(f"[{now}] Market closed (next open: {clock.get('next_open')}). Skipping.")
        return

    account = get_account()
    equity = float(account["equity"])
    positions = get_positions()
    print(f"[{now}] equity=${equity:.2f} open_positions={list(positions.keys())}")

    for symbol in WATCHLIST:
        try:
            closes = get_closes(symbol, LONG_WINDOW + CROSS_LOOKBACK + 1)
        except Exception as e:
            print(f"{symbol}: failed to fetch bars ({e}), skipping")
            continue

        if len(closes) < LONG_WINDOW + 1:
            print(f"{symbol}: not enough bar history yet, skipping")
            continue

        held = symbol in positions

        if held:
            unrealized_plpc = float(positions[symbol]["unrealized_plpc"])
            if unrealized_plpc <= STOP_LOSS_PCT:
                print(f"{symbol}: stop loss hit ({unrealized_plpc:.2%})")
                place_order(symbol, "sell", float(positions[symbol]["market_value"]))
                continue

        short_now = sma(closes, SHORT_WINDOW)
        long_now = sma(closes, LONG_WINDOW)

        # Sign of (SMA_short - SMA_long) for each of the last CROSS_LOOKBACK+1 bars
        diffs = []
        for k in range(min(CROSS_LOOKBACK, len(closes) - LONG_WINDOW), -1, -1):
            window = closes[:len(closes) - k]
            diffs.append(sma(window, SHORT_WINDOW) - sma(window, LONG_WINDOW))
        recent_golden = any(a <= 0 < b for a, b in zip(diffs, diffs[1:]))
        recent_death = any(a >= 0 > b for a, b in zip(diffs, diffs[1:]))

        golden_cross = recent_golden and short_now > long_now
        death_cross = recent_death and short_now < long_now

        if golden_cross and not held and len(positions) < MAX_POSITIONS:
            notional = equity * POSITION_PCT
            print(f"{symbol}: golden cross (SMA{SHORT_WINDOW}={short_now:.2f} > SMA{LONG_WINDOW}={long_now:.2f})")
            place_order(symbol, "buy", notional)
        elif death_cross and held:
            print(f"{symbol}: death cross (SMA{SHORT_WINDOW}={short_now:.2f} < SMA{LONG_WINDOW}={long_now:.2f})")
            place_order(symbol, "sell", float(positions[symbol]["market_value"]))
        else:
            print(f"{symbol}: no action (SMA{SHORT_WINDOW}={short_now:.2f}, SMA{LONG_WINDOW}={long_now:.2f}, held={held})")


if __name__ == "__main__":
    main()

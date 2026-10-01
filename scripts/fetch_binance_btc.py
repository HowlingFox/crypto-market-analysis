#!/usr/bin/env python3
"""Fetch BTCUSDT public Binance USD-M futures market data.

No API key is required. The script saves a JSON bundle that can be passed to
analyze_btc_structure.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://fapi.binance.com"
TIMEOUT = 12


def http_get(base_url: str, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = base_url.rstrip("/") + path
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": "btc-market-structure-alert/1.0"})
    started = time.time()
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return {
                "ok": True,
                "url": url,
                "status": resp.status,
                "elapsed_ms": round((time.time() - started) * 1000, 1),
                "data": json.loads(body),
            }
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        return {"ok": False, "url": url, "status": exc.code, "error": body[:500]}
    except URLError as exc:
        return {"ok": False, "url": url, "error": str(exc.reason)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "url": url, "error": repr(exc)}


def fetch_bundle(symbol: str, base_url: str, kline_limit: int, market_limit: int) -> Dict[str, Any]:
    periods = ["15m", "1h", "4h"]
    fetched_at = datetime.now(timezone.utc)
    bundle: Dict[str, Any] = {
        "meta": {
            "symbol": symbol,
            "base_url": base_url,
            "fetched_at": fetched_at.isoformat(),
            "data_updated_at": fetched_at.strftime("%Y-%m-%d %H:%M:%S"),
            "data_source": "Binance public API",
            "note": "public Binance USD-M futures data; no api key used",
        },
        "klines": {},
        "open_interest_hist": {},
        "taker_long_short": {},
        "global_long_short": {},
        "top_long_short_account": {},
        "top_long_short_position": {},
    }

    for interval in periods:
        bundle["klines"][interval] = http_get(
            base_url,
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": kline_limit},
        )

    bundle["premium_index"] = http_get(base_url, "/fapi/v1/premiumIndex", {"symbol": symbol})
    bundle["funding_rate"] = http_get(base_url, "/fapi/v1/fundingRate", {"symbol": symbol, "limit": 90})
    bundle["open_interest"] = http_get(base_url, "/fapi/v1/openInterest", {"symbol": symbol})

    for period in periods:
        common = {"symbol": symbol, "period": period, "limit": market_limit}
        bundle["open_interest_hist"][period] = http_get(base_url, "/futures/data/openInterestHist", common)
        bundle["taker_long_short"][period] = http_get(base_url, "/futures/data/takerlongshortRatio", common)
        bundle["global_long_short"][period] = http_get(base_url, "/futures/data/globalLongShortAccountRatio", common)
        bundle["top_long_short_account"][period] = http_get(base_url, "/futures/data/topLongShortAccountRatio", common)
        bundle["top_long_short_position"][period] = http_get(base_url, "/futures/data/topLongShortPositionRatio", common)

    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch BTCUSDT public Binance futures market data")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--kline-limit", type=int, default=1000)
    parser.add_argument("--market-limit", type=int, default=96)
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()

    bundle = fetch_bundle(args.symbol.upper(), args.base_url, args.kline_limit, args.market_limit)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
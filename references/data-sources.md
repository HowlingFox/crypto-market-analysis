# Data Sources

## Primary Source: Binance USDⓈ-M Futures Public Market Data

Use public endpoints only. No API key is required for the first version.

All generated alerts should display `数据来源：Binance public API` and the fetch timestamp as `数据更新时间：YYYY-MM-DD HH:mm:ss`.

Base URL:

```text
https://fapi.binance.com
```

Recommended endpoints:

| Data group | Endpoint | Purpose |
|---|---|---|
| OHLCV/Klines | `/fapi/v1/klines` | 15m, 1h, 4h price and volume structure |
| Mark/index/funding | `/fapi/v1/premiumIndex` | mark price, index price, last funding rate, next funding time |
| Funding history | `/fapi/v1/fundingRate` | recent 8h funding history |
| Current OI | `/fapi/v1/openInterest` | current contract open interest |
| OI history | `/futures/data/openInterestHist` | OI changes by period |
| Taker flow | `/futures/data/takerlongshortRatio` | taker buy/sell volume and buy/sell ratio |
| Global long/short | `/futures/data/globalLongShortAccountRatio` | market long/short account ratio |
| Top trader account ratio | `/futures/data/topLongShortAccountRatio` | top trader account long/short ratio |
| Top trader position ratio | `/futures/data/topLongShortPositionRatio` | top trader position long/short ratio |

## Default Parameters

Symbol:

```text
BTCUSDT
```

Timeframes:

```text
15m, 1h, 4h
```

Default limits:

- Klines: 1000 candles per timeframe by default (Binance USDⓈ-M endpoint maximum: 1500)
- OI history: 96 records where available
- Taker flow: 96 records where available
- Long/short ratio: 96 records where available
- Funding history: 90 records when available

## Missing Data Rules

If a data call fails, do not hallucinate the value. Mark the data group as missing.

If only price/volume is available, output only price-volume analysis.

If OI is missing, say: `missing open-interest confirmation`.

If funding is missing, say: `missing funding overcrowding check`.

If taker flow is missing, say: `missing active buy/sell flow confirmation`.

If three or more of OI, funding, taker flow, long/short ratio, and basis are missing, classify as `data_insufficient`.

Technical indicator values are calculated locally from public exchange OHLCV candles because these market-data endpoints return candles, not ready-made KDJ/RSI/AR/BR/WMSR/CCI/OSC values. Fetching 1000 bars gives recursive RSI/KDJ calculations a longer warm-up history; finite-window indicators still use their documented lookback lengths.

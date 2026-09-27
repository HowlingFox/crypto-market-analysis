---
name: btc-market-structure-alert
description: btc market structure alerting for openclaw or chatgpt. use when the user asks to analyze btcusdt with live market structure, volume-price action, taker buy/sell flow, open interest, funding rate, long/short ratio, basis or premium, liquidation-risk proxies, support/resistance, or wants scheduled btc alerts for 1-2 day medium-short-term trading. this skill fetches public binance usdt-m futures data, computes structure signals, classifies market states, and outputs risk-aware alerts without giving direct buy/sell or auto-trading instructions.
---

# BTC Market Structure Alert

## Purpose

Use this skill to make OpenClaw perform repeatable BTCUSDT market-structure scans for 1-2 day medium-short-term trading. The skill must analyze market structure from data, not from intuition, and it must produce alerts rather than trading commands.

The default data source is Binance USDⓈ-M Futures public market data. No API key, exchange secret, wallet key, or trading permission is required.

## Core Workflow

When asked to run a BTC market-structure scan or scheduled alert:

1. Fetch current BTCUSDT public data with `scripts/fetch_binance_btc.py` when live internet access is available.
2. Analyze the saved JSON with `scripts/analyze_btc_structure.py`.
3. If scripts cannot be executed, follow `references/signal-matrix.md` and `references/alert-rules.md` manually using any available market data.
4. Always apply `references/risk-filter.md` before final wording.
5. Output using `references/output-template.md`.
6. Every alert or scan output must include these two metadata lines near the top:
   - `数据更新时间：YYYY-MM-DD HH:mm:ss`
   - `数据来源：Binance public API`

Recommended command sequence:

```bash
python scripts/fetch_binance_btc.py --symbol BTCUSDT --out /tmp/btc_market.json
python scripts/analyze_btc_structure.py --input /tmp/btc_market.json --format markdown
```

For OpenClaw cron, prefer the second command's markdown result as the message body. If no medium/high alert is triggered, keep the response short.

## Required Timeframes

For the user's stated 1-2 day trading style, prioritize:

- 4h: direction and structural background
- 1h: main trade rhythm and confirmation
- 15m: alert trigger and short-term invalidation context

Do not make a high-confidence alert from 5m data alone.

## Required Data Checks

Try to inspect all of the following:

- price and OHLCV on 15m, 1h, and 4h
- volume ratio versus recent average
- taker buy/sell volume and ratio
- open interest current level and 15m/1h/4h/24h changes when available
- current funding rate and funding history
- funding APR, 24h funding sum, 7d/30d percentile, z-score, momentum, and 1-2 day holding-cost estimate
- global and top-trader long/short ratios when available
- mark price, index price, and premium/basis
- support/resistance from recent swing highs/lows and range boundaries
- liquidation-risk proxies: high OI buildup, extreme funding, high volume shock, and fast OI contraction

If three or more core data groups are missing, classify as `data_insufficient` and advise observation only.

## Market State Labels

Classify the current state into one of these labels:

1. `healthy_uptrend`
2. `crowded_long_uptrend`
3. `volume_breakout`
4. `false_breakout_risk`
5. `healthy_downtrend`
6. `crowded_short_downtrend`
7. `volume_breakdown`
8. `leveraged_range_build`
9. `post_liquidation_release`
10. `data_insufficient`

Do not output vague labels such as only “bullish”, “bearish”, or “sideways”.

## Alert Levels

Use four alert levels:

- `none`: no meaningful alert
- `low`: watchlist only
- `medium`: user should pay attention
- `high`: important risk or structure shift; notify clearly

Only medium/high alerts should be long. For none/low alerts, be concise.

## Funding Rate Rules

Funding is an overcrowding and holding-cost indicator, not a standalone directional signal.

Compute or estimate:

- `current_funding_8h`
- `funding_apr = current_funding_8h * 3 * 365`
- `funding_24h_sum = sum(last_3_funding)`
- `funding_7d_percentile`
- `funding_30d_percentile`
- `funding_z_30d`
- `funding_momentum = current - median(last_3_funding)`
- `expected_1d_cost = current_funding_8h * 3`
- `expected_2d_cost = current_funding_8h * 6`

Interpretation:

- Positive funding: longs pay shorts; long side may be crowded.
- Negative funding: shorts pay longs; short side may be crowded.
- Extreme positive funding plus weakening price/flow is a long-crowding warning.
- Extreme negative funding plus weakening sell pressure is a short-crowding warning.

## Safety Constraints

Never produce direct trading instructions such as:

- buy now
- sell now
- go long
- go short
- full position
- all in
- guaranteed rise/fall
- auto place order
- set leverage to a specific value

Allowed final actions:

- observe
- wait for confirmation
- prepare lightly
- reduce exposure
- pause trading
- do not trade
- run pre-trade checklist

If the user asks for execution, state that this skill only provides market-structure alerts and risk checks.

## Resource Map

- `references/data-sources.md`: supported public data endpoints and fields.
- `references/signal-matrix.md`: how to interpret price, volume, OI, funding, taker flow, long/short ratio, and basis combinations.
- `references/alert-rules.md`: alert thresholds and market-state classifier.
- `references/output-template.md`: standard concise output format.
- `references/risk-filter.md`: final safety and anti-overtrading filter.
- `scripts/fetch_binance_btc.py`: fetches public Binance Futures market data to JSON.
- `scripts/analyze_btc_structure.py`: computes indicators and returns structured alerts.

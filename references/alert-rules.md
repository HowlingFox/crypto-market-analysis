# Alert Rules

These thresholds are starting defaults. Adjust after observing real alerts.

## Core Metrics

- `volume_ratio`: latest volume / average of previous 20 candles on same timeframe
- `price_change_1h`: latest close versus close 1h ago where available
- `price_change_4h`: latest close versus close 4h ago where available
- `oi_change_1h`, `oi_change_4h`, `oi_change_24h`: percent changes from OI history
- `taker_ratio`: buyVol / sellVol or endpoint buySellRatio
- `funding_z_30d`: z-score of current funding versus recent history
- `funding_percentile_30d`: current funding percentile in recent history
- `basis_bps`: `(markPrice - indexPrice) / indexPrice * 10000`

## Funding Thresholds

Classify funding crowding:

- `abs(funding_z_30d) < 1`: normal
- `1 <= abs(funding_z_30d) < 2`: elevated
- `2 <= abs(funding_z_30d) < 3`: extreme
- `abs(funding_z_30d) >= 3`: very extreme

Percentile fallback:

- `funding_percentile_30d >= 90`: long side crowded
- `funding_percentile_30d <= 10`: short side crowded

## State Rules

### volume_breakout

Typical conditions:

- close breaks recent 20-candle high on 15m or 1h
- volume_ratio >= 1.8
- taker_ratio >= 1.2
- OI rising on 1h or 4h
- funding not extreme

Alert level: medium/high depending on 1h and 4h alignment.

### false_breakout_risk

Typical conditions:

- price breaks recent high but closes back inside range, or stalls near resistance
- volume_ratio < 1.2
- taker_ratio < 1.1
- OI not rising meaningfully

Alert level: medium if user may chase; otherwise low.

### volume_breakdown

Typical conditions:

- close breaks recent 20-candle low on 15m or 1h
- volume_ratio >= 1.8
- taker_ratio <= 0.8
- OI rising on 1h or 4h

Alert level: medium/high depending on 1h and 4h alignment.

### crowded_long_uptrend

Typical conditions:

- price already up on 4h/24h
- OI rising quickly
- funding_z_30d >= 2 or funding_percentile_30d >= 90
- taker buy strength is flat or weakening
- price near resistance or fails to extend

Alert action: reduce exposure / avoid chasing / wait for pullback confirmation.

### crowded_short_downtrend

Typical conditions:

- price already down on 4h/24h
- OI high or rising
- funding_z_30d <= -2 or funding_percentile_30d <= 10
- taker sell strength is flat or weakening
- price fails to continue lower

Alert action: avoid chasing shorts / watch for squeeze risk.

### leveraged_range_build

Typical conditions:

- 4h price range is narrow
- OI_4h or OI_24h rising
- volume contracting or neutral
- funding near neutral or drifting
- long/short ratio not decisive

Alert action: wait for confirmed break; expect volatility.

### post_liquidation_release

Typical conditions:

- large candle or wick
- volume_ratio >= 2.0
- OI drops sharply, usually <= -3% on 1h/4h
- funding extreme begins to normalize

Alert action: risk partly released; do not assume instant reversal; wait for retest.

## Scoring

Use a 0-10 alert score.

Positive structure points:

- 1h and 4h direction align: +2
- volume confirms move: +2
- taker flow confirms move: +2
- OI supports move without extreme crowding: +2
- clean break of recent range: +1
- funding normal/mild for trend direction: +1

Risk/crowding points:

- funding extreme: +2 risk
- OI rising in tight range: +2 risk
- price fails despite extreme positioning: +2 risk
- wick + volume spike + OI drop: +2 risk

Alert level mapping:

- 0-2: none
- 3-4: low
- 5-6: medium
- 7-10: high

## Final Filtering

If the state is medium/high but data completeness is poor, downgrade one level.

If 4h and 1h conflict, avoid high-confidence directional wording.

If the result suggests a trade but risk-filter conditions are not satisfied, final action becomes `wait for confirmation` or `run pre-trade checklist`.


## Technical Oscillators (15m / 1h / 4h)

The scan prints values from the latest **closed** candle on each timeframe. If a required lookback is unavailable, print `n/a`; do not infer a value. These are context alerts and do not independently indicate a reversal or authorize a trade.

| Indicator | Default calculation | Alert thresholds |
|---|---|---|
| KDJ | (9,3,3); RSV from 9-bar high/low range; K and D recursively smoothed by 1/3 with initial values 50; J = 3K - 2D | K and D both >=80: overbought; both <=20: oversold |
| RSI | Wilder-smoothed RSI, periods 6, 12, 24 | >=70 overbought; <=30 oversold |
| AR | 26-bar sum(High-Open) / sum(Open-Low) * 100 | >=150 overbought; <=50 oversold |
| BR | 26-bar sum(max(High-PrevClose,0)) / sum(max(PrevClose-Low,0)) * 100 | >=400 overbought; <=50 oversold |
| WMSR | 14-bar (Close - HighestHigh) / (HighestHigh - LowestLow) * 100; range -100..0 | >=-20 overbought; <=-80 oversold |
| CCI | 20-bar Typical Price, mean deviation and Lambert constant 0.015 | >=100 overbought; <=-100 oversold |
| OSC | (SMA(Close,7) - SMA(Close,14)) / SMA(Close,14) * 100 | Zero-line context only: positive means fast average above slow average, negative means below; no universal fixed overbought/oversold threshold |

All thresholds are conventional reference levels and may persist during strong trends. Displaying a threshold alert must not promote the overall structural alert level or override the risk filter by itself.

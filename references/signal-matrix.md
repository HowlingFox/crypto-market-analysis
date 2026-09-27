# Signal Matrix

Use this matrix to translate raw data combinations into market-structure meaning.

## Price + Volume

| Combination | Meaning |
|---|---|
| price up + volume expansion | upside move has better confirmation |
| price up + weak volume | rally quality is questionable |
| price down + volume expansion | sell pressure is more credible |
| price down + weak volume | may be pullback rather than confirmed trend |
| breakout + volume < 1.2x average | false-breakout risk |
| breakout + volume > 1.8x average | breakout deserves attention |

## Taker Buy/Sell Flow

| Combination | Meaning |
|---|---|
| taker buy/sell > 1.2 | active buyers dominate |
| taker buy/sell < 0.8 | active sellers dominate |
| price rises but taker buy/sell weakens | rally may be losing initiative |
| price falls but taker sell weakens | selloff may be losing initiative |
| breakout with taker buy/sell > 1.2 | breakout confirmation improves |
| breakdown with taker buy/sell < 0.8 | breakdown confirmation improves |

## Open Interest

| Combination | Meaning |
|---|---|
| price up + OI up | new long-side participation or new leverage; trend may continue if not crowded |
| price up + OI down | short covering; move may exhaust faster |
| price down + OI up | short-side participation or new leverage; downside can continue if not crowded |
| price down + OI down | longs may be closing/liquidating; risk may be partly released |
| price range + OI up | leverage buildup; later volatility risk increases |
| OI sharp drop + volume spike | possible liquidation/position flush |

## Funding Rate

Funding is a crowding and holding-cost indicator.

| Combination | Meaning |
|---|---|
| mild positive funding + uptrend + volume support | generally healthy trend, but avoid chasing without risk plan |
| high positive funding + rising OI + slowing price | long crowding warning |
| high positive funding + price fails at resistance | long liquidation risk increases |
| negative funding + downtrend + sell flow | bearish trend can be active |
| extreme negative funding + price stops falling | short squeeze risk increases |
| funding flips sign quickly | positioning regime is changing; avoid overconfidence |

## Long/Short Ratio

| Combination | Meaning |
|---|---|
| global long/short very high | market may be overlong; long chase risk rises |
| global long/short very low | market may be overshort; short chase risk rises |
| top trader ratio diverges from global ratio | professional/retail positioning divergence; treat as context, not signal |

## Basis/Premium

| Combination | Meaning |
|---|---|
| perp/mark premium expands while price rises | long sentiment is heating |
| premium expands but price stalls | crowded long risk rises |
| discount deepens while price falls | short sentiment is heavy |
| mark/index divergence expands | liquidation sensitivity can rise |

## Liquidation-Risk Proxies

Binance public endpoints do not provide full liquidation heatmap. Use proxies:

- high OI buildup inside a tight range
- extreme funding or long/short ratio
- sudden volume spike
- sudden OI contraction
- long wick through a known support/resistance region

Interpretation:

- OI buildup + tight range = pending volatility, not direction.
- OI drop + volume spike + wick = partial liquidation release.
- Funding extreme + failed continuation = crowding unwind risk.

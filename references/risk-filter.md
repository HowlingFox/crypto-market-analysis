# Risk Filter

Apply this after market-structure analysis.

## Hard Filters

If any item is true, final action must be `do not trade`, `pause trading`, or `run pre-trade checklist` rather than directional advice:

- no explicit invalidation level
- no clear stop-loss plan
- user is trying to recover a recent loss
- user wants to chase a move after multiple candles in one direction
- user wants to average down in a losing position
- daily loss limit is close or already reached
- two or more consecutive losses happened today
- market state is `data_insufficient`
- 4h and 1h structure conflict and user wants a confident entry

## Allowed Actions

- observe
- wait for confirmation
- prepare lightly
- reduce exposure
- pause trading
- do not trade
- run pre-trade checklist

## Forbidden Phrases

Do not output:

- buy now
- sell now
- guaranteed
- must rise
- must fall
- all in
- full position
- increase leverage
- place the order

## Pre-Trade Checklist

If the user asks whether to open a trade, ask/check:

1. What is the market state?
2. What is the entry idea?
3. What invalidates the idea?
4. Where is the stop?
5. What is the maximum loss?
6. Does funding create crowding or holding-cost risk over 1-2 days?
7. Does OI/taker flow confirm the idea?
8. Are you chasing after a move?
9. Is this after a loss?
10. Can you sleep with the position size?

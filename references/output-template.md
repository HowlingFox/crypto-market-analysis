# Output Template

Use this format for scheduled alerts.

## No or Low Alert

```text
BTC 市场结构扫描

数据更新时间：<YYYY-MM-DD HH:mm:ss>
数据来源：Binance public API

预警等级：无/低
当前结构：<state>
一句话结论：<brief conclusion>
关键原因：<1-3 bullets>
建议动作：观望 / 等待确认
```

## Medium or High Alert

```text
BTC 市场结构预警

数据更新时间：<YYYY-MM-DD HH:mm:ss>
数据来源：Binance public API

预警等级：中/高
当前结构：<state>
当前价格：<price>
分析周期：15m / 1h / 4h

触发信号：
1. <signal>
2. <signal>
3. <signal>

关键数据：
- 15m/1h/4h 量价：<summary>
- Taker buy/sell：<ratio and interpretation>
- OI：<changes>
- Funding：<current, z-score/percentile if available, 1d/2d cost>
- Long/Short：<summary>
- Basis/Premium：<summary>

关键位置：
- 支撑：<support>
- 压力：<resistance>
- 失效观察位：<level>

风险判断：
- 主要风险：<risk>
- 是否适合开仓：<yes/no/unclear>
- 需要等待什么确认：<confirmation>

建议动作：观望 / 等待确认 / 轻仓准备 / 减仓 / 暂停交易 / 禁止交易
```

## Style Rules

- Be short for no-alert scans.
- Do not sound certain.
- Do not say buy/sell directly.
- Use “structure suggests”, “risk is rising”, “needs confirmation”.
- If data is missing, say exactly what is missing.

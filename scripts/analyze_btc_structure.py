#!/usr/bin/env python3
"""Analyze a Binance BTCUSDT futures market data bundle.

The script produces JSON or markdown output for OpenClaw scheduled alerts.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

Number = Optional[float]


def as_float(value: Any) -> Number:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_change(new: Number, old: Number) -> Number:
    if new is None or old in (None, 0):
        return None
    return (new - old) / old * 100.0


def percentile_rank(values: List[float], current: float) -> Number:
    if not values:
        return None
    count = sum(1 for v in values if v <= current)
    return count / len(values) * 100.0


def zscore(values: List[float], current: float) -> Number:
    if len(values) < 2:
        return None
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return 0.0
    return (current - mean) / stdev


def median(values: List[float]) -> Number:
    if not values:
        return None
    return statistics.median(values)


def get_data(response: Dict[str, Any]) -> Any:
    if not isinstance(response, dict) or not response.get("ok"):
        return None
    return response.get("data")


def parse_klines(raw: Any) -> List[Dict[str, float]]:
    rows = []
    if not isinstance(raw, list):
        return rows
    for item in raw:
        if not isinstance(item, list) or len(item) < 11:
            continue
        rows.append({
            "open_time": as_float(item[0]) or 0.0,
            "open": as_float(item[1]) or 0.0,
            "high": as_float(item[2]) or 0.0,
            "low": as_float(item[3]) or 0.0,
            "close": as_float(item[4]) or 0.0,
            "volume": as_float(item[5]) or 0.0,
            "close_time": as_float(item[6]) or 0.0,
            "quote_volume": as_float(item[7]) or 0.0,
            "trades": as_float(item[8]) or 0.0,
            "taker_buy_base": as_float(item[9]) or 0.0,
            "taker_buy_quote": as_float(item[10]) or 0.0,
        })
    return rows


def kline_metrics(rows: List[Dict[str, float]]) -> Dict[str, Any]:
    if len(rows) < 25:
        return {"available": False}
    latest = rows[-1]
    prev20 = rows[-21:-1]
    avg_volume = statistics.mean([r["volume"] for r in prev20]) if prev20 else None
    volume_ratio = latest["volume"] / avg_volume if avg_volume else None
    recent20 = rows[-21:-1]
    high20 = max(r["high"] for r in recent20)
    low20 = min(r["low"] for r in recent20)
    close = latest["close"]
    prev_close = rows[-2]["close"] if len(rows) >= 2 else None
    change_last = pct_change(close, prev_close)
    change_20 = pct_change(close, rows[-21]["close"])
    range_20_pct = (high20 - low20) / close * 100.0 if close else None
    close_position = (close - low20) / (high20 - low20) if high20 != low20 else 0.5
    breakout = close > high20
    breakdown = close < low20
    return {
        "available": True,
        "close": close,
        "high20": high20,
        "low20": low20,
        "support": low20,
        "resistance": high20,
        "volume_ratio": volume_ratio,
        "change_last_pct": change_last,
        "change_20_pct": change_20,
        "range_20_pct": range_20_pct,
        "close_position": close_position,
        "breakout": breakout,
        "breakdown": breakdown,
        "latest_candle": latest,
    }


def latest_list_item(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, list) and raw:
        item = raw[-1]
        return item if isinstance(item, dict) else None
    if isinstance(raw, dict):
        return raw
    return None


def series_float(raw: Any, key: str) -> List[float]:
    if not isinstance(raw, list):
        return []
    out: List[float] = []
    for item in raw:
        if isinstance(item, dict):
            val = as_float(item.get(key))
            if val is not None:
                out.append(val)
    return out


def change_from_series(values: List[float], periods_back: int) -> Number:
    if len(values) <= periods_back:
        return None
    return pct_change(values[-1], values[-1 - periods_back])


def oi_metrics(bundle: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"available": False}
    current = get_data(bundle.get("open_interest", {}))
    if isinstance(current, dict):
        out["current_oi"] = as_float(current.get("openInterest"))
        out["available"] = out["current_oi"] is not None
    hist_out: Dict[str, Any] = {}
    for period, response in bundle.get("open_interest_hist", {}).items():
        raw = get_data(response)
        values = series_float(raw, "sumOpenInterest") or series_float(raw, "sum_open_interest")
        if values:
            hist_out[period] = {
                "latest": values[-1],
                "change_1": change_from_series(values, 1),
                "change_4": change_from_series(values, 4),
                "change_24": change_from_series(values, 24),
            }
    if hist_out:
        out["available"] = True
        out["history"] = hist_out
    return out


def taker_metrics(bundle: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"available": False, "by_period": {}}
    for period, response in bundle.get("taker_long_short", {}).items():
        raw = get_data(response)
        item = latest_list_item(raw)
        if not item:
            continue
        ratio = as_float(item.get("buySellRatio"))
        buy = as_float(item.get("buyVol"))
        sell = as_float(item.get("sellVol"))
        if ratio is None and buy is not None and sell not in (None, 0):
            ratio = buy / sell
        out["by_period"][period] = {"ratio": ratio, "buy_vol": buy, "sell_vol": sell}
        out["available"] = True
    return out


def long_short_metrics(bundle: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"available": False, "global": {}, "top_account": {}, "top_position": {}}
    for key, target in [("global_long_short", "global"), ("top_long_short_account", "top_account"), ("top_long_short_position", "top_position")]:
        for period, response in bundle.get(key, {}).items():
            item = latest_list_item(get_data(response))
            if not item:
                continue
            out[target][period] = {
                "long_short_ratio": as_float(item.get("longShortRatio")),
                "long_account": as_float(item.get("longAccount")),
                "short_account": as_float(item.get("shortAccount")),
                "long_position": as_float(item.get("longPosition")),
                "short_position": as_float(item.get("shortPosition")),
            }
            out["available"] = True
    return out


def funding_metrics(bundle: Dict[str, Any]) -> Dict[str, Any]:
    premium = get_data(bundle.get("premium_index", {}))
    hist = get_data(bundle.get("funding_rate", {}))
    out: Dict[str, Any] = {"available": False}
    current: Number = None
    mark: Number = None
    index: Number = None
    next_time = None
    if isinstance(premium, dict):
        current = as_float(premium.get("lastFundingRate"))
        mark = as_float(premium.get("markPrice"))
        index = as_float(premium.get("indexPrice"))
        next_time = premium.get("nextFundingTime")
    hist_values = series_float(hist, "fundingRate")
    if current is None and hist_values:
        current = hist_values[-1]
    if current is None:
        return out
    values_for_stats = hist_values or [current]
    last3 = hist_values[-3:] if len(hist_values) >= 3 else hist_values
    med3 = median(last3) if last3 else current
    basis_bps = (mark - index) / index * 10000 if mark is not None and index not in (None, 0) else None
    out.update({
        "available": True,
        "current_8h": current,
        "current_8h_pct": current * 100,
        "apr_pct": current * 3 * 365 * 100,
        "funding_24h_sum_pct": sum(last3) * 100 if last3 else None,
        "percentile_recent": percentile_rank(values_for_stats, current),
        "z_recent": zscore(values_for_stats, current),
        "momentum_pct": (current - med3) * 100 if med3 is not None else None,
        "expected_1d_cost_pct": current * 3 * 100,
        "expected_2d_cost_pct": current * 6 * 100,
        "mark_price": mark,
        "index_price": index,
        "basis_bps": basis_bps,
        "next_funding_time": next_time,
        "history_count": len(hist_values),
    })
    return out


def classify(km: Dict[str, Any], oi: Dict[str, Any], taker: Dict[str, Any], funding: Dict[str, Any], ls: Dict[str, Any]) -> Tuple[str, str, int, List[str], List[str]]:
    reasons: List[str] = []
    risks: List[str] = []
    missing = sum(1 for g in [oi, taker, funding, ls] if not g.get("available"))
    if missing >= 3 or not km.get("1h", {}).get("available"):
        return "data_insufficient", "low", 3, ["core market data is incomplete"], ["insufficient confirmation"]

    m15 = km.get("15m", {})
    h1 = km.get("1h", {})
    h4 = km.get("4h", {})
    price_up_1h = (h1.get("change_20_pct") or 0) > 0.5
    price_down_1h = (h1.get("change_20_pct") or 0) < -0.5
    price_up_4h = (h4.get("change_20_pct") or 0) > 1.0
    price_down_4h = (h4.get("change_20_pct") or 0) < -1.0
    vol_high = max([v for v in [m15.get("volume_ratio"), h1.get("volume_ratio")] if v is not None] or [0]) >= 1.8
    vol_low_break = max([v for v in [m15.get("volume_ratio"), h1.get("volume_ratio")] if v is not None] or [0]) < 1.2
    taker_1h = taker.get("by_period", {}).get("1h", {}).get("ratio")
    taker_15 = taker.get("by_period", {}).get("15m", {}).get("ratio")
    taker_ratio = taker_15 or taker_1h
    buy_strong = taker_ratio is not None and taker_ratio >= 1.2
    sell_strong = taker_ratio is not None and taker_ratio <= 0.8
    fz = funding.get("z_recent")
    fp = funding.get("percentile_recent")
    funding_extreme_pos = (fz is not None and fz >= 2) or (fp is not None and fp >= 90)
    funding_extreme_neg = (fz is not None and fz <= -2) or (fp is not None and fp <= 10)
    oi_hist = oi.get("history", {})
    oi_1h_change = (oi_hist.get("1h", {}).get("change_4") or oi_hist.get("15m", {}).get("change_4"))
    oi_4h_change = oi_hist.get("4h", {}).get("change_4") or oi_hist.get("1h", {}).get("change_24")
    oi_rising = any((x is not None and x > 2.0) for x in [oi_1h_change, oi_4h_change])
    oi_falling = any((x is not None and x < -3.0) for x in [oi_1h_change, oi_4h_change])
    tight_range = h4.get("range_20_pct") is not None and h4.get("range_20_pct") < 3.0
    breakout = bool(m15.get("breakout") or h1.get("breakout"))
    breakdown = bool(m15.get("breakdown") or h1.get("breakdown"))

    score = 0
    state = "leveraged_range_build"

    if breakout and vol_high and buy_strong and oi_rising and not funding_extreme_pos:
        state = "volume_breakout"
        score += 7
        reasons += ["price broke recent range with volume confirmation", "active buy flow confirms", "OI is rising without extreme funding"]
    elif breakdown and vol_high and sell_strong and oi_rising and not funding_extreme_neg:
        state = "volume_breakdown"
        score += 7
        reasons += ["price broke recent support with volume confirmation", "active sell flow confirms", "OI is rising"]
    elif breakout and (vol_low_break or not buy_strong):
        state = "false_breakout_risk"
        score += 5
        reasons += ["breakout lacks volume or active buy confirmation"]
        risks += ["chasing breakout has elevated failure risk"]
    elif price_up_1h and price_up_4h and funding_extreme_pos and oi_rising:
        state = "crowded_long_uptrend"
        score += 7
        reasons += ["uptrend is accompanied by extreme positive funding and rising OI"]
        risks += ["long side is crowded; chasing is risky"]
    elif price_down_1h and price_down_4h and funding_extreme_neg and oi_rising:
        state = "crowded_short_downtrend"
        score += 7
        reasons += ["downtrend is accompanied by extreme negative funding and elevated OI"]
        risks += ["short side is crowded; squeeze risk is higher"]
    elif oi_falling and vol_high:
        state = "post_liquidation_release"
        score += 6
        reasons += ["volume spike with OI contraction suggests position flush"]
        risks += ["risk may be partly released, but reversal needs retest confirmation"]
    elif tight_range and oi_rising:
        state = "leveraged_range_build"
        score += 5
        reasons += ["price range is tight while OI rises"]
        risks += ["leverage buildup can precede volatility in either direction"]
    elif price_up_1h and price_up_4h:
        state = "healthy_uptrend"
        score += 4
        reasons += ["1h and 4h are both upward"]
        if vol_high:
            score += 1
            reasons.append("volume supports the move")
    elif price_down_1h and price_down_4h:
        state = "healthy_downtrend"
        score += 4
        reasons += ["1h and 4h are both downward"]
        if vol_high:
            score += 1
            reasons.append("volume supports the move")
    else:
        state = "leveraged_range_build" if oi_rising else "data_insufficient"
        score += 3
        reasons += ["no clean multi-timeframe directional structure"]

    if funding_extreme_pos:
        risks.append("funding indicates long-side crowding")
    if funding_extreme_neg:
        risks.append("funding indicates short-side crowding")
    if missing:
        risks.append(f"{missing} confirmation group(s) missing")
        score = max(0, score - missing)

    if score >= 7:
        level = "high"
    elif score >= 5:
        level = "medium"
    elif score >= 3:
        level = "low"
    else:
        level = "none"
    return state, level, min(score, 10), reasons or ["no strong signal"], risks or ["no major structural risk detected"]


def analyze(bundle: Dict[str, Any]) -> Dict[str, Any]:
    klines = {period: kline_metrics(parse_klines(get_data(resp))) for period, resp in bundle.get("klines", {}).items()}
    funding = funding_metrics(bundle)
    oi = oi_metrics(bundle)
    taker = taker_metrics(bundle)
    ls = long_short_metrics(bundle)
    state, level, score, reasons, risks = classify(klines, oi, taker, funding, ls)
    h1 = klines.get("1h", {})
    h4 = klines.get("4h", {})
    price = h1.get("close") or klines.get("15m", {}).get("close") or funding.get("mark_price")
    support_values = [m.get("support") for m in klines.values() if m.get("available")]
    resistance_values = [m.get("resistance") for m in klines.values() if m.get("available")]
    support = min(support_values) if support_values else None
    resistance = max(resistance_values) if resistance_values else None
    action = "观望"
    if level in ("medium", "high"):
        if state in ("crowded_long_uptrend", "false_breakout_risk"):
            action = "等待确认 / 已有多单考虑保护利润"
        elif state == "crowded_short_downtrend":
            action = "等待确认 / 避免追空"
        elif state in ("volume_breakout", "volume_breakdown"):
            action = "等待确认 / 执行开仓前检查"
        elif state == "leveraged_range_build":
            action = "等待放量突破"
        elif state == "post_liquidation_release":
            action = "等待二次确认"
    if state == "data_insufficient":
        action = "观望"
    return {
        "meta": bundle.get("meta", {}),
        "price": price,
        "state": state,
        "alert_level": level,
        "score": score,
        "reasons": reasons,
        "risks": risks,
        "action": action,
        "support": support,
        "resistance": resistance,
        "klines": klines,
        "funding": funding,
        "open_interest": oi,
        "taker_flow": taker,
        "long_short": ls,
    }


def fmt_pct(x: Number, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:.{digits}f}%"


def fmt_num(x: Number, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:.{digits}f}"


def fmt_update_time(meta: Dict[str, Any]) -> str:
    raw = meta.get("data_updated_at") or meta.get("fetched_at")
    if not raw:
        return "n/a"
    raw_text = str(raw)
    try:
        dt = datetime.fromisoformat(raw_text.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw_text.replace("T", " ")[:19]


def render_markdown(result: Dict[str, Any]) -> str:
    funding = result["funding"]
    oi = result["open_interest"]
    taker = result["taker_flow"]
    h1 = result["klines"].get("1h", {})
    h4 = result["klines"].get("4h", {})
    meta = result.get("meta", {})
    data_source = meta.get("data_source") or "Binance public API"
    symbol = meta.get("symbol") or "BTC"
    lines = [
        f"{symbol} 市场结构预警" if result["alert_level"] in ("medium", "high") else f"{symbol} 市场结构扫描",
        "",
        f"数据更新时间：{fmt_update_time(meta)}",
        f"数据来源：{data_source}",
        "",
        f"预警等级：{result['alert_level']}",
        f"当前结构：{result['state']}",
        f"当前价格：{fmt_num(result.get('price'), 2)}",
        f"评分：{result['score']}/10",
        "",
        "触发信号：",
    ]
    for i, reason in enumerate(result["reasons"], 1):
        lines.append(f"{i}. {reason}")
    lines += [
        "",
        "关键数据：",
        f"- 1h 量价：涨跌 {fmt_pct(h1.get('change_20_pct'))}，量能 {fmt_num(h1.get('volume_ratio'), 2)}x",
        f"- 4h 量价：涨跌 {fmt_pct(h4.get('change_20_pct'))}，量能 {fmt_num(h4.get('volume_ratio'), 2)}x",
        f"- Taker buy/sell：15m {fmt_num(taker.get('by_period', {}).get('15m', {}).get('ratio'), 3)}，1h {fmt_num(taker.get('by_period', {}).get('1h', {}).get('ratio'), 3)}",
        f"- OI：当前 {fmt_num(oi.get('current_oi'), 3)}，1h变化 {fmt_pct((oi.get('history', {}).get('1h', {}) or {}).get('change_4'))}，4h变化 {fmt_pct((oi.get('history', {}).get('4h', {}) or {}).get('change_4'))}",
        f"- Funding：8h {fmt_pct(funding.get('current_8h_pct'), 4)}，APR {fmt_pct(funding.get('apr_pct'))}，Z {fmt_num(funding.get('z_recent'), 2)}，1天成本 {fmt_pct(funding.get('expected_1d_cost_pct'), 4)}，2天成本 {fmt_pct(funding.get('expected_2d_cost_pct'), 4)}",
        f"- Basis/Premium：{fmt_num(funding.get('basis_bps'), 2)} bps",
        "",
        "关键位置：",
        f"- 支撑：{fmt_num(result.get('support'), 2)}",
        f"- 压力：{fmt_num(result.get('resistance'), 2)}",
        "",
        "风险判断：",
    ]
    for risk in result["risks"]:
        lines.append(f"- {risk}")
    lines += [
        "",
        f"建议动作：{result['action']}",
        "",
        "注意：这不是直接买卖指令；如需开仓，必须再做止损、仓位和单日风险检查。",
        "",
        "===============================",
        "如需了解机器人并获取更多指标，欢迎咨询：@win88888888888888",
        "更多带单标的咨询：@BitcoinTrader765",
        "===============================",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze BTC market structure from fetched Binance JSON")
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()
    with open(args.input, "r", encoding="utf-8") as f:
        bundle = json.load(f)
    result = analyze(bundle)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
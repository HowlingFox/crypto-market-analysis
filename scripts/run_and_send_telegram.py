#!/usr/bin/env python3
"""Run a Binance market scan and publish the report to a Telegram chat/channel."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__:
    from .analyze_btc_structure import analyze, render_markdown
    from .fetch_binance_btc import fetch_bundle
else:
    from analyze_btc_structure import analyze, render_markdown
    from fetch_binance_btc import fetch_bundle


TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_TEXT_LIMIT = 4096

SIGNAL_ZH = {
    "core market data is incomplete": "核心市场数据不完整",
    "insufficient confirmation": "确认信号不足",
    "price broke recent range with volume confirmation": "价格放量突破近期区间",
    "active buy flow confirms": "主动买入资金流予以确认",
    "OI is rising without extreme funding": "持仓量上升，资金费率未处于极端水平",
    "price broke recent support with volume confirmation": "价格放量跌破近期支撑",
    "active sell flow confirms": "主动卖出资金流予以确认",
    "OI is rising": "未平仓合约量上升",
    "breakout lacks volume or active buy confirmation": "突破缺少成交量或主动买入确认",
    "uptrend is accompanied by extreme positive funding and rising OI": "上升趋势伴随极高正资金费率和未平仓合约量上升",
    "downtrend is accompanied by extreme negative funding and elevated OI": "下降趋势伴随极低负资金费率和未平仓合约量上升",
    "volume spike with OI contraction suggests position flush": "成交量激增且未平仓合约量收缩，可能出现仓位清洗",
    "price range is tight while OI rises": "价格区间收窄，同时未平仓合约量上升",
    "1h and 4h are both upward": "1小时与4小时周期均上涨",
    "1h and 4h are both downward": "1小时与4小时周期均下跌",
    "volume supports the move": "成交量支持当前走势",
    "no clean multi-timeframe directional structure": "多周期方向结构不明确",
    "no strong signal": "暂无强烈信号",
}

RISK_ZH = {
    "insufficient confirmation": "确认信号不足",
    "chasing breakout has elevated failure risk": "追涨突破的失败风险偏高",
    "long side is crowded; chasing is risky": "多头交易拥挤，追涨风险较高",
    "short side is crowded; squeeze risk is higher": "空头交易拥挤，逼空风险较高",
    "risk may be partly released, but reversal needs retest confirmation": "部分风险可能已释放，但反转仍需回踩确认",
    "leverage buildup can precede volatility in either direction": "杠杆累积后可能出现双向波动",
    "funding indicates long-side crowding": "资金费率显示多头交易拥挤",
    "funding indicates short-side crowding": "资金费率显示空头交易拥挤",
    "no major structural risk detected": "暂未发现显著结构性风险",
}


def translate_report_sections(report: str) -> str:
    section = ""
    translated = []
    for line in report.splitlines():
        if line == "触发信号：":
            section = "signals"
        elif line == "风险判断：":
            section = "risks"
        elif line in ("关键数据：", "建议动作：") or line.startswith("建议动作："):
            section = ""

        if section == "signals":
            prefix, separator, text = line.partition(". ")
            if separator and prefix.isdigit():
                line = f"{prefix}. {SIGNAL_ZH.get(text, text)}"
        elif section == "risks" and line.startswith("- "):
            text = line[2:]
            if text.endswith(" confirmation group(s) missing"):
                count = text.split(" ", 1)[0]
                text = f"{count}类确认数据缺失"
            else:
                text = RISK_ZH.get(text, text)
            line = f"- {text}"
        translated.append(line)
    return "\n".join(translated)


def set_report_symbol(report: str, symbol: str) -> str:
    lines = report.splitlines()
    if lines and lines[0].startswith("BTC 市场结构"):
        lines[0] = lines[0].replace("BTC", symbol.upper(), 1)
    return "\n".join(lines)


def convert_update_time_utc8(report: str) -> str:
    prefix = "数据更新时间："
    lines = report.splitlines()
    utc_plus_8 = timezone(timedelta(hours=8))
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        value = line[len(prefix):].strip()
        if value.endswith("UTC+8"):
            break
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            break
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        local_time = timestamp.astimezone(utc_plus_8)
        lines[index] = f"{prefix}{local_time:%Y-%m-%d %H:%M:%S} UTC+8"
        break
    return "\n".join(lines)


def send_message(token: str, chat_id: str, text: str) -> None:
    if len(text) > TELEGRAM_TEXT_LIMIT:
        raise ValueError(
            f"Report is {len(text)} characters; Telegram allows at most "
            f"{TELEGRAM_TEXT_LIMIT} characters per message."
        )

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    body = json.dumps(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    ).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Do not print the request URL: Telegram bot tokens are part of its path.
        raise RuntimeError(f"Telegram API returned HTTP {exc.code}.") from None
    except URLError:
        raise RuntimeError("Could not reach the Telegram Bot API.") from None
    except Exception:
        raise RuntimeError("Telegram message delivery failed.") from None

    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the message; check bot access and chat ID.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan Binance USD-M Futures and post the report to Telegram."
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--kline-limit", type=int, default=100)
    parser.add_argument("--market-limit", type=int, default=96)
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print(
            "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variable.",
            file=sys.stderr,
        )
        return 2

    try:
        bundle = fetch_bundle(
            args.symbol.upper(),
            "https://fapi.binance.com",
            args.kline_limit,
            args.market_limit,
        )
        report = render_markdown(analyze(bundle))
        report = convert_update_time_utc8(report)
        report = translate_report_sections(report)
        report = set_report_symbol(report, args.symbol)
        send_message(token, chat_id, report)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Posted {args.symbol.upper()} scan to Telegram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

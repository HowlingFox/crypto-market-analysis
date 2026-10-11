#!/usr/bin/env python3
"""Run a Binance market scan and publish the report to a Telegram chat/channel."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if __package__:
    from .analyze_btc_structure import analyze, render_markdown
    from .fetch_binance_btc import fetch_bundle
else:
    from analyze_btc_structure import analyze, render_markdown
    from fetch_binance_btc import fetch_bundle


TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_TEXT_LIMIT = 4096
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(PROJECT_ROOT, "logs", "telegram_execution.log")
RECIPIENTS_PATH = os.path.join(PROJECT_ROOT, "logs", "telegram_recipients.json")


def log_execution(message: str) -> None:
    timestamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S UTC+8")
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{timestamp}] {message}\n")
    except OSError as exc:
        print(f"Could not write execution log: {exc}", file=sys.stderr)



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


def telegram_api_error(exc: HTTPError) -> str:
    """Return Telegram's safe error description without exposing the token URL."""
    try:
        payload = json.loads(exc.read().decode("utf-8"))
        description = payload.get("description")
        if description:
            return str(description)
    except Exception:  # noqa: BLE001
        pass
    return f"HTTP {exc.code}"


def load_recipient_state() -> dict[str, object]:
    if not os.path.exists(RECIPIENTS_PATH):
        return {"next_offset": 0, "private_chat_ids": []}
    with open(RECIPIENTS_PATH, "r", encoding="utf-8") as state_file:
        state = json.load(state_file)
    if not isinstance(state, dict):
        raise ValueError("Telegram recipient state must be a JSON object.")
    offset = state.get("next_offset", 0)
    recipients = state.get("private_chat_ids", [])
    if not isinstance(offset, int) or not isinstance(recipients, list):
        raise ValueError("Telegram recipient state has an invalid format.")
    return {"next_offset": offset, "private_chat_ids": [str(chat_id) for chat_id in recipients]}


def save_recipient_state(state: dict[str, object]) -> None:
    os.makedirs(os.path.dirname(RECIPIENTS_PATH), exist_ok=True)
    temporary_path = RECIPIENTS_PATH + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file, ensure_ascii=False, indent=2)
    os.replace(temporary_path, RECIPIENTS_PATH)


def get_updates(token: str, offset: int) -> list[dict[str, object]]:
    params = {"timeout": 0, "allowed_updates": json.dumps(["message"])}
    if offset > 0:
        params["offset"] = offset
    url = f"{TELEGRAM_API}/bot{token}/getUpdates?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "crypto-market-structure-alert/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Telegram getUpdates failed: {telegram_api_error(exc)}") from None
    except URLError:
        raise RuntimeError("Could not reach Telegram getUpdates API.") from None
    except Exception:  # noqa: BLE001
        raise RuntimeError("Could not read Telegram updates.") from None
    if not payload.get("ok"):
        description = payload.get("description") or "Telegram rejected getUpdates."
        raise RuntimeError(str(description))
    result = payload.get("result")
    if not isinstance(result, list):
        raise RuntimeError("Telegram getUpdates returned an invalid result.")
    return result


def discover_private_recipients(token: str) -> list[str]:
    """Persist private chats that have sent the bot a message; /stop opts out."""
    state = load_recipient_state()
    offset = int(state["next_offset"])
    recipients = set(state["private_chat_ids"])
    initial_recipients = set(recipients)
    changed = False
    while True:
        updates = get_updates(token, offset)
        if not updates:
            break
        for update in updates:
            if not isinstance(update, dict):
                continue
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset = max(offset, update_id + 1)
            message = update.get("message")
            if not isinstance(message, dict):
                continue
            chat = message.get("chat")
            if not isinstance(chat, dict) or chat.get("type") != "private" or chat.get("id") is None:
                continue
            sender = message.get("from")
            if isinstance(sender, dict) and sender.get("is_bot"):
                continue
            chat_id = str(chat["id"])
            text_value = message.get("text", "")
            command = str(text_value).split(maxsplit=1)[0].split("@", 1)[0].lower() if text_value else ""
            if command == "/stop":
                recipients.discard(chat_id)
            else:
                recipients.add(chat_id)
        changed = True
        save_recipient_state({"next_offset": offset, "private_chat_ids": sorted(recipients)})
        if len(updates) < 100:
            break
    if changed or recipients != initial_recipients:
        save_recipient_state({"next_offset": offset, "private_chat_ids": sorted(recipients)})
    return sorted(recipients)


def send_message(token: str, chat_id: str, text: str) -> tuple[str, int]:
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
        raise RuntimeError(f"Telegram API error: {telegram_api_error(exc)}") from None
    except URLError:
        raise RuntimeError("Could not reach the Telegram Bot API.") from None
    except Exception:
        raise RuntimeError("Telegram message delivery failed.") from None

    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the message; check bot access and chat ID.")

    message = result.get("result") or {}
    message_id = message.get("message_id")
    sent_chat_id = (message.get("chat") or {}).get("id", chat_id)
    if message_id is None:
        raise RuntimeError("Telegram accepted the message but returned no message ID.")
    return str(sent_chat_id), int(message_id)


def delete_message(token: str, chat_id: str, message_id: int) -> None:
    url = f"{TELEGRAM_API}/bot{token}/deleteMessage"
    body = json.dumps({"chat_id": chat_id, "message_id": message_id}).encode("utf-8")
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
        raise RuntimeError(f"Telegram API returned HTTP {exc.code} while deleting the message.") from None
    except URLError:
        raise RuntimeError("Could not reach the Telegram Bot API to delete the message.") from None
    except Exception:
        raise RuntimeError("Telegram message deletion failed.") from None

    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the message deletion; check bot permissions.")


def format_duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        return f"{seconds // 3600}小时"
    if seconds % 60 == 0:
        return f"{seconds // 60}分钟"
    return f"{seconds}秒"


def schedule_message_deletion(chat_id: str, message_id: int, delete_after_seconds: int) -> None:
    command = [
        sys.executable,
        os.path.abspath(__file__),
        "--delete-chat-id",
        chat_id,
        "--delete-message-id",
        str(message_id),
        "--delete-after-seconds",
        str(delete_after_seconds),
    ]
    if os.name == "nt":
        detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        new_process_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
        creationflags = detached | new_process_group
        try:
            subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags | breakaway,
                close_fds=True,
            )
        except OSError:
            subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
                close_fds=True,
            )
    else:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan Binance USD-M Futures and post the report to Telegram."
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--kline-limit", type=int, default=1000)
    parser.add_argument("--market-limit", type=int, default=96)
    parser.add_argument("--delete-chat-id", help=argparse.SUPPRESS)
    parser.add_argument("--delete-message-id", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--delete-after-seconds", type=int, default=7200, help=argparse.SUPPRESS)
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if args.delete_message_id is not None:
        if not token or not args.delete_chat_id:
            log_execution(f"Deletion worker aborted: credentials or target missing; message_id={args.delete_message_id}")
            print("Missing Telegram credentials or deletion target.", file=sys.stderr)
            return 2
        duration = format_duration(args.delete_after_seconds)
        log_execution(f"Deletion worker started; message_id={args.delete_message_id}; waiting {duration}")
        time.sleep(max(0, args.delete_after_seconds))
        try:
            delete_message(token, args.delete_chat_id, args.delete_message_id)
        except (OSError, ValueError, RuntimeError) as exc:
            log_execution(f"Message deletion failed; message_id={args.delete_message_id}; error={exc}")
            print(str(exc), file=sys.stderr)
            return 1
        log_execution(f"Message deleted; message_id={args.delete_message_id}")
        print(f"Deleted Telegram message {args.delete_message_id} after {duration}.")
        return 0

    recipients_value = os.environ.get("TELEGRAM_CHAT_IDS", "").strip()
    chat_ids = list(dict.fromkeys(value.strip() for value in recipients_value.replace(";", ",").split(",") if value.strip()))
    if not token:
        log_execution(f"Scan aborted: Telegram credentials missing; symbol={args.symbol.upper()}")
        print(
            "Missing TELEGRAM_BOT_TOKEN environment variable.",
            file=sys.stderr,
        )
        return 2

    log_execution(f"Scan started; symbol={args.symbol.upper()}")
    try:
        private_chat_ids = discover_private_recipients(token)
        chat_ids = list(dict.fromkeys(private_chat_ids + chat_ids))
        if not chat_ids:
            raise RuntimeError(
                "No Telegram recipients found. Send the bot a message first, or set TELEGRAM_CHAT_IDS for channels."
            )
        log_execution(f"Telegram recipients ready; private_users={len(private_chat_ids)}; total_targets={len(chat_ids)}")
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
        duration = format_duration(args.delete_after_seconds)
        report = report.replace("此消息1小时后自动删除", f"此消息{duration}后自动删除")
        delivery_errors = []
        for chat_id in chat_ids:
            try:
                sent_chat_id, message_id = send_message(token, chat_id, report)
                schedule_message_deletion(sent_chat_id, message_id, args.delete_after_seconds)
                log_execution(f"Telegram push succeeded; symbol={args.symbol.upper()}; target={sent_chat_id}; message_id={message_id}; deletion scheduled in {duration}")
            except (OSError, ValueError, RuntimeError) as exc:
                delivery_errors.append(f"{chat_id}: {exc}")
                log_execution(f"Telegram push failed; symbol={args.symbol.upper()}; target={chat_id}; error={exc}")
        if delivery_errors:
            raise RuntimeError("Delivery failed for: " + "; ".join(delivery_errors))
    except (OSError, ValueError, RuntimeError) as exc:
        log_execution(f"Scan or push failed; symbol={args.symbol.upper()}; error={exc}")
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Posted {args.symbol.upper()} scan to {len(chat_ids)} Telegram target(s); scheduled deletion in {format_duration(args.delete_after_seconds)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

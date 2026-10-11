#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/kali/crypto-market-analysis
ENV_FILE=/home/kali/.config/crypto-market-analysis/telegram.env

if (( $# > 1 )); then
  printf 'Usage: %s [SYMBOL]\n' "$0" >&2
  exit 2
fi

SYMBOL="${1:-BTCUSDT}"
SYMBOL="${SYMBOL^^}"
if [[ ! "$SYMBOL" =~ ^[A-Z0-9]+$ ]]; then
  printf 'Invalid symbol: %s (use letters and digits only)\n' "$SYMBOL" >&2
  exit 2
fi

if [[ ! -r "$ENV_FILE" ]]; then
  echo "Telegram environment file is missing or unreadable." >&2
  exit 2
fi

set -a
source "$ENV_FILE"
set +a
export PYTHONIOENCODING=utf-8
exec /usr/bin/python3 "$ROOT/scripts/run_and_send_telegram.py" --symbol "$SYMBOL"

# Kali Linux 部署手册

本文说明如何把 `crypto-market-analysis` 部署到 Kali Linux，并配置 Telegram 推送和每 4 小时自动扫描。

## 1. 当前服务器部署状态

| 项目 | 当前配置 |
| --- | --- |
| 服务器 | `192.168.56.101`（Kali Linux） |
| 项目目录 | `/home/kali/crypto-market-analysis` |
| Python | `/usr/bin/python3`，Python 3.14 |
| 市场数据 | Binance USDⓈ-M 公共 API；每个周期默认抓取 1000 根 K 线 |
| 定时执行 | 用户级 cron，每天 00:00、04:00、08:00、12:00、16:00、20:00（Asia/Shanghai） |
| 默认交易对 | `BTCUSDT` |
| 防重叠 | 使用 `flock`，上一次扫描未结束时跳过新实例 |
| Telegram 凭据 | `/home/kali/.config/crypto-market-analysis/telegram.env`，权限 `600` |
| 扫描日志 | `logs/telegram_execution.log` |
| cron 标准输出/错误 | `logs/cron.log` |

Telegram 消息会在发送后约 1 小时由后台进程尝试删除。请确保机器人在目标频道有发送和删除消息的权限。

## 2. 软件依赖

脚本使用 Python 标准库，不需要安装额外的 pip 包。服务器需具备：

- Python 3.10 或更高版本；当前主机为 Python 3.14。
- `cron` 服务、`flock` 和 OpenSSH 客户端。
- 能连接 Binance API 与 Telegram Bot API 的 DNS 和 HTTPS 出站网络。

检查命令：

```bash
python3 --version
systemctl is-active cron
command -v flock
```

## 3. 首次传输项目文件

在 Windows PowerShell 中运行。将 `<SSH私钥路径>` 换成你本机可用的 SSH 私钥路径；不要把私钥放进项目目录或发送到服务器。

```powershell
ssh -i '<SSH私钥路径>' kali@192.168.56.101 'mkdir -p /home/kali/crypto-market-analysis'
scp -i '<SSH私钥路径>' -r scripts references README.md SKILL.md LICENSE kali@192.168.56.101:/home/kali/crypto-market-analysis/
```

不要传输 `.git`、`.venv`、`.idea`、`btc_market.json` 或本机凭据文件。项目代码里不应包含 Telegram Token。

登录服务器后设置普通文件权限：

```bash
chmod 755 /home/kali/crypto-market-analysis
chmod 644 /home/kali/crypto-market-analysis/scripts/*.py
mkdir -p /home/kali/crypto-market-analysis/logs
```

## 4. 安全配置 Telegram 凭据

在 Kali 的 SSH 会话中执行。终端会隐藏 Token 和 Chat ID 的输入，不要开启 `set -x`，也不要把凭据写入命令历史或 crontab：

```bash
install -d -m 700 "$HOME/.config/crypto-market-analysis"
umask 077
read -r -s -p 'Telegram Bot Token: ' TELEGRAM_TOKEN
printf '\n'
read -r -s -p 'Telegram Chat ID: ' TELEGRAM_CHAT
printf '\n'
printf 'TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\n' "$TELEGRAM_TOKEN" "$TELEGRAM_CHAT" > "$HOME/.config/crypto-market-analysis/telegram.env"
chmod 600 "$HOME/.config/crypto-market-analysis/telegram.env"
unset TELEGRAM_TOKEN TELEGRAM_CHAT
```

只核对文件权限，不要 `cat` 凭据文件：

```bash
stat -c '%a %n' "$HOME/.config/crypto-market-analysis/telegram.env"
```

预期权限为 `600`。凭据文件由 `scripts/run_scheduled.sh` 读取，不经过 cron 命令行参数。

## 5. 安装每 4 小时任务

创建启动脚本：

```bash
cat > /home/kali/crypto-market-analysis/scripts/run_scheduled.sh <<'RUNNER'
#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/kali/crypto-market-analysis
ENV_FILE=/home/kali/.config/crypto-market-analysis/telegram.env
if [[ ! -r "$ENV_FILE" ]]; then
  echo "Telegram environment file is missing or unreadable." >&2
  exit 2
fi
set -a
source "$ENV_FILE"
set +a
export PYTHONIOENCODING=utf-8
exec /usr/bin/python3 "$ROOT/scripts/run_and_send_telegram.py" --symbol BTCUSDT
RUNNER
chmod 700 /home/kali/crypto-market-analysis/scripts/run_scheduled.sh
```

把定时规则加入当前用户 crontab。脚本会先移除本程序之前的标记区块，保留其他 cron 项：

```bash
tmp_cron="$(mktemp)"
(crontab -l 2>/dev/null || true) \
  | sed '/^# BEGIN CODEX_CRYPTO_MARKET_ANALYSIS$/,/^# END CODEX_CRYPTO_MARKET_ANALYSIS$/d' \
  > "$tmp_cron"
cat >> "$tmp_cron" <<'CRON'
# BEGIN CODEX_CRYPTO_MARKET_ANALYSIS
CRON_TZ=Asia/Shanghai
0 */4 * * * /usr/bin/flock -n /home/kali/crypto-market-analysis/logs/scan.lock /home/kali/crypto-market-analysis/scripts/run_scheduled.sh >> /home/kali/crypto-market-analysis/logs/cron.log 2>&1
# END CODEX_CRYPTO_MARKET_ANALYSIS
CRON
crontab "$tmp_cron"
rm -f "$tmp_cron"
```

查看任务与服务状态：

```bash
crontab -l
systemctl is-active cron
```

该计划在上海时间每 4 小时整运行。Cron 不会补跑服务器关机期间错过的触发点。

## 6. 手动运行

只抓取和分析、不推送 Telegram：

```bash
cd /home/kali/crypto-market-analysis
python3 scripts/fetch_binance_btc.py --symbol BTCUSDT --out /tmp/btc_market.json
PYTHONIOENCODING=utf-8 python3 scripts/analyze_btc_structure.py --input /tmp/btc_market.json --format markdown
```

运行一次完整扫描并推送（这会向频道发送真实消息）：

```bash
/home/kali/crypto-market-analysis/scripts/run_scheduled.sh
```

检查最近日志：

```bash
tail -n 100 /home/kali/crypto-market-analysis/logs/telegram_execution.log
tail -n 100 /home/kali/crypto-market-analysis/logs/cron.log
```

## 7. 网络故障排查

先区分路由、DNS 与 HTTPS：

```bash
ip route show default
ping -c 1 192.168.88.1
getent ahostsv4 fapi.binance.com api.telegram.org
dig @1.1.1.1 fapi.binance.com A
dig @1.1.1.1 api.telegram.org A
curl --connect-timeout 8 -sS https://fapi.binance.com/fapi/v1/ping
curl --connect-timeout 8 -I https://api.telegram.org/
```

- `Network is unreachable`：检查服务器网关、路由器防火墙和出站网络策略。
- DNS 查询失败或不同解析器返回异常/不一致地址：检查路由器 DNS 代理、网络过滤策略；仅修改 Kali 本机 DNS 未必有效。
- `example.com:443` 可用但 Binance/Telegram 不可用：通常是域名解析或针对目标的出站策略问题。需要在服务器所连接的网络侧允许访问 Binance API 与 Telegram Bot API。
- Binance 请求正常但推送失败：检查 Telegram 环境变量是否存在、机器人是否仍在频道，以及发送/删除消息权限。

诊断时不要把 Token、完整 Telegram API URL 或 `.env` 内容粘贴到日志或聊天里。修复网络后，可先运行第 6 节的“只抓取和分析”命令；需要验证推送时，再明确运行完整推送命令。

## 8. 权限与管理说明

应用可由 `kali` 用户运行，不需要 sudo。用户级 cron 也不需要 root 或 `systemd --user` 常驻会话。更改账户 sudo 权限属于单独的系统管理操作；应由有 root 权限的管理员执行并用 `sudo -l -U kali` 复核。

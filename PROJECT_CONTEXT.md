# 项目核心上下文

> 本文件是后续开发、排障和运维的快速上下文索引。涉及当前运行状态时，以 Kali 服务器上的实际脚本和 crontab 为准；不要把本地旧目录 `L:\Skill\BTC-Trade-Skill` 当作活动项目。

## 项目目标与边界

- 从 Binance USDⓈ-M Futures 公共 API 获取行情，识别 15m、1h、4h 多周期市场结构，形成风险提示和观察建议。
- 可将报告推送到 Telegram 频道；不执行交易、不下单，也不输出必须买卖指令。
- 行情读取不需要 Binance API Key。Telegram 推送使用 Bot Token 和 Chat ID；不得把凭据写入代码、命令参数、日志或文档。

## 当前活动路径

- Windows 项目：`L:\Skill\crypto-market-analysis`
- Kali 主机：`192.168.56.101`
- Kali 项目：`/home/kali/crypto-market-analysis`
- Python：Kali 使用 `/usr/bin/python3`（Python 3.14）。

## 代码入口与职责

| 路径 | 职责 |
| --- | --- |
| `scripts/fetch_binance_btc.py` | 抓取 Binance USDⓈ-M 行情和衍生品数据，可用 `--symbol` 指定标的。 |
| `scripts/analyze_btc_structure.py` | 计算市场结构、技术指标、评分、预警和建议。 |
| `scripts/run_and_send_telegram.py` | 串联抓取与分析，格式化报告并推送 Telegram；支持删除消息的后台子进程。 |
| `scripts/start.ps1` | Windows 完整扫描并推送；支持 `-c` / `-Symbol`，默认 BTCUSDT。 |
| `scripts/start_no_push.ps1`（旧树中名称为 `start_nopush.ps1`） | Windows 只扫描并输出，不推送。 |
| Kali `scripts/run_scheduled.sh` | 完整扫描并推送；支持一个可选标的参数，默认 BTCUSDT。 |
| `references/` | 数据源、信号矩阵、风险过滤、输出模板和指标提醒阈值。 |

## 分析与报告约定

- K 线周期为 15m、1h、4h；默认每周期抓取 1000 根。
- 指标包括 KDJ、RSI(6/12/24)、AR、BR、WMSR、CCI、OSC，以及量价结构、OI、主动买卖比、资金费率、多空比和基差等可用数据。
- 关键数据组缺失时应标记 `data_insufficient` 并建议观望；技术指标超买超卖只是提醒，不是反转确认。
- 报告标题应使用实际交易对；Telegram 报告更新时间使用 UTC+8；“触发信号”和“风险判断”条目使用中文，其余模板字段维持既有格式。
- 详细逻辑以 `README.md`、`SKILL.md` 和 `references/*.md` 为准。

## 执行方式

### Windows

```powershell
# 扫描并推送
.\scripts\start.ps1 -c ETHUSDT

# 只扫描，不推送
.\scripts\start_no_push.ps1 -c ETHUSDT
```

省略标的时默认 BTCUSDT。推送脚本需要当前进程能读取 `TELEGRAM_BOT_TOKEN`；固定频道/群组目标可通过可选的 `TELEGRAM_CHAT_IDS` 配置，个人用户由 `getUpdates` 自动登记。

### Kali

```bash
# 扫描 BTCUSDT 并推送
/home/kali/crypto-market-analysis/scripts/run_scheduled.sh

# 扫描其他标的并推送
/home/kali/crypto-market-analysis/scripts/run_scheduled.sh SOLUSDT
```

Kali 凭据文件为 `/home/kali/.config/crypto-market-analysis/telegram.env`，权限应为 `600`；不要显示或复制其内容。脚本只接受一个由字母和数字组成的标的参数，会转成大写。

## 定时器与代理现状（2026-10-02）

- Kali 用户级 crontab 每 4 小时整运行，时区 `Asia/Shanghai`；现有命令不传标的，因此默认扫描 BTCUSDT。
- cron 命令用 `flock` 防止扫描重叠；cron 服务已确认 active。
- Windows 计划任务 `BTCUSDT-Telegram-Market-Analysis` 已取消；不要误以为 Windows 任务仍在运行。
- 代理地址是 `http://192.168.88.171:7897`。Kali 手动命令曾通过命令级 `http_proxy` / `https_proxy` 成功访问 API；`run_scheduled.sh` 和当前 crontab 未配置代理，因此定时任务不会自动使用代理。
- 用户要求 Telegram 消息发送后延迟删除。Kali 当前代码等待 **180 分钟**；修改代码不会改变已启动的删除子进程。每次推送的删除参数由独立子进程持有，多个消息 ID 不会互相覆盖。

## 重要运维文件

- Telegram 执行日志：`/home/kali/crypto-market-analysis/logs/telegram_execution.log`
- cron 输出/错误：`/home/kali/crypto-market-analysis/logs/cron.log`
- 并发锁：`/home/kali/crypto-market-analysis/logs/scan.lock`
- 部署步骤：`DEPLOYMENT.md`

排障优先检查实际用户 crontab（`crontab -l`）、cron 服务（`systemctl is-active cron`）、两份日志和代理环境。检查凭据时只检查是否存在和权限，不打印值。

## 修改原则

- 保留用户已有本地改动；提交代码前检查工作树状态。
- 修改扫描逻辑时同时确认报告标题、数据源时间、失败处理和 Telegram 推送行为。
- 运行会向频道发消息的完整扫描属于真实外部操作；执行前明确目标标的和是否使用代理。
- 需要调整 cron 时先保留其他 crontab 项；不要改 Windows 定时任务，除非用户另行提出。


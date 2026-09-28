param(
    [Alias('c')]
    [ValidatePattern('^[A-Za-z0-9]+$')]
    [string]$Symbol = 'BTCUSDT'
)

$python = 'D:\Python\Python314\python.exe'
$script = 'L:\Skill\crypto-market-analysis\scripts\run_and_send_telegram.py'
$symbolToScan = $Symbol.ToUpperInvariant()

$env:TELEGRAM_BOT_TOKEN = [Environment]::GetEnvironmentVariable('TELEGRAM_BOT_TOKEN', 'Machine')
$env:TELEGRAM_CHAT_ID = [Environment]::GetEnvironmentVariable('TELEGRAM_CHAT_ID', 'Machine')
if (-not $env:TELEGRAM_BOT_TOKEN -or -not $env:TELEGRAM_CHAT_ID) {
    throw 'Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in Windows system environment.'
}

& $python $script --symbol $symbolToScan
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

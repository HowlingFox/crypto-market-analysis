param(
    [Alias('c')]
    [ValidatePattern('^[A-Za-z0-9]+$')]
    [string]$Symbol = 'BTCUSDT'
)

$python = 'D:\Python\Python314\python.exe'
$symbolToScan = $Symbol.ToUpperInvariant()
$output = 'L:\Skill\BTC-Trade-Skill\btc_market.json'

& $python 'L:\Skill\BTC-Trade-Skill\scripts\fetch_binance_btc.py' --symbol $symbolToScan --out $output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:PYTHONIOENCODING = 'utf-8'
& $python 'L:\Skill\BTC-Trade-Skill\scripts\analyze_btc_structure.py' --input $output --format markdown
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

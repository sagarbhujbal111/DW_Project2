$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$interpreter = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (!(Test-Path $interpreter)) {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($python) {
        & py -3 -m venv .venv
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (!$python) { throw 'Install Python 3.11+ and rerun run.ps1.' }
        & $python.Source -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
& $interpreter -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $interpreter windows_mysql.py
if ($LASTEXITCODE -ne 0) { throw 'MySQL startup failed.' }
& $interpreter bootstrap.py
if ($LASTEXITCODE -ne 0) { throw 'Warehouse setup failed.' }
$appPort = & $interpreter -c "from database import os; print(os.getenv('APP_PORT', '8000'))"
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:$appPort/api/health" -TimeoutSec 2
    if ($health.warehouse -eq 'ecommerce_dw' -and $health.tagline -eq 'From first order to forever customer') {
        Write-Host "CartPulse is running at http://127.0.0.1:$appPort/"
        return
    }
} catch { }
& $interpreter -m uvicorn app:app --host 127.0.0.1 --port $appPort
exit $LASTEXITCODE

# CNAT NOISERELIEF Startup Script for PowerShell
Write-Host "Starting CNAT NOISERELIEF..." -ForegroundColor Cyan
python src/main.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Application exited with code $LASTEXITCODE" -ForegroundColor Red
}

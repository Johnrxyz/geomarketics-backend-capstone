# Reseed database with fresh data
Set-Location $PSScriptRoot\..
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Re-seeding database..." -ForegroundColor Yellow
python scripts/seed.py

# LC Public Market Backend - Start Script
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Starting LC Public Market Backend..." -ForegroundColor Green
Write-Host "API will be available at: http://localhost:8000/api/v1/" -ForegroundColor Cyan
Write-Host "Admin panel at: http://localhost:8000/admin/" -ForegroundColor Cyan
Write-Host ""
python manage.py runserver 8000

# Flask Cache Cleanup Script for Windows PowerShell
# Removes all Python cache and Flask temporary files

Write-Host "🧹 Cleaning Python cache..." -ForegroundColor Green

# Remove __pycache__ directories
Get-ChildItem -Path . -Recurse -Directory -Name "__pycache__" | 
    ForEach-Object { Remove-Item -Path $_ -Recurse -Force -ErrorAction SilentlyContinue }

# Remove .pyc files
Get-ChildItem -Path . -Recurse -Include "*.pyc" | 
    ForEach-Object { Remove-Item -Path $_ -Force -ErrorAction SilentlyContinue }

# Remove .pyo files
Get-ChildItem -Path . -Recurse -Include "*.pyo" | 
    ForEach-Object { Remove-Item -Path $_ -Force -ErrorAction SilentlyContinue }

# Remove Flask instance folder
if (Test-Path "instance") {
    Remove-Item -Path "instance" -Recurse -Force -ErrorAction SilentlyContinue
}

# Remove .webassets-cache
if (Test-Path ".webassets-cache") {
    Remove-Item -Path ".webassets-cache" -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "✅ Cache cleanup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "You can now restart Flask:" -ForegroundColor Cyan
Write-Host "  python backend/app.py" -ForegroundColor Yellow

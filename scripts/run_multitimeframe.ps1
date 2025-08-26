# Script para ejecutar el bot multitimeframe
# run_multitimeframe.ps1

Write-Host "🎯 Starting Multitimeframe Trading Bot..." -ForegroundColor Green

# Verificar que estamos en el directorio correcto
$currentDir = Get-Location
Write-Host "📁 Current directory: $currentDir" -ForegroundColor Cyan

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "🐍 Python version: $pythonVersion" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Python not found! Please install Python." -ForegroundColor Red
    exit 1
}

# Verificar que los archivos existen
$mainFile = "pro_bot/app/main_multitimeframe.py"
if (-not (Test-Path $mainFile)) {
    Write-Host "❌ Main file not found: $mainFile" -ForegroundColor Red
    exit 1
}

$configFile = "configs/ml.yaml"
if (-not (Test-Path $configFile)) {
    Write-Host "❌ Config file not found: $configFile" -ForegroundColor Red
    exit 1
}

Write-Host "✅ All files found" -ForegroundColor Green

# Configurar variables de entorno
$env:PYTHONPATH = "$currentDir;$env:PYTHONPATH"

Write-Host "🚀 Launching multitimeframe bot..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow

# Ejecutar el bot
try {
    python $mainFile
} catch {
    Write-Host "❌ Error running the bot: $_" -ForegroundColor Red
    exit 1
}

Write-Host "👋 Bot stopped" -ForegroundColor Blue

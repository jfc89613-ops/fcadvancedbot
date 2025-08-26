# Script para probar el sistema multitimeframe
# test_multitimeframe.ps1

Write-Host "🔬 Testing Multitimeframe System..." -ForegroundColor Green

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

# Verificar archivos de test
$testFile = "test_multitimeframe.py"
if (-not (Test-Path $testFile)) {
    Write-Host "❌ Test file not found: $testFile" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Test file found" -ForegroundColor Green

# Configurar variables de entorno
$env:PYTHONPATH = "$currentDir;$env:PYTHONPATH"

Write-Host "🚀 Running multitimeframe test..." -ForegroundColor Green
Write-Host "This will run for 2 minutes. Press Ctrl+C to stop early." -ForegroundColor Yellow

# Ejecutar el test
try {
    python $testFile
} catch {
    Write-Host "❌ Error running test: $_" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Test completed" -ForegroundColor Blue

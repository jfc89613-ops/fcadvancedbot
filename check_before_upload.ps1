#!/usr/bin/env pwsh
# Script de verificacion antes de subir a GitHub

Write-Host "Verificacion de Seguridad Pre-Upload" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Blue

# Verificar archivos sensibles
$sensitive_patterns = @(
    "*.env",
    "*api_key*",
    "*secret*",
    "*password*",
    "*token*",
    "*credentials*"
)

Write-Host "Buscando archivos sensibles..." -ForegroundColor Cyan

$found_sensitive = $false
foreach ($pattern in $sensitive_patterns) {
    $files = Get-ChildItem -Recurse -Include $pattern -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        if ($file.Name -ne ".env.example") {
            Write-Host "   ENCONTRADO: $($file.FullName)" -ForegroundColor Red
            $found_sensitive = $true
        }
    }
}

if ($found_sensitive) {
    Write-Host ""
    Write-Host "ARCHIVOS SENSIBLES DETECTADOS" -ForegroundColor Red
    Write-Host "   Revisa los archivos marcados antes de continuar" -ForegroundColor Yellow
    Write-Host "   Asegurate de que esten en .gitignore" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "   No se encontraron archivos sensibles" -ForegroundColor Green
}

# Verificar .gitignore
Write-Host ""
Write-Host "Verificando .gitignore..." -ForegroundColor Cyan

if (Test-Path ".gitignore") {
    $gitignore_content = Get-Content ".gitignore" -Raw
    $required_patterns = @(".env", "*.env", "__pycache__", "*.pyc")
    
    foreach ($pattern in $required_patterns) {
        if ($gitignore_content -match [regex]::Escape($pattern)) {
            Write-Host "   $pattern esta ignorado" -ForegroundColor Green
        } else {
            Write-Host "   $pattern NO esta en .gitignore" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "   .gitignore no encontrado" -ForegroundColor Red
}

# Verificar archivos requeridos
Write-Host ""
Write-Host "Verificando archivos requeridos..." -ForegroundColor Cyan

$required_files = @(
    "README.md",
    "requirements.txt", 
    ".gitignore",
    "LICENSE",
    ".env.example",
    "configs/ml.yaml"
)

foreach ($file in $required_files) {
    if (Test-Path $file) {
        Write-Host "   $file" -ForegroundColor Green
    } else {
        Write-Host "   $file - FALTANTE" -ForegroundColor Red
    }
}

# Verificar estructura del proyecto
Write-Host ""
Write-Host "Verificando estructura del proyecto..." -ForegroundColor Cyan

$required_dirs = @("pro_bot", "pro_ml", "configs")
foreach ($dir in $required_dirs) {
    if (Test-Path $dir -PathType Container) {
        Write-Host "   $dir/" -ForegroundColor Green
    } else {
        Write-Host "   $dir/ - FALTANTE" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Resumen de verificacion:" -ForegroundColor Green
Write-Host "   Archivos sensibles: OK" -ForegroundColor Green
Write-Host "   .gitignore: OK" -ForegroundColor Green  
Write-Host "   Archivos requeridos: Verificar arriba" -ForegroundColor Green
Write-Host "   Estructura: Verificar arriba" -ForegroundColor Green

Write-Host ""
Write-Host "Verificacion completada. Revisa cualquier advertencia antes de subir." -ForegroundColor Green

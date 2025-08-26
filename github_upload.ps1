#!/usr/bin/env pwsh
# Script para subir el proyecto Binance Futures Pro a GitHub

Write-Host "Preparando Binance Futures Pro para GitHub..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Blue

# Verificar si estamos en el directorio correcto
if (-not (Test-Path "pro_bot" -PathType Container)) {
    Write-Host "Error: No se encontro el directorio 'pro_bot'" -ForegroundColor Red
    Write-Host "Asegurate de estar en el directorio raiz del proyecto" -ForegroundColor Yellow
    exit 1
}

Write-Host "Verificando estructura del proyecto..." -ForegroundColor Cyan

# Verificar archivos importantes
$important_files = @("README.md", "requirements.txt", ".gitignore", "configs/ml.yaml")
foreach ($file in $important_files) {
    if (Test-Path $file) {
        Write-Host "   $file" -ForegroundColor Green
    } else {
        Write-Host "   $file - FALTANTE" -ForegroundColor Red
    }
}

# Verificar que .env no este en el staging
Write-Host ""
Write-Host "Verificando archivos sensibles..." -ForegroundColor Cyan
if (Test-Path ".env") {
    Write-Host "ADVERTENCIA: Archivo .env detectado" -ForegroundColor Yellow
    Write-Host "Asegurate de que este en .gitignore" -ForegroundColor Yellow
    
    # Verificar si .env está en .gitignore
    if (Test-Path ".gitignore") {
        $gitignore_content = Get-Content ".gitignore" -Raw
        if ($gitignore_content -match "\.env") {
            Write-Host ".env esta correctamente en .gitignore" -ForegroundColor Green
        } else {
            Write-Host "ERROR: .env NO esta en .gitignore!" -ForegroundColor Red
            exit 1
        }
    }
}

# Crear .env.example si no existe
if (-not (Test-Path ".env.example")) {
    Write-Host "Creando .env.example..." -ForegroundColor Cyan
    $env_example = @"
# Binance API Configuration
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here

# Trading Configuration
TESTNET=true
MAX_MARGIN_USDT=0.5
MAX_SYMBOLS=19

# Symbol Configuration (19 fixed symbols)
SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,ADAUSDT,XRPUSDT,SOLUSDT,DOGEUSDT,AVAXUSDT,LINKUSDT,LTCUSDT,SUIUSDT,WIFUSDT,FARTCOINUSDT,HYPEUSDT,PROMPTUSDT,BIOUSDT,ENAUSDT,1000PEPEUSDT,ONTUSDT

# Optional Settings
KLINE_INTERVAL=1m
WARMUP_LOOKBACK_MIN=1500
"@
    $env_example | Out-File -FilePath ".env.example" -Encoding UTF8
    Write-Host ".env.example creado" -ForegroundColor Green
}

# Inicializar git si no existe
if (-not (Test-Path ".git" -PathType Container)) {
    Write-Host "Inicializando repositorio Git..." -ForegroundColor Cyan
    git init
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Git inicializado" -ForegroundColor Green
    } else {
        Write-Host "Error al inicializar Git" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Repositorio Git ya existe" -ForegroundColor Cyan
}

# Agregar archivos al staging
Write-Host "Agregando archivos al staging..." -ForegroundColor Cyan
git add .
if ($LASTEXITCODE -eq 0) {
    Write-Host "Archivos agregados" -ForegroundColor Green
} else {
    Write-Host "Error al agregar archivos" -ForegroundColor Red
    exit 1
}

# Mostrar status
Write-Host "Estado del repositorio:" -ForegroundColor Cyan
git status --short

# Crear commit inicial
Write-Host ""
$commit_message = Read-Host "Mensaje del commit (Enter para usar el predeterminado)"
if ([string]::IsNullOrWhiteSpace($commit_message)) {
    $commit_message = "Initial commit: Binance Futures Pro Trading Bot with ML and advanced risk management"
}

Write-Host "Creando commit..." -ForegroundColor Cyan
git commit -m $commit_message
if ($LASTEXITCODE -eq 0) {
    Write-Host "Commit creado exitosamente" -ForegroundColor Green
} else {
    Write-Host "Error al crear commit" -ForegroundColor Red
    exit 1
}

# Preguntar por el repositorio remoto
Write-Host ""
Write-Host "Configuracion del repositorio remoto:" -ForegroundColor Cyan
Write-Host "1. Ve a https://github.com y crea un nuevo repositorio" -ForegroundColor Yellow
Write-Host "2. NO inicialices con README, .gitignore o LICENSE" -ForegroundColor Yellow
Write-Host "3. Copia la URL del repositorio" -ForegroundColor Yellow
Write-Host ""

$repo_url = Read-Host "URL del repositorio de GitHub (ej: https://github.com/usuario/repo.git)"

if ([string]::IsNullOrWhiteSpace($repo_url)) {
    Write-Host "No se proporciono URL. Puedes agregar el remoto manualmente despues:" -ForegroundColor Yellow
    Write-Host "   git remote add origin <URL_DEL_REPOSITORIO>" -ForegroundColor Cyan
    Write-Host "   git branch -M main" -ForegroundColor Cyan
    Write-Host "   git push -u origin main" -ForegroundColor Cyan
} else {
    # Agregar remoto
    Write-Host "Agregando remoto..." -ForegroundColor Cyan
    git remote add origin $repo_url
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Remoto agregado" -ForegroundColor Green
    } else {
        Write-Host "Error al agregar remoto" -ForegroundColor Red
        Write-Host "Verifica que la URL sea correcta" -ForegroundColor Yellow
        exit 1
    }

    # Cambiar a branch main
    Write-Host "Cambiando a branch main..." -ForegroundColor Cyan
    git branch -M main
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Branch main configurado" -ForegroundColor Green
    } else {
        Write-Host "Error al configurar branch main" -ForegroundColor Red
    }

    # Push inicial
    Write-Host "Subiendo a GitHub..." -ForegroundColor Cyan
    git push -u origin main
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Proyecto subido exitosamente a GitHub!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Tu proyecto esta ahora en GitHub!" -ForegroundColor Green
        Write-Host "Puedes verlo en: $repo_url" -ForegroundColor Cyan
    } else {
        Write-Host "Error al subir a GitHub" -ForegroundColor Red
        Write-Host "Posibles causas:" -ForegroundColor Yellow
        Write-Host "- Credenciales incorrectas" -ForegroundColor Yellow
        Write-Host "- URL del repositorio incorrecta" -ForegroundColor Yellow
        Write-Host "- El repositorio ya existe y no esta vacio" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Proximos pasos:" -ForegroundColor Cyan
Write-Host "1. Verifica que el .env este en .gitignore" -ForegroundColor Green
Write-Host "2. Configura .env.example para otros usuarios" -ForegroundColor Green
Write-Host "3. Actualiza el README con tu informacion" -ForegroundColor Green
Write-Host "4. Considera agregar mas documentacion" -ForegroundColor Green
Write-Host ""
Write-Host "Proyecto listo para compartir!" -ForegroundColor Green

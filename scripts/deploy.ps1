
param(
  [string]$PemPath = "C:\Users\YOURUSER\Desktop\VIRI1.pem",
  [string]$Host = "ubuntu@3.68.191.38",
  [string]$ZipLocal = ".\binance_futures_pro_multi20_registry_deploy.zip",
  [string]$RemoteDir = "~/binance_futures_pro"
)

# Requiere OpenSSH cliente en Windows (ssh/scp en PATH)
if (!(Test-Path $ZipLocal)) {
  Write-Error "No se encontró el ZIP local: $ZipLocal"
  exit 1
}

# Copia ZIP y .env
Write-Host "[*] Creando carpeta remota..."
ssh -i $PemPath $Host "mkdir -p $RemoteDir"

Write-Host "[*] Subiendo ZIP del proyecto..."
scp -i $PemPath $ZipLocal $Host:"$RemoteDir/app.zip"

if (Test-Path ".env") {
  Write-Host "[*] Subiendo .env..."
  scp -i $PemPath .env $Host:"$RemoteDir/.env"
} else {
  Write-Warning "No se encontró .env local; recuerda crearla en el servidor."
}

Write-Host "[*] Ejecutando setup remoto..."
scp -i $PemPath scripts/remote_setup.sh $Host:"$RemoteDir/remote_setup.sh"
ssh -i $PemPath $Host "chmod +x $RemoteDir/remote_setup.sh && bash $RemoteDir/remote_setup.sh"

Write-Host "[*] Despliegue completo. Para ver logs:"
Write-Host "ssh -i $PemPath $Host 'sudo journalctl -u binance-bot -f'"

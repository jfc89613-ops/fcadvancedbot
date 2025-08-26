
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/binance_futures_pro"
PY=python3

echo "[*] Actualizando sistema y herramientas básicas..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip git unzip

echo "[*] Creando directorio de la app en $APP_DIR"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

if [ -f app.zip ]; then rm -f app.zip; fi
echo "[*] Recibí el ZIP. Descomprimiendo..."
unzip -o app.zip

echo "[*] Creando venv e instalando dependencias..."
$PY -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p outputs/models outputs/runtime

echo "[*] (Opcional) Entrenamiento inicial si no hay modelo global..."
if [ ! -f outputs/models/best_model.joblib ]; then
  echo "No hay modelo global; ejecutando entrenamiento rápido (puede tardar)."
  $PY -m pro_ml.core.training.train || echo "Entrenamiento falló o no configurado; continúa."
fi

echo "[*] Instalando servicio systemd..."
SERVICE_FILE="/etc/systemd/system/binance-bot.service"
sudo bash -c "cat > $SERVICE_FILE" <<'EOF'
[Unit]
Description=Binance Futures Pro Bot (ML)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=%h/binance_futures_pro
Environment="PYTHONUNBUFFERED=1"
ExecStart=%h/binance_futures_pro/.venv/bin/python -m pro_bot.app.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "[*] Recargando systemd y habilitando servicio..."
sudo systemctl daemon-reload
sudo systemctl enable binance-bot.service
sudo systemctl restart binance-bot.service

echo "[*] Listo. Logs en: sudo journalctl -u binance-bot -f"


echo "[*] (Opcional) Entrenamiento batch top-20 (modo rápido)"
echo "    Para ejecutarlo manualmente: source .venv/bin/activate && bash scripts/train_batch.sh configs/ml.yaml '' 20 1"

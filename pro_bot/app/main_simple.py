import os
import logging
import yaml
import pandas as pd
from collections import defaultdict
from datetime import datetime
import threading
import time

from pro_bot.config import settings
from pro_bot.core.client import get_client
from pro_bot.core.ws_multi import start_kline_multiplex
from pro_bot.core.execution import refresh_open_positions_cache

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main_simple")

# Configuración
CFG_PATH = os.getenv("ML_CFG", "configs/ml.yaml")
with open(CFG_PATH, 'r') as f:
    cfg = yaml.safe_load(f)

log.info("🚀 BOT iniciando en MAINNET")

# Buffers simples
message_count = 0
kline_count = 0
symbol_data = defaultdict(int)

def _on_msg(msg):
    global message_count, kline_count
    try:
        message_count += 1
        
        # Log cada 10 mensajes
        if message_count % 10 == 0:
            log.info(f"Received {message_count} total messages")
        
        data = msg.get('data', msg)
        if data.get('e') != 'kline':
            return
            
        k = data['k']
        if not k['x']:  # Solo klines cerradas
            return
            
        sym = data.get('s') or k.get('s')
        kline_count += 1
        symbol_data[sym] += 1
        
        # Log cada kline cerrada
        log.info(f"Closed kline #{kline_count} for {sym} - Price: {k['c']}")
        
        # Aquí iría la lógica ML, pero por ahora solo logging
        
    except Exception as e:
        log.error(f"Error in _on_msg: {e}")

def status_thread():
    """Thread que reporta estado cada 30 segundos"""
    while True:
        time.sleep(30)
        log.info(f"Status: {message_count} msgs, {kline_count} klines, {len(symbol_data)} symbols active")
        if symbol_data:
            log.info(f"Top symbols: {dict(list(symbol_data.items())[:5])}")

def main():
    log.info("Starting simple bot...")
    
    # Inicializar cliente
    get_client()
    refresh_open_positions_cache()
    
    # Usar símbolos fijos del .env
    symbols_env = os.getenv("SYMBOLS", "").strip()
    if symbols_env:
        syms = [s.strip() for s in symbols_env.split(",") if s.strip()]
        log.info(f"Using {len(syms)} fixed symbols: {syms[:5]}...")
    else:
        syms = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        log.info(f"Using fallback symbols: {syms}")
    
    # Iniciar thread de estado
    status_thread_obj = threading.Thread(target=status_thread, daemon=True)
    status_thread_obj.start()
    
    # Iniciar WebSocket
    interval = "1m"
    log.info(f"Starting WebSocket for {len(syms)} symbols with interval {interval}")
    
    try:
        twm = start_kline_multiplex(syms, interval=interval, callback=_on_msg)
        log.info("WebSocket started successfully, waiting for messages...")
        twm.join()
    except KeyboardInterrupt:
        log.info("Stopping bot...")
        twm.stop()
    except Exception as e:
        log.error(f"Error in main: {e}")

if __name__ == "__main__":
    main()

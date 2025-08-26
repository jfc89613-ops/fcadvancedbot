
import os
import logging
import yaml
import pandas as pd
from collections import defaultdict
from datetime import datetime

from pro_bot.config import settings
from pro_bot.core.client import get_client
from pro_bot.core.ws_multi import start_kline_multiplex
from pro_bot.core.sl_tp_manager import SLTPManager
# from pro_bot.core.universe import fetch_top_usdt_perpetuals_by_volume  # No necesario con símbolos fijos
from pro_bot.core.execution import (
    has_open_position, 
    open_positions_count,
    _can_open_new_position
)

from pro_ml.core.features.microstructure import build_features
from pro_ml.core.live.inference_multi import LiveModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main_multi")

CFG_PATH = os.getenv("ML_CFG", "configs/ml.yaml")
with open(CFG_PATH, 'r') as f:
    cfg = yaml.safe_load(f)

def standardize_margin_for_symbols(symbols):
    """Estandariza el tipo de margen para todos los símbolos"""
    client = get_client()
    client.standardize_margin_for_all_symbols(symbols)

log.info("🚀 BOT iniciando en MAINNET")

serv = cfg.get('serving', {})
lm = LiveModel(
    base_dir='outputs/models',
    prob_long=serv.get('prob_long', 0.57),
    prob_short=serv.get('prob_short', 0.43)
)

DF = defaultdict(lambda: pd.DataFrame(columns=['open','high','low','close','volume']))
PM = {}

# Restaurar MAX_SYMBOLS para funcionalidad completa
MAX_SYMBOLS = int(os.getenv("MAX_SYMBOLS", "19"))
# UNIVERSE_REFRESH_MIN is reserved for future automatic rotation

def _ensure_pm(sym):
    if sym not in PM:
        PM[sym] = SLTPManager(cfg, sym)  # Pasar símbolo como parámetro
    return PM[sym]

def _on_msg(msg):
    try:
        # Log inicial para debug
        if not hasattr(_on_msg, 'total_msgs'):
            _on_msg.total_msgs = 0
        _on_msg.total_msgs += 1
        
        if _on_msg.total_msgs <= 5:  # Primeros 5 mensajes para debug
            log.info(f"Raw message #{_on_msg.total_msgs}: {type(msg)} - {str(msg)[:200]}...")
        
        data = msg.get('data', msg)
        
        # Verificar el tipo de evento
        event_type = data.get('e')
        if not event_type:
            log.warning(f"No event type in message: {data}")
            return
            
        if event_type != 'kline':
            if _on_msg.total_msgs <= 10:  # Solo log las primeras veces
                log.info(f"Ignoring event type: {event_type}")
            return
            
        k = data.get('k')
        if not k:
            log.warning(f"No kline data in message: {data}")
            return
            
        # Verificar si es kline cerrada
        if not k.get('x'):
            return  # Solo procesar klines cerradas
            
        sym = data.get('s') or k.get('s')
        if not sym:
            log.warning(f"No symbol in kline: {k}")
            return
        
        # Log cada 50 klines procesadas
        if not hasattr(_on_msg, 'processed_klines'):
            _on_msg.processed_klines = 0
        _on_msg.processed_klines += 1
        
        if _on_msg.processed_klines % 50 == 0:
            log.info(f"Processed {_on_msg.processed_klines} closed klines. Latest: {sym}")
        
        ts = int(k['t']) // 1000
        row = {
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
        }
        dfi = DF[sym]
        dfi.loc[datetime.fromtimestamp(ts)] = row
        DF[sym] = dfi

        # Solo procesar si tenemos suficientes datos
        if len(dfi) < 150:
            return

        try:
            feats_df = build_features(dfi, cfg)
            if len(feats_df) < 30:
                return
            latest = feats_df.iloc[-1]
        except Exception as e:
            log.error(f"[{sym}] Error in build_features: {e}")
            return
            
        last_close = float(dfi.iloc[-1]['close'])
        atr = float(latest['atr']) if 'atr' in latest and pd.notnull(latest['atr']) else 0.0

        try:
            pm = _ensure_pm(sym)
        except Exception as e:
            log.error(f"[{sym}] Error creating position manager: {e}")
            return

        try:
            decision, prob = lm.decide(sym, latest)  # Usar LiveModel multi-símbolo
        except Exception as e:
            log.error(f"[{sym}] Error in ML inference: {e}")
            return

        try:
            pm.manage(last_close=last_close, atr=atr)

            # Verificar límites de riesgo antes de abrir nuevas posiciones
            if decision in ("LONG", "SHORT") and not pm.state.active:
                # Verificar si podemos abrir nueva posición
                if not _can_open_new_position(sym):
                    log.info(f"[{sym}] Cannot open new position - risk limits")
                    return
                    
                # Abrir posición con todas las funcionalidades
                log.info(f"[{sym}] Opening {decision} position (prob: {prob:.3f}), price: {last_close:.4f}")
                pm.open_trade(direction=decision, atr=atr, use_limit=True)
        except Exception as e:
            log.error(f"[{sym}] Error in position management: {e}")
            return
        
        # Log periódico de señales (cada 10 señales por símbolo)
        if not hasattr(_on_msg, 'signal_count'):
            _on_msg.signal_count = {}
        _on_msg.signal_count[sym] = _on_msg.signal_count.get(sym, 0) + 1
        
        if _on_msg.signal_count[sym] % 10 == 0 and decision != "HOLD":
            log.info(f"[{sym}] Signal #{_on_msg.signal_count[sym]}: {decision} (prob: {prob:.3f})")

    except Exception as e:
        log.warning(f"[{msg.get('stream','?')}] error: {e}")

def warmup_symbol(symbol: str, interval: str, lookback_min: int = 1500):
    """Precarga datos históricos para un símbolo"""
    from pro_bot.core.binance_klines import fetch_klines
    try:
        log.info(f"[{symbol}] Starting warmup...")
        df = fetch_klines(symbol, interval, limit=lookback_min)
        if df is not None and len(df) > 0:
            DF[symbol] = df.copy()
            log.info(f"[{symbol}] Warmup completed: {len(df)} rows loaded")
        else:
            log.warning(f"[{symbol}] Warmup failed: no data received")
    except Exception as e:
        log.error(f"[{symbol}] Warmup error: {e}")

def main():
    get_client()
    
    # Log de posiciones abiertas al inicio (sin cache)
    open_count = open_positions_count()
    log.info(f"Open positions: {open_count}/5")
    
    # Usar símbolos fijos del archivo .env
    symbols_env = os.getenv("SYMBOLS", "").strip()
    if symbols_env:
        syms = [s.strip() for s in symbols_env.split(",") if s.strip()]
        log.info(f"Using fixed symbols from env: {len(syms)} symbols: {', '.join(syms[:10])}{'...' if len(syms) > 10 else ''}")
    else:
        # Fallback a una lista básica si no hay SYMBOLS en .env
        syms = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT"]
        log.info(f"Using fallback symbols: {len(syms)} symbols")
    
    # WARMUP: Precargar datos históricos para todos los símbolos
    log.info("Starting warmup phase...")
    interval = (settings.kline_interval or "1m").replace("1min","1m")
    lookback = settings.warmup_lookback_min
    
    for symbol in syms:
        warmup_symbol(symbol, interval, lookback)
    
    log.info(f"Warmup completed for {len(syms)} symbols. Starting real-time processing...")
    
    twm = start_kline_multiplex(syms, interval=interval, callback=_on_msg)
    try:
        twm.join()
    except KeyboardInterrupt:
        twm.stop()

if __name__ == "__main__":
    main()

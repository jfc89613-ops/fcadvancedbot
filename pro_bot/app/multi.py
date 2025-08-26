import os
import queue
import threading
import logging
from collections import defaultdict
from datetime import datetime, timezone

import yaml
import pandas as pd

from pro_bot.config import settings
from pro_bot.core.client import get_client
from pro_bot.core.ws_multi import start_kline_multiplex
from pro_bot.core.execution import (
    enter_position,
    _can_open_new_position,
    refresh_open_positions_cache,
    has_open_position,
    open_positions_count,
)

# ML
from pro_ml.core.features.microstructure import build_features
from pro_ml.core.live.inference_multi import LiveModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("multi")

CFG_PATH = os.getenv("ML_CFG", "configs/ml.yaml")
with open(CFG_PATH, "r") as f:
    cfg = yaml.safe_load(f)

serv = cfg.get("serving", {})
lm = LiveModel(
    base_dir="outputs/models",
    prob_long=serv.get("prob_long", 0.57),
    prob_short=serv.get("prob_short", 0.43),
)

# Buffers por símbolo
KQ = defaultdict(queue.Queue)
DF = defaultdict(lambda: pd.DataFrame(columns=["open", "high", "low", "close", "volume"]))

def on_kline_factory(symbol: str):
    def on_kline(msg):
        try:
            if msg.get("e") != "kline":
                return
            k = msg.get("k", {})
            if not k.get("x"):
                return
            ts_ms = int(k["t"])
            row = {
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low":  float(k["l"]),
                "close": float(k["c"]),
                "volume": float(k["v"]),
            }
            KQ[symbol].put((ts_ms, row))
        except Exception as e:
            log.warning(f"[{symbol}] on_kline error: {e}")
    return on_kline

def warmup_symbol(symbol: str, interval: str, lookback_min: int = 2000):
    from pro_bot.core.binance_klines import fetch_klines
    df = fetch_klines(symbol, interval, limit=lookback_min)
    DF[symbol] = df.copy()
    log.info(f"[{symbol}] warmup rows: {len(df)}")

def worker(symbol: str):
    # Bucle de decisiones por símbolo
    while True:
        try:
            ts_ms, row = KQ[symbol].get(timeout=120)
        except Exception:
            log.warning(f"[{symbol}] no klines in 120s (revisar conexión)")
            continue

        idx = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
        DF[symbol].loc[idx] = row

        feats_df = build_features(DF[symbol], cfg)
        if len(feats_df) < 10:
            continue
        latest = feats_df.iloc[-1]

        # Decisión ML
        decision, prob = lm.decide(symbol, latest)
        log.info(f"[{symbol}] ML Decision: {decision} p={prob:.3f}")

        if decision in ("LONG", "SHORT"):
            # bloqueos: una por símbolo + máximo global
            if not _can_open_new_position(symbol):
                log.info(f"[{symbol}] ya tiene posición abierta; no abriré otra.")
                continue
            max_open = int(getattr(settings, "max_open_positions", 5))
            if open_positions_count() >= max_open:
                log.info(f"[{symbol}] límite global de posiciones ({max_open}) alcanzado; se omite entrada.")
                continue
            try:
                log.info(f"[{symbol}] Entering {decision} via LIMIT")
                enter_position(decision, use_limit=True, symbol=symbol)
            except Exception as e:
                log.warning(f"[{symbol}] enter error: {e}")

def main():
    get_client()  # init (margin/leverage/mode)

    # Descubrir símbolos
    from pro_bot.core.symbols import top_usdtm_symbols_by_quote_volume, forced_symbols_from_env
    syms = forced_symbols_from_env() or top_usdtm_symbols_by_quote_volume(int(os.getenv("TOPN", "20")))
    log.info(f"Symbols: {syms}")

    # Warmup para todos los símbolos
    for symbol in syms:
        warmup_symbol(symbol, settings.kline_interval, settings.warmup_lookback_min)

    # Crear callback global para todos los símbolos
    def on_kline_multiplex(msg):
        """Callback para multiplex que maneja todos los símbolos"""
        try:
            data = msg.get("data", {})
            if not data:
                return
            
            symbol = data.get("s", "").upper()
            kline = data.get("k", {})
            
            if not symbol or not kline:
                return
                
            # Solo procesar si es el cierre de la vela
            if not kline.get("x", False):
                return
                
            ts_ms = int(kline["t"])
            row = {
                "open": float(kline["o"]),
                "high": float(kline["h"]),
                "low": float(kline["l"]),
                "close": float(kline["c"]),
                "volume": float(kline["v"]),
            }
            
            KQ[symbol].put((ts_ms, row))
        except Exception as e:
            log.warning(f"on_kline_multiplex error: {e}")

    # Iniciar WebSocket multiplex para todos los símbolos
    twm = start_kline_multiplex(syms, settings.kline_interval, on_kline_multiplex)

    # Worker por símbolo
    workers = []
    for symbol in syms:
        t = threading.Thread(target=worker, args=(symbol,), daemon=True)
        t.start()
        workers.append(t)

    # Cache refresh
    refresh_open_positions_cache()
    t_refresh = threading.Thread(target=refresh_open_positions_cache, daemon=True)
    t_refresh.start()

    log.info("Bot started. Ctrl+C to stop.")
    try:
        twm.join()  # Mantener el WebSocket vivo
    except KeyboardInterrupt:
        log.info("Stopping...")
        twm.stop()

if __name__ == "__main__":
    main()

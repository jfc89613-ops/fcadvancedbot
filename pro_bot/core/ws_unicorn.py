import threading
import json
import logging
from unicorn_binance_websocket_api.manager import BinanceWebSocketApiManager

log = logging.getLogger("ws_unicorn")
_ubwa = None

def ensure_ws_started():
    global _ubwa
    if _ubwa:
        return _ubwa
    # Futuros USDT-M en Binance.com
    _ubwa = BinanceWebSocketApiManager(exchange="binance.com-futures")
    log.info("WS (unicorn) started")
    return _ubwa

def add_kline_socket(symbol: str, interval: str, callback):
    """
    Crea un stream kline y reenvía al callback en el formato:
    {"e":"kline","k":{...}}
    """
    ubwa = ensure_ws_started()
    chan = f"kline_{interval}"

    def _proc(msg: str):
        try:
            data = json.loads(msg)
            k = (data.get("data") or {}).get("k")
            if k:
                wrapped = {"e": "kline", "k": k}
                callback(wrapped)
        except Exception as e:
            log.warning(f"[{symbol}] WS cb error: {e}")

    # Unicorn acepta listas: canales, símbolos en minúsculas
    ubwa.create_stream([chan], [symbol.lower()], process_stream_data=_proc)
    log.info(f"WS kline (unicorn) added: {symbol} {interval}")
    return True

import logging
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient

log = logging.getLogger("ws_connector")

_ws = None

def ensure_ws_started():
    global _ws
    if _ws:
        return _ws
    _ws = UMFuturesWebsocketClient()
    _ws.start()
    log.info("WS (connector) started")
    return _ws

def add_kline_socket(symbol: str, interval: str, callback):
    """
    Abre un stream de klines para UM Futures y reenvía al callback
    con el mismo formato que esperaba tu código: {"e":"kline","k":{...}}
    """
    ws = ensure_ws_started()

    def _cb(msg):
        try:
            data = msg.get("data") or {}
            k = data.get("k") or {}
            # Normalizamos al formato legacy de python-binance
            wrapped = {"e": "kline", "k": k}
            callback(wrapped)
        except Exception as e:
            log.warning(f"[{symbol}] WS cb error: {e}")

    # Nota: binance-connector usa el símbolo en minúsculas
    ws.kline(symbol=symbol.lower(), interval=interval, id=f"k-{symbol}-{interval}", callback=_cb)
    log.info(f"WS kline (connector) added: {symbol} {interval}")
    return True

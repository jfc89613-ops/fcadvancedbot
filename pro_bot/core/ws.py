import logging
from binance import ThreadedWebsocketManager
from ..config import settings
from .client import get_client

log = logging.getLogger("ws")

# Singleton del WS manager
_TWM = None

def ensure_ws_started():
    """
    Inicia (si no existe) y devuelve el ThreadedWebsocketManager global.
    """
    global _TWM
    if _TWM is not None:
        return _TWM

    # Inicializa credenciales/cliente (sincroniza hora, modos, etc.)
    cli = get_client().client

    twm = ThreadedWebsocketManager(
        api_key=settings.api_key,
        api_secret=settings.api_secret,
        testnet=settings.testnet
    )
    twm.start()
    log.info("WS manager started")
    _TWM = twm
    return _TWM

def _start_kline_socket(twm: ThreadedWebsocketManager, symbol: str, interval: str, callback):
    """
    Compatibilidad con distintos nombres de método según versión de python-binance.
    """
    for name in ("start_kline_futures_socket", "start_kline_future_socket", "start_kline_socket"):
        if hasattr(twm, name):
            getattr(twm, name)(callback=callback, symbol=symbol, interval=interval)
            log.info(f"WS kline socket added: {symbol} {interval}")
            return
    raise RuntimeError("No se encontró método de kline compatible en ThreadedWebsocketManager")

def add_kline_socket(symbol: str, interval: str, callback):
    """
    Registra un nuevo socket de klines en el TWM global (no bloquea).
    """
    twm = ensure_ws_started()
    _start_kline_socket(twm, symbol, interval, callback)

def start_streams(symbol: str, on_kline, on_user=None):
    """
    Mantiene compatibilidad con llamadas antiguas:
    - Abre kline para `symbol`
    - Opcionalmente abre user-data stream
    Devuelve el TWM global.
    """
    twm = ensure_ws_started()
    _start_kline_socket(twm, symbol, settings.kline_interval, on_kline)

    if on_user is not None:
        try:
            # listen key para user stream de futuros
            cli = get_client().client
            listen_key = cli.futures_stream_get_listen_key()["listenKey"]
            for method_name in ("start_futures_user_socket", "start_user_socket"):
                if hasattr(twm, method_name):
                    getattr(twm, method_name)(callback=on_user, listen_key=listen_key)
                    break
        except Exception as e:
            log.warning(f"No se pudo iniciar user stream: {e}")

    return twm

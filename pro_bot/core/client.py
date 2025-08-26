import time, logging
from binance.client import Client
from ..config import settings
log = logging.getLogger("client")
FUTURES_MAIN_URL = "https://fapi.binance.com/fapi"
FUTURES_TESTNET_URL = "https://testnet.binancefuture.com/fapi"

class FuturesClient:
    def __init__(self):
        self.client = Client(settings.api_key, settings.api_secret, testnet=settings.testnet)
        # Forzar URL de Futuros correcta
        self.client.FUTURES_URL = FUTURES_TESTNET_URL if settings.testnet else FUTURES_MAIN_URL

        # Sincronía de tiempo
        self.sync_time()

        # Aumentar pool HTTP para muchas peticiones concurrentes (evitar "Connection pool is full")
        try:
            self.client.REQUESTS_PARAMS = {"timeout": 10, "pool_maxsize": 200}
            sess = self.client.session
            from requests.adapters import HTTPAdapter
            a = HTTPAdapter(pool_connections=200, pool_maxsize=200)
            sess.mount("https://", a); sess.mount("http://", a)
        except Exception as _e:
            log.info(f"pool tuning: {_e}")

        # Configuración de cuenta (margin/leverage/position mode) para el símbolo principal
        self._configure_account()

    def sync_time(self, retries: int = 3):
        for a in range(1, retries+1):
            try:
                server_time = self.client.get_server_time()["serverTime"]
                local = int(time.time()*1000)
                self.client._timestamp_offset = server_time - local
                log.info(f"Time sync OK. Offset: {self.client._timestamp_offset} ms"); return
            except Exception as e:
                log.warning(f"Time sync failed (attempt {a}): {e}"); time.sleep(1*a)
        raise RuntimeError("No se pudo sincronizar hora con Binance.")
    def _configure_account(self):
        sym = settings.symbol
        try: self.client.futures_change_margin_type(symbol=sym, marginType=settings.margin_type)
        except Exception as e: log.info(f"margin_type: {e}")
        try: self.client.futures_change_leverage(symbol=sym, leverage=settings.leverage)
        except Exception as e: log.info(f"leverage: {e}")
        try:
            dual = "true" if settings.position_mode.upper() == "HEDGE" else "false"
            self.client.futures_change_position_mode(dualSidePosition=dual)
        except Exception as e: log.info(f"position_mode: {e}")
    def exchange_info(self): return self.client.futures_exchange_info()
    def account(self): return self.client.futures_account()
    def ticker_price(self, symbol: str): return self.client.futures_symbol_ticker(symbol=symbol)
client_singleton=None
def get_client():
    global client_singleton
    if client_singleton is None: client_singleton = FuturesClient()
    return client_singleton

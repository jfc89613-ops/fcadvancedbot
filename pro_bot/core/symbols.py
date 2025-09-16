
import logging
from typing import List, Dict, Any
from .client import get_client

log = logging.getLogger("symbols")

def _fapi_ticker_24hr_raw():
    cli = get_client().client
    # Try official method first; fallback to raw endpoint
    for name in ("futures_ticker_24hr", "futures_ticker"):
        if hasattr(cli, name):
            try:
                data = getattr(cli, name)()
                if isinstance(data, list) and data:
                    return data
            except Exception as e:
                log.info(f"{name} failed: {e}")
    # Fallback to low-level request
    try:
        return cli._request_futures_api('get', 'ticker/24hr')
    except Exception as e:
        log.error(f"Fallback 24hr request failed: {e}")
        return []

def _usdt_perpetual_symbols() -> Dict[str, Any]:
    info = get_client().client.futures_exchange_info()
    out = {}
    for sym in info.get("symbols", []):
        try:
            if sym.get("contractType") == "PERPETUAL" and sym.get("quoteAsset") == "USDT" and sym.get("status") == "TRADING":
                out[sym["symbol"]] = sym
        except Exception:
            continue
    return out

def top_usdtm_symbols_by_quote_volume(n: int = 20) -> List[str]:
    perps = _usdt_perpetual_symbols()
    raw = _fapi_ticker_24hr_raw()
    rows = []
    for r in raw:
        sym = r.get("symbol")
        if sym in perps:
            try:
                qv = float(r.get("quoteVolume", 0.0))
            except Exception:
                qv = 0.0
            rows.append((sym, qv))
    rows.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in rows[:n]]

# --- añadido: forzar símbolos vía variable de entorno SYMBOLS ---
import os

def forced_symbols_from_env():
    """
    Lee SYMBOLS de .env (coma-separado), normaliza a MAYÚSCULAS,
    y filtra a los que sean USDT-M perpetuos si se puede consultar el exchange info.
    Si no hay nada en SYMBOLS, devuelve [].
    """
    raw = os.getenv("SYMBOLS", "").strip()
    if not raw:
        return []
    syms = [x.strip().upper() for x in raw.split(",") if x.strip()]
    # Intenta filtrar a la lista de PERPs válidos
    try:
        perps = set(_usdt_perpetual_symbols())
        syms = [x for x in syms if x in perps]
    except Exception:
        # si falla exchange_info en el arranque, dejar la lista tal cual
        pass
    # Dedup conservando orden
    seen = set()
    out = []
    for x in syms:
        if x not in seen:
            out.append(x); seen.add(x)
    return out


DEFAULT_TRADING_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "LTCUSDT", "TRXUSDT", "LINKUSDT",
    "AVAXUSDT", "MATICUSDT", "DOTUSDT", "OPUSDT", "ARBUSDT",
    "SUIUSDT", "1000PEPEUSDT", "APTUSDT", "ATOMUSDT",
]


def get_trading_symbols(client=None, limit: int = 19) -> List[str]:
    """Obtiene la lista de símbolos a operar respetando configuraciones y fallback."""
    forced = forced_symbols_from_env()
    if forced:
        log.info(f"Usando {len(forced)} símbolos definidos en SYMBOLS")
        return forced[:limit]

    try:
        top_symbols = top_usdtm_symbols_by_quote_volume(limit)
        if top_symbols:
            log.info(f"Seleccionados {len(top_symbols)} símbolos por volumen 24h")
            return top_symbols
    except Exception as exc:
        log.warning(f"No se pudo obtener símbolos por volumen: {exc}")

    log.warning("Usando lista de símbolos por defecto")
    return DEFAULT_TRADING_SYMBOLS[:limit]

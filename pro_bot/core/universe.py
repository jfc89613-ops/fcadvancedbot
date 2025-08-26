
import logging
from typing import List
from .client import get_client

log = logging.getLogger("universe")

def fetch_top_usdt_perpetuals_by_volume(max_symbols: int = 320) -> List[str]:
    cli = get_client().client
    info = cli.futures_exchange_info()
    usdt_perp = set()
    for s in info["symbols"]:
        try:
            if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                usdt_perp.add(s["symbol"])
        except Exception:
            continue

    tickers = cli.futures_ticker()
    scored = []
    for t in tickers:
        sym = t.get("symbol")
        if sym in usdt_perp:
            try:
                qv = float(t.get("quoteVolume", 0.0))
            except Exception:
                qv = 0.0
            scored.append((sym, qv))
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [s for s,_ in scored[:max_symbols]]
    log.info(f"Universe selected ({len(top)}): {', '.join(top[:15])} ...")
    return top

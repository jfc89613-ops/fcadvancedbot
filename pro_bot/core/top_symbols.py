import logging
from typing import List, Optional, Set
from .client import get_client
log = logging.getLogger("symbols")

def usdt_perpetual_set() -> Set[str]:
    info = get_client().exchange_info()
    perps = set()
    for s in info["symbols"]:
        if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
            perps.add(s["symbol"])
    return perps

def top_usdtm_by_quote_volume(n: int = 20, allow: Optional[Set[str]] = None) -> List[str]:
    cli = get_client().client
    stats = cli.futures_ticker()  # 24hr stats list
    allow = allow or usdt_perpetual_set()
    rows = []
    for it in stats:
        sym = it.get("symbol")
        if sym not in allow: continue
        try:
            qv = float(it.get("quoteVolume", 0.0))
        except Exception:
            qv = 0.0
        rows.append((qv, sym))
    rows.sort(reverse=True)
    return [s for _, s in rows[:n]]

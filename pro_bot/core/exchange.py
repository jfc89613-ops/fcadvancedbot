import math
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, getcontext
from .client import get_client

getcontext().prec = 28

def _decimals_from_step(step: str) -> int:
    # "0.01000000" -> 2 ; "1.00000000" -> 0
    s = str(step)
    if "." not in s:
        return 0
    return len(s.split(".")[1].rstrip("0"))

class SymbolFilters:
    def __init__(self, symbol: str):
        info = get_client().exchange_info()
        sym = next(s for s in info["symbols"] if s["symbol"] == symbol)
        self.symbol = symbol
        self.price_step = None
        self.qty_step = None
        self.min_notional = None
        self.max_leverage = int(sym.get("leverageFilter", {}).get("maxLeverage", 125)) if "leverageFilter" in sym else 125

        for f in sym["filters"]:
            if f["filterType"] == "PRICE_FILTER":
                self.price_step = Decimal(f["tickSize"])
            elif f["filterType"] in ("LOT_SIZE", "MARKET_LOT_SIZE"):
                self.qty_step = Decimal(f["stepSize"])
                self.min_qty = Decimal(f.get("minQty", "0"))
            elif f["filterType"] == "MIN_NOTIONAL":
                # En Futuros suele venir "notional"
                self.min_notional = Decimal(str(f.get("notional", "0")))

        if self.price_step is None:
            self.price_step = Decimal("0.01")
        if self.qty_step is None:
            self.qty_step = Decimal("0.001")
        if self.min_notional is None:
            self.min_notional = Decimal("0")

        self.price_decimals = _decimals_from_step(str(self.price_step))
        self.qty_decimals = _decimals_from_step(str(self.qty_step))

    # ---- helpers de redondeo/format ----
    def _floor_step(self, x: Decimal, step: Decimal) -> Decimal:
        return (x / step).to_integral_value(rounding=ROUND_FLOOR) * step

    def _ceil_step(self, x: Decimal, step: Decimal) -> Decimal:
        return (x / step).to_integral_value(rounding=ROUND_CEILING) * step

    def round_price_down(self, price: float) -> Decimal:
        return self._floor_step(Decimal(str(price)), self.price_step)

    def round_price_up(self, price: float) -> Decimal:
        return self._ceil_step(Decimal(str(price)), self.price_step)

    def round_qty_down(self, qty: float) -> Decimal:
        return self._floor_step(Decimal(str(qty)), self.qty_step)

    def ensure_min_qty(self, qty: Decimal) -> Decimal:
        if hasattr(self, "min_qty") and qty < self.min_qty:
            return self._ceil_step(self.min_qty, self.qty_step)
        return qty

    def fmt_price(self, px: Decimal) -> str:
        return f"{px:.{self.price_decimals}f}"

    def fmt_qty(self, q: Decimal) -> str:
        return f"{q:.{self.qty_decimals}f}"

    # ---- notional / leverage ----
    def ensure_min_notional(self, price: Decimal, qty: Decimal) -> Decimal:
        notional = price * qty
        if self.min_notional > 0 and notional < self.min_notional:
            needed = self.min_notional / price
            qty = self._ceil_step(needed, self.qty_step)
        return qty

_filters_cache = {}

def get_filters(symbol: str) -> SymbolFilters:
    f = _filters_cache.get(symbol)
    if f is None:
        f = SymbolFilters(symbol)
        _filters_cache[symbol] = f
    return f

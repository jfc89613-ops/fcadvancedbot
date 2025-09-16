import asyncio
import logging
import threading
import time
from decimal import Decimal
from typing import Dict, List, Optional
from ..config import settings
from .client import get_client
from .exchange import get_filters
from .risk import decide_qty_for_margin

log = logging.getLogger("exec")

SIDE = {"BUY":"BUY","SELL":"SELL"}

# --- Nueva función: obtener todas las posiciones abiertas usando la API de Binance ---
from dataclasses import dataclass

@dataclass
class PositionInfo:
    symbol: str
    positionAmt: float
    entryPrice: float
    markPrice: float
    unrealizedProfit: float
    leverage: int
    liquidationPrice: float
    side: str

_cache_lock = threading.Lock()
_open_positions_cache: Dict[str, "PositionInfo"] = {}
_pending_limit_orders_cache: set[str] = set()
_last_cache_refresh: float = 0.0

def cancel_pending_limit_orders():
    """Cancela todas las órdenes LIMIT pendientes (de entrada)"""
    client = get_client().client
    try:
        # Obtener todas las órdenes abiertas
        open_orders = client.futures_get_open_orders()
        cancelled = []
        
        for order in open_orders:
            if order.get("type") == "LIMIT":
                symbol = order.get("symbol")
                order_id = order.get("orderId")
                try:
                    client.futures_cancel_order(symbol=symbol, orderId=order_id)
                    cancelled.append(symbol)
                    log.info(f"✅ Cancelled LIMIT order for {symbol} (ID: {order_id})")
                except Exception as e:
                    log.error(f"❌ Failed to cancel LIMIT order for {symbol}: {e}")
        
        if cancelled:
            log.info(f"🧹 Cancelled {len(cancelled)} LIMIT orders: {cancelled}")
        else:
            log.info("✅ No LIMIT orders to cancel")
            
    except Exception as e:
        log.error(f"Error getting open orders: {e}")

def set_all_symbols_to_crossed_margin(extra_symbols: Optional[List[str]] = None):
    """Configura todos los símbolos activos para usar margen cruzado"""
    client = get_client()

    # Obtener símbolos con posiciones abiertas
    active_symbols = get_all_open_positions()

    # Lista de símbolos comunes para configurar
    common_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'LTCUSDT', 'XRPUSDT',
                     'ONTUSDT', '1000PEPEUSDT', 'WIFUSDT', 'SUIUSDT', 'HYPEUSDT',
                     'ENAUSDT', 'LINKUSDT', 'AVAXUSDT', 'PROMPTUSDT', 'FARTCOINUSDT',
                     'BIOUSDT', 'BNBUSDT']

    merged = set(active_symbols + common_symbols)
    if extra_symbols:
        merged.update(extra_symbols)

    all_symbols = list(merged)

    log.info(f"🔧 Configurando {len(all_symbols)} símbolos para margen CROSSED...")
    
    success_count = 0
    for symbol in all_symbols:
        try:
            client.client.futures_change_margin_type(symbol=symbol, marginType="CROSSED")
            log.info(f"✅ {symbol}: Margen cambiado a CROSSED")
            success_count += 1
        except Exception as e:
            # Es normal que algunos ya estén en CROSSED
            if "No need to change margin type" in str(e) or "marginType is invalid" in str(e):
                log.info(f"ℹ️ {symbol}: Ya está en CROSSED")
                success_count += 1
            else:
                log.warning(f"⚠️ {symbol}: Error cambiando margen: {e}")
    
    log.info(f"🎯 Configuración completada: {success_count}/{len(all_symbols)} símbolos en CROSSED")

def get_all_open_positions_info():
    """Obtiene todas las posiciones abiertas y su información usando la API de Binance."""
    client = get_client().client
    positions = client.futures_position_information()
    open_positions = []
    for pos in positions:
        amt = float(pos.get("positionAmt", "0"))
        if amt != 0:
            side = "LONG" if amt > 0 else "SHORT"
            open_positions.append(PositionInfo(
                symbol=pos.get("symbol"),
                positionAmt=amt,
                entryPrice=float(pos.get("entryPrice", "0")),
                markPrice=float(pos.get("markPrice", "0")),
                unrealizedProfit=float(pos.get("unRealizedProfit", "0")),
                leverage=int(pos.get("leverage", "1")),
                liquidationPrice=float(pos.get("liquidationPrice", "0")),
                side=side
            ))
    return open_positions

def last_price(symbol: str) -> float:
    p = get_client().ticker_price(symbol)
    return float(p["price"])

def market_order(side: str, symbol: str, qty_str: str, reduce_only: bool = False):
    params = dict(symbol=symbol, side=side, type="MARKET", quantity=qty_str, recvWindow=settings.recv_window)
    if reduce_only:
        params["reduceOnly"] = "true"
    return get_client().client.futures_create_order(**params)

def limit_order(side: str, symbol: str, qty_str: str, price_str: str, tif: str="GTC", reduce_only: bool=False):
    params = dict(symbol=symbol, side=side, type="LIMIT", quantity=qty_str, price=price_str, timeInForce=tif, recvWindow=settings.recv_window)
    if reduce_only:
        params["reduceOnly"] = "true"
    return get_client().client.futures_create_order(**params)

def place_tp_sl(symbol: str, side_open: str, tp_price: Optional[Decimal], sl_price: Optional[Decimal]):
    """ Coloca TP/SL en MARK_PRICE con pequeño buffer para no disparar inmediato """
    opposite = "SELL" if side_open == "BUY" else "BUY"
    cli = get_client().client
    f = get_filters(symbol)

    def _safe(px: Optional[Decimal], above: bool) -> Optional[str]:
        if px is None: return None
        # buffer = 2 ticks en la dirección correcta
        buf = f.price_step * Decimal("2")
        px = f.round_price_up(float(px)) if above else f.round_price_down(float(px))
        px = px + buf if above else px - buf
        return f.fmt_price(px)

    tp_str = _safe(tp_price, above=True) if tp_price is not None else None
    sl_str = _safe(sl_price, above=False) if sl_price is not None else None

    if tp_str:
        try:
            cli.futures_create_order(
                symbol=symbol, side=opposite, type="TAKE_PROFIT_MARKET",
                stopPrice=tp_str, closePosition="true",
                workingType="MARK_PRICE", recvWindow=settings.recv_window
            )
        except Exception as e:
            log.warning(f"TP error: {e}")

    if sl_str:
        try:
            cli.futures_create_order(
                symbol=symbol, side=opposite, type="STOP_MARKET",
                stopPrice=sl_str, closePosition="true",
                workingType="MARK_PRICE", recvWindow=settings.recv_window
            )
        except Exception as e:
            log.warning(f"SL error: {e}")

# --- control de posiciones abiertas (consulta directa API) ---

def has_open_position(symbol: str) -> bool:
    """Verificar si hay posición abierta consultando Binance directamente"""
    try:
        position_info = get_client().client.futures_position_information(symbol=symbol)
        if position_info:
            amt = Decimal(position_info[0].get("positionAmt", "0"))
            return amt != 0
    except Exception as e:
        log.warning(f"Error checking position for {symbol}: {e}")
        return False
    
    return False

def get_position_details(symbol: str):
    """Obtener detalles completos de la posición desde Binance"""
    try:
        position_info = get_client().client.futures_position_information(symbol=symbol)
        if position_info:
            pos = position_info[0]
            amt = Decimal(pos.get("positionAmt", "0"))
            if amt != 0:
                return {
                    "symbol": symbol,
                    "positionAmt": amt,
                    "entryPrice": Decimal(pos.get("entryPrice", "0")),
                    "unrealizedPnl": Decimal(pos.get("unRealizedPnl", "0")),
                    "percentage": Decimal(pos.get("percentage", "0")),
                    "side": "LONG" if amt > 0 else "SHORT"
                }
    except Exception as e:
        log.error(f"Error getting position details for {symbol}: {e}")
    return None

def get_all_open_positions():
    """Obtener todas las posiciones abiertas desde Binance API"""
    try:
        with _cache_lock:
            if _open_positions_cache and (time.time() - _last_cache_refresh) < 60:
                return sorted(_open_positions_cache.keys())

        infos = get_client().client.futures_position_information()
        open_symbols = []

        for p in infos:
            sym = p.get("symbol")
            amt = Decimal(p.get("positionAmt", "0"))
            if amt != 0:
                open_symbols.append(sym)

        return sorted(open_symbols)
    except Exception as e:
        log.warning(f"get_all_open_positions error: {e}")
        return []

def get_pending_limit_orders():
    """Obtener órdenes LIMIT pendientes desde Binance API"""
    try:
        orders = get_client().client.futures_get_open_orders()
        pending_symbols = []
        
        for order in orders:
            if order.get("type") == "LIMIT" and order.get("status") == "NEW":
                symbol = order.get("symbol")
                if symbol not in pending_symbols:
                    pending_symbols.append(symbol)
        
        return sorted(pending_symbols)
    except Exception as e:
        log.warning(f"get_pending_limit_orders error: {e}")
        return []

def _refresh_caches_once(open_positions: Optional[List[PositionInfo]] = None,
                         pending_limits: Optional[List[str]] = None) -> None:
    """Actualizar caches internos desde la API"""
    global _open_positions_cache, _pending_limit_orders_cache, _last_cache_refresh

    positions = open_positions if open_positions is not None else get_all_open_positions_info()
    pending = pending_limits if pending_limits is not None else get_pending_limit_orders()

    with _cache_lock:
        _open_positions_cache = {p.symbol: p for p in positions}
        _pending_limit_orders_cache = set(pending)
        _last_cache_refresh = time.time()

    log.debug(
        "Cache actualizado: %d posiciones abiertas, %d órdenes LIMIT pendientes",
        len(_open_positions_cache),
        len(_pending_limit_orders_cache),
    )

def refresh_open_positions_cache(poll_interval: int = 30):
    """Actualiza el cache de posiciones. En hilos daemon corre en bucle."""

    def _update():
        try:
            _refresh_caches_once()
        except Exception as e:
            log.warning(f"refresh_open_positions_cache error: {e}")

    if threading.current_thread().daemon:
        while True:
            _update()
            time.sleep(poll_interval)
    else:
        _update()

def get_cached_open_positions() -> List[str]:
    """Devuelve símbolos del cache actual."""
    with _cache_lock:
        return sorted(_open_positions_cache.keys())

def get_cached_pending_orders() -> List[str]:
    with _cache_lock:
        return sorted(_pending_limit_orders_cache)

def get_active_trading_symbols():
    """Obtener símbolos con posiciones abiertas (ya no incluye órdenes LIMIT)"""
    open_positions = get_all_open_positions()
    # Ya no incluimos pending_orders ya que usamos solo MARKET orders
    return sorted(open_positions)

def open_positions_count() -> int:
    """Retorna el número de posiciones abiertas consultando API directamente"""
    return len(get_all_open_positions())

def active_trading_count() -> int:
    """Retorna el número total de posiciones abiertas (ya no incluye órdenes LIMIT)"""
    return len(get_all_open_positions())

def has_pending_limit_order(symbol: str) -> bool:
    """Verificar si hay una orden LIMIT pendiente para un símbolo"""
    try:
        with _cache_lock:
            if _pending_limit_orders_cache and (time.time() - _last_cache_refresh) < 60:
                return symbol in _pending_limit_orders_cache

        orders = get_client().client.futures_get_open_orders(symbol=symbol)
        for order in orders:
            if order.get("type") == "LIMIT" and order.get("status") == "NEW":
                return True
        return False
    except Exception as e:
        log.warning(f"Error checking pending orders for {symbol}: {e}")
        return False

def _can_open_new_position(symbol: str) -> bool:
    """Verifica si se puede abrir una nueva posición para el símbolo"""
    # No abrir si ya hay posición en este símbolo
    if has_open_position(symbol):
        return False
    
    # No abrir si ya hay una orden LIMIT pendiente para este símbolo
    if has_pending_limit_order(symbol):
        log.info(f"[{symbol}] Ya hay orden LIMIT pendiente, no se abre nueva posición")
        return False
    
    # Verificar límite máximo de posiciones abiertas + órdenes pendientes
    max_positions = 5  # Límite fijo de 5 posiciones/órdenes activas
    current_active = active_trading_count()
    open_positions = get_all_open_positions()
    pending_orders = get_pending_limit_orders()
    
    if current_active >= max_positions:
        log.info(f"Límite alcanzado: {current_active}/{max_positions} posiciones/órdenes activas")
        log.info(f"  Posiciones abiertas ({len(open_positions)}): {open_positions}")
        log.info(f"  Órdenes LIMIT pendientes ({len(pending_orders)}): {pending_orders}")
        return False
    
    return True

# --- entrada principal ---
def enter_position(direction: str, use_limit: bool = True, limit_offset_bps: int = 3,
                   tp_rr: float = 1.5, sl_rr: float = 1.0, symbol: Optional[str] = None) -> dict:
    """Abre una nueva posición y devuelve detalles de la orden."""
    sym = symbol or settings.symbol
    result: Dict[str, object] = {
        "success": False,
        "symbol": sym,
        "direction": direction,
    }

    try:
        max_positions = int(getattr(settings, "max_open_positions", 5))
    except Exception:
        max_positions = 5

    current_positions = get_all_open_positions_info()
    current_active = len(current_positions)
    if current_active >= max_positions:
        msg = f"Límite de {max_positions} posiciones activas alcanzado. No se abre {sym}. Activas: {current_active}"
        log.info(msg)
        result["error"] = msg
        return result

    if has_open_position(sym):
        msg = f"[{sym}] ya hay posición abierta; se omite nueva entrada."
        log.info(msg)
        result["error"] = msg
        return result

    if has_pending_limit_order(sym):
        msg = f"[{sym}] orden LIMIT pendiente detectada; no se abre nueva posición"
        log.info(msg)
        result["error"] = msg
        return result

    try:
        px = Decimal(str(last_price(sym)))
    except Exception as exc:
        msg = f"[{sym}] error obteniendo precio: {exc}"
        log.error(msg)
        result["error"] = msg
        return result

    f = get_filters(sym)

    try:
        qty, lev = decide_qty_for_margin(sym, float(px))
    except Exception as exc:
        msg = f"[{sym}] error calculando cantidad: {exc}"
        log.error(msg)
        result["error"] = msg
        return result

    if qty <= 0:
        msg = f"[{sym}] Qty inválida para MIN_NOTIONAL: {f.min_notional}"
        log.error(msg)
        result["error"] = msg
        return result

    qty_str = f.fmt_qty(qty)

    if direction == "LONG":
        side_open = SIDE["BUY"]
        tp = px * (Decimal("1") + Decimal("0.03") * Decimal(str(tp_rr)))
        sl = px * (Decimal("1") - Decimal("0.02") * Decimal(str(sl_rr)))
    elif direction == "SHORT":
        side_open = SIDE["SELL"]
        tp = px * (Decimal("1") - Decimal("0.03") * Decimal(str(tp_rr)))
        sl = px * (Decimal("1") + Decimal("0.02") * Decimal(str(sl_rr)))
    else:
        msg = f"[{sym}] señal NEUTRAL; no se abre posición"
        log.info(msg)
        result["error"] = msg
        return result

    try:
        ord_resp = market_order(side_open, sym, qty_str)
    except Exception as exc:
        msg = f"[{sym}] error creando orden MARKET: {exc}"
        log.error(msg)
        result["error"] = msg
        return result

    order_id = ord_resp.get("orderId", "?")
    log.info(f"[{sym}] MARKET order placed: {order_id}")

    result.update({
        "order": ord_resp,
        "side": side_open,
        "qty": float(qty),
        "qty_str": qty_str,
        "leverage": lev,
        "tp_price": float(tp),
        "sl_price": float(sl),
    })

    place_tp_sl(sym, side_open, tp, sl)

    position_details = get_position_details(sym)
    if position_details:
        entry_price = float(position_details["entryPrice"])
        filled_qty = abs(float(position_details["positionAmt"]))
    else:
        entry_price = float(px)
        filled_qty = float(qty)

    result.update({
        "entry_price": entry_price,
        "filled_qty": filled_qty,
        "success": True,
    })

    # Refrescar caches tras la operación
    _refresh_caches_once()

    return result


# Funciones adicionales para SLTPManager
def enter_basic(symbol: str, direction: str) -> dict:
    """Función básica de entrada de posición para SLTPManager (solo MARKET)"""
    return enter_position(direction, use_limit=False, symbol=symbol)

def stop_market(symbol: str, side: str, stop_price: float, qty: Optional[str] = None, close_position: bool = False):
    """Crear orden stop market"""
    cli = get_client().client
    params = {
        "symbol": symbol,
        "side": side,
        "type": "STOP_MARKET",
        "stopPrice": str(stop_price),
        "recvWindow": settings.recv_window
    }
    
    if close_position:
        params["closePosition"] = "true"
    elif qty:
        params["quantity"] = qty
    else:
        # Si no se especifica qty y no es close_position, usar la posición actual
        params["closePosition"] = "true"
    
    try:
        return cli.futures_create_order(**params)
    except Exception as e:
        log.error(f"Error creating stop market order: {e}")
        return None

def take_profit_market(symbol: str, side: str, stop_price: float, qty: Optional[str] = None, close_position: bool = False):
    """Crear orden take profit market"""
    cli = get_client().client
    params = {
        "symbol": symbol,
        "side": side,
        "type": "TAKE_PROFIT_MARKET",
        "stopPrice": str(stop_price),
        "recvWindow": settings.recv_window
    }
    
    if close_position:
        params["closePosition"] = "true"
    elif qty:
        params["quantity"] = qty
        # CRÍTICO: NO usar closePosition cuando se especifica cantidad exacta
    else:
        # Solo si no se especifica qty NI close_position, usar close_position
        log.warning(f"take_profit_market: No qty specified and close_position=False, defaulting to closePosition=true")
        params["closePosition"] = "true"
    
    try:
        return cli.futures_create_order(**params)
    except Exception as e:
        log.error(f"Error creating take profit market order: {e}")
        return None


class TradingEngine:
    """Motor de ejecución asincrónico utilizado por el bot multitimeframe."""

    def __init__(self, client, cfg_path: str = "configs/ml.yaml"):
        self.client = client
        self.cfg_path = cfg_path
        self.symbols: List[str] = []
        self.initialized = False
        self._locks_guard = asyncio.Lock()
        self._symbol_locks: Dict[str, asyncio.Lock] = {}

    async def initialize(self, symbols: Optional[List[str]] = None) -> None:
        """Inicializa el motor configurando margen y refrescando caches."""
        if symbols is not None:
            self.symbols = list(symbols)

        await asyncio.to_thread(refresh_open_positions_cache)
        extra = self.symbols if self.symbols else None
        await asyncio.to_thread(set_all_symbols_to_crossed_margin, extra)
        await asyncio.to_thread(cancel_pending_limit_orders)
        self.initialized = True
        log.info("✅ TradingEngine ready (margen CROSSED verificado)")

    async def cleanup(self) -> None:
        """Limpieza al detener el motor."""
        await asyncio.to_thread(cancel_pending_limit_orders)
        await asyncio.to_thread(refresh_open_positions_cache)
        self._symbol_locks.clear()
        self.initialized = False

    async def _get_symbol_lock(self, symbol: str) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._symbol_locks.get(symbol)
            if lock is None:
                lock = asyncio.Lock()
                self._symbol_locks[symbol] = lock
            return lock

    async def get_position(self, symbol: str) -> Optional[dict]:
        details = await asyncio.to_thread(get_position_details, symbol)
        if not details:
            return None

        normalized = dict(details)
        for key in ("positionAmt", "entryPrice", "unrealizedPnl", "percentage"):
            if key in normalized and normalized[key] is not None:
                try:
                    normalized[key] = float(normalized[key])
                except Exception:
                    pass
        return normalized

    async def _enter(self, symbol: str, direction: str) -> dict:
        lock = await self._get_symbol_lock(symbol)
        async with lock:
            try:
                result = await asyncio.to_thread(
                    enter_position,
                    direction,
                    False,
                    3,
                    1.5,
                    1.0,
                    symbol,
                )
            except Exception as exc:
                log.error(f"[{symbol}] error ejecutando entrada {direction}: {exc}")
                return {
                    "success": False,
                    "symbol": symbol,
                    "direction": direction,
                    "error": str(exc),
                }

            if not result:
                return {
                    "success": False,
                    "symbol": symbol,
                    "direction": direction,
                    "error": "enter_position returned no data",
                }

            if not result.get("success"):
                log.warning(f"[{symbol}] no se pudo abrir posición {direction}: {result.get('error')}")
            else:
                log.info(f"[{symbol}] posición {direction} abierta correctamente")

            return result

    async def enter_long_position(self, symbol: str) -> dict:
        return await self._enter(symbol, "LONG")

    async def enter_short_position(self, symbol: str) -> dict:
        return await self._enter(symbol, "SHORT")

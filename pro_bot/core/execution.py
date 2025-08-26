import logging
from decimal import Decimal
from typing import Optional
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

def set_all_symbols_to_crossed_margin():
    """Configura todos los símbolos activos para usar margen cruzado"""
    client = get_client()
    
    # Obtener símbolos con posiciones abiertas
    active_symbols = get_all_open_positions()
    
    # Lista de símbolos comunes para configurar
    common_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'LTCUSDT', 'XRPUSDT', 
                     'ONTUSDT', '1000PEPEUSDT', 'WIFUSDT', 'SUIUSDT', 'HYPEUSDT',
                     'ENAUSDT', 'LINKUSDT', 'AVAXUSDT', 'PROMPTUSDT', 'FARTCOINUSDT',
                     'BIOUSDT', 'BNBUSDT']
    
    all_symbols = list(set(active_symbols + common_symbols))
    
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
                   tp_rr: float = 1.5, sl_rr: float = 1.0, symbol: Optional[str] = None):
    """
    Abre una nueva posición. No modifica posiciones existentes.
    """
    sym = symbol or settings.symbol

    # --- Límite de posiciones activas (solo abiertas) ---
    MAX_ACTIVE_POSITIONS = 5
    current_active = len(get_all_open_positions_info())  # Solo posiciones abiertas
    if current_active >= MAX_ACTIVE_POSITIONS:
        log.info(f"Límite de {MAX_ACTIVE_POSITIONS} posiciones activas alcanzado. No se abre {sym}. Activas: {current_active}")
        return

    # --- Evitar modificar una posición existente ---
    # La lógica actual no modifica la cantidad de una posición ya abierta.
    # Simplemente abre una nueva si no existe para este símbolo.
    if has_open_position(sym):
        log.info(f"[{sym}] ya hay posición abierta; se omite nueva entrada.")
        return

    px = Decimal(str(last_price(sym)))
    f = get_filters(sym)

    # qty usando nuevo cálculo: MIN_NOTIONAL / ENTRY_PRICE
    qty, lev = decide_qty_for_margin(sym, float(px))
    if qty <= 0:
        raise ValueError(f"[{sym}] Qty inválida para MIN_NOTIONAL: {f.min_notional}")

    qty_str = f.fmt_qty(qty)

    # precios y orden market
    if direction == "LONG":
        side_open = SIDE["BUY"]
        tp = px * (Decimal("1") + Decimal("0.03") * Decimal(str(tp_rr)))
        sl = px * (Decimal("1") - Decimal("0.02") * Decimal(str(sl_rr)))
    elif direction == "SHORT":
        side_open = SIDE["SELL"]
        tp = px * (Decimal("1") - Decimal("0.03") * Decimal(str(tp_rr)))
        sl = px * (Decimal("1") + Decimal("0.02") * Decimal(str(sl_rr)))
    else:
        log.info(f"[{sym}] NEUTRAL; no se abre posición.")
        return

    # enviar orden MARKET
    ord_resp = market_order(side_open, sym, qty_str)
    log.info(f"[{sym}] MARKET order placed: {ord_resp.get('orderId','?')}")

    # TP/SL
    place_tp_sl(sym, side_open, tp, sl)


# Funciones adicionales para SLTPManager
def enter_basic(symbol: str, direction: str):
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

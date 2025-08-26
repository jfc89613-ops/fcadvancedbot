from decimal import Decimal
import logging
from ..config import settings
from .exchange import get_filters
from .client import get_client

log = logging.getLogger("risk")

def set_leverage_if_needed(symbol: str, target_leverage: int):
    cli = get_client().client
    try:
        cli.futures_change_leverage(symbol=symbol, leverage=target_leverage)
        log.info(f"[{symbol}] leverage set to {target_leverage}")
    except Exception as e:
        log.warning(f"[{symbol}] leverage set error: {e}")

def decide_qty_for_margin(symbol: str, price_f: float, prefer_max_margin_usdt: float = None) -> tuple[Decimal,int]:
    """
    Nuevo cálculo simplificado de qty:
      1. qty_base = 2 * min_qty (del filtro LOT_SIZE)
      2. Ajustar leverage para cumplir MIN_NOTIONAL
      3. qty_final = MIN_NOTIONAL / ENTRY_PRICE
    Retorna (qty_decimal, leverage_usado). qty=0 si no es viable.
    """
    f = get_filters(symbol)
    price = Decimal(str(price_f))
    
    # 1. Cantidad base: 2 * min_qty (filtro correcto de Binance)
    min_qty = f.min_qty  # Esto viene del filtro LOT_SIZE/MARKET_LOT_SIZE
    qty_base = min_qty * Decimal("2")
    
    # 2. Calcular notional con qty_base
    notional_base = qty_base * price
    
    # 3. Usar MIN_NOTIONAL como referencia con buffer del 1%
    min_notional_required = f.min_notional * Decimal("1.01")  # +1% buffer para evitar errores
    
    # 4. qty_final siempre será (MIN_NOTIONAL * 1.01) / ENTRY_PRICE
    qty_final = min_notional_required / price
    qty_final = f.round_qty_down(float(qty_final))
    
    # 5. Asegurar que cumple con mínimos del exchange
    qty_final = max(qty_final, min_qty)
    qty_final = f.ensure_min_qty(qty_final)
    
    # 6. Verificación final: asegurar que el notional final sea >= MIN_NOTIONAL * 1.01
    final_notional = qty_final * price
    if final_notional < min_notional_required:
        # Ajustar qty hacia arriba para garantizar el notional mínimo
        adjusted_qty = min_notional_required / price
        qty_final = f.round_qty_up(float(adjusted_qty))  # Redondear hacia ARRIBA
        final_notional = qty_final * price
        log.info(f"[{symbol}] 🔧 Adjusted qty: {qty_final} to meet notional requirement: {final_notional:.2f} >= {min_notional_required:.2f}")
    
    # 7. Calcular leverage necesario para esta qty
    final_notional = qty_final * price
    
    # Leverage inicial configurado
    base_leverage = int(getattr(settings, "leverage", 5))
    max_leverage = int(f.max_leverage)
    
    # El leverage no necesita ser ajustado, usamos el configurado
    # ya que qty se calcula en base a MIN_NOTIONAL
    leverage_used = min(base_leverage, max_leverage)
    
    # 8. Verificar que el resultado es válido
    if qty_final <= 0:
        log.error(f"[{symbol}] ❌ Invalid qty_final: {qty_final}")
        return Decimal("0"), leverage_used
    
    # 9. Configurar leverage si es necesario
    set_leverage_if_needed(symbol, leverage_used)
    
    # Log del resultado
    margin_used = final_notional / leverage_used
    min_notional_original = f.min_notional
    log.info(f"[{symbol}] 📊 qty: {qty_final} | notional: {final_notional:.2f} | leverage: {leverage_used} | margin: {margin_used:.3f} USD")
    log.info(f"[{symbol}] 🔧 min_qty: {min_qty} | min_notional: {min_notional_original:.2f} (+1% buffer → {min_notional_required:.2f}) | price: {price:.4f}")
    
    return qty_final, leverage_used



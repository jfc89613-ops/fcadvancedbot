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
    Calcula qty usando exactamente 0.5 USD de margen por posición (con fallback a 1 USD):
      - Margen fijo: 0.5 USDT por posición (fallback: 1 USDT)
      - Ajusta apalancamiento automáticamente para cumplir minNotional
      - Calcula qty = (margen * leverage) / precio
    Retorna (qty_decimal, leverage_usado). qty=0 si no es viable.
    """
    f = get_filters(symbol)
    price = f.round_price_down(price_f)  # price alineado a tick

    # Margen preferido: usar parámetro o default de settings (0.5 USD)
    preferred_margin = Decimal(str(prefer_max_margin_usdt or settings.max_margin_usdt))
    fallback_margin = Decimal("1.0")  # Fallback: 1 USDT
    
    # Intentar primero con el margen preferido (0.5 USD)
    result = _try_calculate_position(symbol, price, preferred_margin, f)
    if result[0] > 0:  # Si fue exitoso
        return result
    
    # Si falló con 0.5 USD, intentar con fallback de 1 USD
    log.warning(f"[{symbol}] ⚠️ Failed with {preferred_margin} USD margin, trying fallback {fallback_margin} USD")
    result = _try_calculate_position(symbol, price, fallback_margin, f)
    if result[0] > 0:  # Si fue exitoso con fallback
        log.info(f"[{symbol}] ✅ Fallback successful with {fallback_margin} USD margin")
        return result
    
    # Si ambos fallaron
    log.error(f"[{symbol}] ❌ Failed with both {preferred_margin} USD and {fallback_margin} USD margins")
    return Decimal("0"), int(getattr(settings, "leverage", 5))

def _try_calculate_position(symbol: str, price: Decimal, target_margin: Decimal, f) -> tuple[Decimal, int]:
    """Función auxiliar para intentar calcular posición con un margen específico"""
    
    # Leverage actual (comenzamos con el configurado)
    curr_lev = int(getattr(settings, "leverage", 5))
    max_lev = int(f.max_leverage)
    min_lev = 1

    # Calcular el mínimo notional requerido
    min_notional_required = max(f.min_notional, price * f.qty_step)
    
    # Calcular el leverage mínimo necesario para cubrir el minNotional con el margen objetivo
    min_leverage_needed = int((min_notional_required / target_margin).to_integral_value(rounding="ROUND_CEILING"))
    
    # Asegurar que el leverage esté en el rango válido
    optimal_leverage = max(min_leverage_needed, min_lev)
    optimal_leverage = min(optimal_leverage, max_lev)
    
    # Si el leverage óptimo es diferente al actual, actualizarlo
    if optimal_leverage != curr_lev:
        log.info(f"[{symbol}] Adjusting leverage from {curr_lev} to {optimal_leverage} for {target_margin} USD margin (minNotional: {min_notional_required:.2f})")
        set_leverage_if_needed(symbol, optimal_leverage)
        curr_lev = optimal_leverage
    
    # Verificar si es posible con el leverage máximo
    max_notional_possible = target_margin * curr_lev
    if min_notional_required > max_notional_possible:
        log.warning(f"[{symbol}] Imposible cumplir minNotional {min_notional_required:.2f} con margen {target_margin} y leverage máximo {curr_lev}")
        return Decimal("0"), curr_lev
    
    # Calcular cantidad usando exactamente el margen objetivo
    # qty = (margen * leverage) / precio
    raw_qty = (target_margin * curr_lev) / price
    qty = f.round_qty_down(float(raw_qty))
    
    # Asegurar que cumple con los mínimos del símbolo
    qty = f.ensure_min_qty(qty)
    qty = f.ensure_min_notional(price, qty)
    
    # Validación final: verificar que el notional sea alcanzable con nuestro margen
    final_notional = price * qty
    required_margin = final_notional / curr_lev
    
    if required_margin > target_margin * Decimal("1.01"):  # 1% de tolerancia
        log.warning(f"[{symbol}] qty {qty} requiere margen {required_margin:.3f} que excede el límite de {target_margin}")
        # Ajustar qty para que use exactamente el margen objetivo
        adjusted_qty = (target_margin * curr_lev) / price
        qty = f.round_qty_down(float(adjusted_qty))
        
        # Verificar que aún cumple con minimos
        if qty * price < f.min_notional:
            log.warning(f"[{symbol}] No es posible usar exactamente {target_margin} USD con este símbolo")
            return Decimal("0"), curr_lev
    
    log.info(f"[{symbol}] Using margin: {(qty * price / curr_lev):.3f} USD, leverage: {curr_lev}, qty: {qty}, notional: {qty * price:.2f}")
    
    return qty, curr_lev

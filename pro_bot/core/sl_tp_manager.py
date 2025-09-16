
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta
from ..config import settings
from .exchange import SymbolFilters
from .execution import (enter_basic, stop_market, take_profit_market, last_price)

log = logging.getLogger("sl_tp")

@dataclass
class TradeState:
    active: bool = False
    side: Optional[str] = None          # 'BUY' for long, 'SELL' for short (open side)
    entry_price: float = 0.0
    qty: float = 0.0
    r_value: float = 0.0                # distance from entry to initial SL
    sl_order_id: Optional[int] = None   # STOP_MARKET closePosition=true
    tp_order_ids: List[Optional[int]] = field(default_factory=list)
    realized_partial: float = 0.0       # qty closed via TP
    break_even_moved: bool = False
    trailing_active: bool = False       # Nueva: flag para tracking del trailing
    last_trail_price: float = 0.0       # Nueva: último precio de trailing
    max_favorable_r: float = 0.0        # Nueva: máximo R alcanzado

class SLTPManager:
    def __init__(self, cfg: dict, symbol: str):
        self.cfg = cfg
        self.symbol = symbol
        self.state = TradeState()
        self.filters = SymbolFilters(self.symbol)
        self.risk = cfg.get("risk", {})
        
        # Sistema de cooldown para evitar overtrading
        self.cooldown_minutes = int(self.risk.get("cooldown_minutes", 5))  # 5 min por defecto
        self.last_close_time: Optional[datetime] = None  # Última vez que se cerró una posición
        self.last_open_time: Optional[datetime] = None   # Última vez que se abrió una posición

        self.stop_loss_atr_mult = float(self.risk.get("stop_loss_atr_mult", 2.5))
        
        # NUEVA CONFIGURACIÓN: TP basado en porcentaje del valor de la posición en PnL USDT
        self.tp_pnl_percentages = list(self.risk.get("tp_pnl_percentages", [50.0, 30.0, 20.0]))  # % del valor de posición
        self.tp_allocation = list(self.risk.get("tp_allocation", [0.5, 0.25, 0.25]))  # % de qty a cerrar
        
        # Asegurar exactamente 3 TP levels y allocations
        if len(self.tp_pnl_percentages) != 3:
            log.warning(f"[{self.symbol}] ⚠️ Expected 3 TP PnL%, got {len(self.tp_pnl_percentages)}. Using defaults.")
            self.tp_pnl_percentages = [50.0, 30.0, 20.0]  # 50%, 30%, 20% del valor de posición
            
        if len(self.tp_allocation) != 3:
            log.warning(f"[{self.symbol}] ⚠️ Expected 3 TP allocations, got {len(self.tp_allocation)}. Using defaults.")
            self.tp_allocation = [0.5, 0.25, 0.25]
            
        # Validar que las allocations sumen 1.0 y sean positivas
        total_alloc = sum(self.tp_allocation)
        if abs(total_alloc - 1.0) > 0.01:
            log.warning(f"[{self.symbol}] ⚠️ TP allocations sum to {total_alloc}, should be 1.0. Normalizing...")
            self.tp_allocation = [alloc / total_alloc for alloc in self.tp_allocation]
            
        # Asegurar que todas las allocations sean positivas
        for i, alloc in enumerate(self.tp_allocation):
            if alloc <= 0:
                log.warning(f"[{self.symbol}] ⚠️ TP{i+1} allocation = {alloc}, setting to minimum 0.01")
                self.tp_allocation[i] = 0.01
                
        log.info(f"[{self.symbol}] 🎯 TP Config: {list(zip(self.tp_pnl_percentages, self.tp_allocation))}")
        log.info(f"[{self.symbol}] 📊 TP1: {self.tp_pnl_percentages[0]}% posición = {self.tp_allocation[0]*100}% qty")
        log.info(f"[{self.symbol}] 📊 TP2: {self.tp_pnl_percentages[1]}% posición = {self.tp_allocation[1]*100}% qty") 
        log.info(f"[{self.symbol}] 📊 TP3: {self.tp_pnl_percentages[2]}% posición = {self.tp_allocation[2]*100}% qty")
        
        # Configuración optimizada de trailing stop
        self.trailing_activate_after_r = float(self.risk.get("trailing", {}).get("activate_after_r", 1.0))  # Activar más temprano
        self.trailing_atr_mult = float(self.risk.get("trailing", {}).get("atr_mult", 0.8))  # Más conservador
        self.trailing_step_r = float(self.risk.get("trailing", {}).get("step_r", 0.25))  # Mover cada 0.25R
        self.trailing_min_move = float(self.risk.get("trailing", {}).get("min_move", 0.1))  # Mínimo movimiento
        self.break_even_r = float(self.risk.get("break_even_r", 0.75))  # Break-even más temprano
        
        # Configuración de comisiones para break-even real
        self.commission_rate = float(self.risk.get("commission_rate", 0.0008))  # 0.08% total por defecto (conservador)

    def _round_qty(self, q: float) -> float:
        return float(self.filters.round_qty_down(q))
    
    def is_in_cooldown(self) -> bool:
        """Verifica si el símbolo está en cooldown después de abrir/cerrar posición"""
        now = datetime.now()
        cooldown_delta = timedelta(minutes=self.cooldown_minutes)
        
        # Verificar cooldown por cierre de posición
        if self.last_close_time and (now - self.last_close_time) < cooldown_delta:
            remaining = (self.last_close_time + cooldown_delta - now).total_seconds() / 60
            return True, f"cierre hace {remaining:.1f}m"
            
        # Verificar cooldown por apertura de posición
        if self.last_open_time and (now - self.last_open_time) < cooldown_delta:
            remaining = (self.last_open_time + cooldown_delta - now).total_seconds() / 60
            return True, f"apertura hace {remaining:.1f}m"
            
        return False, ""
    
    def _set_cooldown_open(self):
        """Marca el tiempo de apertura para cooldown"""
        self.last_open_time = datetime.now()
        log.info(f"[{self.symbol}] 🕒 Cooldown iniciado: {self.cooldown_minutes}m tras apertura")
    
    def _set_cooldown_close(self):
        """Marca el tiempo de cierre para cooldown"""
        self.last_close_time = datetime.now()
        log.info(f"[{self.symbol}] 🕒 Cooldown iniciado: {self.cooldown_minutes}m tras cierre")
    
    def _check_position_closed(self):
        """Verifica si la posición se cerró y activa cooldown si es necesario"""
        from .execution import has_open_position
        
        # Si teníamos posición activa pero ya no hay posición abierta
        if self.state.active and not has_open_position(self.symbol):
            log.info(f"[{self.symbol}] 🏁 Posición cerrada detectada - Activando cooldown")
            self._set_cooldown_close()
            self.state = TradeState()  # Reset estado
            return True
        return False
    
    def _validate_tp_setup(self):
        """Validar que la configuración TP sea segura"""
        log.info(f"[{self.symbol}] 🔍 Validating TP setup...")
        
        # Verificar que los porcentajes de PnL sean decrecientes
        for i in range(len(self.tp_pnl_percentages) - 1):
            if self.tp_pnl_percentages[i] <= self.tp_pnl_percentages[i + 1]:
                log.warning(f"[{self.symbol}] ⚠️ TP{i+1} PnL% ({self.tp_pnl_percentages[i]}%) should be > TP{i+2} ({self.tp_pnl_percentages[i+1]}%)")
        
        # Verificar que TP1 y TP2 no tomen >90% de qty
        for i, alloc in enumerate(self.tp_allocation[:2], 1):
            if alloc >= 0.9:  # Si TP1 o TP2 toman >90% 
                log.warning(f"[{self.symbol}] ⚠️ TP{i} allocation = {alloc*100:.1f}% (risky for partial close)")
        
        # Verificar que las allocations no cierren toda la posición antes de TP3
        partial_sum = sum(self.tp_allocation[:2])
        if partial_sum >= 0.95:
            log.warning(f"[{self.symbol}] ⚠️ TP1+TP2 = {partial_sum*100:.1f}% (may close full position)")
        
        log.info(f"[{self.symbol}] ✅ TP Strategy: {self.tp_pnl_percentages[0]}%/{self.tp_pnl_percentages[1]}%/{self.tp_pnl_percentages[2]}% PnL triggers")
        log.info(f"[{self.symbol}] ✅ TP Allocation: TP1+TP2={partial_sum*100:.1f}% PARTIAL, TP3={self.tp_allocation[2]*100:.1f}% REMAINING")

    def open_trade(self, direction: str, atr: float, use_limit: bool = True, limit_offset_bps: int = 3):
        if self.state.active:
            log.info(f"[{self.symbol}] Ya hay una operación activa, se ignora nueva apertura.")
            return
            
        # Verificar cooldown antes de abrir nueva posición
        in_cooldown, reason = self.is_in_cooldown()
        if in_cooldown:
            log.info(f"[{self.symbol}] 🕒 En cooldown: {reason} - Apertura bloqueada")
            return
        
        # Validar configuración TP antes de abrir
        self._validate_tp_setup()

        basic = enter_basic(self.symbol, direction)
        if not basic or not basic.get("success"):
            log.warning(f"[{self.symbol}] ❌ No se pudo abrir posición básica: {basic.get('error', 'Unknown error')}")
            return

        entry_price = float(basic.get("entry_price", last_price(self.symbol)))
        qty = float(basic.get("filled_qty", basic.get("qty", 0.0)))
        side_open = basic.get("side", "BUY" if direction == "LONG" else "SELL")   # BUY for long, SELL for short

        if qty <= 0:
            log.error(f"[{self.symbol}] ❌ Cantidad inválida devuelta por enter_basic: {qty}")
            return

        if direction == "LONG":
            sl_price = entry_price - self.stop_loss_atr_mult * atr
            r_value = entry_price - sl_price
        elif direction == "SHORT":
            sl_price = entry_price + self.stop_loss_atr_mult * atr
            r_value = sl_price - entry_price

        sl_resp = stop_market(self.symbol, side="SELL" if side_open == "BUY" else "BUY",
                              stop_price=sl_price, qty=None, close_position=True)

        tp_ids = []
        tp_created_count = 0
        
        # Calcular valor total de la posición en USDT
        position_value_usdt = qty * entry_price
        
        for i, (pnl_percentage, alloc) in enumerate(zip(self.tp_pnl_percentages, self.tp_allocation), 1):
            # Validar allocation positiva
            if alloc <= 0:
                log.warning(f"[{self.symbol}] ⚠️ TP{i} skipped: allocation = {alloc}")
                tp_ids.append(None)
                continue
                
            # Calcular y validar cantidad
            tp_qty = self._round_qty(qty * alloc)
            if tp_qty <= 0:
                # Si la cantidad redondeada es 0, usar la cantidad mínima del símbolo
                min_qty = self.filters.step_size
                tp_qty = min_qty
                log.warning(f"[{self.symbol}] ⚠️ TP{i} qty too small, using min_qty = {tp_qty} (original: {qty * alloc})")
                if tp_qty > qty:
                    log.error(f"[{self.symbol}] ❌ TP{i} min_qty > total_qty, skipping")
                    tp_ids.append(None)
                    continue

            # NUEVA LÓGICA: Calcular precio TP basado en % del valor de la posición
            target_pnl_usdt = position_value_usdt * (pnl_percentage / 100.0)  # PnL objetivo en USDT
            
            if direction == "LONG":
                # Para LONG: tp_price = entry_price + (target_pnl_usdt / qty)
                tp_price = entry_price + (target_pnl_usdt / qty)
                side_close = "SELL"
            elif direction == "SHORT":
                # Para SHORT: tp_price = entry_price - (target_pnl_usdt / qty)
                tp_price = entry_price - (target_pnl_usdt / qty)
                side_close = "BUY"

            try:
                # CRÍTICO: Solo TP3 puede usar close_position=True si es necesario
                # TP1 y TP2 SIEMPRE deben ser parciales (close_position=False)
                close_position = False  # Por defecto, NUNCA cerrar completamente
                
                # Opcional: permitir que TP3 cierre completamente si la cantidad es muy pequeña
                if i == 3 and tp_qty >= qty * 0.9:  # Si TP3 es >90% de la posición
                    close_position = True
                    log.info(f"[{self.symbol}] 📋 TP{i} will close position (qty={tp_qty} >= 90% of {qty})")
                
                tp_resp = take_profit_market(self.symbol, side=side_close, stop_price=tp_price, qty=str(tp_qty), close_position=close_position)
                order_id = tp_resp.get("orderId")
                tp_ids.append(order_id)
                tp_created_count += 1
                
                close_status = "PARTIAL" if not close_position else "FULL"
                target_pnl_usdt = position_value_usdt * (pnl_percentage / 100.0)
                log.info(f"[{self.symbol}] ✅ TP{i} @ {pnl_percentage}% pos (${target_pnl_usdt:.2f}): qty={tp_qty} price={tp_price:.4f} mode={close_status} id={order_id}")
            except Exception as e:
                log.error(f"[{self.symbol}] ❌ TP{i} failed: {e}")
                tp_ids.append(None)
        
        # Verificar que se crearon las 3 órdenes TP
        if tp_created_count < 3:
            log.warning(f"[{self.symbol}] ⚠️ Only {tp_created_count}/3 TP orders created!")
        else:
            log.info(f"[{self.symbol}] 🎯 All {tp_created_count} TP orders created successfully")

        self.state = TradeState(active=True, side=side_open, entry_price=entry_price, qty=qty, r_value=r_value,
                                sl_order_id=sl_resp.get("orderId"), tp_order_ids=tp_ids, realized_partial=0.0,
                                break_even_moved=False, trailing_active=False, last_trail_price=0.0, max_favorable_r=0.0)
        
        # Activar cooldown tras apertura
        self._set_cooldown_open()
        
        log.info(f"[{self.symbol}] 🚀 Abrir {direction}: entry={entry_price:.4f} qty={qty}, SL@{sl_price:.4f}, PosValue=${position_value_usdt:.2f}")

    def manage(self, last_close: float, atr: float):
        # Verificar si la posición se cerró para activar cooldown
        if self._check_position_closed():
            return
            
        if not self.state.active:
            return

        s = self.state
        if s.side == "BUY":
            direction = "LONG"
        elif s.side == "SELL":
            direction = "SHORT"

        # Calcular R no realizado actual
        if direction == "LONG":
            r_unreal = (last_close - s.entry_price) / (s.r_value + 1e-12)
        else:
            r_unreal = (s.entry_price - last_close) / (s.r_value + 1e-12)

        # Actualizar máximo R alcanzado
        s.max_favorable_r = max(s.max_favorable_r, r_unreal)

        # 1. BREAK-EVEN (considerando comisiones de trading)
        if not s.break_even_moved and r_unreal >= self.break_even_r:
            # Calcular break-even real considerando comisiones
            # Asumimos comisiones taker: 0.04% entrada + 0.04% salida = 0.08% total
            commission_rate = 0.0008  # 0.08% total (conservador)
            commission_offset = s.entry_price * commission_rate
            
            if direction == "LONG":
                # Para LONG: necesitamos precio ligeramente superior para cubrir comisiones
                be_price_with_commission = s.entry_price + commission_offset
                new_sl = be_price_with_commission - 1e-6
            else:
                # Para SHORT: necesitamos precio ligeramente inferior para cubrir comisiones  
                be_price_with_commission = s.entry_price - commission_offset
                new_sl = be_price_with_commission + 1e-6
                
            stop_market(self.symbol, side="SELL" if s.side == "BUY" else "BUY", stop_price=new_sl, qty=None, close_position=True)
            s.break_even_moved = True
            log.info(f"[{self.symbol}] 📍 Break-even: SL @ {new_sl:.4f} (entrada: {s.entry_price:.4f}, comisiones: +{commission_offset:.4f}, R: {r_unreal:.2f})")

        # 2. TRAILING STOP INTELIGENTE
        self._update_trailing_stop(last_close, atr, r_unreal, direction)

    def _update_trailing_stop(self, last_close: float, atr: float, current_r: float, direction: str):
        """Sistema de trailing stop optimizado y progresivo"""
        s = self.state
        
        # Activar trailing si alcanzamos el umbral
        if not s.trailing_active and current_r >= self.trailing_activate_after_r:
            s.trailing_active = True
            s.last_trail_price = last_close
            log.info(f"[{self.symbol}] 🎯 Trailing activado @ R={current_r:.2f}")

        if not s.trailing_active:
            return

        # Calcular nuevo precio de trailing basado en volatilidad dinámica
        atr_factor = self._get_dynamic_atr_factor(current_r)
        trail_distance = atr * atr_factor

        if direction == "LONG":
            new_trail_price = last_close - trail_distance
            # Solo mover si el nuevo precio es superior al anterior (más favorable)
            if s.last_trail_price == 0.0 or new_trail_price > s.last_trail_price:
                # Verificar que el movimiento sea significativo
                if s.last_trail_price == 0.0 or abs(new_trail_price - s.last_trail_price) >= self.trailing_min_move:
                    stop_market(self.symbol, side="SELL", stop_price=new_trail_price, qty=None, close_position=True)
                    s.last_trail_price = new_trail_price
                    log.info(f"[{self.symbol}] 📈 Trailing LONG → SL: {new_trail_price:.4f} (R: {current_r:.2f}, ATR: {atr_factor:.1f}x)")
        else:
            new_trail_price = last_close + trail_distance
            # Solo mover si el nuevo precio es inferior al anterior (más favorable)
            if s.last_trail_price == 0.0 or new_trail_price < s.last_trail_price:
                if s.last_trail_price == 0.0 or abs(s.last_trail_price - new_trail_price) >= self.trailing_min_move:
                    stop_market(self.symbol, side="BUY", stop_price=new_trail_price, qty=None, close_position=True)
                    s.last_trail_price = new_trail_price
                    log.info(f"[{self.symbol}] 📉 Trailing SHORT → SL: {new_trail_price:.4f} (R: {current_r:.2f}, ATR: {atr_factor:.1f}x)")

    def _get_dynamic_atr_factor(self, current_r: float) -> float:
        """Factor de ATR dinámico basado en el R alcanzado"""
        base_factor = self.trailing_atr_mult
        
        # Hacer el trailing más conservador a medida que ganamos más
        if current_r >= 3.0:
            return base_factor * 0.5  # Muy conservador en grandes ganancias
        elif current_r >= 2.0:
            return base_factor * 0.7  # Conservador
        elif current_r >= 1.5:
            return base_factor * 0.8  # Moderado
        else:
            return base_factor  # Normal

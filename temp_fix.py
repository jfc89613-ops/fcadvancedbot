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

        # --- NUEVO ESQUEMA: ÓRDENES MARKET Y PRECIO DIRECTO DE BINANCE ---
        from .execution import last_price, market_order, take_profit_market
        from .risk import decide_qty_for_margin
        
        entry_price = last_price(self.symbol)  # Precio actual del ticker
        f = self.filters
        qty, lev = decide_qty_for_margin(self.symbol, entry_price)  # Nuevo cálculo: MIN_NOTIONAL / ENTRY_PRICE
        side_open = "BUY" if direction == "LONG" else "SELL"
        qty_str = f.fmt_qty(qty)

        # Ejecutar orden MARKET
        ord_resp = market_order(side_open, self.symbol, qty_str)
        log.info(f"[{self.symbol}] MARKET order placed: {ord_resp.get('orderId','?')}")

        # Calcular stop-loss y R
        if direction == "LONG":
            sl_price = entry_price - self.stop_loss_atr_mult * atr
            r_value = entry_price - sl_price
        else:
            sl_price = entry_price + self.stop_loss_atr_mult * atr
            r_value = sl_price - entry_price

        sl_resp = stop_market(self.symbol, side="SELL" if side_open == "BUY" else "BUY",
                              stop_price=sl_price, qty=None, close_position=True)

        tp_ids = []
        tp_created_count = 0
        _round_qty_cache = {}

        for i, (mult, alloc) in enumerate(zip(self.take_profit_levels, self.tp_allocation), 1):
            # Validar allocation positiva
            if alloc <= 0:
                log.warning(f"[{self.symbol}] ⚠️ TP{i} skipped: allocation = {alloc}")
                tp_ids.append(None)
                continue

            # Calcular y validar cantidad con caché
            raw_tp_qty = qty * alloc
            if raw_tp_qty in _round_qty_cache:
                tp_qty = _round_qty_cache[raw_tp_qty]
            else:
                tp_qty = self._round_qty(raw_tp_qty)
                _round_qty_cache[raw_tp_qty] = tp_qty

            if tp_qty <= 0:
                min_qty = f.qty_step
                tp_qty = min_qty
                log.warning(f"[{self.symbol}] ⚠️ TP{i} qty too small, using min_qty = {tp_qty} (original: {qty * alloc})")
                if tp_qty > qty:
                    log.error(f"[{self.symbol}] ❌ TP{i} min_qty > total_qty, skipping")
                    tp_ids.append(None)
                    continue

            # Calcular precio TP
            if direction == "LONG":
                tp_price = entry_price + mult * r_value
                side_close = "SELL"
            else:
                tp_price = entry_price - mult * r_value
                side_close = "BUY"

            try:
                close_position = False
                if i == 3 and tp_qty >= qty * 0.9:
                    close_position = True
                    log.info(f"[{self.symbol}] 📋 TP{i} will close position (qty={tp_qty} >= 90% of {qty})")

                tp_resp = take_profit_market(self.symbol, side=side_close, stop_price=tp_price, qty=str(tp_qty), close_position=close_position)
                order_id = tp_resp.get("orderId")
                tp_ids.append(order_id)
                tp_created_count += 1

                close_status = "PARTIAL" if not close_position else "FULL"
                log.info(f"[{self.symbol}] ✅ TP{i} @ {mult}R: qty={tp_qty} price={tp_price:.4f} mode={close_status} id={order_id}")
            except Exception as e:
                log.error(f"[{self.symbol}] ❌ TP{i} failed: {e}")
                tp_ids.append(None)

        if tp_created_count < 3:
            log.warning(f"[{self.symbol}] ⚠️ Only {tp_created_count}/3 TP orders created!")
        else:
            log.info(f"[{self.symbol}] 🎯 All {tp_created_count} TP orders created successfully")

        self.state = TradeState(active=True, side=side_open, entry_price=entry_price, qty=qty, r_value=r_value,
                                sl_order_id=sl_resp.get("orderId"), tp_order_ids=tp_ids, realized_partial=0.0,
                                break_even_moved=False, trailing_active=False, last_trail_price=0.0, max_favorable_r=0.0)

        self._set_cooldown_open()
        log.info(f"[{self.symbol}] 🚀 Abrir {direction}: entry={entry_price:.4f} qty={qty}, SL@{sl_price:.4f}, R={r_value:.4f}")

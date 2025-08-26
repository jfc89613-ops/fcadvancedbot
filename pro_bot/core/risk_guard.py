
import json
import os
import logging
from datetime import datetime, timezone
from .client import get_client

log = logging.getLogger("risk_guard")

RUNTIME_DIR = "outputs/runtime"
BASELINE_FILE = os.path.join(RUNTIME_DIR, "equity_baseline.json")
LOCK_FILE = os.path.join(RUNTIME_DIR, "kill_switch.lock")

def _today_key():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _ensure_dirs():
    os.makedirs(RUNTIME_DIR, exist_ok=True)

def _get_equity_usdt():
    # Futures account wallet balance (USDT-M)
    acct = get_client().client.futures_account()
    # Prefer totalWalletBalance in USDT
    eq = float(acct.get("totalWalletBalance", 0.0))
    return eq

class RiskGuard:
    def __init__(self, max_daily_dd: float = 0.03):
        _ensure_dirs()
        self.max_daily_dd = max_daily_dd
        self._load_or_init()

    def _load_or_init(self):
        self.today = _today_key()
        self.tripped = os.path.exists(LOCK_FILE)
        self.baseline = None
        if os.path.exists(BASELINE_FILE):
            try:
                data = json.load(open(BASELINE_FILE, "r"))
            except Exception:
                data = {}
        else:
            data = {}
        if data.get("date") != self.today:
            # new day -> set new baseline
            eq = _get_equity_usdt()
            data = {"date": self.today, "baseline_equity": eq}
            json.dump(data, open(BASELINE_FILE, "w"))
            # reset kill switch for new day
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
            self.tripped = False
            log.info(f"[RiskGuard] Nueva sesión {self.today}. Equity base: {eq:.2f} USDT")
        self.baseline = float(data.get("baseline_equity", 0.0))

    def is_tripped(self) -> bool:
        return self.tripped

    def trip(self):
        open(LOCK_FILE, "w").write(self.today)
        self.tripped = True
        log.error("[RiskGuard] KILL-SWITCH ACTIVADO. Bloqueando nuevas entradas.")

    def on_loop(self):
        # Check date rollover or baseline existence
        if _today_key() != self.today or self.baseline is None:
            self._load_or_init()
            return
        try:
            eq = _get_equity_usdt()
        except Exception as e:
            log.warning(f"[RiskGuard] No se pudo leer equity: {e}")
            return
        if self.baseline <= 0:
            return
        dd = (eq - self.baseline) / self.baseline
        if dd <= -abs(self.max_daily_dd):
            self.trip()
        # (Opcional) podrías registrar métricas aquí

    def can_trade(self) -> bool:
        """
        Check if trading is allowed based on risk guard status.
        Returns False if kill switch is tripped or there are other risk conditions.
        """
        # First update the risk status
        self.on_loop()
        
        # Return False if kill switch is active
        if self.is_tripped():
            return False
            
        # Add any additional risk checks here if needed
        # For now, just check if we're not tripped
        return True


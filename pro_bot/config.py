from pydantic import BaseModel
from dotenv import load_dotenv
import os
load_dotenv()
class Settings(BaseModel):
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    symbol: str = os.getenv("SYMBOL", "BTCUSDT")
    leverage: int = int(os.getenv("LEVERAGE", 5))
    margin_type: str = os.getenv("MARGIN_TYPE", "CROSSED")
    position_mode: str = os.getenv("POSITION_MODE", "ONE_WAY")
    max_position_usdt: float = float(os.getenv("MAX_POSITION_USDT", 0.5))
    risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", 0.01))
    max_margin_usdt: float = float(os.getenv("MAX_MARGIN_USDT", 0.5))
    max_open_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", 5))
    auto_leverage: bool = os.getenv("AUTO_LEVERAGE", "true").lower() == "true"
    kline_interval: str = os.getenv("KLINE_INTERVAL", "1m")
    recv_window: int = int(os.getenv("RECV_WINDOW", 5000))
    warmup_interval: str = os.getenv("WARMUP_INTERVAL", "1m")
    warmup_lookback_min: int = int(os.getenv("WARMUP_LOOKBACK_MIN", 1500))
    train_interval: str = os.getenv("TRAIN_INTERVAL", "1m")
    train_lookback_days: int = int(os.getenv("TRAIN_LOOKBACK_DAYS", 30))
settings = Settings()

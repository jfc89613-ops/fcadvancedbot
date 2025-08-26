import os, queue, threading, logging, yaml
import pandas as pd
from datetime import datetime, timedelta, timezone
from pro_bot.config import settings
from pro_bot.core.client import get_client
from pro_bot.core.ws import start_streams
from pro_bot.core.execution import enter_position, refresh_open_positions_cache
from pro_bot.core.binance_klines import fetch_klines
from pro_ml.core.features.microstructure import build_features
from pro_ml.core.live.inference import LiveModel
logging.basicConfig(level=logging.INFO); log=logging.getLogger("main")
CFG_PATH=os.getenv("ML_CFG","configs/ml.yaml")
with open(CFG_PATH,"r") as f: cfg=yaml.safe_load(f)
serv=cfg.get("serving",{})
lm=LiveModel("outputs/models/best_model.joblib","outputs/models/metadata.joblib",
             prob_long=serv.get("prob_long",0.57), prob_short=serv.get("prob_short",0.43))
kl_q=queue.Queue()
def warmup_df():
    lookback_min = int(settings.warmup_lookback_min)
    interval = settings.warmup_interval
    # En lugar de usar start/end, usamos limit directamente
    df = fetch_klines(settings.symbol, interval=interval, limit=lookback_min)
    if df.empty: return pd.DataFrame(columns=["open","high","low","close","volume"])
    return df
DF = warmup_df()
log.info(f"WARMUP DF rows: {len(DF)}")
def on_kline(msg):
    try:
        if msg.get("e")!="kline": return
        k=msg["k"]
        if not k["x"]: return
        ts=int(k["t"])//1000
        row={"open":float(k["o"]),"high":float(k["h"]),"low":float(k["l"]),"close":float(k["c"]),"volume":float(k["v"])}
        kl_q.put((ts,row))
    except Exception as e: log.warning(f"on_kline error: {e}")
def on_user(msg): log.info(f"USER: {msg.get('e')}: {msg}")
def ws_thread():
    twm=start_streams(on_kline=on_kline, on_user=on_user)
    try: twm.join()
    except KeyboardInterrupt: twm.stop()
def main():
    get_client()
    refresh_open_positions_cache()
    t=threading.Thread(target=ws_thread, daemon=True); t.start()
    global DF
    while True:
        ts,row=kl_q.get()
        DF.loc[pd.to_datetime(ts, unit="s", utc=True)]=row
        feats_df=build_features(DF, cfg)
        if len(feats_df)<10: continue
        latest=feats_df.iloc[-1]
        decision,prob=lm.decide(latest)
        log.info(f"ML Decision: {decision} p={prob:.3f}")
        if decision in ("LONG","SHORT"):
            try: enter_position(decision, use_limit=True)
            except Exception as e: log.warning(f"No se pudo entrar posición: {e}")
if __name__=="__main__": main()

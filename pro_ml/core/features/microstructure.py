import numpy as np, pandas as pd
def realized_vol(close: pd.Series, span: int=1440)->pd.Series:
    ret=np.log(close).diff(); return ret.ewm(span=span, adjust=False).std().fillna(0)
def ofi_proxy(df: pd.DataFrame, window:int=120)->pd.Series:
    sign=np.sign(df["close"].diff()).fillna(0); flow=sign*df["volume"]
    return flow.rolling(window, min_periods=1).sum()
def queue_imbalance_proxy(df: pd.DataFrame, window:int=20)->pd.Series:
    rng=(df["high"]-df["low"]).replace(0, np.nan)
    qi=(df["close"]- (df["high"]+df["low"])/2)/rng
    return qi.rolling(window, min_periods=1).mean().fillna(0)
def microprice_proxy(df: pd.DataFrame, window:int=20)->pd.Series:
    mp=(df["high"]+df["low"]+2*df["close"])/4
    return mp.rolling(window, min_periods=1).mean()
def rsi(close: pd.Series, n:int=14)->pd.Series:
    d=close.diff(); up,down=d.clip(lower=0), -d.clip(upper=0)
    ru=up.ewm(alpha=1/n, adjust=False).mean(); rd=down.ewm(alpha=1/n, adjust=False).mean()
    rs=ru/(rd+1e-12); return 100-(100/(1+rs))
def true_range(df: pd.DataFrame)->pd.Series:
    pc=df["close"].shift(1)
    return pd.concat([df["high"]-df["low"], (df["high"]-pc).abs(), (df["low"]-pc).abs()], axis=1).max(axis=1)
def build_features(df: pd.DataFrame, cfg: dict)->pd.DataFrame:
    out=df.copy()
    out["ret1"]=np.log(out["close"]).diff()
    out["rv"]=realized_vol(out["close"], span=cfg["features"]["vol_ewm_span"])
    out["ofi"]=ofi_proxy(out, window=cfg["features"]["ofi_window"])
    out["qi"]=queue_imbalance_proxy(out)
    out["mp"]=microprice_proxy(out); out["mp_diff"]=out["mp"].diff()
    out["rsi"]=rsi(out["close"], cfg["features"]["rsi_len"])
    tr=true_range(out); atr=tr.rolling(cfg["features"]["atr_len"]).mean()
    out["atr"]=atr.bfill().fillna(0)
    feats=["ret1","rv","ofi","qi","mp","mp_diff","rsi","atr"]
    out[feats]=out[feats].shift(1); out=out.dropna(); return out

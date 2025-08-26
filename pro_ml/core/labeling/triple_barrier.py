import numpy as np, pandas as pd
def triple_barrier_labels(df: pd.DataFrame, horizon_min:int, pt_mult:float, sl_mult:float, use_atr:bool=True):
    close=df["close"]; scale=df["atr"] if use_atr else df["rv"]
    pt=close*(1+pt_mult*(scale/(close+1e-12)))
    sl=close*(1-sl_mult*(scale/(close+1e-12)))
    idx=df.index; y=np.zeros(len(df),dtype=int); t1=[]
    for i,_ in enumerate(idx):
        end_i=i+horizon_min
        if end_i>=len(df): t1.append(idx[-1]); y[i]=0; continue
        c0=close.iloc[i]; up,dn=pt.iloc[i], sl.iloc[i]; path=close.iloc[i+1:end_i+1]
        hit_up=(path>=up).idxmax() if (path>=up).any() else None
        hit_dn=(path<=dn).idxmax() if (path<=dn).any() else None
        if hit_up is not None and (hit_dn is None or hit_up<=hit_dn): y[i]=1; t1.append(hit_up)
        elif hit_dn is not None: y[i]=0; t1.append(hit_dn)
        else: y[i]=int(close.iloc[end_i]>c0); t1.append(idx[end_i])
    out=df.copy(); out["label"]=y; out["t1"]=pd.to_datetime(t1); return out

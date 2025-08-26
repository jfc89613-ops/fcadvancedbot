import os, re, yaml, joblib
from dotenv import load_dotenv
load_dotenv()

from pro_ml.core.data.loader_binance import DataLoader
from pro_ml.core.data.resampling import ensure_uniform
from pro_ml.core.features.microstructure import build_features
from pro_ml.core.labeling.triple_barrier import triple_barrier_labels
from pro_ml.core.models.xgb_optuna import XGBOptuna
from pro_ml.core.eval.metrics import evaluate_probs
from pro_bot.core.top_symbols import top_usdtm_by_quote_volume

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def train_one(base_cfg, symbol, force=False):
    out_dir = f"outputs/models/{symbol}"
    model_p = f"{out_dir}/best_model.joblib"
    meta_p  = f"{out_dir}/metadata.joblib"

    if (not force) and os.path.exists(model_p) and os.path.exists(meta_p):
        print(f"[{symbol}] ya tiene modelo, skip (usa FORCE_RETRAIN=1 para forzar)")
        return

    cfg = yaml.safe_load(open("configs/ml.yaml"))
    cfg["datasource"]["symbol"] = symbol

    dl = DataLoader(cfg, symbol=symbol)
    raw = dl.load()
    raw = ensure_uniform(raw, freq=cfg["datasource"].get("timeframe","1m"))
    if raw.empty:
        print(f"[{symbol}] sin datos, skip"); return

    feats = build_features(raw, cfg)
    lab = triple_barrier_labels(
        feats,
        cfg["labeling"]["horizon_min"],
        cfg["labeling"]["pt_mult"],
        cfg["labeling"]["sl_mult"],
        cfg["labeling"]["use_atr"]
    )

    cols = [c for c in feats.columns if c not in ["t1","label"]]
    X, y, t1 = lab[cols], lab["label"], lab["t1"]

    modeler = XGBOptuna(cfg)
    model, best_params = modeler.fit(X, y, t1)
    p = model.predict_proba(X)[:,1]
    metrics = evaluate_probs(y, p)

    ensure_dir(out_dir)
    joblib.dump(model, model_p)
    joblib.dump({"features": cols, "best_params": best_params, "metrics": metrics}, meta_p)
    print(f"[{symbol}] saved -> {out_dir}  metrics={metrics}")

def main():
    # FORCE_RETRAIN=1 para reentrenar aunque ya exista modelo
    force = os.getenv("FORCE_RETRAIN","0") in ("1","true","True","YES","yes")

    symbols_env = os.getenv("SYMBOLS","").strip()
    if symbols_env:
        raw = [x.strip() for x in symbols_env.split(",") if x.strip()]
        # Acepta solo símbolos estilo Futuros USDT
        symbols = [x.upper() for x in raw if re.fullmatch(r"[A-Z0-9]+USDT", x.upper())]
        if not symbols:
            print("SYMBOLS inválido; cayendo a TopN")
    else:
        symbols = []

    if not symbols:
        topn_raw = os.getenv("TOPN","20").split("#",1)[0].strip()  # quita comentarios inline
        try:
            topn = int(topn_raw)
        except Exception:
            topn = 20
        symbols = top_usdtm_by_quote_volume(topn)

    print("Training symbols:", symbols)
    base_cfg = yaml.safe_load(open("configs/ml.yaml"))
    for sym in symbols:
        try:
            print(f"=== [{sym}] training ===")
            train_one(base_cfg, sym, force=force)
        except Exception as e:
            print(f"[{sym}] ERROR: {e}")

if __name__ == "__main__":
    main()

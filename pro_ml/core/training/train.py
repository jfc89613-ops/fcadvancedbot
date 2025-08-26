import os, yaml, joblib
from ..data.loader_binance import DataLoader
from ..data.resampling import ensure_uniform
from ..features.microstructure import build_features
from ..labeling.triple_barrier import triple_barrier_labels
from ..models.xgb_optuna import XGBOptuna
from ..eval.metrics import evaluate_probs
def run_training(cfg_path="configs/ml.yaml"):
    cfg=yaml.safe_load(open(cfg_path))
    dl=DataLoader(cfg); raw=dl.load()
    raw=ensure_uniform(raw, freq=cfg["datasource"].get("timeframe","1m"))
    if raw.empty: raise SystemError("No se cargaron datos desde Binance.")
    feats=build_features(raw, cfg)
    lab=triple_barrier_labels(feats, cfg["labeling"]["horizon_min"], cfg["labeling"]["pt_mult"], cfg["labeling"]["sl_mult"], cfg["labeling"]["use_atr"])
    cols=[c for c in feats.columns if c not in ["t1","label"]]
    X=lab[cols]; y=lab["label"]; t1=lab["t1"]
    modeler=XGBOptuna(cfg); model,best_params=modeler.fit(X,y,t1)
    p=model.predict_proba(X)[:,1]; metrics=evaluate_probs(y,p)
    os.makedirs("outputs/models", exist_ok=True)
    joblib.dump(model,"outputs/models/best_model.joblib")
    joblib.dump({"features":cols,"best_params":best_params,"metrics":metrics},"outputs/models/metadata.joblib")
    print("Saved model with metrics:", metrics)
if __name__=="__main__": run_training()

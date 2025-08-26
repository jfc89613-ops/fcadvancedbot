import optuna, numpy as np, xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from ..cv.purged_kfold import PurgedKFold
from ..eval.metrics import evaluate_probs
class XGBOptuna:
    def __init__(self, cfg): self.cfg=cfg; self.best_model=None; self.best_params=None
    def _suggest(self, trial: optuna.Trial):
        return {"booster":"gbtree","objective":self.cfg["model"]["objective"],"eval_metric":self.cfg["model"]["eval_metric"],"tree_method":"hist",
                "max_depth":trial.suggest_int("max_depth",3,8),"learning_rate":trial.suggest_float("learning_rate",0.01,0.2,log=True),
                "subsample":trial.suggest_float("subsample",0.6,1.0),"colsample_bytree":trial.suggest_float("colsample_bytree",0.6,1.0),
                "min_child_weight":trial.suggest_float("min_child_weight",1.0,50.0,log=True),
                "lambda":trial.suggest_float("lambda",1e-3,10.0,log=True),"alpha":trial.suggest_float("alpha",1e-3,10.0,log=True),
                "n_estimators":trial.suggest_int("n_estimators",200,1200,step=100)}
    def fit(self, X, y, t1):
        n_splits=self.cfg["cv"]["n_splits"]; embargo=self.cfg["cv"]["embargo_frac"]
        def objective(trial):
            params=self._suggest(trial); aucs=[]
            for tr,te in PurgedKFold(n_splits=n_splits, embargo_frac=embargo).split(X,t1):
                X_tr,X_te=X.iloc[tr],X.iloc[te]; y_tr,y_te=y.iloc[tr],y.iloc[te]
                scale_pos=(len(y_tr)-y_tr.sum())/(y_tr.sum()+1e-9)
                clf=xgb.XGBClassifier(**params, scale_pos_weight=scale_pos)
                clf.fit(X_tr, y_tr, eval_set=[(X_te,y_te)], verbose=False)
                p=clf.predict_proba(X_te)[:,1]; aucs.append(evaluate_probs(y_te,p)["auc"])
            return float(np.mean(aucs))
        study=optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.cfg["optuna"]["n_trials"], timeout=self.cfg["optuna"]["timeout"])
        self.best_params=study.best_params
        base=xgb.XGBClassifier(**{**self.best_params, **{"booster":"gbtree","objective":self.cfg["model"]["objective"],"eval_metric":self.cfg["model"]["eval_metric"],"tree_method":"hist"}})
        base.fit(X,y); self.best_model=CalibratedClassifierCV(base, cv=3, method="isotonic").fit(X,y)
        return self.best_model, self.best_params

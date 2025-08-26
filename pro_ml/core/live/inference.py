import joblib, pandas as pd
class LiveModel:
    def __init__(self, model_path="outputs/models/best_model.joblib", metadata_path="outputs/models/metadata.joblib", prob_long=0.55, prob_short=0.45):
        self.model=joblib.load(model_path); meta=joblib.load(metadata_path)
        self.cols=meta["features"]; self.prob_long, self.prob_short=prob_long, prob_short
    def decide(self, latest_features_row: pd.Series):
        x=latest_features_row[self.cols].to_frame().T
        p=float(self.model.predict_proba(x)[:,1][0])
        if p>=self.prob_long: return "LONG", p
        elif p<=self.prob_short: return "SHORT", p
        return "NEUTRAL", p

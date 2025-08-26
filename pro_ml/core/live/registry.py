
import os
import joblib

class ModelRegistry:
    def __init__(self, base_dir='outputs/models', default_model='best_model.joblib', default_meta='metadata.joblib'):
        self.base_dir = base_dir
        self.default_model = os.path.join(base_dir, default_model)
        self.default_meta  = os.path.join(base_dir, default_meta)
        self.cache = {}  # symbol -> (model, meta)
        self.global_pair = (joblib.load(self.default_model), joblib.load(self.default_meta))

    def get(self, symbol: str):
        if symbol in self.cache:
            return self.cache[symbol]
        model_p = os.path.join(self.base_dir, f"{symbol}_best_model.joblib")
        meta_p  = os.path.join(self.base_dir, f"{symbol}_metadata.joblib")
        if os.path.exists(model_p) and os.path.exists(meta_p):
            pair = (joblib.load(model_p), joblib.load(meta_p))
        else:
            pair = self.global_pair
        self.cache[symbol] = pair
        return pair

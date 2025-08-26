import os
import joblib
import pandas as pd


class LiveModel:
    """
    Carga bajo demanda y en caché el modelo por símbolo desde:
      outputs/models/<SYMBOL>/best_model.joblib
      outputs/models/<SYMBOL>/metadata.joblib

    Uso:
      lm = LiveModel(prob_long=0.57, prob_short=0.43)
      decision, p = lm.decide("BTCUSDT", latest_features_row)
    """
    def __init__(self, base_dir: str = "outputs/models", prob_long: float = 0.57, prob_short: float = 0.43):
        self.base_dir = base_dir
        self.prob_long = prob_long
        self.prob_short = prob_short
        self._models = {}          # symbol -> model
        self._cols_by_symbol = {}  # symbol -> feature list

    def _paths(self, symbol: str):
        sd = os.path.join(self.base_dir, symbol.upper())
        return (
            os.path.join(sd, "best_model.joblib"),
            os.path.join(sd, "metadata.joblib"),
        )

    def load_for(self, symbol: str):
        symbol = symbol.upper()
        if symbol in self._models:
            return

        mpath, meta_path = self._paths(symbol)
        if not os.path.exists(mpath) or not os.path.exists(meta_path):
            raise FileNotFoundError(f"Modelo no encontrado para {symbol}: {mpath} / {meta_path}")

        model = joblib.load(mpath)
        meta = joblib.load(meta_path)
        cols = meta.get("features")
        if cols is None:
            raise ValueError(f"Metadata inválida: 'features' no encontrado para {symbol}")

        self._models[symbol] = model
        self._cols_by_symbol[symbol] = list(cols)

    def decide(self, symbol: str, latest_features_row: pd.Series):
        """
        Devuelve ('LONG'|'SHORT'|'NEUTRAL', prob) para un símbolo.
        Alinea columnas del modelo y rellena faltantes con 0.
        """
        symbol = symbol.upper()
        self.load_for(symbol)

        cols = self._cols_by_symbol[symbol]
        x = latest_features_row.reindex(cols)
        # Si faltan columnas, rellena con 0
        x = x.fillna(0.0)
        X = x.to_frame().T

        model = self._models[symbol]
        p = float(model.predict_proba(X)[:, 1][0])

        if p >= self.prob_long:
            return "LONG", p
        elif p <= self.prob_short:
            return "SHORT", p
        return "NEUTRAL", p

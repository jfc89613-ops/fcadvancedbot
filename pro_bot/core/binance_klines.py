
import time
import pandas as pd
from .client import get_client

_MAX_LIMIT = 1500

_MINUTES = {
    "1m":1,"3m":3,"5m":5,"15m":15,"30m":30,
    "1h":60,"2h":120,"4h":240,"6h":360,"8h":480,"12h":720,
    "1d":1440
}

_COLS = [
    "open_time","open","high","low","close","volume",
    "close_time","quote_asset_volume","number_of_trades",
    "taker_buy_base_asset_volume","taker_buy_quote_asset_volume","ignore"
]

def _to_df(rows):
    if not rows:
        return pd.DataFrame(columns=["open","high","low","close","volume"])
    df = pd.DataFrame(rows, columns=_COLS)
    for c in ["open","high","low","close","volume","quote_asset_volume",
              "taker_buy_base_asset_volume","taker_buy_quote_asset_volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # índice UTC naive
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    df = df.set_index("open_time").sort_index()
    return df[["open","high","low","close","volume"]]

def fetch_klines(symbol: str, interval: str, *, limit: int|None=None,
                 start: int|None=None, end: int|None=None) -> pd.DataFrame:
    """
    Trae klines de Binance Futuros.
    - Si limit <= 1500: una llamada.
    - Si limit > 1500: pagina hacia atrás con endTime hasta cubrir 'limit' y devuelve las últimas 'limit'.
    - Si limit es None y hay start/end: pagina hacia adelante desde start hasta end.
    - Si no hay limit/start/end: devuelve los últimos 1000 (compat).
    """
    cli = get_client().client

    # Caso 1: limit especificado
    if limit is not None:
        if limit <= _MAX_LIMIT:
            rows = cli.futures_klines(symbol=symbol, interval=interval, limit=limit)
            return _to_df(rows)

        # limit > 1500 → paginar hacia atrás (de "ahora" hacia el pasado)
        rows_all = []
        end_time = None  # None -> último chunk
        remaining = int(limit)

        while remaining > 0:
            chunk = min(remaining, _MAX_LIMIT)
            if end_time is None:
                rows = cli.futures_klines(symbol=symbol, interval=interval, limit=chunk)
            else:
                rows = cli.futures_klines(symbol=symbol, interval=interval, endTime=end_time, limit=chunk)
            if not rows:
                break
            # prepend nuevos anteriores
            rows_all = rows + rows_all
            # preparar siguiente ventana: ir antes del primer open_time devuelto
            first_open = rows[0][0]  # ms
            end_time = int(first_open) - 1
            remaining -= len(rows)
            # pequeña pausa para rate limit
            time.sleep(0.03)

            # seguridad: si el nuevo end_time no avanza, cortar
            if len(rows) < chunk:
                break

        if not rows_all:
            return _to_df(rows_all)

        # dejar solo las últimas 'limit' velas
        df = _to_df(rows_all)
        if len(df) > limit:
            df = df.iloc[-limit:]
        return df

    # Caso 2: rango start/end (pagina hacia adelante)
    if start is not None or end is not None:
        rows_all = []
        cur_start = start
        while True:
            rows = cli.futures_klines(symbol=symbol, interval=interval,
                                      startTime=cur_start, endTime=end, limit=_MAX_LIMIT)
            if not rows:
                break
            rows_all.extend(rows)
            last_close = rows[-1][6]  # close_time
            cur_start = int(last_close) + 1
            if len(rows) < _MAX_LIMIT:
                break
            time.sleep(0.03)
        return _to_df(rows_all)

    # Caso 3: compat
    rows = cli.futures_klines(symbol=symbol, interval=interval, limit=1000)
    return _to_df(rows)

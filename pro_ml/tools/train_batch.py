
import argparse
import os
import yaml
import json
from copy import deepcopy
from pathlib import Path
from datetime import datetime

# Reuse training components
from pro_ml.core.training.train import run_training as run_single_training
from pro_bot.config import settings
from pro_bot.core.symbols import top_usdtm_symbols_by_quote_volume

def patch_cfg_for_symbol(cfg: dict, symbol: str) -> dict:
    cfg = deepcopy(cfg)
    # Ensure outputs dir
    os.makedirs('outputs/models', exist_ok=True)
    # Patch datasource for Mongo or CSV
    kind = cfg['datasource']['kind']
    cfg['datasource']['symbol'] = symbol
    # Conventional names: klines_{SYMBOL}_1m
    if kind == 'mongo':
        col_base = cfg['datasource']['mongo'].get('collection', 'klines_SYMBOL_1m')
        if 'SYMBOL' in col_base:
            cfg['datasource']['mongo']['collection'] = col_base.replace('SYMBOL', symbol)
        else:
            cfg['datasource']['mongo']['collection'] = f'klines_{symbol}_1m'
    elif kind == 'csv':
        path = cfg['datasource']['csv'].get('path', './data/SYMBOL_1m.csv')
        if 'SYMBOL' in path:
            cfg['datasource']['csv']['path'] = path.replace('SYMBOL', symbol)
        else:
            # fallback: ./data/{symbol}_1m.csv
            p = Path(path)
            cfg['datasource']['csv']['path'] = str(p.parent / f"{symbol}_1m.csv")
    return cfg

def move_outputs_to_symbol(symbol: str):
    """Rename global outputs to symbol-specific names if exist."""
    import shutil
    src_model = Path('outputs/models/best_model.joblib')
    src_meta  = Path('outputs/models/metadata.joblib')
    if src_model.exists():
        dst_model = Path(f'outputs/models/{symbol}_best_model.joblib')
        shutil.move(str(src_model), str(dst_model))
    if src_meta.exists():
        dst_meta = Path(f'outputs/models/{symbol}_metadata.joblib')
        shutil.move(str(src_meta), str(dst_meta))

def main():
    ap = argparse.ArgumentParser(description='Batch training per symbol (top-N or custom list).')
    ap.add_argument('--cfg', default='configs/ml.yaml', help='Base YAML config')
    ap.add_argument('--symbols', default='', help='Comma-separated symbol list (overrides discovery)')
    ap.add_argument('--topN', type=int, default=None, help='If provided, train top-N by 24h quoteVolume (USDT-M PERP)')
    ap.add_argument('--fast', action='store_true', help='Fast mode: reduce Optuna trials to speed up')
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.cfg, 'r'))

    # Fast mode: cut trials
    if args.fast:
        cfg.setdefault('optuna', {})
        cfg['optuna']['n_trials'] = min(20, int(cfg['optuna'].get('n_trials', 80)))
        cfg['optuna']['timeout'] = cfg['optuna'].get('timeout', None)

    if args.symbols.strip():
        symbols = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
    else:
        n = args.topN if args.topN is not None else (settings.top_n_symbols if getattr(settings, 'top_n_symbols', None) else 20)
        print(f"Discovering top {n} symbols by 24h quoteVolume (USDT-M PERP)...")
        symbols = top_usdtm_symbols_by_quote_volume(n)

    print("Training symbols:", symbols)

    report = {}
    for sym in symbols:
        print(f"\n=== [{sym}] training ===")
        cfg_sym = patch_cfg_for_symbol(cfg, sym)
        # Write a temp cfg to avoid threading issues
        tmp_cfg_path = f'outputs/models/_tmp_{sym}_cfg.yaml'
        os.makedirs('outputs/models', exist_ok=True)
        with open(tmp_cfg_path, 'w') as f:
            yaml.safe_dump(cfg_sym, f)

        # Run single training using patched cfg
        run_single_training(tmp_cfg_path)

        # Move outputs to symbol-specific filenames
        move_outputs_to_symbol(sym)

        # Load metadata for summary, if exists
        meta_path = f'outputs/models/{sym}_metadata.joblib'
        try:
            import joblib
            meta = joblib.load(meta_path)
            report[sym] = {
                'best_params': meta.get('best_params', {}),
                'metrics': meta.get('metrics', {}),
            }
        except Exception as e:
            report[sym] = {'error': str(e)}

    # Save batch report
    stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    with open(f'outputs/reports/train_batch_{stamp}.json', 'w') as f:
        json.dump(report, f, indent=2)
    print("\nBatch report saved to outputs/reports/")


if __name__ == '__main__':
    main()

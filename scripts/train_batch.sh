
#!/usr/bin/env bash
set -euo pipefail

CFG="${1:-configs/ml.yaml}"
SYMBOLS="${2:-}"
TOPN="${3:-20}"
FAST="${4:-0}"

PY="./.venv/bin/python"
if [ ! -x "$PY" ]; then PY="python3"; fi

CMD=("$PY" "-m" "pro_ml.tools.train_batch" "--cfg" "$CFG")
if [ -n "$SYMBOLS" ]; then
  CMD+=("--symbols" "$SYMBOLS")
else
  CMD+=("--topN" "$TOPN")
fi
if [ "$FAST" != "0" ]; then
  CMD+=("--fast")
fi

echo "Running: ${CMD[@]}"
"${CMD[@]}"

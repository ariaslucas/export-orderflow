#!/bin/bash

BASE_DIR="/Users/lucasarias/orderflow-extractor"
PYTHON_EXE="$BASE_DIR/.venv/bin/python"
SCRIPT_PY="$BASE_DIR/orderflow_extractor.py"
OUTPUT_FILE="/Users/lucasarias/Library/CloudStorage/GoogleDrive-arias.lucas95@gmail.com/Mi unidad/Trading/orderflow.txt"

if [ ! -f "$PYTHON_EXE" ]; then
    echo "ERROR: Entorno virtual no encontrado en $PYTHON_EXE"
    exit 1
fi

if [ ! -f "$SCRIPT_PY" ]; then
    echo "ERROR: Script no encontrado en $SCRIPT_PY"
    exit 1
fi

while true; do
    "$PYTHON_EXE" "$SCRIPT_PY" -s BTCUSDT -t 5m -c 30 --clipboard --output "$OUTPUT_FILE"
    sleep 60
done
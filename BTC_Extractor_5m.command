#!/bin/bash
echo ""
echo "======================================================="
echo "EXTRACCION DE ORDER FLOW - BTCUSDT 5m"
echo "======================================================="
echo ""

# Directorio actual del script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# En Mac solemos usar python3 por defecto
python3 "$DIR/orderflow_extractor.py" -s BTCUSDT -t 5m -c 30 --clipboard

echo ""
echo "Presione ENTER para cerrar..."
read

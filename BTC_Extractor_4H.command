#!/bin/bash
echo ""
echo "======================================================="
echo "EXTRACCION DE ORDER FLOW - BTCUSDT 4H (10 Velas)"
echo "======================================================="
echo ""

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
python3 "$DIR/orderflow_extractor.py" -s BTCUSDT -t 4h -c 10 --clipboard

echo ""
echo "Presione ENTER para cerrar..."
read

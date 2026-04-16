#!/bin/bash
echo ""
echo "======================================================="
echo "EXTRACCION DE ORDER FLOW - ETHUSDT 1H (24 Velas)"
echo "======================================================="
echo ""

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
python3 "$DIR/orderflow_extractor.py" -s ETHUSDT -t 1h -c 24 --clipboard

echo ""
echo "Presione ENTER para cerrar..."
read

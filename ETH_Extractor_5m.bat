@echo off
echo.
echo =======================================================
echo EXTRACCION DE ORDER FLOW - ETHUSDT 5m
echo =======================================================
echo.

"C:\Trading\Lab\.venv\Scripts\python.exe" "%~dp0orderflow_extractor.py" -s ETHUSDT -t 5m -c 30 --clipboard

echo.
echo Presione cualquier tecla para cerrar...
pause >nul

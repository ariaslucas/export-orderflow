@echo off
echo.
echo =======================================================
echo EXTRACCION DE ORDER FLOW - ETHUSDT 1H (24 Velas)
echo =======================================================
echo.

"C:\Trading\Lab\.venv\Scripts\python.exe" "%~dp0orderflow_extractor.py" -s ETHUSDT -t 1h -c 24 --clipboard

echo.
echo Presione cualquier tecla para cerrar...
pause >nul

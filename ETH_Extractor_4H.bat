@echo off
echo.
echo =======================================================
echo EXTRACCION DE ORDER FLOW - ETHUSDT 4H (10 Velas)
echo =======================================================
echo.

"C:\Trading\Lab\.venv\Scripts\python.exe" "%~dp0orderflow_extractor.py" -s ETHUSDT -t 4h -c 10 --clipboard

echo.
echo Presione cualquier tecla para cerrar...
pause >nul

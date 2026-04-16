@echo off
echo.
echo =======================================================
echo EXTRACCION DE ORDER FLOW - BTCUSDT 5m (LOOP 60s)
echo =======================================================
echo Presione Ctrl+C para detener
echo.

:loop
"C:\Trading\Lab\.venv\Scripts\python.exe" "%~dp0orderflow_extractor.py" -s BTCUSDT -t 5m -c 30 --clipboard --output "%~dp0orderflow.txt"
copy /Y "%~dp0orderflow.txt" "G:\Mi unidad\Trading\orderflow.txt" >nul 2>&1
copy /Y "%~dp0orderflow.csv" "G:\Mi unidad\Trading\orderflow.csv" >nul 2>&1
powershell -Command "for ($i=60; $i -ge 1; $i--) { Write-Host \"`r  Proxima extraccion en $i seg...  \" -NoNewline; Start-Sleep -Seconds 1 }; Write-Host ''"
goto loop
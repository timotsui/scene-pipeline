@echo off
rem Double-click launcher for the asset inspection viewer
rem (composition/asset_viewer.py): orbit any single catalog asset referenced
rem by the scene, for checking mesh quality / canonical yaw / facing.
rem Close this window to stop the server.
set SCENE=bedroom_marble
set PORT=8323
cd /d "%~dp0composition"
echo Starting asset viewer for %SCENE% at http://localhost:%PORT% ...
echo (close this window to stop it)
start /min cmd /c "timeout /t 2 >nul & start http://localhost:%PORT%"
python asset_viewer.py --scene %SCENE% --port %PORT%
pause

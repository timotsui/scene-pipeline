@echo off
rem Double-click launcher for the interactive 3D placement viewer
rem (entangled_gen/viewer/serve.py). Opens the browser after the server is
rem up. Close this window to stop the server.
rem Optional: drag-drop nothing / edit SCENE below to change the default.
set SCENE=bedroom_marble
set PORT=8321
cd /d "%~dp0entangled_gen"
echo Starting viewer for %SCENE% at http://localhost:%PORT% ...
echo (scene dropdown in the page switches scenes; close this window to stop)
start /min cmd /c "timeout /t 2 >nul & start http://localhost:%PORT%/?scene=%SCENE%"
python viewer\serve.py --scene %SCENE% --port %PORT%
pause

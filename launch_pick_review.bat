@echo off
rem Double-click launcher for the retrieval pick-review viewer
rem (composition/review_server.py): per-box candidate strips (dimension-fit
rem + CLIP order) for judging the retrieval stages.
rem Close this window to stop the server.
set SCENE=bedroom_marble
set PORT=8322
cd /d "%~dp0composition"
echo Starting pick-review viewer for %SCENE% at http://localhost:%PORT% ...
echo (close this window to stop it)
start /min cmd /c "timeout /t 2 >nul & start http://localhost:%PORT%"
python review_server.py --scene %SCENE% --port %PORT%
pause

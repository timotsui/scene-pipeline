@echo off
rem Double-click launcher for the lift-only benchmark viewer.
rem Streams the trained Gaussian PLYs from the machine-local Hypersim output.
rem Close this window to stop the server.
set SCENE=ai_051_002
set PORT=8765
set "BENCHMARK_ROOT=%~dp0..\CS-8903-OVM\week7\entangled_gen\out\lifting_benchmark\hypersim"
set "VIEWER_URL=http://localhost:%PORT%/benchmarks/lifting/reports/scene3d/?scene=%SCENE%"

if not exist "%BENCHMARK_ROOT%\training\%SCENE%_gsplat5000\ply\point_cloud_4999.ply" (
  echo Could not find the lifting benchmark splats at:
  echo %BENCHMARK_ROOT%
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 'http://localhost:%PORT%/benchmarks/lifting/reports/scene3d/data/manifest.json'; if($r.StatusCode -eq 200){exit 0} } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
  echo The lift-only viewer is already running. Opening it now.
  start "" "%VIEWER_URL%"
  exit /b 0
)

cd /d "%~dp0"
echo Starting the lift-only viewer at %VIEWER_URL% ...
echo Five scenes are available in the dropdown. Close this window to stop.
start /min cmd /c "timeout /t 2 >nul & start %VIEWER_URL%"
python benchmarks\lifting\serve_scene3d.py --benchmark-root "%BENCHMARK_ROOT%" --port %PORT%
pause

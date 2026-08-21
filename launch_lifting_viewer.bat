@echo off
rem Double-click launcher for the lift-only pipeline walkthrough.
rem The walkthrough links to the heavier interactive 3D splat viewer on demand.
rem Close this window to stop the server.
set SCENE=ai_051_002
set PORT=8765
set "BENCHMARK_ROOT=%~dp0..\CS-8903-OVM\week7\entangled_gen\out\lifting_benchmark\hypersim"
set "VIEWER_URL=http://localhost:%PORT%/benchmarks/lifting/reports/pipeline_walkthrough/?scene=%SCENE%&stage=input"

if not exist "%BENCHMARK_ROOT%\training\%SCENE%_gsplat5000\ply\point_cloud_4999.ply" (
  echo Could not find the lifting benchmark splats at:
  echo %BENCHMARK_ROOT%
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 'http://localhost:%PORT%/benchmarks/lifting/reports/scene3d/data/manifest.json'; if($r.StatusCode -eq 200){exit 0} } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
  echo The lift-only report server is already running. Opening the walkthrough now.
  start "" "%VIEWER_URL%"
  exit /b 0
)

cd /d "%~dp0"
echo Starting the lift-only walkthrough at %VIEWER_URL% ...
echo Five scenes and ten executed stages are available. Close this window to stop.
start /min cmd /c "timeout /t 2 >nul & start %VIEWER_URL%"
python benchmarks\lifting\serve_scene3d.py --benchmark-root "%BENCHMARK_ROOT%" --port %PORT%
pause

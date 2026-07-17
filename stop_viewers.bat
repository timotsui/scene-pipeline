@echo off
rem Stop any viewer servers still holding the viewer ports (orphans started
rem outside the launcher windows). Kills whatever LISTENS on 8321 (3D
rem placement viewer), 8322 (pick review), 8323 (asset viewer).
rem Launcher-window servers don't need this: closing their window stops them.
powershell -NoProfile -Command ^
  "$pids = 8321,8322,8323 | ForEach-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue } | Select-Object -ExpandProperty OwningProcess -Unique; if (-not $pids) { Write-Host 'no viewer servers running' } else { foreach ($p in $pids) { $n = (Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName; Write-Host ('stopping PID ' + $p + ' (' + $n + ')'); Stop-Process -Id $p -Force } }"
pause

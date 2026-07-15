# launch_m3d_video_guarded.ps1 -- the ONLY approved way to start the m3d
# video retry after the 2026-07-06 12:56 hard freeze. Applies the GPU power
# guard (clock lock), arms the deadman watchdog, THEN starts the run in one
# hidden persistent wsl.exe. A run needs BOTH guards:
#   deadman    = RAM/freeze guard (12:56 swap-thrash class)
#   clock lock = power guard (16:57 EC instant-off class; resets EVERY reboot)
#
# MUST run from an ELEVATED PowerShell (nvidia-smi -lgc needs admin):
#   powershell -NoProfile -ExecutionPolicy Bypass -File launch_m3d_video_guarded.ps1
#
# Watch progress:
#   Get-Content <out>\logs\m3d_video_bedroom_hw1.log -Tail 20 -Wait
#   Get-Content <out>\logs\m3d_video_bedroom_hw1_resources.log -Tail 5 -Wait
#   Get-Content <out>\logs\deadman.log -Tail 5 -Wait
# When the run finishes (or dies): Stop-Process -Id <deadman pid printed below>

$ErrorActionPreference = 'Stop'
$Tools  = $PSScriptRoot
$OutWin = 'D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out'
$Start  = '/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/matrix3d/start_m3d_video.sh'

# preflight 0: GPU clock lock (power guard). Resets on every reboot; the
# 2026-07-06 16:57 crash was an EC power trip because it was missing. The only
# reliable confirmation is nvidia-smi's own "GPU clocks set to" line --
# clocks.max.gr always reports hardware max even when locked. Idempotent.
$lockOut = (nvidia-smi -lgc 300,1500) -join ' '
if ($lockOut -notmatch 'GPU clocks set to') {
    throw "GPU clock lock FAILED (not elevated?). nvidia-smi said: $lockOut"
}
Write-Host "GPU power guard: $lockOut"

# preflight: pano present, swap cap really lowered (a stale 40GB is the killer)
if (-not (Test-Path "$OutWin\bedroom_hw1\panorama.png")) { throw 'panorama.png missing for bedroom_hw1' }
$wslconf = Get-Content "$env:USERPROFILE\.wslconfig" -Raw
if ($wslconf -notmatch '(?m)^swap=24GB') { throw '.wslconfig swap is not 24GB -- fix before launching' }
# wsl.exe prints UTF-16 -- strip the interleaved nulls before matching
$running = ((wsl.exe --list --running) -join ' ') -replace "`0", ''
if ($running -match 'Ubuntu') { Write-Host 'NOTE: WSL already running -- config changes only apply after a full stop.' }

# 1. arm the deadman (hidden, survives this console)
$dm = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"$Tools\deadman.ps1" `
    -WindowStyle Hidden -PassThru
Write-Host "deadman ARMED pid=$($dm.Id) (log: $OutWin\logs\deadman.log)"

# 2. one hidden persistent wsl.exe running the zero-arg start script
$job = Start-Process wsl.exe -ArgumentList '-d','Ubuntu-24.04','--','bash',$Start `
    -WindowStyle Hidden -PassThru
Write-Host "m3d video LAUNCHED wsl.exe pid=$($job.Id) (job log: $OutWin\logs\m3d_video_bedroom_hw1.log)"
Write-Host "Expected outcome: pano_video.mp4, a clean cgroup OOM-kill, or a deadman trip -- NOT a frozen box."

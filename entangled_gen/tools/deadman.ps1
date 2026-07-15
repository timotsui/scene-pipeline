# deadman.ps1 -- Windows-side machine guard for heavy WSL gen runs.
#
# Saved as a file after 2026-07-06: the original lived only inside a Claude
# session and died with it -- the 12:56 m3d video run then hard-froze the box
# with no guard armed (hard reset). Arm this BEFORE any runtime-risky launch:
#   powershell -NoProfile -ExecutionPolicy Bypass -File deadman.ps1
# (launch_m3d_video_guarded.ps1 arms it hidden, automatically.)
#
# Trips `wsl --shutdown` on any of:
#   1. Windows free RAM < MinFreeMB        (the 00:58 + 01:45 incident mode)
#   2. WSL unresponsive ProbeFailTrip times in a row (~2 min)   (freeze mode)
#   3. WSL swap used > SwapTripMB for SwapTrip consecutive samples (~2 min)
#      -- sustained near-cap swap is thrash; with swap=24GB the kernel
#      OOM-killer should fire first, this is the backstop.
#
# The 20 s probe (`wsl free -m`) doubles as VM keepalive. STOP the watchdog
# once the run is done (PID is logged + printed): Stop-Process -Id <pid>.
#
# NOT SUFFICIENT ALONE: this guards RAM/freeze deaths only. The 2026-07-06
# 16:57 crash was an EC power trip under sustained GPU load -- deadman was
# armed and reading "ok" 20 s before the box went dark. Every risky run also
# needs the power guard: `nvidia-smi -lgc 300,1500` (elevated; RESETS EVERY
# REBOOT; only confirmation is the command's own "GPU clocks set to" output).
# launch_m3d_video_guarded.ps1 applies both.

param(
    [string]$Distro     = 'Ubuntu-24.04',
    [int]$MinFreeMB     = 1200,
    [int]$SwapTripMB    = 20000,
    [int]$SwapTrip      = 6,      # consecutive samples over SwapTripMB
    [int]$ProbeFailTrip = 3,      # consecutive probe timeouts
    [int]$ProbeTimeoutS = 45,
    [int]$IntervalS     = 20,
    [string]$LogPath    = 'D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\logs\deadman.log'
)

function Log([string]$msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $LogPath -Value $line
    Write-Host $line
}

function Trip([string]$reason) {
    Log "TRIP: $reason -> wsl --shutdown"
    wsl.exe --shutdown
    Start-Sleep -Seconds 5
    $os = Get-CimInstance Win32_OperatingSystem
    Log ("post-shutdown Windows free RAM = {0} MB. Watchdog exiting." -f [math]::Round($os.FreePhysicalMemory/1KB))
    exit 1
}

Log "ARMED pid=$PID distro=$Distro minfree=${MinFreeMB}MB swaptrip=${SwapTripMB}MBx$SwapTrip probefail=x$ProbeFailTrip interval=${IntervalS}s"

$probeFails = 0
$swapHits   = 0
$probeOut   = Join-Path $env:TEMP "deadman_probe_$PID.txt"
$probeErr   = Join-Path $env:TEMP "deadman_probe_$PID.err"

while ($true) {
    # 1. Windows free RAM -- immediate trip
    $os = Get-CimInstance Win32_OperatingSystem
    $freeMB = [math]::Round($os.FreePhysicalMemory/1KB)
    if ($freeMB -lt $MinFreeMB) { Trip "Windows free RAM ${freeMB}MB < ${MinFreeMB}MB" }

    # 2+3. WSL responsiveness + swap level (probe also keeps the VM alive)
    $swapUsed = -1
    $p = Start-Process -FilePath wsl.exe -ArgumentList '-d', $Distro, '--', 'free', '-m' `
        -RedirectStandardOutput $probeOut -RedirectStandardError $probeErr `
        -WindowStyle Hidden -PassThru
    if (-not $p.WaitForExit($ProbeTimeoutS * 1000)) {
        try { $p.Kill() } catch {}
        $probeFails++
        Log "probe TIMEOUT ($probeFails/$ProbeFailTrip) winfree=${freeMB}MB"
        if ($probeFails -ge $ProbeFailTrip) { Trip "WSL unresponsive $probeFails probes (~$([int]($probeFails*($IntervalS+$ProbeTimeoutS)/60)) min)" }
    } else {
        $probeFails = 0
        foreach ($line in (Get-Content $probeOut)) {
            if ($line -match '^Swap:\s+\d+\s+(\d+)') { $swapUsed = [int]$matches[1] }
        }
        if ($swapUsed -gt $SwapTripMB) {
            $swapHits++
            Log "swap HIGH ${swapUsed}MB ($swapHits/$SwapTrip) winfree=${freeMB}MB"
            if ($swapHits -ge $SwapTrip) { Trip "WSL swap ${swapUsed}MB > ${SwapTripMB}MB for $swapHits samples" }
        } else {
            $swapHits = 0
            Log "ok winfree=${freeMB}MB wslswap=${swapUsed}MB"
        }
    }
    Start-Sleep -Seconds $IntervalS
}

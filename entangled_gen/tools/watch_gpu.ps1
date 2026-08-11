# watch_gpu.ps1 — crash forensics logger for the laptop's hard power-off problem.
#
# WHY THIS EXISTS
#   This machine hard-powers-off under GPU burst (no bugcheck, no minidump —
#   Windows logs Kernel-Power 41 with BugcheckCode=0, i.e. it lost power
#   mid-instruction). When that happens there is NO postmortem evidence unless
#   something was writing the GPU/battery state to disk as it went.
#
# WHAT IT DOES
#   Samples once a second and appends ONE LINE PER SAMPLE, flushed and closed
#   every time, so the last line on disk is the last moment the machine was
#   alive. That last line is the whole point — do not buffer it.
#
# COLUMNS
#   timestamp, gpu_temp_C, gpu_power_W, sm_clock_MHz, gpu_mem_MiB, gpu_util_%, ac_online, batt_rate_mW, batt_pct
#
#   The first six match the pre-existing gpu_watch.csv format exactly, so old
#   and new samples read the same. The last three are new: if the cause really
#   is power delivery rather than the GPU itself, the AC/battery state in the
#   final seconds is the evidence that shows it.
#
# USAGE
#   powershell -ExecutionPolicy Bypass -File watch_gpu.ps1 [-OutFile <path>]
#   Runs until killed. Launch it detached (WMI Win32_Process.Create) if it must
#   outlive the shell that started it.

param(
    [string]$OutFile = "D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\logs\gpu_watch.csv",
    [int]$IntervalMs = 1000
)

$ErrorActionPreference = 'Continue'

$dir = Split-Path -Parent $OutFile
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

Add-Content -Path $OutFile -Encoding utf8 -Value "=== watch start $((Get-Date).ToString('o')) pid=$PID cols=timestamp,temp_C,power_W,sm_MHz,mem_MiB,util_pct,ac_online,batt_rate_mW,batt_pct ==="

# Read the battery/AC state. Returns three fields, or n/a when WMI has nothing
# to say (desktop, or the battery class is unavailable).
function Get-PowerState {
    try {
        $b = Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction Stop | Select-Object -First 1
        if ($null -eq $b) { return @('n/a', 'n/a', 'n/a') }
        $ac = if ($b.PowerOnline) { 1 } else { 0 }
        # DischargeRate and ChargeRate are mW and mutually exclusive; sign the
        # single number so one column carries both (negative = draining).
        $rate = if ($b.DischargeRate -gt 0) { -1 * $b.DischargeRate } else { $b.ChargeRate }
        $pct = 'n/a'
        $full = Get-CimInstance -Namespace root\wmi -ClassName BatteryFullChargedCapacity -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($full -and $full.FullChargedCapacity -gt 0) {
            $pct = [math]::Round(100.0 * $b.RemainingCapacity / $full.FullChargedCapacity, 1)
        }
        return @($ac, $rate, $pct)
    } catch {
        return @('n/a', 'n/a', 'n/a')
    }
}

# One long-lived nvidia-smi in loop mode: one process, not one per second.
$query = 'timestamp,temperature.gpu,power.draw,clocks.sm,memory.used,utilization.gpu'
& nvidia-smi --query-gpu=$query --format=csv,noheader "-lms" $IntervalMs 2>$null | ForEach-Object {
    $line = $_.Trim()
    if ($line.Length -eq 0) { return }
    $p = Get-PowerState
    # Add-Content opens, writes and closes — the line is on disk before the
    # next sample is taken. That survives a power cut; a buffered stream does not.
    Add-Content -Path $OutFile -Encoding utf8 -Value ("{0}, {1}, {2}, {3}" -f $line, $p[0], $p[1], $p[2])
}

Add-Content -Path $OutFile -Encoding utf8 -Value "=== watch stop $((Get-Date).ToString('o')) (nvidia-smi exited) ==="

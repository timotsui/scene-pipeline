# install_gpu_clock_lock.ps1 — register the boot-time GPU clock lock.
#
# WHY: this laptop hard-powers-off under GPU burst load. The fix is
#   nvidia-smi -lgc 0,1500  (see docs/POWER_CRASHES.md). Windows has no
#   persistence mode, so the lock dies on every reboot — and since the failure
#   IS a reboot, every crash silently clears it and the next run goes
#   unprotected. A boot-triggered task closes that gap.
#
# THIS SCRIPT MUST RUN ELEVATED. It creates ONE scheduled task and changes
# nothing else. To undo: uninstall_gpu_clock_lock.ps1 (or see the bottom).

#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'

$TaskName = 'GPUClockLock'
$Exe      = 'C:\Windows\system32\nvidia-smi.exe'
$LockArgs = '-lgc 0,1500'

if (-not (Test-Path $Exe)) { throw "nvidia-smi not found at $Exe" }

# Replace any previous version of this task so re-running is safe.
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Existing '$TaskName' found — replacing it."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action  = New-ScheduledTaskAction -Execute $Exe -Argument $LockArgs
$trigger = New-ScheduledTaskTrigger -AtStartup

# Run as SYSTEM so the lock is applied before anyone logs in, and so the task
# can be triggered later WITHOUT a UAC prompt.
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' `
                                        -LogonType ServiceAccount `
                                        -RunLevel Highest

# The default task settings would sabotage this on a laptop: Windows refuses to
# start tasks on battery and kills running ones when you unplug. Both are
# disabled explicitly — the lock must hold regardless of power source.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName    $TaskName `
                       -Action      $action `
                       -Trigger     $trigger `
                       -Principal   $principal `
                       -Settings    $settings `
                       -Description 'Pins GPU SM clocks to <=1500 MHz at boot. Mitigates hard power-off under GPU burst load. See scene-pipeline/entangled_gen/docs/POWER_CRASHES.md' | Out-Null

Write-Host "Registered scheduled task '$TaskName':"
Write-Host "  runs   : $Exe $LockArgs"
Write-Host "  as     : SYSTEM (highest privileges)"
Write-Host "  when   : at every system startup"
Write-Host ""

# Apply it right now too, so the current boot is protected without a reboot.
Write-Host "Applying the lock to the current session..."
& $Exe -lgc 0,1500
Write-Host ""
& $Exe --query-gpu=clocks.max.sm,clocks.sm --format=csv

Write-Host ""
Write-Host "Done. To remove later, from an elevated shell:"
Write-Host "  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
Write-Host "  nvidia-smi -rgc"

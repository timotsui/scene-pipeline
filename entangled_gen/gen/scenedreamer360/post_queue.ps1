# post_queue.ps1 (2026-07-04) - Windows-side follow-on to overnight_queue.sh.
# Waits for the WSL generation queue to log "queue done", then per scene runs
# the extraction chain on the GPU (free again by then):
#   shot.py 4-yaw views -> seg_views.py (GroundingDINO+SAM) -> lift_views.py
# giving scene_manifest_<scene>.json for bedroom/livingroom/kitchen by morning.
# NB: ASCII only in this file - PS 5.1 reads no-BOM files as ANSI and UTF-8
# em-dash bytes decode to a curly quote that breaks string parsing.
# Launch detached:
#   Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',<this> -WindowStyle Hidden
$ROOT = "D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen"
$SHOT = "$ROOT\rendertools\shot.py"
$LOG  = "$ROOT\out\logs\postqueue.log"

function Log($m) { Add-Content $LOG "$(Get-Date -Format 'MM-dd HH:mm:ss') $m" }

Log "watcher start - polling queue.log for 'queue done' (5 min interval, 10 h cap)"
$deadline = (Get-Date).AddHours(10)
while ($true) {
    $q = Get-Content "$ROOT\out\logs\queue.log" -Raw -ErrorAction SilentlyContinue
    if ($q -and $q -match "queue done") { break }
    if ((Get-Date) -gt $deadline) { Log "TIMEOUT waiting for queue done - exiting"; exit 1 }
    Start-Sleep -Seconds 300
}
Log "queue done detected - starting extraction"

$LOOKS = [ordered]@{ "yaw000" = "0,0,3"; "yaw090" = "3,0,0"; "yaw180" = "0,0,-3"; "yaw270" = "-3,0,0" }

foreach ($sc in @("bedroom", "livingroom", "kitchen")) {
    $ply = "$ROOT\out\$sc\gen_raw.ply"
    if (-not (Test-Path $ply)) { Log "$sc SKIP - $ply missing (run failed?)"; continue }
    $slog = "$ROOT\out\logs\postqueue_$sc.log"
    $vdir = "$ROOT\out\$sc\views"
    New-Item -ItemType Directory -Force $vdir | Out-Null

    foreach ($k in $LOOKS.Keys) {
        $look = $LOOKS[$k]
        cmd /c "python `"$SHOT`" 0,0,0 $look --up 0,1,0 --fov 75 --res 900x900 --ply `"$ply`" --out `"$vdir\gpu_$k.webp`" --no-open >> `"$slog`" 2>&1"
        Log "$sc render $k rc=$LASTEXITCODE"
    }

    cmd /c "python `"$ROOT\seg_views.py`" --scene $sc >> `"$slog`" 2>&1"
    Log "$sc seg rc=$LASTEXITCODE"

    cmd /c "python `"$ROOT\lift_views.py`" --scene $sc >> `"$slog`" 2>&1"
    $ok = Test-Path "$ROOT\out\$sc\scene_manifest.json"
    Log "$sc lift rc=$LASTEXITCODE manifest_written=$ok"
}
Log "watcher done"

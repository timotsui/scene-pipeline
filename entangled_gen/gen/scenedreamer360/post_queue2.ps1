# post_queue2.ps1 (2026-07-05) - extraction follow-on for the spatial-prompting
# experiment (queue2): per scene, 4-yaw views -> seg -> lift -> package.
# ASCII only in this file (PS 5.1 ANSI parsing gotcha).
$ROOT = "D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen"
$SHOT = "$ROOT\rendertools\shot.py"
$LOG  = "$ROOT\out\logs\postqueue2.log"

function Log($m) { Add-Content $LOG "$(Get-Date -Format 'MM-dd HH:mm:ss') $m" }

Log "watcher2 start - polling queue2.log for 'queue2 done' (5 min interval, 10 h cap)"
$deadline = (Get-Date).AddHours(10)
while ($true) {
    $q = Get-Content "$ROOT\out\logs\queue2.log" -Raw -ErrorAction SilentlyContinue
    if ($q -and $q -match "queue2 done") { break }
    if ((Get-Date) -gt $deadline) { Log "TIMEOUT waiting for queue2 done - exiting"; exit 1 }
    Start-Sleep -Seconds 300
}
Log "queue2 done detected - starting extraction"

$LOOKS = [ordered]@{ "yaw000" = "0,0,3"; "yaw090" = "3,0,0"; "yaw180" = "0,0,-3"; "yaw270" = "-3,0,0" }
$VOCABS = @{
    "ctrlroom"      = "chair. door. window. picture. lamp.";
    "bedroomdim"    = "bed. nightstand. wardrobe. dresser. lamp. window. door. rug. pillow. curtain. picture. chair.";
    "livingspatial" = "sofa. couch. armchair. coffee table. television. rug. lamp. window. curtain. picture. door.";
    "bedroom_s1"    = "bed. nightstand. wardrobe. dresser. lamp. window. door. rug. pillow. curtain. picture. chair."
}

foreach ($sc in @("ctrlroom", "bedroomdim", "livingspatial", "bedroom_s1")) {
    $ply = "$ROOT\out\$sc\gen_raw.ply"
    if (-not (Test-Path $ply)) { Log "$sc SKIP - $ply missing (run failed?)"; continue }
    $slog = "$ROOT\out\logs\postqueue2_$sc.log"
    $vdir = "$ROOT\out\$sc\views"
    New-Item -ItemType Directory -Force $vdir | Out-Null

    foreach ($k in $LOOKS.Keys) {
        $look = $LOOKS[$k]
        cmd /c "python `"$SHOT`" 0,0,0 $look --up 0,1,0 --fov 75 --res 900x900 --ply `"$ply`" --out `"$vdir\gpu_$k.webp`" --no-open >> `"$slog`" 2>&1"
        Log "$sc render $k rc=$LASTEXITCODE"
    }

    $vocab = $VOCABS[$sc]
    cmd /c "python `"$ROOT\seg_views.py`" --scene $sc --prompt `"$vocab`" >> `"$slog`" 2>&1"
    Log "$sc seg rc=$LASTEXITCODE"

    cmd /c "python `"$ROOT\lift_views.py`" --scene $sc >> `"$slog`" 2>&1"
    Log "$sc lift rc=$LASTEXITCODE manifest=$(Test-Path "$ROOT\out\$sc\scene_manifest.json")"

    cmd /c "python `"$ROOT\agent_package.py`" --scene $sc >> `"$slog`" 2>&1"
    Log "$sc package rc=$LASTEXITCODE"
}
Log "watcher2 done"

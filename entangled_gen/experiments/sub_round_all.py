"""SUB ROUNDS — FLEET DRIVER: level-1 recursion over every anchor
with deferred subs (canon SR0–SR7, PLAN_SUB_ROUNDS.md).

Runs cp1 → cp2 → cp3 → cp4 --aligned → cp5 --align (the canon path)
per anchor, sequentially (GPU renders pace the laptop — the crash
gotcha), collecting per-anchor status; a failing anchor is recorded
and skipped, never a fleet-killer. Ends by writing the OVERVIEW page:
sub_experiment/index.html — one row per anchor (counts, flags,
level-2 deferrals, links to every checkpoint page, the cp5 front
shot inline).

  python sub_round_all.py [--scene bedroom_marble] [--only id,id]
"""
import argparse
import html
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
import paths  # noqa: E402

STEPS = [
    ("cp1", ["sub_round_cp1.py"]),
    ("cp2", ["sub_round_cp2.py"]),
    ("cp3", ["sub_round_cp3.py"]),
    ("cp4", ["sub_round_cp4.py", "--aligned"]),
    ("cp5", ["sub_round_cp5.py", "--align", "--picks-dir", "cp4_aligned",
             "--out", "cp5_final"]),
    ("cp6", ["sub_round_cp6.py"]),
    ("cp7", ["sub_round_cp7.py"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--only", default=None)
    ap.add_argument("--overview-only", action="store_true",
                    help="rebuild index.html from what's on disk — no "
                         "steps run (use after --only reruns, which "
                         "would otherwise shrink the overview)")
    a = ap.parse_args()

    cdir = paths.compose_dir(a.scene)
    sl = json.loads((cdir / "shopping.json").read_text("utf-8"))
    anchors = sorted({s["anchor"] for s in sl["subs_deferred"]})
    if a.only and not a.overview_only:
        anchors = [x.strip() for x in a.only.split(",") if x.strip()]
    names = {it["id"]: it["name"] for it in sl["items"]}
    n_subs = {}
    for s in sl["subs_deferred"]:
        n_subs[s["anchor"]] = n_subs.get(s["anchor"], 0) + 1

    if a.overview_only:
        root = cdir / "sub_experiment"
        fleet = [{"anchor": oid, "name": names.get(oid, "?"),
                  "n_subs": n_subs.get(oid, 0), "steps": {},
                  "ok": (root / oid / "cp5_final"
                         / "placements.json").exists()
                  or (root / oid / "cp3" / "assignment.json").exists()}
                 for oid in anchors]
        build_overview(root, a.scene, fleet)
        print(f"[fleet] overview rebuilt from disk: "
              f"{root / 'index.html'}")
        return

    fleet = []
    t0 = time.time()
    for oid in anchors:
        st = {"anchor": oid, "name": names.get(oid, "?"),
              "n_subs": n_subs.get(oid, 0), "steps": {}, "ok": True}
        print(f"=== {oid} ({st['name']}, {st['n_subs']} subs) ===",
              flush=True)
        for step, cmd in STEPS:
            t1 = time.time()
            r = subprocess.run(
                [sys.executable, str(HERE / cmd[0]), "--scene", a.scene,
                 "--anchor", oid] + cmd[1:],
                capture_output=True, text=True)
            dt = round(time.time() - t1, 1)
            tail = (r.stdout or "").strip().splitlines()[-2:]
            st["steps"][step] = {"rc": r.returncode, "s": dt,
                                 "tail": tail}
            print(f"  {step}: rc={r.returncode} {dt}s", flush=True)
            if r.returncode != 0:
                st["ok"] = False
                st["error"] = (r.stderr or "").strip().splitlines()[-8:]
                print("  STOP (recorded):",
                      "\n    ".join(st["error"]), flush=True)
                break
            time.sleep(2)   # pace GPU bursts (laptop power gotcha)
        fleet.append(st)

    root = cdir / "sub_experiment"
    (root / "fleet.json").write_text(
        json.dumps({"scene": a.scene, "elapsed_s": round(time.time() - t0),
                    "anchors": fleet}, indent=1), encoding="utf-8")
    build_overview(root, a.scene, fleet)
    ok = sum(1 for f in fleet if f["ok"])
    print(f"[fleet] {ok}/{len(fleet)} anchors clean, "
          f"{round(time.time()-t0)}s total")
    print(f"[fleet] overview: {root / 'index.html'}")


def build_overview(root, scene, fleet):
    css = """
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#141414;color:#e8e8e8;
     font:15px/1.55 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1560px;margin:0 auto;padding:28px 32px 120px}
h1{font-size:24px;margin:0 0 4px}
.sub{color:#9a9a9a;margin:0 0 20px}
.contract{background:#1c1c1c;border-left:3px solid #ffd479;
          padding:14px 18px;margin:18px 0;border-radius:0 4px 4px 0}
.contract b{color:#ffd479}
.card{background:#191919;border:1px solid #2b2b2b;border-radius:7px;
      padding:14px 16px;margin:16px 0;display:grid;
      grid-template-columns:340px 1fr;gap:16px}
.card.bad{border-color:#5d3030}
.card img{width:100%;border-radius:4px;background:#000;display:block}
.hd{font-weight:600;font-size:16px;margin:0 0 6px}
.meta{color:#9a9a9a;font-size:13px;margin:2px 0}
.links a{color:#9dc6ff;font-size:13px;margin-right:12px}
.warn{color:#ff9d9d;font-size:13px}
.mono{font-family:Consolas,monospace;font-size:12.5px}
"""
    rows = []
    for f in fleet:
        oid = f["anchor"]
        adir = root / oid
        # pull per-cp summary numbers where the records exist
        bits = []
        warn = []
        try:
            s1 = json.loads((adir / "cp1" / "seeds.json").read_text("utf-8"))
            if s1.get("level2_deferred"):
                bits.append(f'level-2 deferred: '
                            f'{len(s1["level2_deferred"])}')
        except Exception:
            s1 = None
        try:
            s2 = json.loads((adir / "cp2" / "boards.json").read_text("utf-8"))
            bits.append(f'boards: {s2["n_boards"]}')
            if s2["n_boards"] == 0:
                warn.append("NO usable surface (SR2 skip)")
        except Exception:
            pass
        try:
            s3 = json.loads((adir / "cp3" / "assignment.json")
                            .read_text("utf-8"))
            if s3.get("n_flagged"):
                warn.append(f'cp3 flags: {s3["n_flagged"]}')
        except Exception:
            pass
        try:
            s4 = json.loads((adir / "cp4_aligned" / "picks.json")
                            .read_text("utf-8"))
            bits.append(f'picks: {sum(1 for r in s4["subs"] if r["pick"])}'
                        f'/{s4["n_subs"]}')
            if s4.get("n_flagged"):
                warn.append(f'pick flags: {s4["n_flagged"]}')
        except Exception:
            pass
        try:
            s5 = json.loads((adir / "cp5_final" / "placements.json")
                            .read_text("utf-8"))
            bits.append(f'placed: {s5["n_placed"]}')
            if s5.get("n_overlap_pairs"):
                warn.append(f'overlaps: {s5["n_overlap_pairs"]}')
        except Exception:
            pass
        if not f["ok"]:
            warn.append("STEP FAILED: " + next(
                (k for k, v in f["steps"].items() if v["rc"]), "?"))
        try:
            s6 = json.loads((adir / "cp6" / "placements_jiggled.json")
                            .read_text("utf-8"))
            if s6.get("n_placed"):
                bits.append(f'jiggle {s6["overlap_pairs_before"]}'
                            f'→{s6["overlap_pairs_after"]} ovl')
                if s6.get("overlap_pairs_after"):
                    warn.append(f'residual overlaps: '
                                f'{s6["overlap_pairs_after"]}')
        except Exception:
            pass
        try:
            s7 = json.loads((adir / "cp7" / "placements_walked.json")
                            .read_text("utf-8"))
            if s7.get("n_items"):
                bits.append(
                    f'cp7 xlvl {len(s7["cross_level_pairs_before"])}'
                    f'→{len(s7["cross_level_pairs_after"])} · host '
                    f'{len(s7["host_clips_before"])}'
                    f'→{len(s7["host_clips_after"])}')
                if s7.get("swaps"):
                    bits.append(f'{len(s7["swaps"])} walked')
                if s7.get("kills"):
                    warn.append(f'cp7 kills: {len(s7["kills"])}')
                if s7.get("dry"):
                    warn.append(f'cp7 dry: {len(s7["dry"])}')
        except Exception:
            pass
        links = []
        for cp in ("cp1", "cp2", "cp3", "cp4_aligned", "cp5_final",
                   "cp6", "cp7"):
            if (adir / cp / "index.html").exists():
                links.append(f'<a href="{oid}/{cp}/index.html">{cp}</a>')
        shot = (f'<img src="{oid}/cp7/front.png">'
                if (adir / "cp7" / "front.png").exists() else
                f'<img src="{oid}/cp6/front.png">'
                if (adir / "cp6" / "front.png").exists() else
                f'<img src="{oid}/cp5_final/front.png">'
                if (adir / "cp5_final" / "front.png").exists()
                else '<div class="meta">no final render</div>')
        rows.append(
            f'<div class="card{"" if f["ok"] else " bad"}">'
            f'<div>{shot}</div><div>'
            f'<p class="hd">{oid} · {html.escape(f["name"])} · '
            f'{f["n_subs"]} subs</p>'
            f'<p class="meta mono">{" · ".join(bits) or "no records"}</p>'
            + (f'<p class="warn">{" · ".join(warn)}</p>' if warn else "")
            + f'<p class="links">{" ".join(links)}</p>'
            '</div></div>')

    h = ['<!doctype html><meta charset="utf-8">',
         f'<title>sub rounds — fleet overview — {scene}</title>',
         f'<style>{css}</style><div class="wrap">',
         '<h1>Sub rounds — level-1 fleet overview</h1>',
         f'<p class="sub">{scene} · canon SR0–SR7 · one row per anchor '
         '· click into any checkpoint page</p>',
         '<div class="contract">'
         '<b>What this ran:</b> the support recursion at level 1 — '
         'seeds &rarr; boards &rarr; assignment &rarr; aligned shopping '
         '&rarr; aligned placement per anchor (PLAN_SUB_ROUNDS.md).<br>'
         '<b>What to judge:</b> per anchor, the cp5 front shot — things '
         'standing on real surfaces where the real ones are. Warnings '
         'are honest records (NO_BOARD skips, flags, overlaps), not '
         'errors.<br>'
         '<b>Not yet:</b> sub-level jiggle/check/walk · level-2 riders '
         '(deferred, hosts first) · merge into fitted_preview.</div>']
    h += rows
    h.append('</div>')
    (root / "index.html").write_text("\n".join(h), encoding="utf-8")


if __name__ == "__main__":
    main()

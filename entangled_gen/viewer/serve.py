"""
Live placement viewer server (multi-scene).

Any scene with viewer/data/<scene>.bin is servable; the browser picks via
?scene=X (dropdown in the HUD). Per-scene live placement files:
out/<scene>/live_placement.json — edit one and the browser updates in 0.5 s.
POST /capture saves canvas views to out/viewer_caps/ for LLM feedback.

Run:  python viewer/serve.py --scene bedroom --port 8321   (--scene = default only)
"""
import argparse, base64, json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import paths  # noqa: E402
sys.path.insert(0, str(ROOT / "graph"))
import scene_state  # noqa: E402

# set in main(); class H reads these module globals at request time
args = None
CAPS = None


def placement_file(sc):
    return paths.live_placement(sc)


def box_sources(sc):
    """Method-organized box sets (2026-07-25 reorg; 2026-07-26 grouped):
    one entry per detection/lift METHOD. group='current' = the canonical
    lane; group='archive' = superseded/reference methods, rendered in the
    HUD's collapsed archive section (files stay on disk — nothing deleted).
    Registry order = HUD order. Only entries whose file exists are served.

    2026-08-01 (user: latest-and-greatest only): registry EMPTIED — the
    resolved scene model is the one current view; every box-source layer
    below is superseded audit. Entries kept commented for one-line
    re-enable; all files remain on disk."""
    sd = paths.scene_dir(sc)
    # (2026-08-06: the temporary directional-prior A/B pair lived here for
    # the user eyeball — RULED same day, prior promoted, entries removed.)
    # 2026-08-06 TEMPORARY streak-surgery previews (R-S2-22 gate): remove
    # both when ruled.
    # The vote layer's label is composed LIVE from the manifest's own
    # provenance header (2026-08-08): a hard-coded "run 10" caption was
    # still showing while the file already held run 16 boxes. Never
    # hand-write a run number in a label again — read it.
    #
    # 2026-08-08 (user): "46 obj" read as "46 SLICED boxes", and it is not
    # — the layer draws each object's SHIPPING box, and only the
    # voted/voted_pano ones came out of a slice election at all. The
    # rest are geometric exemptions (flat wall/ceiling objects, perp-cam
    # re-boxed) or the ORIGINAL pre-vote box shipped because the slice
    # was too thin or the election blew past the outlier guard. The label
    # now says shipped / sliced / not-sliced, counted from the file.
    _sv = sd / "scene_manifest_slicevote_preview.json"
    _svlab = "vote stage"
    _svstat = "unreadable"
    _SLICED = ("voted", "voted_pano")   # went through the election
    _STATUSES = _SLICED + ("kept", "kept_wall", "kept_ceiling",
                           "kept_outlier")
    try:
        _h = json.loads(_sv.read_text(encoding="utf-8"))
        _n = len(_h.get("objects") or [])
        _tally = {}
        for _o in (_h.get("objects") or []):
            for _f in (_o.get("flags") or []):
                if isinstance(_f, str) and _f in _STATUSES:
                    _tally[_f] = _tally.get(_f, 0) + 1
                    break
        _svstat = " / ".join(f"{v} {k}" for k, v in sorted(_tally.items(),
                                                           key=lambda x:
                                                           -x[1]))
        _cut = sum(_tally.get(s, 0) for s in _SLICED)
        _svlab = ("vote stage · " + str(_h.get("run_id") or "?")
                  + (" · CANON-ELIGIBLE" if _h.get("canon_eligible")
                     else " · partial/mixed — NOT canon")
                  + f" · {_n} shipped ({_cut} sliced, {_n - _cut} "
                    f"exempt/kept)")
    except Exception:                                   # noqa: BLE001
        pass
    # LATEST-AND-GREATEST ORDER (user ruling 2026-08-08, restating the
    # 08-01 rule): the MATERIALIZED layer is the one current view — it is
    # the whole chain folded into one state (vote boxes + J8 swaps + J8s
    # pieces + J1 merges + J9 product annotations). Everything that feeds
    # it is an INPUT, not a competing answer, so the vote manifest and
    # the hand-composed judge preview move to the collapsed archive
    # section. Files stay on disk; nothing is deleted.
    # ---- TEMPORARY A/B PAIR (2026-08-10, user eyeball) ----------------
    # Same pattern as the 08-06 directional-prior pair: two vote runs side
    # by side so the box moves can be SEEN rather than read off a delta
    # table. RED = the old run the graph was built from (44 of its 46
    # boxes date from r20260808-203800, old code + old params), GREEN =
    # tonight's full re-run under the current shell and current code.
    # Both labels read their own run_id from the file — the 08-08 lesson
    # (a hard-coded "run 10" caption outliving the boxes) applies here too.
    # REMOVE BOTH once ruled; the files stay on disk.
    _ab = sd / "_pre_eps05_backup_manifest.json"

    def _ablab(p, side):
        try:
            _j = json.loads(p.read_text(encoding="utf-8"))
            _n = len(_j.get("objects") or [])
            return (f"A/B {side} · {_j.get('run_id') or '?'} · "
                    f"{_j.get('run_kind') or '?'}"
                    + ("/mixed" if _j.get("mixed_provenance") else "")
                    + f" · {_n} boxes")
        except Exception:                                   # noqa: BLE001
            return f"A/B {side} · unreadable"

    srcs = [
        ("vote_ab_old", _ablab(_ab, "SHELL_EPS 0.03"), "current", _ab,
         "#ff5252",
         "TEMPORARY A/B — RED = the vote with the OLD 3 cm shell "
         "electorate filter (run r20260810-233757). Pair with GREEN, the "
         "same vote at 5 cm. 14 boxes differ; every one SHRANK. LOOK AT "
         "TWO THINGS SEPARATELY, because the one constant did both: "
         "(1) AT THE WALLS the change helped — obj_012 -0.20 m, obj_014 "
         "-0.08 m, magazines/tv stand tighter; obj_022 (plant, on a shelf "
         "1.77 m up) is the clean control, tighter in x/z with its bottom "
         "untouched. (2) AT THE FLOOR it hurt — SHELL_EPS applies to floor "
         "and ceiling too, so every floor-standing object lifted off the "
         "ground: obj_028 chair's box now floats 0.267 m above the floor "
         "(was 0.121), obj_020 0.199 (was 0.155), obj_006 coffee table "
         "0.103 (was 0.066). DISPLAY ONLY. Remove both entries once "
         "ruled."),
        ("vote_ab_new", _ablab(sd / "scene_manifest_slicevote_preview.json",
                               "SHELL_EPS 0.05"), "current",
         sd / "scene_manifest_slicevote_preview.json", "#4caf50",
         "TEMPORARY A/B — GREEN = the vote with the NEW 5 cm shell "
         "electorate filter (user ruling: \"3cm was arbitrary anyway, try "
         "5\"). Everything else identical to RED — same renders, same "
         "cameras, only who is allowed to VOTE changed. THE QUESTION ON "
         "THE TABLE: the wall gain is real but the floor loss is real "
         "too, because one constant governs walls, floor AND ceiling. The "
         "proposal is to SPLIT it — keep 5 cm at walls, put the floor and "
         "ceiling back to 3 cm — since everything measured (a 4.2 cm "
         "median skin, wall_00's density peak at 3-4 cm) was measured at "
         "WALLS and says nothing about the floor. Same file the cyan "
         "'vote stage' archive layer draws."),
        ("slicevote", _svlab, "archive",
         sd / "scene_manifest_slicevote_preview.json", "#00bcd4",
         "SUPERSEDED 2026-08-08 by the materialized layer (it is this "
         "layer's boxes with every verdict applied) — kept as the vote "
         "stage's raw output for side-by-side. NOTE the counts in the "
         "label: 'shipped' is every object, 'sliced' is only the ones "
         "that went through the vote election; the rest are geometric "
         "exemptions or the ORIGINAL pre-vote box. "
         "Slice-vote election (2026-08-07 late; user-PASSED "
         "R-S2-35..39, the canonical vote state; cyan to match the "
         "cone map's pano-filtered box): per resolved node — top-box "
         "prism slice, view-tunnel cards, 3-tier escalation ladder, "
         "6-voter election gate 3, pano-mask filter. Runs 6-10 rules: "
         "half-space shell electorate filter, winning-blob pano filter, "
         "plan-fill v2 record, large_empty_notch doubt (>=0.5 m2), "
         "PROTRUSION wall exemption (<=0.20 m into the room), SHELL "
         "CLIP on every shipping box (outside openings ship as 0.02 m "
         "wall panels), never-silent kept path (<100-dot slices ship "
         "original as 'kept'), perp-cam re-box for kept_wall/"
         "kept_ceiling flat objects (13/14 re-boxed; glass door "
         "corrected 0.53 m). Outlier guard 8x. Statuses THIS run: "
         + _svstat +                      # counted, never hand-written
         ". Per-box status + doubt flags in each object's "
         "flags field. Preview manifest — runner wiring pending"),
        # parallax_voted REMOVED from the HUD 2026-08-10 (user: retired
        # shot systems are not mentioned) — the manifest was written only
        # by the retired retake experiments (parallax_retake.py, then
        # clobbered by render_aimed_views.py — two writers, one filename) and is
        # archived with them under archive_2026-08-10_retired_shots/.
        # set A / set B (two-standpoint experiment) REMOVED from the HUD
        # 2026-08-06 cone session (user: "we no longer need those");
        # scene_manifest_pano2c.json stays on disk; the sp1 manifests are
        # archived (2026-08-10, with the bubble rigs).
        # ("support_clipped", ...) removed from HUD — wiring premature
        # until support judgment runs on voted geometry (R-S2-22 note)
        # judge_preview: COMPOSED server-side (judge_preview() below), not
        # a file — the path here is its base input, used for the exists()
        # gate; /boxes.json special-cases the key.
        ("judge_preview", "judge preview · J8/J8s (SUPERSEDED)", "archive",
         sd / "scene_manifest_slicevote_preview.json", "#b388ff",
         "SUPERSEDED 2026-08-08 by the 'materialized' layer (amber): this "
         "was the hand-composed PREVIEW of what materialize would do; the "
         "real Phase C output now exists in scene_graph.json['grouped'] and "
         "is served as src=materialized. Kept as-is (behaviour unchanged) "
         "for side-by-side comparison of preview vs actual. — "
         "judge preview: J8 ship rulings + J8s split pieces + coverage "
         "drops (NOT materialized — display only). Per object the box "
         "the judges would ship: shipping box by default; a J8 ONE_BOX "
         "verdict naming a box swaps it in (ship=vote -> the report's "
         "vote2, ship=pano -> its pano, ship=rebox_candidate -> the "
         "rejected face-on re-box on the vote doubt; current/either "
         "keep shipping); J8s split_chain replaces the case node's box "
         "with its final piece boxes; J8s covered_by_existing shows the "
         "case node's box tagged dropped:covered (would NOT ship — its "
         "content is the owners' boxes, already present as their own "
         "nodes). Composed live from scene_manifest_slicevote_preview + "
         "graph/multiplicity.json + graph/split_cuts.json + "
         "vote/slicevote_report.json; missing side files degrade "
         "to the plain shipping boxes"),
    ]
    # same-product (J9): TWO composed layers, one colour each, so the set
    # members and the one size being bought for them can be told apart and
    # toggled independently. Both only appear once J9 has run.
    for _k, _lab, _col, _n in (
        ("sp_members", "same-product · set members (J9)", "#7c4dff",
         "The members J9 ruled ONE PRODUCT, each drawn with its OWN "
         "voted box, verbatim. The exemplar — the member whose box "
         "became the size to buy — says EXEMPLAR in its label."),
        ("sp_sizes", "same-product · size to buy (J9)", "#ff4081",
         "The CANONICAL size drawn at every member of the set, so one "
         "size can be seen against each real instance. Centred on the "
         "member's own box centre (no up-axis assumption): read it as "
         "same middle, whose extent is bigger. USER RULING 08-08: the "
         "size is ONE member's measured box copied verbatim, never a "
         "blend — the members' floor dimensions are not comparable "
         "across differently-facing objects, and averaging a "
         "vote-flagged box in would hide that it was flagged.")):
        if same_product_layer(sc, _k.split("_")[1]) is not None:
            srcs.append((_k, _lab, "current",
                         sd / "graph" / "same_product.json", _col, _n))

    # materialized: COMPOSED server-side (materialized() below) from
    # scene_graph.json['grouped'] — /boxes.json special-cases the key. The
    # entry only appears when that additive block exists (other scenes:
    # no entry, and the route 404s), and its note carries THIS scene's
    # real counts rather than a hard-coded summary.
    cv = voted_layer(sc)
    if cv is not None:
        n = cv.get("counts") or {}
        srcs.append((
            "materialized",
            # the layer NAMES ITSELF — a hand-written "graph.carved" here
            # survived the rename as "graph.voted" and was pointing at the
            # wrong layer within minutes. Read it, never type it.
            f"★ LATEST — the whole chain through J9 "
            f"(graph.{cv.get('_layer_name') or '?'}, "
            f"{len(cv.get('nodes') or [])} nodes)",
            "current", sd / "scene_graph.json", "#ffb300",
            "THE CURRENT STATE (user ruling 2026-08-08): every stage "
            "folded into ONE layer, so this is the thing to look at — the "
            "layers below it are its inputs, not rival answers. "
            "graph/materialize_layers.py (Phase C), status "
            + str(cv.get("status") or "?")
            + ": an ADDITIVE block in scene_graph.json, NOT promoted to "
            "canon (record/judged/resolved/vote/voted_edges untouched). "
            "Boxes are "
            "COPIES, never recomputed: vote shipping box -> J8 box ruling "
            "-> J8s split pieces -> J1 SAME merges -> J9 same-product "
            "annotation (no resize) -> unclear ships unchanged. This "
            "scene: " + f"{n.get('resolved_in', '?')} resolved in -> "
            f"{n.get('nodes_out', '?')} boxes out, {n.get('dropped', 0)} "
            f"dropped (own ↳ toggle, ghost outlines — NOT shipping), "
            f"{n.get('j8_box_swapped', 0)} box swap(s), "
            f"{n.get('j8s_pieces_made', 0)} split piece(s), "
            f"{n.get('j1_merged_away', 0)} merged away, "
            f"{n.get('j9_annotated', 0)} same-product annotations, "
            f"{n.get('conflicts', 0)} conflict(s), "
            f"{n.get('open_questions', 0)} open question(s) on "
            f"{n.get('nodes_with_open_doubts', 0)} node(s) — click a box "
            "to read them"))

    # HUD ORDER = registry order, and the current row must lead with the
    # one canonical state. Explicit rank so adding a layer later cannot
    # quietly push it down the row; anything unranked keeps its place
    # after the ranked ones (stable sort).
    rank = {"materialized": 0, "sp_members": 1, "sp_sizes": 2}
    srcs.sort(key=lambda e: rank.get(e[0], 99))
    return srcs
    #     # ---- current: the pano-track funnel, upstream -> downstream ----
    #     # stage 1 (recentered full set) -> stage 2 (f30 score filter) ->
    #     # stage 3 = geometry dedup + GRAPH RECORD (the "graph record"
    #     # toggle in the main checkbox row — richer view than a box layer)
    #     ("pano_track", "pano · stage 1 · recentered full set", "current",
    #      sd / "scene_manifest_pano2c_rc.json", "#ffd24d",
    #      "STAGE 1 — the most UPSTREAM full manifest (input to stage 2): "
    #      "detection chain output after the recenter round. Self-rendered "
    #      "pano at (0,0)+1.6m -> 20-crop rig -> batched-vocab detect thr "
    #      "0.20 -> z-buffer lift -> robust merge q.05 -> RECENTER as the "
    #      "real filter (42 phantoms refuted by aimed close-ups, no "
    #      "arithmetic gate). 108 objects; floor-gap min +0.012"),
    #     ("pano_track_f30", "pano · stage 2 · f30 score filter", "current",
    #      sd / "scene_manifest_pano2c_rc_f30.json", "#7fd4ff",
    #      "STAGE 2 — stage 1 after the hard 0.30 score filter "
    #      "(manifest_filter.py; no reruns, pure post-processing): 102 "
    #      "objects, 6 dropped (3 toy, 2 book, 1 conditioner; 3 of the 6 "
    #      "were retake-confirmed — the filter overrules the verifier "
    #      "there; drops preserved in filtered_out). INPUT to stage 3 = the "
    #      "scene-graph RECORD (same 102 objects as nodes, duplicate pairs "
    #      "as SAME_CANDIDATE edges — no dedup stage, merging is a judge "
    #      "verdict; toggle 'graph record' above)"),
    #     # Δ pre-recenter audit layer REMOVED from the HUD (user, 07-26
    #     # late, "for simplicity"); the file stays on disk
    #     # (scene_manifest_pano_rcdelta.json — 42 refuted + 26 pre-
    #     # refinement boxes) and pano_track_diffs.py can regenerate it.
    #     # ---- archive / reference: superseded by decisions on record ----
    #     # REMOVED from the HUD entirely (user, 07-26 late): f30+dedup
    #     # geometry-only (redundant view — the 'graph record' layer draws
    #     # the same 93 boxes with the full card; the FILE stays the record
    #     # builder's input), f30+dedup LLM version (retired method), and
    #     # Δ gate kills (audit of the dropped 0.40 gate). Files untouched
    #     # on disk: scene_manifest_pano2c_rc_f30_dd.json / _dd_llm.json /
    #     # scene_manifest_pano_gatekills.json.
    #     # sweep-lane entries (G3/robust/gated/G4) RETIRED from the HUD
    #     # 2026-07-26 — superseded by the canonical pano track; manifests
    #     # stay on disk (scene_manifest_sweep*.json) for the record.
    #     # fuse · 3h2 pool entry REMOVED 2026-07-26 — never built; the
    #     # multiview-vote idea lives on the map's parked-ideas card.
    #     ("recenter_C1", "pano 1.0 · recenter C1 (superseded)",
    #      "archive", sd / "recenter_experiment" / "manifest_C1_raw.json",
    #      "#f0a028",
    #      "Marble-pano lane, superseded by the canonical PANO TRACK "
    #      "(carries the +6.5cm registration pedestal); kept for comparison"),
    #     ("analyzer_hybrid", "analyzer + OUR lift (hybrid · closed)",
    #      "archive", sd / "scene_manifest_analyzer_hybrid.json", "#00c89a",
    #      "REFERENCE (experiment closed 07-26): analyzer's OWLv2 detections "
    #      "AND clustering kept 1:1, geometry replaced by our SAM + z-buffer "
    #      "lift + robust per-axis fusion. Verdict: their clustering shreds "
    #      "(8x bed); the pano track won the FIND comparison"),
    #     ("analyzer", "analyzer · OWLv2 vote (reference)",
    #      "archive", sd / "analyzer" / "bridged_boxes.json", "#00ffff",
    #      "REFERENCE (analyzer demoted to side tool 07-26): bridged "
    #      "clusters — surface-biased centers, fabricated depth extent "
    #      "(w+h)/2; kept runnable as an independent second opinion"),
    #     ("legacy_v1", "yaw4 mask-lift +amodal (retired)",
    #      "archive", paths.manifest(sc), "#8899aa",
    #      "ARCHIVED: the old default scene_manifest.json: 4 gpu_yaw renders "
    #      "-> GroundingDINO+SAM -> per-pixel z-buffer mask lift -> "
    #      "label+IoU merge (lift_views.py), then splat-amodal box extension "
    #      "(amodal_apply.py, 2026-07-15). 4-yaw observation retired 07-24"),


def judge_preview(sc):
    """Compose the judge-preview box layer (display only, NOT materialized):
    the manifest's shipping boxes edited per the J8 multiplicity verdicts
    (graph/multiplicity.json) and the J8s split executions
    (graph/split_cuts.json), vote2 boxes from vote/
    slicevote_report.json, plus the J1 SAME merges from
    scene_graph.json voted_edges (duplicate pairs: the smaller box is
    tagged merged into its survivor, geometry unchanged). Materialize (Phase C) stays the only editor —
    this just previews what it would do. Every side file is optional
    (other scenes): absent ones simply leave boxes unchanged. Returns a
    manifest-style dict, or None when the base manifest is missing."""
    sd = paths.scene_dir(sc)
    manf = sd / "scene_manifest_slicevote_preview.json"
    if not manf.exists():
        return None
    man = json.loads(manf.read_text())

    def load(f, key):   # tolerant reader: {} / [] on absent or bad file
        try:
            return json.loads(f.read_text()).get(key) or []
        except Exception:
            return []

    rep = {r.get("id"): r.get("boxes") or {}
           for r in load(sd / "vote" / "slicevote_report.json",
                         "results")}
    mult = {c["id"]: c.get("verdict") or {}
            for c in load(sd / "graph" / "multiplicity.json", "cases")
            if c.get("id")}
    splits = {c["id"]: c
              for c in load(sd / "graph" / "split_cuts.json", "cases")
              if c.get("id")}
    # J8 v2.2 ship keys name a box; "rebox_candidate" is the rejected
    # face-on re-box the vote recorded on its own doubt (same source
    # materialize reads — the verdict file is never a geometry source).
    rejected = {}
    for n in load(sd / "graph" / "vote_doubts.json", "nodes"):
        for d in n.get("doubts") or []:
            if d.get("kind") == "rebox_rejected_smaller" \
                    and d.get("proposed_box"):
                rejected[n["id"]] = d["proposed_box"]

    def ship_box(oid, v):
        """The box a ONE_BOX verdict asks to ship, or None for a no-op /
        a key this node has no box for. Legacy box_ruling accepted."""
        key = v.get("ship") or {"ship_vote": "vote", "ship_pano": "pano",
                                "either": "either"}.get(v.get("box_ruling"))
        if key in ("vote", "pano"):
            b = (rep.get(oid) or {}).get(
                "vote2" if key == "vote" else "pano") or {}
            return (key, b) if "lo" in b and "hi" in b else None
        if key == "rebox_candidate":
            b = rejected.get(oid) or {}
            return (key, b) if "lo" in b and "hi" in b else None
        return None

    # J1 SAME merges from the graph record (tolerant: absent file/layer
    # = no merges). For each SAME-verdict SAME_CANDIDATE edge the
    # smaller-volume node merges into the larger (the survivor).
    def _vol(o):
        lo, hi = o["aabb_min"], o["aabb_max"]
        return abs((hi[0] - lo[0]) * (hi[1] - lo[1]) * (hi[2] - lo[2]))
    vols = {o["id"]: _vol(o) for o in man.get("objects", [])}
    merged = {}   # loser id -> survivor id
    try:
        # the voted LAYER's own edges; graph["voted_edges"] is the
        # retired half-layer, kept second for scenes voted before 08-11
        _g = json.loads((sd / "scene_graph.json").read_text())
        gedges = ((_g.get("voted") or {}).get("edges")
                  or (_g.get("voted_edges") or {}).get("edges") or [])
    except Exception:
        gedges = []
    for e in gedges:
        if e.get("type") != "SAME_CANDIDATE":
            continue
        if ((e.get("verdict") or {}).get("verdict")) != "SAME":
            continue
        a, b = e.get("a"), e.get("b")
        if not a or not b or a == b or a not in vols or b not in vols:
            continue
        loser, surv = (a, b) if vols[a] <= vols[b] else (b, a)
        merged[loser] = surv

    out = []

    def add(oid, name, lo, hi, tag, flags):
        out.append({
            "id": oid,
            "label": f"{oid} {tag}" if tag else f"{oid} {name}",
            "name": name,
            "judge_tag": tag,
            "aabb_min": list(lo), "aabb_max": list(hi),
            "center": [(lo[i] + hi[i]) / 2 for i in range(3)],
            "size": [hi[i] - lo[i] for i in range(3)],
            "flags": flags})

    not_shipping = []   # omitted boxes, recorded (never silently lost)
    for o in man.get("objects", []):
        oid = o["id"]
        name = o.get("name") or (o.get("label") or "").split(" (")[0]
        lo, hi = o["aabb_min"], o["aabb_max"]
        sp = splits.get(oid)
        if sp and sp.get("resolution") == "split_chain" and sp.get("pieces"):
            # J8s executed cut: the node's box is REPLACED by its final
            # piece boxes (each tagged; owners recorded)
            for pc in sp["pieces"]:
                b = pc.get("box") or {}
                if "lo" in b and "hi" in b:
                    add(f"{oid}:{pc.get('id', '?')}", name,
                        b["lo"], b["hi"], "piece",
                        ["judge_piece", f"owner:{pc.get('owner', '?')}"])
            continue
        if sp and sp.get("resolution") == "covered_by_existing":
            # J8s coverage drop: this box would NOT ship — its content is
            # the owners' boxes (already present as their own nodes).
            # OMITTED from the drawn set (user 2026-08-08: tagged boxes
            # render like normal ones and read as stale); recorded in
            # the payload's not_shipping ledger instead.
            not_shipping.append({"id": oid, "why": "dropped:covered"})
            continue
        surv = merged.get(oid)
        if surv and surv != oid:
            # J1 SAME merge: the (smaller) duplicate would NOT ship —
            # the survivor's box is already present as its own node.
            # OMITTED from the drawn set; recorded in the ledger.
            not_shipping.append({"id": oid, "why": f"merged:->{surv}"})
            continue
        v = mult.get(oid)
        if v and v.get("outcome") == "ONE_BOX":
            sb = ship_box(oid, v)
            if sb:                        # box absent -> unchanged
                key, b = sb
                add(oid, name, b["lo"], b["hi"], f"ship:{key}",
                    [f"judge_ship_{key}"])
                continue
        add(oid, name, lo, hi, "", ["judge_default"])

    return {"scene": sc,
            "status": "judge preview (NOT materialized — display only)",
            "source": "viewer/serve.py judge_preview(): "
                      "scene_manifest_slicevote_preview.json + "
                      "graph/multiplicity.json (J8) + "
                      "graph/split_cuts.json (J8s) + "
                      "vote/slicevote_report.json + "
                      "scene_graph.json voted_edges (J1 SAME merges)",
            "frame": man.get("frame"),
            "not_shipping": not_shipping,
            "n_objects": len(out),
            "objects": out}


# ---- materialized layer (Phase C) -------------------------------------
# scene_graph.json's ADDITIVE `voted` block (graph/materialize_layers.py):
# the first real materialize output. The judge_preview layer above was the
# hand-composed preview of exactly this; this layer supersedes it.
_voted_cache = {}   # scene -> (scene_graph.json mtime, voted dict or None)


def same_product_layer(sc, kind):
    """The J9 same-product layers, composed from graph/same_product.json +
    the vote preview manifest the sizes were measured from.

    Two layers, because the client paints one colour per source and the
    whole point is telling them apart:
      kind="members" — each SET MEMBER's own voted box, verbatim. What
                       the judge decided is one product.
      kind="sizes"   — the CANONICAL box (the exemplar's measured size)
                       drawn at every member, so "one size for the set"
                       can be seen against each real instance.

    The size box is CENTRED on the member's own box centre. That needs no
    up-axis assumption, which is deliberate: this scene's frame is y-down
    and sign mistakes on the up axis have bitten this pipeline before.
    Read it as "same middle, whose extent is bigger" — not as two objects
    standing on a floor.

    Returns None when J9 has not run for this scene (route 404s)."""
    sd = paths.scene_dir(sc)
    try:
        sp = json.loads((sd / "graph" / "same_product.json")
                        .read_text(encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        return None
    # THE SAME GEOMETRY THE VERDICTS WERE MADE ON. J9 judges the settled
    # layer, whose node set includes ids the vote manifest has never
    # heard of (split pieces like obj_011#1) and excludes ones it still
    # lists (merged-away nodes). Reading the manifest here drew a set
    # minus its own members.
    boxes = {}
    cv = voted_layer(sc)
    for n in (cv or {}).get("nodes") or []:
        if n.get("geometry"):
            boxes[n["id"]] = n["geometry"]
    if not boxes:
        try:
            man = json.loads((sd / "scene_manifest_slicevote_preview.json")
                             .read_text(encoding="utf-8"))
            boxes = {o["id"]: o for o in man.get("objects") or []}
        except Exception:                               # noqa: BLE001
            return None

    out, groups = [], []
    for gi, gr in enumerate(sp.get("groups") or [], 1):
        if not gr.get("same_object"):
            continue
        picked = gr.get("set_members") or []
        if not picked:
            continue
        csize = gr.get("canonical_size")
        exemplar = gr.get("canonical_size_from")
        basis = gr.get("canonical_size_basis") or {}
        label = f"g{gi} {gr.get('name') or ''}".strip()
        groups.append({
            "group": label, "n_members": len(picked),
            "canonical_size": csize, "from": exemplar,
            "spread_long_m": basis.get("set_spread_long_m"),
            "spread_short_m": basis.get("set_spread_short_m"),
            "spread_height_m": basis.get("set_spread_height_m")})
        for mid in picked:
            b = boxes.get(mid)
            if not b:
                continue
            is_ex = (mid == exemplar)
            if kind == "members":
                out.append({
                    "id": mid,
                    "label": (f"{mid} · {label}"
                              + (" · EXEMPLAR" if is_ex else "")),
                    "name": gr.get("name"),
                    "product_group": label,
                    "is_exemplar": is_ex,
                    "size_m": [round(float(v), 3) for v in b["size"]],
                    "canonical_size": csize,
                    "canonical_size_from": exemplar,
                    "flags": (["set_member"] + (["EXEMPLAR"] if is_ex
                                                else [])
                              + [f"group:{label}"]),
                    "aabb_min": list(b["aabb_min"]),
                    "aabb_max": list(b["aabb_max"]),
                    "center": list(b["center"]),
                    "size": list(b["size"])})
            elif kind == "sizes" and csize:
                c = list(b["center"])
                h = [float(v) / 2 for v in csize]
                out.append({
                    "id": f"{mid}_size",
                    "label": (f"{mid} · size to buy"
                              + (" (source)" if is_ex else "")),
                    "name": gr.get("name"),
                    "product_group": label,
                    "is_exemplar": is_ex,
                    "of_member": mid,
                    "measured_size_m": [round(float(v), 3)
                                        for v in b["size"]],
                    "canonical_size": csize,
                    "canonical_size_from": exemplar,
                    "flags": ["canonical_size",
                              f"from:{exemplar}", f"group:{label}"]
                             + (["IS THE SOURCE BOX"] if is_ex else []),
                    "center": c,
                    "size": [float(v) for v in csize],
                    "aabb_min": [c[i] - h[i] for i in range(3)],
                    "aabb_max": [c[i] + h[i] for i in range(3)]})

    if not out:
        return None
    return {"scene": sc,
            "status": sp.get("status") or "UNTESTED",
            "kind": kind,
            "source": "viewer/serve.py same_product_layer(): "
                      "graph/same_product.json set_members + "
                      "scene_manifest_slicevote_preview.json boxes "
                      "(RAW frame, like every other box layer)",
            "note": sp.get("known_open"),
            "groups": groups,
            "n_objects": len(out),
            "objects": out}


def voted_layer(sc):
    """Read scene_graph.json['grouped'] (or None when the scene has no
    graph / no voted block / an unreadable one). mtime-cached because
    both the registry gate (box_sources) and the box composer
    (materialized) need the same 0.5 MB parse."""
    p = paths.scene_dir(sc) / "scene_graph.json"
    try:
        mt = p.stat().st_mtime
    except OSError:
        return None
    ent = _voted_cache.get(sc)
    if ent and ent[0] == mt:
        return ent[1]
    try:
        # explicit utf-8: the judges' notes carry em-dashes, and read_text()
        # would otherwise decode them through the Windows locale codepage
        g = json.loads(p.read_text(encoding="utf-8"))
        # THE CURRENT LAYER, asked for rather than named (user rule
        # 2026-08-09). Hard-coding "voted" meant the viewer would keep
        # drawing it after a newer stage landed.
        name, cv = scene_state.current(g)
        if cv is not None:
            cv = {**cv, "_layer_name": name}
    except Exception:
        cv = None
    if not isinstance(cv, dict) or not cv.get("nodes"):
        cv = None
    _voted_cache[sc] = (mt, cv)
    return cv


# rules that only restate where the box CAME from (no edit of its own):
# skipped when picking the box label's tag, still listed in flags.
MAT_BASE_RULES = ("geometry_base_voted", "geometry_base_resolved_fallback",
                  "inherited_from_parent")


def _mat_tag(rule, pv, node):
    """Short label tag for the highest-precedence rule that fired on a
    node — what materialize DID to this box, readable in the 3D view
    without opening the card (sprites clip ~10 chars, so keep it short)."""
    if rule == "j8s_split_piece":
        return "split piece"
    if rule == "j1_same_merge_survivor":
        got = pv.get("merged_from") or node.get("merged_from") or []
        return ("merged " + "+".join(got)) if got else "merged"
    if rule == "j9_same_product_annotation":
        g = pv.get("product_group") or node.get("product_group") or ""
        return ("same-product " + (g.split("_")[0] or g)) if g \
            else "same-product"
    return {"j8_box_swap": "J8 box swap",
            "j8_box_swapped": "J8 vote box",
            "j8_box_ruling_noop": "J8 noop",
            "j8_ruling_not_applicable": "J8 n/a",
            "j8_unclear_ship_unchanged": "J8 unclear",
            "j8s_piece_owned_by_existing": "piece->existing"}.get(rule, rule)


def _mat_box(g):
    """center/size from a voted geometry block (both are recorded; this
    only fills them in if an older record left them out). Returns None
    when there is no box to draw."""
    lo, hi = (g or {}).get("aabb_min"), (g or {}).get("aabb_max")
    if not lo or not hi:
        return None
    return {"aabb_min": list(lo), "aabb_max": list(hi),
            "center": list(g.get("center")
                           or [(lo[i] + hi[i]) / 2 for i in range(3)]),
            "size": list(g.get("size")
                         or [hi[i] - lo[i] for i in range(3)])}


def _shown_rel(sc, n):
    """The node's `shown` picture (inherited into `grouped` since
    08-11B) as a scene-dir-relative POSIX path the /shown_pic route can
    serve, or None. User ask 2026-08-12: the latest-layer card must show
    what the thing IS and the shot it is seen as."""
    p = ((n.get("shown") or {}).get("picture") or {}).get("path")
    if not p:
        return None
    f = Path(p)
    if not f.is_absolute():
        f = paths.scene_dir(sc) / p
    try:
        return f.resolve().relative_to(
            paths.scene_dir(sc).resolve()).as_posix()
    except (ValueError, OSError):
        return None


def materialized(sc):
    """Compose the MATERIALIZED box layer: the voted block's nodes drawn
    VERBATIM (geometry copied, nothing recomputed here either), each box
    carrying its provenance rule trail plus any conflict / open question
    filed against it — seeing which boxes still carry unresolved
    questions is this layer's whole point.

    DROPPED nodes (merged away / split-replaced / discarded side) are NOT
    in `objects`: they do not ship, and drawing them as normal boxes
    would read as stale (user ruling 2026-08-08). They ride in a separate
    `dropped` list with their former geometry + why, which the client
    renders behind its own default-off ghost toggle.

    Returns None when the scene has no voted block (route 404s)."""
    cv = voted_layer(sc)
    if cv is None:
        return None
    confl, opens = {}, {}
    for c in cv.get("conflicts") or []:
        confl.setdefault(c.get("node"), []).append(c)
    for q in cv.get("open_questions") or []:
        opens.setdefault(q.get("node"), []).append(q)

    out = []
    for n in cv.get("nodes") or []:
        box = _mat_box(n.get("geometry"))
        if box is None:
            continue          # nothing to draw (counts still report it)
        nid = n.get("id")
        prov = n.get("provenance") or []
        rules = [p.get("rule") for p in prov if p.get("rule")]
        tag = ""
        for p in reversed(prov):
            if p.get("rule") and p["rule"] not in MAT_BASE_RULES:
                tag = _mat_tag(p["rule"], p, n)
                break
        cf, oq = confl.get(nid) or [], opens.get(nid) or []
        flags = list(rules)                    # the card shows these
        if cf:
            flags.append("CONFLICT")
        if oq:
            flags.append("open_question")
        name = n.get("name") or ""
        out.append({
            "id": nid,
            "label": f"{nid} {tag}" if tag else f"{nid} {name}",
            "name": name,
            "mat_tag": tag,
            "mat_rules": rules,
            "provenance": prov,
            "members": n.get("members") or [],
            "mat_from": n.get("from"),
            "split_from": n.get("split_from"),
            "merged_from": n.get("merged_from") or [],
            "product_group": n.get("product_group"),
            "canonical_size": n.get("canonical_size"),
            "conflicts": cf,
            "open_questions": oq,
            "flags": flags,
            # identity for the click card (user ask 2026-08-12: "i can't
            # see anything about the box, like what is it, where is it
            # from, the shot tile")
            "description": (n.get("appearance") or {}).get("description"),
            "shown_pic": _shown_rel(sc, n),
            **box})

    dropped = []
    for d in cv.get("dropped") or []:
        e = {k: v for k, v in d.items() if k != "geometry_was"}
        e["label"] = f"{d.get('id')} {d.get('rule') or 'dropped'}"
        box = _mat_box(d.get("geometry_was"))
        if box:
            e.update(box)
        dropped.append(e)

    return {"scene": sc,
            "status": cv.get("status") or "UNTESTED-TRIAL",
            "source": "viewer/serve.py materialized(): scene_graph.json "
                      "['voted'] verbatim (graph/materialize_layers.py, "
                      "Phase C) — RAW frame, like every other box layer",
            "built": cv.get("built"),
            "built_from": cv.get("built_from"),
            "note": cv.get("note"),
            "precedence": cv.get("precedence") or [],
            "counts": cv.get("counts") or {},
            "conflicts": cv.get("conflicts") or [],
            "open_questions": cv.get("open_questions") or [],
            "dropped": dropped,
            "n_objects": len(out),
            "objects": out}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain", cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if not cache:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _scene(self, q):
        sc = (q.get("scene") or [args.scene])[0]
        return "".join(ch for ch in sc if ch.isalnum() or ch in "_-") or args.scene

    # which graph SLICES each layer actually consumes -- a layer is
    # stale only when a slice it depends on changed (08-02C redesign:
    # the old whole-graph mtime gate staled EVERYTHING on any graph
    # write, e.g. the additive facing field)
    FP_NEED = {"supported_by.json": ("geometry", "testimony"),
               "consistency.json": ("geometry", "testimony"),
               "snap.json": ("geometry",),
               "edit_proposals.json": ("geometry",),
               "shopping.json": ("geometry",),
               "fitted_preview.json": ("geometry",),
               "fit_check.json": ("geometry",)}
    _fp_cache = {}   # scene -> (graph mtime, fingerprint)

    def _graph_fp(self, sc):
        p = paths.scene_dir(sc) / "scene_graph.json"
        if not p.exists():
            return None
        mt = p.stat().st_mtime
        ent = self._fp_cache.get(sc)
        if ent and ent[0] == mt:
            return ent[1]
        fp = paths.graph_fingerprint(sc)
        self._fp_cache[sc] = (mt, fp)
        return fp

    def _compose_json(self, sc, name, run_hint):
        """Serve a compose/ layer with a CONTENT-FINGERPRINT freshness
        check: the layer's stamped graph_fingerprint is compared against
        the current graph's, per the slices this layer consumes
        (FP_NEED). Stale layers are served IN FULL with stale:true +
        stale_hint added -- the viewer badges them instead of hiding
        them (debugging must still see the data). Unstamped legacy
        files fall back to the old mtime comparison."""
        f = paths.compose_dir(sc) / name
        if not f.exists():
            return self._send(404, b"no compose/" + name.encode() + b"; run "
                              + run_hint.encode() + b" --scene " + sc.encode())
        raw = f.read_bytes()
        cur = self._graph_fp(sc)
        why = None
        try:
            layer = json.loads(raw)
        except ValueError:
            layer = None
        if layer is not None and cur:
            need = self.FP_NEED.get(name, ("geometry",))
            stamped = layer.get("graph_fingerprint")
            if stamped:
                changed = [k for k in need
                           if stamped.get(k) != cur.get(k)]
                if changed:
                    why = "graph " + "+".join(changed) + " changed"
            else:
                graph = paths.scene_dir(sc) / "scene_graph.json"
                if graph.exists() \
                        and f.stat().st_mtime < graph.stat().st_mtime:
                    why = "unstamped layer older than the graph"
            if why:
                layer["stale"] = True
                layer["stale_hint"] = (f"{why}; re-run {run_hint} "
                                       f"--scene {sc}")
                return self._send(200, json.dumps(layer).encode(),
                                  "application/json")
        self._send(200, raw, "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        sc = self._scene(q)
        if p == "/":
            self._send(200, (HERE / "index.html").read_bytes(), "text/html")
        elif p == "/scenes.json":
            scenes = sorted(f.stem for f in (HERE / "data").glob("*.bin"))
            actf = HERE / "data" / "_active.json"
            try:
                act = json.loads(actf.read_text())
            except Exception:
                act = {}
            active = [s for s in act.get("active", []) if s in scenes] \
                or [args.scene]
            # named groups (ordered); scenes with no payload are dropped,
            # scenes in no group land in the viewer's archive bucket
            groups = [{"label": g.get("label", "?"),
                       "scenes": [s for s in g.get("scenes", [])
                                  if s in scenes]}
                      for g in act.get("groups", [])]
            self._send(200, json.dumps({"scenes": scenes, "active": active,
                                        "groups": groups,
                                        "default": args.scene}).encode(),
                       "application/json")
        elif p == "/scene.bin":
            f = HERE / "data" / f"{sc}.bin"
            if f.exists():
                self._send(200, f.read_bytes(), "application/octet-stream", cache=True)
            else:
                self._send(404, b"no point payload; run viewer/prep_scene.py")
        elif p == "/meta.json":
            f = HERE / "data" / f"{sc}.json"
            if not f.exists():
                return self._send(404, b"no meta")
            meta = json.loads(f.read_text())
            meta["scene"] = sc
            manf = paths.manifest(sc)
            boot = paths.scene_dir(sc) / "frame_bootstrap.json"
            if manf.exists():
                man = json.loads(manf.read_text())
                meta["floor_y"] = man["frame"]["floor_y"]
                meta["ceiling_y"] = man["frame"]["ceiling_y"]
            elif boot.exists():
                # pre-lift scenes: the intake module's frame record (same
                # convention — bundle frame, y-down — since 2026-08-06)
                fb = json.loads(boot.read_text())
                meta["floor_y"] = fb["floor_y"]
                meta["ceiling_y"] = fb["ceiling_y"]
            # (gpu_yaw photo-pose harvesting removed 2026-07-25 — yaw track
            # retired; startup pose is now derived from floor_y client-side)
            # sensing standpoints (2026-08-06 two-standpoint experiment):
            # one entry per rig_* dir -> HUD snap-to-eye buttons
            sps = []
            for rig in sorted(paths.scene_dir(sc).glob("rig_*")):
                mf = rig / "pano_selfrender_meta.json"
                if mf.exists():
                    sps.append({"name": rig.name,
                                "eye_raw": json.loads(mf.read_text())["eye_raw"]})
            if sps:
                meta["standpoints"] = sps
            self._send(200, json.dumps(meta).encode(), "application/json")
        elif p == "/raw":
            # ground-truth page: the Marble bundle exactly as shipped
            self._send(200, (HERE / "raw.html").read_bytes(), "text/html")
        elif p in ("/bundle_splats.spz", "/bundle_collider.glb"):
            # stream RAW BUNDLE FILES (no conversion, no copy) for raw.html
            bp = paths.scene_dir(sc) / "bundle_path.txt"
            if not bp.exists():
                return self._send(404, b"no bundle_path.txt for this scene")
            bundle = Path(bp.read_text().strip())
            pat = "*.spz" if p.endswith(".spz") else "*collider*.glb"
            hits = sorted(bundle.glob(pat))
            if not hits:
                return self._send(404, f"no {pat} in bundle".encode())
            ctype = ("application/octet-stream" if p.endswith(".spz")
                     else "model/gltf-binary")
            self._send(200, hits[0].read_bytes(), ctype)
        elif p == "/manifest.json":
            # ?man=<variant> serves scene_manifest_<variant>.json (e.g. the
            # week8 pano-lift manifests) without touching the default one
            man = (q.get("man") or [""])[0]
            if man and man.replace("_", "").isalnum():
                f = paths.scene_dir(sc) / f"scene_manifest_{man}.json"
            else:
                f = paths.manifest(sc)
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no manifest")
        elif p == "/clearance.json":
            f = HERE / "data" / f"{sc}_clearance.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no envelope computed for this scene")
        elif p == "/placement.json":
            f = placement_file(sc)
            body = f.read_bytes() if f.exists() else b'{"placements":[]}'
            self._send(200, body, "application/json")
        elif p == "/box_sources.json":
            # method-box registry: which competing box sets exist for sc
            out = [{"key": k, "label": lb, "group": gp, "color": c, "note": nt}
                   for k, lb, gp, f, c, nt in box_sources(sc) if f.exists()]
            self._send(200, json.dumps({"sources": out}).encode(),
                       "application/json")
        elif p == "/boxes.json":
            # one method box set, by registry key (?src=<key>)
            src = (q.get("src") or [""])[0]
            if src == "judge_preview":
                # COMPOSED layer (judge_preview()), not a file on disk
                data = judge_preview(sc)
                if data is not None:
                    return self._send(200, json.dumps(data).encode(),
                                      "application/json")
                return self._send(404, b"no scene_manifest_slicevote_"
                                       b"preview.json for this scene")
            if src in ("sp_members", "sp_sizes"):
                # COMPOSED layers (same_product_layer()), not files
                data = same_product_layer(sc, src.split("_")[1])
                if data is not None:
                    return self._send(200, json.dumps(data).encode(),
                                      "application/json")
                return self._send(404, b"no graph/same_product.json with "
                                       b"a same-product set; run graph/"
                                       b"judge_same_product.py --scene "
                                       + sc.encode())
            if src == "materialized":
                # COMPOSED layer (materialized()), not a file on disk:
                # scene_graph.json's additive 'voted' block (Phase C)
                data = materialized(sc)
                if data is not None:
                    return self._send(200, json.dumps(data).encode(),
                                      "application/json")
                return self._send(404, b"no scene_graph.json['grouped'] for "
                                       b"this scene; run graph/"
                                       b"materialize_layers.py --scene "
                                       + sc.encode())
            f = next((f for k, _, _, f, _, _ in box_sources(sc) if k == src), None)
            if f is not None and f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"unknown or missing box source; see /box_sources.json")
        elif p == "/conemap.json":
            # TEMPORARY cone-map experiment (2026-08-06 follow-up, k-rule
            # calibration evidence): per-object view-claim points + the
            # strict-AND vs >=2-vote candidate boxes + retake camera poses.
            # Built by the scratchpad cone_map script; remove when the
            # strictness rule is decided.
            f = paths.scene_dir(sc) / "vote" / "conemap.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no vote/conemap.json for this scene")
        elif p == "/collisions.json":
            # collide.py --export output: mesh-overlap pairs + RENDER-frame
            # overlap boxes for the viewer's collision layer
            f = paths.package_dir(sc) / "collisions.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no collisions.json; run composition/"
                                b"collide.py --scene " + sc.encode()
                                + b" --export")
        elif p == "/analyzer_boxes.json":
            # bridge_boxes.py output (Step 6 -- format-bridge): splat_analyzer
            # clusters as manifest-style boxes, RAW frame (same as
            # scene_manifest.json). sc is sanitized by _scene() (alnum/_-),
            # so the path cannot traverse.
            f = paths.scene_dir(sc) / "analyzer" / "bridged_boxes.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no analyzer/bridged_boxes.json; run "
                                b"analyzer/bridge_boxes.py --scene "
                                + sc.encode())
        elif p == "/analyzer_cameras.json":
            # splat_analyzer job cameras (transforms.json verbatim): sampled
            # standpoints + per-frame OpenCV c2w poses, RAW frame (the tool
            # never transforms its input). ?job=<name> picks a job dir;
            # default = newest analyzer/job_*/ that has a transforms.json.
            # job is sanitized like sc, so the path cannot traverse.
            job = (q.get("job") or [""])[0]
            job = "".join(ch for ch in job if ch.isalnum() or ch in "_-")
            base = paths.scene_dir(sc) / "analyzer"
            if job:
                cands = [base / job / "transforms.json"]
            else:
                cands = sorted(base.glob("job_*/transforms.json"),
                               key=lambda f: f.stat().st_mtime, reverse=True)
            f = next((c for c in cands if c.exists()), None)
            if f is not None:
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no analyzer job transforms.json; drop a "
                                b"splat_analyzer job dir into analyzer/")
        elif p == "/scene_graph.json":
            # graph/build_graph.py + build_edges.py + describe_nodes.py output
            # (Steps 1-3 -- scene graph): nodes + typed edges + appearance,
            # RAW frame. Feeds the "graph nodes" layer. sc is sanitized by
            # _scene() (alnum/_-), so the path cannot traverse.
            f = paths.scene_dir(sc) / "scene_graph.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no scene_graph.json; run "
                                b"graph/build_graph.py --scene " + sc.encode())
        elif p == "/multiplicity.json":
            # graph/judge_multiplicity.py output (J8): per doubt-flagged
            # voted node a one-vs-many verdict (outcome + box_ruling or
            # identity+parts). Verdicts REFERENCE nodes — materialize
            # (Phase C) is the editor; the viewer just shows them on the
            # judged card. sc sanitized by _scene(), no traversal.
            f = paths.scene_dir(sc) / "graph" / "multiplicity.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no graph/multiplicity.json; run "
                                b"graph/judge_multiplicity.py --scene "
                                + sc.encode())
        elif p == "/supported_by.json":
            # compose/supported_by.py output (STEP 3 module 1): per object
            # the superseding supported_by options; RAW frame ids only (no
            # geometry of its own). Feeds the scene-graph row's support
            # arrows + semantic anchor tint. sc sanitized by _scene().
            # Freshness-gated vs scene_graph.json (see _compose_json).
            self._compose_json(sc, "supported_by.json",
                               "compose/supported_by.py")
        elif p == "/consistency.json":
            # compose/consistency.py output (STEP 3 module 2): per-edge
            # KEEP/DROP verdicts vs the supported_by layer (R2 gate).
            # Feeds the scene-graph row's consistency review colors.
            self._compose_json(sc, "consistency.json",
                               "compose/consistency.py")
        elif p == "/snap.json":
            # compose/snap.py output (PH1 analyzer): per-object deterministic
            # correction making the top supported_by option physically exact
            # (R4 gate). Feeds the scene-graph row's snap ghosts + colors.
            self._compose_json(sc, "snap.json", "compose/snap.py")
        elif p == "/edit_proposals.json":
            # compose/propose_edits.py output (isolated add/delete
            # proposer): DELETE verdicts per doubt-flagged object + ADD
            # proposals with declared support. Feeds the scene-graph
            # row's edits review mode.
            self._compose_json(sc, "edit_proposals.json",
                               "compose/propose_edits.py")
        elif p == "/shown_pic":
            # the picture a node is CURRENTLY seen as (graph['shown'],
            # inherited into `grouped`) — the click card's shot tile.
            # `f` is scene-dir-relative from materialized()._shown_rel;
            # resolve + parents-check confines it to the scene folder,
            # extension whitelisted. Same traversal guard as /vendor/.
            rel = (q.get("f") or [""])[0]
            base = paths.scene_dir(sc).resolve()
            try:
                f = (base / rel).resolve()
            except (ValueError, OSError):
                f = base
            ext = f.suffix.lower()
            if (rel and ext in (".png", ".webp", ".jpg", ".jpeg")
                    and f.is_file() and base in f.parents):
                ctype = {".webp": "image/webp", ".jpg": "image/jpeg",
                         ".jpeg": "image/jpeg"}.get(ext, "image/png")
                self._send(200, f.read_bytes(), ctype, cache=True)
            else:
                self._send(404, b"no such shown picture")
        elif p.startswith("/graph_crops/"):
            # per-node evidence crops (graph/describe_nodes.py output) for the
            # graph layer's click card. Filename sanitized to alnum/_-. and
            # resolve+parents-checked like /vendor/ -- blocks ../ traversal.
            base = (paths.scene_dir(sc) / "graph" / "crops").resolve()
            name = p[len("/graph_crops/"):].lstrip("/")
            name = "".join(ch for ch in name if ch.isalnum() or ch in "_-.")
            f = (base / name).resolve() if name else base
            if name and f.is_file() and base in f.parents:
                self._send(200, f.read_bytes(), "image/png", cache=True)
            else:
                self._send(404, b"no such graph crop")
        elif p.startswith("/graph_crops_ctx/"):
            # CONTEXT crops (padded 35%/35%/75% + red outline) — the exact
            # views the appearance-v3 describe pass saw; shown in the judged
            # card alongside tight crops so review sees the pipeline's real
            # evidence. Same names as graph/crops/, same sanitize+resolve.
            base = (paths.scene_dir(sc) / "graph" / "crops_ctx").resolve()
            name = p[len("/graph_crops_ctx/"):].lstrip("/")
            name = "".join(ch for ch in name if ch.isalnum() or ch in "_-.")
            f = (base / name).resolve() if name else base
            if name and f.is_file() and base in f.parents:
                self._send(200, f.read_bytes(), "image/png", cache=True)
            else:
                self._send(404, b"no such graph ctx crop")
        elif p == "/composed.glb":
            # composition C6 output (RENDER frame; browser flips via
            # frame.raw_to_render, self-inverse)
            f = paths.package_dir(sc) / "composed_scene2.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no composed_scene2.glb; run composition/place2.py")
        elif p == "/fitted_preview.json":
            # compose/fit_preview.py record: what was placed + the
            # DECIDED front per item (front_dir_raw) -- feeds the fit
            # view's bright arrows
            self._compose_json(sc, "fitted_preview.json",
                               "compose/fit_preview.py")
        elif p == "/fit_check.json":
            # compose/fit_check.py output (deterministic bounds+clip
            # report over the placed preview) -- feeds the scene-model
            # row's fit-check view (red OOB / orange clips + overlap
            # region wireframes)
            self._compose_json(sc, "fit_check.json",
                               "compose/fit_check.py")
        elif p == "/shopping.json":
            # compose/shopping.py output (anchor candidates + deferred
            # subs): the FIT SET -- feeds the scene-model row's fit view
            self._compose_json(sc, "shopping.json", "compose/shopping.py")
        elif p == "/fitted_preview.glb":
            # compose/fit_preview.py output: the shopping module's #1
            # candidates naively placed (RAW frame baked in, no
            # browser-side flip) -- the "fitted preview" HUD layer
            f = paths.compose_dir(sc) / "fitted_preview.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no fitted_preview.glb; run "
                                b"compose/fit_preview.py --scene "
                           + sc.encode())
        elif p == "/subs_preview.glb":
            # sub rounds: every anchor's best sub GLB merged (cp7
            # host-aware > cp6 jiggled > cp5 raw; RAW frame like
            # fitted_preview.glb — no browser-side flip). Built by
            # experiments/build_subs_preview.py.
            f = paths.compose_dir(sc) / "subs_preview.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no subs_preview.glb; run "
                                b"experiments/build_subs_preview.py "
                                b"--scene " + sc.encode())
        elif p == "/collider.glb":
            # Marble bundle collider, ICP-registered into the RAW frame
            # (collider_register.py) — already raw, so NO browser-side flip.
            f = paths.scene_dir(sc) / "collider_registered.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no collider_registered.glb; run "
                                b"collider_register.py --scene " + sc.encode())
        elif p == "/human.glb":
            # stock reference human for scale eyeballing (CesiumMan,
            # Khronos glTF sample assets, CC-BY 4.0 Cesium), BAKED to a
            # static y-up mesh: exactly 1.75 m tall, feet at y=0 (the
            # raw skinned+Z_UP original defeated browser-side bbox
            # scaling -- wall-sized legs, 08-02). Scene-independent.
            f = HERE / "assets" / "human_static.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary",
                           cache=True)
            else:
                self._send(404, b"no viewer/assets/human.glb")
        elif p == "/splat.ply":
            # full-quality splat for the hi-fi renderer (GaussianSplats3D).
            # Streamed in chunks: gen_raw.ply can be 100-800 MB.
            f = paths.OUT / sc / "gen_raw.ply"
            if not f.exists():
                return self._send(404, b"no gen_raw.ply for this scene")
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(f.stat().st_size))
            self.send_header("Cache-Control", "max-age=300")
            self.end_headers()
            with f.open("rb") as fh:
                while True:
                    chunk = fh.read(1 << 20)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        elif p.startswith("/vendor/"):
            # locally-vendored JS modules (three, OrbitControls, GLTFLoader,
            # gaussian-splats-3d) so the viewer works with NO internet. Served
            # with a JS mime type — ES-module <script type=module> imports are
            # rejected by the browser unless the response is a JS content-type.
            base = (HERE / "vendor").resolve()
            f = (base / p[len("/vendor/"):].lstrip("/")).resolve()
            if f.is_file() and base in f.parents:      # blocks ../ traversal
                ctype = "text/javascript" if f.suffix == ".js" else "application/octet-stream"
                self._send(200, f.read_bytes(), ctype, cache=True)
            else:
                self._send(404, b"no such vendor file")
        else:
            self._send(404, b"not found")

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        sc = self._scene(q)
        n = int(self.headers["Content-Length"])
        req = json.loads(self.rfile.read(n))
        if u.path == "/capture":
            png = base64.b64decode(req["image"].split(",", 1)[1])
            ts = time.strftime("%H%M%S")
            f = CAPS / f"cap_{sc}_{ts}.png"
            f.write_bytes(png)
            (CAPS / "latest.png").write_bytes(png)
            meta = {"scene": sc, **req.get("camera", {})}
            (CAPS / f"cap_{sc}_{ts}.json").write_text(json.dumps(meta))
            (CAPS / "latest.json").write_text(json.dumps(meta))
            self._send(200, f"saved {f.name}".encode())
        elif u.path == "/placement":
            req["scene"] = sc
            req.setdefault("note", "edited via live viewer")
            f = placement_file(sc)
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps(req, indent=2))
            tmp.replace(f)
            self._send(200, b"placement saved")
        elif u.path == "/bookmark":
            cam = req.get("camera", {})
            pos = cam.get("pos", [0, 0, 0]); tgt = cam.get("target", [0, 0, 0])
            shot = (f"python rendertools/shot.py {pos[0]:.2f},{pos[1]:.2f},{pos[2]:.2f} "
                    f"{tgt[0]:.2f},{tgt[1]:.2f},{tgt[2]:.2f} --fov {cam.get('fov', 65):.0f} "
                    f"--up 0,1,0 --ply out/{sc}/gen_raw.ply --out <out.webp> --no-open")
            bmf = CAPS / "bookmarks.json"
            bms = json.loads(bmf.read_text()) if bmf.exists() else []
            bms.append({"time": time.strftime("%H:%M:%S"), "scene": sc,
                        "camera": cam, "shot_cmd": shot})
            bmf.write_text(json.dumps(bms, indent=2))
            self._send(200, f"bookmark #{len(bms)} saved".encode())
        else:
            self._send(404, b"not found")

    def log_message(self, *a):
        pass


def main():
    global args, CAPS
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom", help="default scene for /")
    ap.add_argument("--port", type=int, default=8321)
    args = ap.parse_args()

    CAPS = paths.OUT / "viewer_caps"   # shared data root (local_paths.json), not the repo tree
    CAPS.mkdir(parents=True, exist_ok=True)

    print(f"[viewer] default scene={args.scene} http://localhost:{args.port} "
          f"(?scene=<name> to switch; live files: out/<scene>/live_placement.json)",
          flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()


if __name__ == "__main__":
    main()

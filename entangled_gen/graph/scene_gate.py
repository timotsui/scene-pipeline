"""THE CHECKPOINT BETWEEN STAGES — is the state of this scene legal?

Rule #1 is a hundred scenes with nobody watching. The thing that makes
that dangerous is not a stage that crashes — a crash is loud, and the
runner stops. It is a stage that SUCCEEDS AND DOES NOTHING, and the next
stage quietly reads the previous run's answer. Nothing in the pipeline
ever failed a scene for that, because every individual number being
printed was true.

So this module asks the questions no single stage can answer about
itself, and it asks them BETWEEN every pair of stages:

    before(stage)   is the layer this stage reads present and fresh?
    after(stage)    did this stage actually write, just now, the layer
                    and the files it promised — and is that layer now
                    the state of the scene?
    final()         did the whole run FINISH: nothing stale, the chain
                    ended on `grouped`, and the evidence layer is whole?

WHY MTIME AND NOT CONTENT. `after()` requires each promised file to have
been written DURING the stage's own run, not merely to exist. Existence
proves only that some earlier run made it. That mtime test is the one
generic way to catch the silent no-op, and it works without this module
knowing anything about what any stage does.

WHAT THIS DELIBERATELY DOES NOT DO. It does not judge whether the answers
are GOOD. A box can be legal and wrong; the vote can fall back to a
full-height wedge on eleven objects and every check here still passes.
That is the right split — this is the gate on the MACHINERY, and the
gates on the judgements belong to the judges and to the user. Where a
known quality defect can be counted cheaply it is reported as INFO, so a
scene carries the number without failing for it.

EXIT CODES. 0 pass, 3 gate failure. (2 is node_evidence refusing to
write a layer with holes; 1 is an ordinary crash. A runner can tell the
three apart.)

    python graph/scene_gate.py --scene S --report
    python graph/scene_gate.py --scene S --final
    python graph/scene_gate.py --scene S --before evidence
    python graph/scene_gate.py --scene S --after  evidence --since <epoch>
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (HERE, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import paths          # noqa: E402
import scene_state    # noqa: E402
import stages         # noqa: E402

GATE_FAIL = 3

# A file written by a stage can carry an mtime a shade older than the
# moment we started timing it — clocks, filesystem granularity, and on
# Windows a copy that preserves the original timestamp. Two seconds of
# slack keeps the no-op test meaningful without making it flaky.
MTIME_SLACK_S = 2.0


class Result:
    """What a gate found. `ok` is the verdict; `lines` is the report."""

    def __init__(self, what):
        self.what = what
        self.lines = []
        self.ok = True

    def add(self, level, msg):
        """level: PASS, FAIL, WARN or INFO. Only FAIL changes the verdict."""
        self.lines.append((level, msg))
        if level == "FAIL":
            self.ok = False
        return self

    def print(self, prefix="[gate]"):
        mark = {"PASS": "ok  ", "FAIL": "FAIL", "WARN": "warn", "INFO": "    "}
        print(f"{prefix} {self.what}")
        for level, msg in self.lines:
            print(f"{prefix}   {mark.get(level, level)}  {msg}")
        print(f"{prefix} {'PASS' if self.ok else 'FAIL'}: {self.what}",
              flush=True)
        return self


def load(scene):
    gf = paths.scene_dir(scene) / "scene_graph.json"
    if not gf.exists():
        raise SystemExit(f"[gate] no scene graph at {gf}")
    return json.loads(gf.read_text(encoding="utf-8"))


def _load_if_needed(scene, graph, stage):
    """The graph, but ONLY when this stage's checks actually read it.

    ⚠ THE INTAKE FUNNEL RUNS BEFORE THE GRAPH EXISTS. Every stage from
    frame_bootstrap to room_shell happens before build_graph has written
    scene_graph.json, and they write FILES, not layers — so none of their
    checks touch the graph at all. Loading it up front made `before` and
    `after` raise "[gate] no scene graph" on every one of them, which
    would have killed the very first genuinely fresh scene at its very
    first stage. Found 2026-08-11B by asking the gate about a bundle that
    had never been run; it cannot be found on a dev scene, because every
    dev scene already has a graph."""
    if graph is not None:
        return graph
    if stage.reads or stage.writes or stage.graph_keys:
        return load(scene)
    return None


def _layer_state(graph, name):
    """(present, stale) for a layer, using the same 'whole = it has nodes'
    rule the rest of the pipeline uses."""
    if name == "record":
        present = bool(graph.get("nodes"))
    else:
        b = graph.get(name)
        present = bool(isinstance(b, dict) and b.get("nodes"))
    return present, scene_state.is_stale(graph, name)


def _report_missing_inputs(scene, stage, r):
    """Name the files this stage declared and has not got.

    REPORTED, NEVER REFUSED, and the reason is the fit loop: fit_preview
    legitimately reads fit_walk.json, rotation_check.json and its OWN
    prior output, none of which exist on round one. A missing input is
    normal there and fatal in the funnel, and the gate cannot tell those
    apart from the table alone — the module can, and does, by crashing.
    So this puts the fact in the run log, where a hundred scenes' worth
    of it can be read afterwards, and leaves the verdict to the module.

    It earns its place on the funnel, where a stage that reads a file
    another stage was supposed to write now says which one is missing
    instead of dying inside PIL or json."""
    sd = paths.scene_dir(scene)
    gone = [rel for rel in stage.inputs if not (sd / rel).exists()]
    if gone:
        r.add("INFO", f"declared input(s) not on disk: {', '.join(gone)}"
                      + (" — normal on the first round of the fit loop"
                         if stage.key in getattr(stages, "FIT_LOOP", ())
                         else ""))


def before(scene, stage, graph=None):
    """The layer this stage reads must be present and not stale.

    Present but STALE is the interesting case and the reason this check
    exists: the file still holds that layer, it still reads fine, and it
    was computed from inputs that no longer exist. Reading it is exactly
    the failure this whole exercise is about, so it is a FAIL and not a
    warning."""
    g = _load_if_needed(scene, graph, stage)
    r = Result(f"before `{stage.key}` ({stage.title})")
    _report_missing_inputs(scene, stage, r)
    if not stage.reads:
        r.add("INFO", "reads no layer")
        return r
    present, stale = _layer_state(g, stage.reads)
    if not present:
        r.add("FAIL", f"needs layer `{stage.reads}`, which is not in this "
                      f"graph. Present: {', '.join(scene_state.present(g)) or 'none'}")
    elif stale:
        why = ((g.get(stage.reads) or {}).get("stale_since") or {}).get("layer")
        r.add("FAIL", f"layer `{stage.reads}` is STALE — `{why}` was "
                      f"rewritten after it was built, so it was computed "
                      f"from inputs that no longer exist. Re-run the stage "
                      f"that writes `{stage.reads}` first.")
    else:
        r.add("PASS", f"reads `{stage.reads}`: present and fresh")
    return r


def after(scene, stage, since=None, graph=None):
    """Did this stage do what it promised, during this run?

    Three questions, and a stage only answers the ones it declared:
      * the layer it writes is present, fresh, and now the state of the scene
      * the graph blocks it writes exist
      * the files it writes exist AND were written since the stage started
    """
    g = _load_if_needed(scene, graph, stage)
    sd = paths.scene_dir(scene)
    r = Result(f"after `{stage.key}` ({stage.title})")

    if stage.writes:
        present, stale = _layer_state(g, stage.writes)
        if not present:
            r.add("FAIL", f"promised layer `{stage.writes}` and it is not "
                          f"in the graph — the stage exited 0 without "
                          f"writing it")
        elif stale:
            why = ((g.get(stage.writes) or {}).get("stale_since")
                   or {}).get("layer")
            r.add("FAIL", f"layer `{stage.writes}` is present but STALE: "
                          f"`{why}` was rewritten after it was built, so "
                          f"this layer was computed from inputs that no "
                          f"longer exist. Either this stage never ran, or "
                          f"an earlier one ran after it.")
        else:
            r.add("PASS", f"layer `{stage.writes}` present and fresh")
            # ONLY MEANINGFUL IMMEDIATELY AFTER THE STAGE RAN. A live run
            # passes `since`; then the layer just written must be the
            # newest, because writing it swept everything after it stale.
            # In a retrospective scan (`--report`, no `since`) an earlier
            # layer standing under a later one is the normal, healthy
            # shape of a finished scene — flagging it there would make
            # every complete run look broken.
            if since is not None:
                cur = scene_state.current_name(g)
                if cur != stage.writes:
                    r.add("FAIL", f"`{stage.writes}` was written but the "
                                  f"state of the scene is `{cur}` — a later "
                                  f"layer is standing over it, which means "
                                  f"the stale sweep did not run. The chain "
                                  f"was run out of order.")
                ok, msg = scene_state.check(g)
                r.add("PASS" if ok else "FAIL", f"scene_state.check(): {msg}")

    for key in stage.graph_keys:
        if g.get(key):
            r.add("PASS", f"graph['{key}'] written")
        else:
            r.add("FAIL", f"promised graph['{key}'] and it is absent — the "
                          f"stage exited 0 without writing it")

    for rel in stage.artifacts:
        p = sd / rel
        if not p.exists():
            r.add("FAIL", f"promised {rel} and it does not exist")
            continue
        if since is None:
            r.add("PASS", f"{rel} exists")
            continue
        age = p.stat().st_mtime
        if age + MTIME_SLACK_S < since:
            r.add("FAIL", f"{rel} exists but was NOT written by this run "
                          f"(last written {since - age:.0f}s before the "
                          f"stage started). The stage did nothing and "
                          f"exited 0 — the next stage would have read the "
                          f"previous run's answer.")
        else:
            r.add("PASS", f"{rel} written by this run")

    if not (stage.writes or stage.graph_keys or stage.artifacts):
        r.add("INFO", "this stage promises no output the gate can check")
    return r


def stale_inputs(scene, graph):
    """Layers whose INPUT FILE changed after the layer was built.

    THE HOLE THIS CLOSES. The stale sweep understands LAYERS and nothing
    else, but half of what these stages read is a FILE — the vote's
    preview manifest, the judges' verdict sidecars, the view plan. Re-run
    `j8` on its own and it rewrites `graph/multiplicity.json`, which
    `settled` was built from; every layer still looks fresh, because
    nothing in the chain ever knew that file was an input. `check()`
    passes, the end-of-run gate passes, and `settled` is quietly built
    from verdicts that no longer exist.

    So: each stage declares in graph/stages.py the files it consumes that
    another stage produced, every layer records `written_at` when it is
    stamped, and this compares the two. A file NEWER than the layer that
    consumed it means the layer is out of date, whatever the layer chain
    thinks.

    Returns [(level, message)]. A layer written before `written_at`
    existed reports nothing — "I cannot tell" must never be dressed up as
    "fine", and it resolves itself the first time the stage re-runs.

    ⚠ IT USED TO WALK `CHAIN` ONLY (fixed 2026-08-11B), which made every
    `inputs` tuple in COMPOSE decorative and would have made INTAKE's the
    same. A stage with no layer is not exempt from the problem — it is
    the ordinary case in both of those tables — so the comparison had to
    stop being "input vs the layer's written_at" and become "input vs
    WHATEVER THIS STAGE LAST PRODUCED", which for those stages is the
    oldest of its own declared artifacts.
    """
    sd = paths.scene_dir(scene)
    out = []
    order = stages.INTAKE + stages.RECORD + stages.CHAIN + stages.COMPOSE

    # WHICH FILES A LATER STAGE IS SUPPOSED TO REWRITE.
    #
    # ⚠ THIS GUARD EXISTS BECAUSE THE CHECK WAS WRONG WITHOUT IT, AND
    # WRONG IN THE WORST WAY: it told the operator to do something the
    # design forbids. On the first fresh scene it reported "`judged` was
    # built 9 min BEFORE its input graph/judge_pairs_cache.json — re-run
    # `build_judged` and everything after it." Both halves of that are
    # true and the conclusion is not. The Phase-B2 loop-back re-runs J1
    # AFTER the vote, which rewrites that cache on purpose, and
    # docs/AUTOMATION_READINESS.md:301-304 says in terms: "J2 is NOT part
    # of the loop-back ... re-running build_judged would rewrite the
    # immutable `judged` layer and sweep the vote stale." A check whose
    # remedy corrupts the scene is worse than no check.
    #
    # So: an input that some LATER stage declares as its own artifact is
    # a designed loop-back, not staleness. Structural, from the tables —
    # no list of special cases to keep in step.
    later_writes = {}
    for i, st in enumerate(order):
        for rel in st.artifacts:
            later_writes.setdefault(rel, []).append(i)

    for idx, st in enumerate(order):
        if not st.inputs:
            continue

        # WHEN DID THIS STAGE LAST PRODUCE ANYTHING? A layer stage says so
        # in the graph. A file stage's answer is the OLDEST of its own
        # artifacts — oldest, not newest, because if any one of them
        # predates an input then that one was built from something that no
        # longer exists, and taking the newest would hide it.
        # LAYER stages get a FAIL and file stages get a WARN, and the
        # difference is what the evidence can actually support. A layer's
        # `written_at` is a stamp, and the layer chain is a straight line:
        # an input newer than the layer means the layer is wrong. A file
        # stage has no stamp, so the proxy is its oldest artifact — and
        # the pipeline has DELIBERATE loop-backs where a later stage
        # rewrites an earlier one's input, which look identical:
        #   * scene_scale rescales every scene_manifest_pano*.json IN
        #     PLACE (scene_scale.py:107), including the very manifest it
        #     declares as its input, so its input is ALWAYS newer;
        #   * rotation_check reads fitted_preview.json, and the closing
        #     place->jiggle pass rewrites that file afterwards, by design.
        # Failing a scene for those would make the final gate red on
        # every run, and a gate that is always red is a gate nobody
        # reads. So: report it, say it might be the loop, do not fail.
        if st.writes:
            built = scene_state.written_at(graph, st.writes)
            made, level = f"`{st.writes}`", "FAIL"
        else:
            times = [(sd / rel).stat().st_mtime for rel in st.artifacts
                     if (sd / rel).exists()]
            built = min(times) if times else None
            made, level = f"`{st.key}`'s output", "WARN"
        if built is None:
            continue        # never ran, or predates the stamp: cannot tell

        # A STAGE INSIDE THE FIT LOOP CANNOT BE JUDGED THIS WAY. The loop
        # runs the same four stages repeatedly, and each round is SUPPOSED
        # to read files a later stage of the previous round wrote — that
        # is what makes it a loop. Comparing mtimes there reports the loop
        # working correctly as a fault.
        if st.key in getattr(stages, "FIT_LOOP", ()):
            continue

        for rel in st.inputs:
            p = sd / rel
            if not p.exists():
                continue                 # absence is the artifacts check's job
            if any(w > idx for w in later_writes.get(rel, ())):
                continue                 # designed loop-back, see above
            newer = p.stat().st_mtime - built
            if newer > MTIME_SLACK_S:
                ago = (f"{newer:.0f}s" if newer < 90 else
                       f"{newer/60:.0f} min" if newer < 5400 else
                       f"{newer/3600:.1f} h")
                out.append((
                    level,
                    f"{made} was built {ago} BEFORE its "
                    f"input {rel} was last written. The stage that writes "
                    f"that file has run since, so {made} was built "
                    f"from something that no longer exists. Re-run "
                    f"`{st.key}` and everything after it."
                    + ("" if level == "FAIL" else
                       "  (WARN, not FAIL: this stage writes files rather "
                       "than a layer, so there is no stamp to compare "
                       "against — and it may simply be a designed "
                       "loop-back, where a later stage rewrites this "
                       "stage's input on purpose.)")))
    return out


def _shown_counts(g):
    return ((g.get("shown") or {}).get("counts") or {})


def final(scene, graph=None):
    """Did the run FINISH? The check nothing had before.

    A scene could end with `grouped` marked stale and the runner reported
    success. Every fact needed to know better was already in the file —
    check() passed, the stale list named it, the log even said so — and
    nothing gated on it."""
    g = graph if graph is not None else load(scene)
    r = Result(f"final state of `{scene}`")

    ok, msg = scene_state.check(g)
    r.add("PASS" if ok else "FAIL", f"scene_state.check(): {msg}")

    cur = scene_state.current_name(g)
    if cur == stages.FINAL_LAYER:
        r.add("PASS", f"the chain ended on `{stages.FINAL_LAYER}`")
    else:
        r.add("FAIL", f"the chain ended on `{cur}`, not "
                      f"`{stages.FINAL_LAYER}` — the run did not finish")

    stale = (g.get("layer") or {}).get("stale") or []
    if stale:
        r.add("FAIL", f"layer(s) left stale: {', '.join(stale)}. Each was "
                      f"built from inputs that have since been rewritten; "
                      f"re-run their stages.")
    else:
        r.add("PASS", "no stale layers")

    c = _shown_counts(g)
    if not c:
        r.add("FAIL", "no graph['shown'] counts — the evidence layer was "
                      "never written, so the judges fell back to detector "
                      "crops cut around boxes that have since moved")
    else:
        n, pic, prob = c.get("nodes"), c.get("with_picture"), c.get("problems")
        if prob:
            level = "WARN" if (g.get("shown") or {}).get("allow_holes") else "FAIL"
            r.add(level, f"evidence layer has {prob} node(s) with no "
                         f"picture" + (" (holes accepted deliberately)"
                                       if level == "WARN" else ""))
        if pic != n:
            r.add("FAIL", f"evidence layer covers {pic} of {n} nodes")
        elif not prob:
            r.add("PASS", f"evidence layer whole: {pic}/{n} nodes have a "
                          f"picture")

    for level, msg in stale_inputs(scene, g):
        r.add(level, msg)

    for level, msg in quality_notes(scene, g):
        r.add(level, msg)
    return r


def quality_notes(scene, g):
    """Known defects that survive into every scene, counted not judged.

    These NEVER fail a scene. They are the numbers that say how much of
    this scene was really measured, so a hundred runs can be sorted by
    it afterwards instead of all looking alike."""
    out = []
    # The vote's own doubts. THE SOURCE IS THE SIDECAR, graph/
    # vote_doubts.json, not a graph block: this note is wanted straight
    # after the `doubts` stage, and `voted` — the layer that folds the
    # same doubts onto its nodes — does not exist yet at that point. (It
    # read the graph['vote'] block until 2026-08-11, when that block was
    # retired as a second copy.)
    #
    # `slice_fallback` is the doubt that says how much of this scene was
    # really measured: the plan view found nothing, so the slice fell
    # back to a full-height wedge that only constrains left-right and the
    # box shipped roughly as it arrived.
    dp = paths.scene_dir(scene) / "graph" / "vote_doubts.json"
    vn = {}
    if dp.exists():
        try:
            vn = {n["id"]: n for n in
                  (json.loads(dp.read_text(encoding="utf-8")).get("nodes")
                   or [])}
        except (ValueError, KeyError, TypeError):
            out.append(("WARN", "graph/vote_doubts.json is unreadable, so "
                                "the slice-fallback count is missing from "
                                "this scene's report"))
    fb = [nid for nid, n in vn.items()
          if any((d or {}).get("kind") == "slice_fallback"
                 for d in (n.get("doubts") or []))]
    # THE DENOMINATOR IS EVERY NODE THE VOTE SAW, not every node that
    # raised a doubt. The sidecar lists only the doubted ones (30 of 46
    # on living), so counting its length would silently shrink the
    # denominator and make the same scene look worse — "9 of 30" where
    # the honest number is "9 of 46". The vote runs on `resolved`, and
    # the doubts are keyed by those pre-settlement ids, so that is the
    # set to measure against.
    n_all = len((g.get("resolved") or {}).get("nodes") or []) or len(vn)
    if fb:
        out.append(("INFO", f"{len(fb)} of {n_all} node(s) fell back to a "
                            f"full-height wedge: the plan view found "
                            f"nothing, so nothing re-measured the box and "
                            f"it shipped roughly as it arrived. PARKED by "
                            f"user ruling 2026-08-11 — see docs/PARKED.md "
                            f"§1. Reported, never tuned."))
    # SAME_CANDIDATE EDGES THAT REACHED THE END UNJUDGED (found 2026-08-11).
    # build_edges proposes "these two might be one object" geometrically;
    # J1 (judge_pairs) answers it — but J1 runs on the RECORD, before the
    # vote. The vote then moves every box, which can propose BRAND NEW
    # candidates that no judge in the chain ever sees: on living_marble
    # two chairs came out 96% contained in one another. materialize merges
    # only pairs whose verdict is SAME, so an unjudged candidate is
    # silently NOT merged and the scene ships a duplicate object.
    #
    # It is reported and never failed, because the answer is a judgement
    # nobody has made yet, not a broken machine. See PLAN_AUTOMATION.
    for name in ("voted", "voted_edges"):
        es = (g.get(name) or {}).get("edges") or []
        unjudged = [e for e in es if e.get("type") == "SAME_CANDIDATE"
                    and not (e.get("verdict") or {}).get("verdict")]
        if unjudged:
            pairs = ", ".join(f"{e['a']}~{e['b']}" for e in unjudged[:6])
            out.append(("WARN", f"{len(unjudged)} SAME_CANDIDATE edge(s) in "
                                f"`{name}` have no verdict ({pairs}). The "
                                f"vote proposed them by moving the boxes, "
                                f"and the Phase-B2 loop-back is what "
                                f"answers them — run `j1_repairs` "
                                f"(judge_pairs --edges-from voted) "
                                f"before j8. materialize merges only SAME "
                                f"verdicts, so until it runs these ship "
                                f"as separate objects."))
            break
    # WAS THIS SCENE VOTED IN ONE PIECE? slicevote sets canon_eligible
    # false when the run was partial (`--only`) or when the boxes it
    # merged came from more than one code revision. It was computed,
    # written, carried into graph['voted']['run'] — and read by nothing
    # except a diff sheet and a viewer badge. A scene resumed after an
    # interruption therefore builds `settled` and `grouped` on boxes made
    # by two revisions and says nothing about it.
    run = ((g.get("voted") or {}).get("run") or {})
    if run and not run.get("canon_eligible", True):
        out.append(("WARN", f"the vote for this scene is NOT canon-eligible "
                            f"(run {run.get('run_id')}): it was partial, or "
                            f"the boxes it merged came from more than one "
                            f"code revision. Everything built on top of it "
                            f"inherits that."))

    # HOW MANY VERDICTS WERE THE JUDGES UNABLE TO GIVE. Each LLM stage
    # falls back to a default when a call fails, which is right for one
    # case and catastrophic for forty — an expired token turns a whole
    # scene into confident-looking defaults. The count is recorded by the
    # stage; this reports it. Where the acceptable line falls is the
    # user's judgement, so it is never a failure here.
    for fn, who in (("multiplicity.json", "J8"),
                    ("split_cuts.json", "J8s"),
                    ("same_product.json", "J9")):
        p = paths.scene_dir(scene) / "graph" / fn
        if not p.exists():
            continue
        try:
            jf = (json.loads(p.read_text(encoding="utf-8"))
                  or {}).get("judge_failures") or {}
        except (ValueError, OSError):
            out.append(("WARN", f"{fn} could not be read to check how many "
                                f"{who} verdicts defaulted"))
            continue
        if jf.get("defaulted"):
            out.append(("WARN", f"{who}: {jf['defaulted']} of "
                                f"{jf.get('total')} case(s) got a DEFAULT "
                                f"verdict because the call failed, not "
                                f"because the judge decided "
                                f"({', '.join((jf.get('ids') or [])[:6])})"))

    sh = (g.get("shown") or {}).get("nodes") or []
    it = sh.items() if isinstance(sh, dict) else ((n.get("id"), n) for n in sh)
    culled = sum(1 for _, n in it
                 if any(v.get("occluders_removed")
                        for v in (((n.get("shown") or {}).get("views")) or [])))
    if culled:
        out.append(("INFO", f"{culled} node(s) carry a supplementary view "
                            f"with occluders deleted in front of them"))
    return out


def report(scene):
    """The whole scan in one place — AUTOMATION_READINESS section 3."""
    g = load(scene)
    print(f"[gate] scan of `{scene}`")
    print(f"[gate]   live layers : {', '.join(scene_state.present(g)) or 'none'}")
    print(f"[gate]   stale       : "
          f"{', '.join((g.get('layer') or {}).get('stale') or []) or 'none'}")
    print(f"[gate]   current     : {scene_state.current_name(g)}")
    print(f"[gate]   check()     : {scene_state.check(g)}")
    print(f"[gate]   shown counts: {_shown_counts(g) or 'none'}")
    print()
    for st in stages.CHAIN:
        b = before(scene, st, graph=g)
        a = after(scene, st, since=None, graph=g)
        mark = "ok  " if (b.ok and a.ok) else "FAIL"
        print(f"[gate]   {mark} {st.key:12s} {st.reads or '-':9s} -> "
              f"{st.writes or '-'}")
        for res in (b, a):
            for level, msg in res.lines:
                if level == "FAIL":
                    print(f"[gate]          {msg}")
    print()
    return final(scene, graph=g).print()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", required=True)
    ap.add_argument("--before", default="", help="stage key to check before")
    ap.add_argument("--after", default="", help="stage key to check after")
    ap.add_argument("--since", type=float, default=None,
                    help="epoch seconds the stage started; with --after, "
                         "promised files must be newer than this")
    ap.add_argument("--final", action="store_true",
                    help="did the whole run finish")
    ap.add_argument("--report", action="store_true",
                    help="the full per-stage scan")
    a = ap.parse_args()

    if a.report:
        sys.exit(0 if report(a.scene).ok else GATE_FAIL)

    g = load(a.scene)
    results = []
    if a.before:
        results.append(before(a.scene, stages.get(a.before), graph=g))
    if a.after:
        results.append(after(a.scene, stages.get(a.after), since=a.since,
                             graph=g))
    if a.final or not results:
        results.append(final(a.scene, graph=g))
    ok = all(r.print().ok for r in results)
    sys.exit(0 if ok else GATE_FAIL)


if __name__ == "__main__":
    main()

"""
Step 4 -- graph-review build: render out/<scene>/scene_graph.json into a
SELF-CONTAINED interactive review page  out/<scene>/graph_review.html
(CHECKPOINT G1 -- graph correctness review; PLAN_SCENE_GRAPH.md section 3).

Standalone + idempotent: pure function of scene_graph.json (+ two optional
sanity inputs, see below); rerunning overwrites the same file. NO network
dependencies -- all CSS/JS is inline, plain hand-written (no graph lib is
vendored and none is fetched); the only external references are RELATIVE
<img> paths into graph/crops/ (describe_nodes.py output), so the page works
opened directly as a file from out/<scene>/.

Page contents (mechanical assembly of graph facts -- this script makes NO
quality judgment; the user judges at Checkpoint G1):
  1. WAITING-ON-YOU banner (What / Why / Look-for)
  2. stats strip (node/edge/tier/dispute counts)
  3. top-down XZ SVG minimap: node box footprints colored by confidence
     tier, architecture dashed, envelope floor/wall outline, per-edge-type
     line overlays (toggles; edges to floor/ceiling planes draw as dots --
     they have no XZ extent). Click a footprint -> jump to its node card.
  4. node explorer: cards grouped by tier then type -- identity, provenance,
     appearance + crops (click to enlarge), caveat badges, edge list with
     numeric evidence
  5. edge tables per type, sortable on numeric columns (INTERPENETRATES
     pre-sorted by overlap volume desc); z_fabricated rows dimmed
  6. sanity panel: floating list, unattached architecture, label disputes
     (appearance.label_agreement == false), undescribed nodes, recorded
     input inconsistencies (match accounting, loop-adds without nodes,
     render-frame collide export, envelope-outlier windows), edge self-check

Optional sanity inputs (each skipped with a note if missing):
  analyzer/match_report.json      -- match accounting (19 + 17 + 67 = 103)
  package/composed_state2.json    -- loop-add ids (add_*) that seeded no node

Run:  python graph/graph_review.py --scene bedroom_marble
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import paths  # noqa: E402

TIER_ORDER = ["confirmed", "candidate", "weak"]
TIER_COL = {"confirmed": "#33ee66", "candidate": "#ffb020", "weak": "#ff3333"}
EDGE_ORDER = ["ON", "IN", "IN_WALL", "ATTACHED", "INTERPENETRATES"]
EDGE_COL = {"ON": "#33ee66", "IN": "#3c82e6", "IN_WALL": "#8844dd",
            "ATTACHED": "#aa66ff", "INTERPENETRATES": "#ff3333"}
EDGE_MEANING = {
    "ON": "a is supported by b (bottom-face contact)",
    "IN": "a is contained in b (overlap fraction of the smaller box)",
    "IN_WALL": "architecture detection sits in an envelope wall plane",
    "ATTACHED": "anchored to ceiling plane / curtain-window pairing",
    "INTERPENETRATES": "box overlap with no other relation (duplicates self-expose here)",
}


def esc(s):
    return (str("" if s is None else s).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def fmt(v, nd=3):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return esc(v)
    r = round(v, nd)
    return str(int(r)) if r == int(r) else f"{r:g}"


def ev_str(edge):
    parts = []
    for k, v in (edge.get("evidence") or {}).items():
        parts.append(f"{k} {fmt(v)}")
    return ", ".join(parts)


def crop_rel(p):
    """Absolute crop path -> path relative to out/<scene>/ (forward slashes)."""
    return "graph/crops/" + Path(str(p)).name


def node_ref(nid, nodes_by_id):
    n = nodes_by_id.get(nid)
    lab = f" {esc(n['label'])}" if n else ""
    return f'<a class="nref" href="#node-{esc(nid)}">{esc(nid)}{lab}</a>'


# --------------------------------------------------------------------------
# page sections
# --------------------------------------------------------------------------

def banner_html(scene):
    look = [
        ("a", "spot-check <b>ON</b> edges against reality — is the lamp really "
              "on the desk, the chair on the floor? (3D viewer helps here)"),
        ("b", "<b>IN</b> edges plausibility — books in shelves yes; nonsense "
              "containments no"),
        ("c", "architecture typing sane — doors / windows / curtains / AC "
              "tagged <i>architecture</i> vs movables tagged <i>object</i>"),
        ("d", "appearance descriptions vs the actual crops — click through a "
              "dozen node cards"),
        ("e", "walk the WEAK tier + the label-dispute list — which nodes are "
              "hallucinated or duplicates and should be pruned"),
        ("f", "the floating list — real wall-mounted items (art, shelf) vs "
              "detection junk"),
    ]
    lis = "".join(f"<li><b>({k})</b> {t}</li>" for k, t in look)
    return f"""
<div class="banner">
 <div class="btitle">&#128308; WAITING ON YOU — Checkpoint G1: graph correctness review</div>
 <p><b>What:</b> this page + the 3D viewer layer
 (<code>launch_viewer.bat</code> &rarr; <code>localhost:8321</code> &rarr; tick
 <b>&ldquo;graph nodes&rdquo;</b>; per-tier and per-edge-type sub-toggles appear
 under the checkbox row, click any box for its appearance card with crops).</p>
 <p><b>Why:</b> <code>scene_graph.json</code> becomes the substrate every
 downstream stage reads — wrong ON edges poison placement, hallucinated nodes
 poison retrieval, bad appearance poisons asset matching. Your node-seed choice
 (analyzer-only, decision 2026-07-22) is also on trial here: the analyzer boxes
 are now the single source of truth for what exists in <i>{esc(scene)}</i>.</p>
 <p><b>Look for:</b></p><ul>{lis}</ul>
</div>"""


def stats_html(g, disputes, undescribed):
    c = g["counts"]
    ec = g["edge_summary"]["edge_counts"]
    n_edges = sum(ec.values())
    tiers = " / ".join(
        f'<span style="color:{TIER_COL[t]}">{t} {c["by_tier"].get(t, 0)}</span>'
        for t in TIER_ORDER)
    etypes = " · ".join(
        f'<span style="color:{EDGE_COL[t]}">{t} {ec.get(t, 0)}</span>'
        for t in EDGE_ORDER if t in ec)
    floating = len(g["edge_summary"].get("floating", []))
    described = sum(1 for n in g["nodes"]
                    if n.get("source") == "detection" and n.get("appearance"))
    ndet = c["detection_nodes"]
    return (f'<div class="stats"><b>{c["nodes"]} nodes</b> '
            f'({ndet} detection + {c["envelope_nodes"]} envelope) · '
            f'tiers {tiers} · <b>{n_edges} edges</b> ({etypes}) · '
            f'described {described}/{ndet} · '
            f'label disputes {len(disputes)} · undescribed {len(undescribed)} · '
            f'floating {floating}</div>')


def minimap_html(g, nodes_by_id):
    """Top-down XZ SVG: footprints by tier + per-type edge overlays."""
    det = [n for n in g["nodes"] if n.get("source") == "detection"]
    floor = nodes_by_id.get("arch_floor", {})
    ext = (floor.get("geometry") or {}).get("extent") or {}
    xr = ext.get("x_raw", [-3, 3])
    zr = ext.get("z_raw", [-3, 3])
    xs = [xr[0], xr[1]]
    zs = [zr[0], zr[1]]
    for n in det:
        a, b = n["geometry"]["aabb_min"], n["geometry"]["aabb_max"]
        xs += [a[0], b[0]]
        zs += [a[2], b[2]]
    pad = 0.35
    x0, x1 = min(xs) - pad, max(xs) + pad
    z0, z1 = min(zs) - pad, max(zs) + pad
    S = 110.0
    W, H = (x1 - x0) * S, (z1 - z0) * S

    def X(x):
        return (x - x0) * S

    def Z(z):
        return (z - z0) * S

    out = [f'<svg id="minimap" viewBox="0 0 {W:.0f} {H:.0f}" '
           f'width="{W:.0f}" height="{H:.0f}">']
    # envelope floor outline + wall planes
    out.append(f'<rect x="{X(xr[0]):.1f}" y="{Z(zr[0]):.1f}" '
               f'width="{(xr[1]-xr[0])*S:.1f}" height="{(zr[1]-zr[0])*S:.1f}" '
               f'class="room"><title>envelope floor extent (arch_floor / '
               f'arch_wall_*)</title></rect>')
    # node footprints (draw big ones first so small stay clickable)
    order = sorted(det, key=lambda n: -(n["geometry"]["size"][0] *
                                        n["geometry"]["size"][2]))
    for n in order:
        a, b = n["geometry"]["aabb_min"], n["geometry"]["aabb_max"]
        col = TIER_COL.get(n["confidence_tier"], "#ccc")
        dash = ' stroke-dasharray="4 3"' if n["type"] == "architecture" else ""
        tip = (f'{n["id"]} {n["label"]} [{n["confidence_tier"]}'
               f'{", architecture" if n["type"] == "architecture" else ""}]')
        out.append(
            f'<rect x="{X(a[0]):.1f}" y="{Z(a[2]):.1f}" '
            f'width="{(b[0]-a[0])*S:.1f}" height="{(b[2]-a[2])*S:.1f}" '
            f'fill="{col}" fill-opacity="0.14" stroke="{col}" '
            f'stroke-opacity="0.85"{dash} class="mnode" '
            f'onclick="jumpTo(\'{n["id"]}\')"><title>{esc(tip)}</title></rect>')
    # edge overlays per type (toggled by checkboxes; default ON only)
    ax_i = {"x": 0, "y": 1, "z": 2}
    for t in EDGE_ORDER:
        seg = []
        for e in g["edges"]:
            if e["type"] != t:
                continue
            na, nb = nodes_by_id.get(e["a"]), nodes_by_id.get(e["b"])
            if not na or not nb:
                continue
            ca = (na["geometry"].get("center") or None)
            if ca is None:
                continue  # 'a' is always a detection node in this graph
            gb = nb["geometry"]
            dim = "z_fabricated" in (e.get("caveats") or [])
            op = "0.25" if dim else "0.8"
            if gb.get("center"):
                cb = gb["center"]
                seg.append(f'<line x1="{X(ca[0]):.1f}" y1="{Z(ca[2]):.1f}" '
                           f'x2="{X(cb[0]):.1f}" y2="{Z(cb[2]):.1f}" '
                           f'stroke="{EDGE_COL[t]}" stroke-opacity="{op}"/>')
            else:
                pl = gb.get("plane") or {}
                if pl.get("axis") == "y":
                    # floor/ceiling plane: no XZ direction -> dot at the node
                    seg.append(f'<circle cx="{X(ca[0]):.1f}" '
                               f'cy="{Z(ca[2]):.1f}" r="3.4" '
                               f'fill="{EDGE_COL[t]}" fill-opacity="{op}"/>')
                else:
                    cb = list(ca)
                    cb[ax_i[pl["axis"]]] = pl["value_raw"]
                    seg.append(f'<line x1="{X(ca[0]):.1f}" y1="{Z(ca[2]):.1f}" '
                               f'x2="{X(cb[0]):.1f}" y2="{Z(cb[2]):.1f}" '
                               f'stroke="{EDGE_COL[t]}" stroke-opacity="{op}"/>')
        vis = "" if t == "ON" else ' style="display:none"'
        out.append(f'<g id="me-{t}"{vis}>{"".join(seg)}</g>')
    out.append(f'<text x="6" y="{H-8:.0f}" class="axlab">x (m) &#8594;  ·  '
               f'z (m) &#8595;  ·  RAW frame, top-down</text>')
    out.append("</svg>")

    boxes = " ".join(
        f'<label style="color:{EDGE_COL[t]}"><input type="checkbox" '
        f'onchange="mmToggle(\'{t}\', this.checked)"'
        f'{" checked" if t == "ON" else ""}> {t}</label>'
        for t in EDGE_ORDER)
    legend = (" · ".join(f'<span style="color:{TIER_COL[t]}">&#9632; {t}</span>'
                         for t in TIER_ORDER)
              + ' · dashed outline = architecture-typed detection · green frame '
                '= envelope floor extent · dots = edges to the floor/ceiling '
                'plane (no XZ direction) · faint = z_fabricated evidence · '
                'click a footprint to jump to its card')
    return (f'<h2 id="sec-minimap">spatial minimap (top-down XZ)</h2>'
            f'<div class="mmwrap"><div class="mmtools">edge overlay: {boxes}'
            f'</div><div class="dim">{legend}</div>{"".join(out)}</div>')


def caveat_badges(cavs):
    return "".join(f'<span class="cav">{esc(c)}</span>' for c in (cavs or []))


def appearance_html(n):
    ap = n.get("appearance")
    if not ap:
        if n.get("source") != "detection":
            return ""
        return ('<div class="undesc">? undescribed — the appearance pass '
                'returned nothing for this node (1 retry)</div>')
    warn = ""
    if ap.get("label_agreement") is False:
        warn = ('<div class="dispute">&#9888; label dispute — the VLM '
                'description does not match the detector label</div>')
    chips = []
    for c in ap.get("colors") or []:
        chips.append(f'<span class="chip">{esc(c)}</span>')
    if ap.get("material"):
        chips.append(f'<span class="chip chipm">{esc(ap["material"])}</span>')
    if ap.get("style"):
        chips.append(f'<span class="chip chips2">{esc(ap["style"])}</span>')
    return (f'{warn}<div class="adesc">&ldquo;{esc(ap.get("description"))}'
            f'&rdquo;</div><div>{"".join(chips)}</div>')


def crops_html(n):
    crops = (n.get("views") or {}).get("crops") or []
    if not crops:
        return ""
    imgs = []
    for c in crops:
        rel = crop_rel(c["path"])
        tip = (f'{Path(str(c["path"])).name} — frame {c.get("frame_idx")}, '
               f'det {fmt(c.get("det_score"), 3)}, {c.get("area_px")} px')
        imgs.append(f'<img src="{esc(rel)}" loading="lazy" '
                    f'title="{esc(tip)}" onclick="showImg(this.src)">')
    return f'<div class="crops">{"".join(imgs)}</div>'


def edge_list_html(nid, edges_by_node, nodes_by_id):
    el = edges_by_node.get(nid, [])
    if not el:
        return '<div class="dim">no edges</div>'
    rows = []
    for e in el:
        outgoing = e["a"] == nid
        other = e["b"] if outgoing else e["a"]
        if e["type"] == "INTERPENETRATES":
            arrow = "&#8596;"
        else:
            arrow = "&#8594;" if outgoing else "&#8592;"
        dim = ' edim' if "z_fabricated" in (e.get("caveats") or []) else ""
        rows.append(
            f'<div class="erow{dim}"><span style="color:{EDGE_COL[e["type"]]}">'
            f'{e["type"]}</span> {arrow} {node_ref(other, nodes_by_id)} '
            f'<span class="dim">({ev_str(e)})</span></div>')
    head = f'<div class="ehead">edges ({len(el)})</div>'
    if len(rows) > 10:
        return (head + "".join(rows[:10])
                + f'<details><summary class="dim">+{len(rows)-10} more</summary>'
                + "".join(rows[10:]) + "</details>")
    return head + "".join(rows)


def node_card_html(n, edges_by_node, nodes_by_id):
    tier = n["confidence_tier"]
    prov = n.get("provenance") or {}
    bits = []
    if n.get("source") == "detection":
        bits.append(f'cat <b>{esc(n.get("canonical_category"))}</b>')
        bits.append(f'votes {prov.get("votes")}')
        bits.append(f'peak {fmt(prov.get("peak_score"), 3)}')
        bits.append(f'{prov.get("standpoint_count")} standpoints')
        if prov.get("matched_manifest_id"):
            bits.append(f'manifest <b>{esc(prov["matched_manifest_id"])}</b> '
                        f'({fmt(prov.get("match_distance_m"), 3)} m)')
        g = n["geometry"]
        bits.append("size " + " × ".join(fmt(v, 2) for v in g["size"]) + " m")
    else:
        bits.append(f'envelope {esc((n["geometry"].get("plane") or {}).get("axis", ""))}'
                    f' plane @ {fmt((n["geometry"].get("plane") or {}).get("value_raw"))}')
    cut = (n.get("gaussians") or {})
    if cut.get("cut"):
        bits.append(f'gaussians cut: {cut.get("count")} ({esc(cut.get("variant"))})')
    if (n.get("state") or {}).get("pick_uid"):
        bits.append("retrieval pick attached")
    src_badge = ('<span class="badge benv">envelope</span>'
                 if n.get("source") == "envelope" else "")
    return f"""
<div class="card" id="node-{esc(n['id'])}">
 <div class="chead"><span class="nid">{esc(n['id'])}</span>
  <b>{esc(n['label'])}</b>
  <span class="badge" style="color:{TIER_COL[tier]};border-color:{TIER_COL[tier]}">{tier}</span>
  <span class="badge btype">{esc(n['type'])}</span>{src_badge}</div>
 <div class="meta">{' · '.join(bits)}</div>
 <div>{caveat_badges(n['geometry'].get('caveats'))}</div>
 {appearance_html(n)}
 {crops_html(n)}
 {edge_list_html(n['id'], edges_by_node, nodes_by_id)}
</div>"""


def explorer_html(g, edges_by_node, nodes_by_id):
    out = ['<h2 id="sec-nodes">node explorer — grouped by tier, then type</h2>',
           '<p class="dim">every card: identity · provenance · caveats · VLM '
           'appearance · evidence crops (click to enlarge) · edge list with '
           'numeric evidence. Weak tier = votes &lt; 8.</p>']
    for tier in TIER_ORDER:
        tnodes = [n for n in g["nodes"] if n["confidence_tier"] == tier]
        if not tnodes:
            continue
        out.append(f'<h3 style="color:{TIER_COL[tier]}">{tier} '
                   f'({len(tnodes)})</h3>')
        for typ in ["architecture", "object"]:
            grp = sorted((n for n in tnodes if n["type"] == typ),
                         key=lambda n: (n.get("source") != "envelope", n["id"]))
            if not grp:
                continue
            out.append(f'<h4>{typ} ({len(grp)})</h4><div class="cards">')
            out.extend(node_card_html(n, edges_by_node, nodes_by_id)
                       for n in grp)
            out.append("</div>")
    return "".join(out)


def edge_tables_html(g, nodes_by_id):
    # per-type evidence columns (key, header); sortable numeric via data-v
    cols = {
        "ON": [("gap_m", "gap m"), ("overlap_frac_of_a", "footprint ovl"),
               ("supporter", "supporter")],
        "IN": [("frac_of_smaller", "frac of smaller"),
               ("overlap_vol_m3", "overlap m³"), ("vol_small_m3", "vol small"),
               ("vol_big_m3", "vol big")],
        "IN_WALL": [("wall_distance_m", "dist m"), ("wall_axis", "axis"),
                    ("wall_value_raw", "plane")],
        "ATTACHED": [("ceiling_distance_m", "ceiling dist m"),
                     ("rule", "rule")],
        "INTERPENETRATES": [("overlap_vol_m3", "overlap m³"),
                            ("frac_of_smaller", "frac of smaller")],
    }
    out = ['<h2 id="sec-edges">edge tables (every edge, numeric evidence)</h2>',
           '<p class="dim">click a column header to sort · dimmed rows carry '
           'the z_fabricated caveat (box depth extents are fabricated as '
           '(w+h)/2, so overlap-derived numbers are inflated — shown, not '
           'hidden)</p>']
    for t in EDGE_ORDER:
        edges = [e for e in g["edges"] if e["type"] == t]
        if not edges:
            continue
        if t == "INTERPENETRATES":  # default order: largest overlap first
            edges = sorted(edges, key=lambda e: -(e["evidence"]
                           .get("overlap_vol_m3") or 0))
        ths = "".join(f'<th onclick="sortTable(this)">{esc(h)}</th>'
                      for _, h in cols[t])
        rows = []
        for e in edges:
            dim = ' class="edim"' if "z_fabricated" in (e.get("caveats") or []) else ""
            tds = []
            for k, _ in cols[t]:
                v = (e.get("evidence") or {}).get(k)
                dv = f' data-v="{v}"' if isinstance(v, (int, float)) else ""
                tds.append(f'<td{dv}>{fmt(v) if v is not None else "—"}</td>')
            extra = ", ".join(f"{k} {fmt(v)}" for k, v in
                              (e.get("evidence") or {}).items()
                              if k not in [c[0] for c in cols[t]])
            tds.append(f'<td class="dim">{esc(extra) or "—"}</td>')
            rows.append(f'<tr{dim}><td>{node_ref(e["a"], nodes_by_id)}</td>'
                        f'<td>{node_ref(e["b"], nodes_by_id)}</td>'
                        f'{"".join(tds)}</tr>')
        out.append(
            f'<details class="etable" open><summary><span style="color:'
            f'{EDGE_COL[t]}"><b>{t}</b></span> ({len(edges)}) '
            f'<span class="dim">— {esc(EDGE_MEANING[t])}</span></summary>'
            f'<table><thead><tr><th onclick="sortTable(this)">a</th>'
            f'<th onclick="sortTable(this)">b</th>{ths}<th>other evidence</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></details>')
    return "".join(out)


def sanity_html(g, nodes_by_id, scene_dir):
    es = g["edge_summary"]
    out = ['<h2 id="sec-sanity">sanity panel</h2>']

    # ---- floating ----
    fl = es.get("floating", [])
    rows = "".join(
        f'<tr><td>{node_ref(f["id"], nodes_by_id)}</td>'
        f'<td style="color:{TIER_COL.get(f.get("tier"), "#ccc")}">'
        f'{esc(f.get("tier"))}</td>'
        f'<td data-v="{f.get("floor_gap_m")}">{fmt(f.get("floor_gap_m"))}</td>'
        f'</tr>' for f in fl)
    out.append(
        f'<details open><summary><b>floating objects ({len(fl)})</b> '
        f'<span class="dim">— object-typed nodes with no ON and no IN edge. '
        f'Expected residents: wall art + the wall-mounted shelf; the rest is '
        f'candidate detection junk / duplicate clusters</span></summary>'
        f'<table><thead><tr><th>node</th><th>tier</th>'
        f'<th onclick="sortTable(this)">floor gap m</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></details>')

    # ---- unattached architecture ----
    ua = es.get("unattached_architecture", [])
    if ua:
        lis = "".join(f'<li>{node_ref(u["id"], nodes_by_id)} '
                      f'<span class="dim">[{esc(u.get("tier"))}]</span></li>'
                      for u in ua)
        out.append(f'<details open><summary><b>unattached architecture '
                   f'({len(ua)})</b> <span class="dim">— architecture-typed '
                   f'detections with no IN_WALL / ATTACHED anchor</span>'
                   f'</summary><ul>{lis}</ul></details>')

    # ---- label disputes ----
    disputes = [n for n in g["nodes"] if (n.get("appearance") or {})
                .get("label_agreement") is False]
    rows = "".join(
        f'<tr><td>{node_ref(n["id"], nodes_by_id)}</td>'
        f'<td>{esc(n["label"])}</td>'
        f'<td>&ldquo;{esc((n["appearance"] or {}).get("description"))}&rdquo;'
        f'</td></tr>' for n in disputes)
    out.append(
        f'<details open><summary><b>label disputes ({len(disputes)})</b> '
        f'<span class="dim">— appearance.label_agreement == false: the VLM '
        f'looked at the crops and disagreed with the detector label. Prime '
        f'hallucination/duplicate suspects</span></summary>'
        f'<table><thead><tr><th>node</th><th>detector label</th>'
        f'<th>VLM description</th></tr></thead><tbody>{rows}</tbody>'
        f'</table></details>')

    # ---- undescribed ----
    und = [n for n in g["nodes"] if n.get("source") == "detection"
           and not n.get("appearance")]
    lis = "".join(f'<li>{node_ref(n["id"], nodes_by_id)} '
                  f'<span class="dim">[{esc(n["confidence_tier"])}] — '
                  f'appearance null after 1 retry; crops exist in its card'
                  f'</span></li>' for n in und)
    out.append(f'<details open><summary><b>undescribed nodes ({len(und)})</b>'
               f'</summary><ul>{lis or "<li>none</li>"}</ul></details>')

    # ---- recorded input inconsistencies ----
    items = []
    # (1) match accounting, re-derived from match_report.json
    mr_p = scene_dir / "analyzer" / "match_report.json"
    try:
        mr = json.loads(mr_p.read_text(encoding="utf-8"))
        tot, mat, only = (mr["analyzer_total"],
                          mr["analyzer_matched_to_manifest"],
                          mr["analyzer_only_count"])
        gap = tot - mat - only
        items.append(
            f"<b>match accounting:</b> {tot} analyzer boxes = {mat} "
            f"matched-to-manifest + {only} analyzer-only + <b>{gap} in "
            f"neither bucket</b> (match_report.json’s two lists do not "
            f"partition the boxes; recorded at Step 1, metadata attach "
            f"unaffected)")
    except Exception:
        items.append("<b>match accounting:</b> analyzer/match_report.json "
                     "not readable — accounting check skipped")
    # (2) loop-adds without nodes, re-derived from composed_state2.json
    cs_p = scene_dir / "package" / "composed_state2.json"
    try:
        adds = sorted(set(re.findall(r"add_\d+", cs_p.read_text(
            encoding="utf-8"))))
        orphan = [a for a in adds if a not in nodes_by_id]
        if orphan:
            items.append(
                f"<b>loop-adds without nodes:</b> {', '.join(orphan)} exist "
                f"in package/composed_state2.json (C7-loop additions) but "
                f"seeded no graph node — the node seed is analyzer boxes "
                f"only (user decision 2026-07-22)")
    except Exception:
        items.append("<b>loop-adds:</b> package/composed_state2.json not "
                     "readable — loop-add check skipped")
    # (3) render-frame collide export (recorded in graph provenance)
    ce = (g.get("provenance") or {}).get("collide_export")
    if ce:
        items.append(
            f"<b>collisions.json is RENDER-frame:</b> "
            f"{esc(ce.get('note'))} (n_pairs {ce.get('n_pairs')})")
    # (4) envelope-outlier windows (caveat recorded on the nodes)
    outl = [n["id"] for n in g["nodes"]
            if "center_outside_envelope" in (n["geometry"].get("caveats") or [])]
    if outl:
        items.append(
            f"<b>envelope outliers:</b> {', '.join(esc(i) for i in outl)} "
            f"(window boxes whose centers fall OUTSIDE the envelope extent — "
            f"caveat center_outside_envelope; windows sit in the wall plane, "
            f"the envelope is the splat p1–p99 interior)")
    lis = "".join(f"<li>{it}</li>" for it in items)
    out.append(f'<details open><summary><b>recorded input inconsistencies '
               f'({len(items)})</b></summary><ul>{lis}</ul></details>')

    # ---- edge self-check ----
    sc = es.get("self_check", {})
    ok = sc.get("passed")
    det = sc.get("details")
    det_s = ("<ul>" + "".join(f"<li>{esc(d)}</li>" for d in det) + "</ul>"
             if isinstance(det, list) else f"<div>{esc(det)}</div>")
    out.append(
        f'<details><summary><b>build_edges frame self-check:</b> '
        f'<span style="color:{"#33ee66" if ok else "#ff3333"}">'
        f'{"PASS" if ok else "FAIL"}</span> <span class="dim">— '
        f'manifest-confirmed floor-standers must be ON arch_floor, nothing ON '
        f'arch_ceiling (guards the up = &minus;y sign)</span></summary>'
        f'{det_s}</details>')
    return "".join(out)


CSS = """
body { margin: 0; background: #14141a; color: #ddd;
       font: 13px/1.5 monospace; padding: 14px 18px 60px; }
a { color: #7fc4ff; } a.nref { color: #7fc4ff; text-decoration: none; }
a.nref:hover { text-decoration: underline; }
h2 { color: #ffe27f; border-bottom: 1px solid #333; padding-bottom: 3px;
     margin-top: 34px; }
h3 { margin: 18px 0 4px; } h4 { margin: 10px 0 4px; color: #9ab; }
code { color: #aee7a0; }
.dim { color: #889; }
.banner { border: 2px solid #d03030; background: #2a1518; border-radius: 8px;
          padding: 10px 16px; margin-bottom: 12px; }
.btitle { font-size: 17px; font-weight: bold; color: #ff6a5a; }
.banner ul { margin: 4px 0 8px; }
.stats { background: #1d1d26; border-radius: 6px; padding: 8px 12px;
         margin-bottom: 6px; }
.mmwrap { background: #1d1d26; border-radius: 6px; padding: 10px;
          overflow-x: auto; }
.mmtools { margin-bottom: 4px; } .mmtools label { margin-right: 12px; }
#minimap { background: #101016; border-radius: 4px; margin-top: 6px; }
#minimap .room { fill: none; stroke: #4d8f4d; stroke-width: 2.5; }
#minimap .mnode { cursor: pointer; }
#minimap .mnode:hover { fill-opacity: 0.45; }
#minimap .axlab { fill: #6fae6f; font: 12px monospace; }
.cards { display: flex; flex-wrap: wrap; gap: 8px; }
.card { background: #1d1d26; border: 1px solid #2c2c38; border-radius: 6px;
        padding: 8px 10px; width: 380px; }
.card:target { outline: 2px solid #ffee44; }
.chead { font-size: 13px; } .nid { color: #8899aa; }
.meta { color: #9ab; margin: 2px 0; }
.badge { border: 1px solid #667; border-radius: 4px; padding: 0 5px;
         font-size: 11px; margin-left: 4px; }
.btype { color: #aac; } .benv { color: #6fae6f; border-color: #6fae6f; }
.cav { display: inline-block; background: #2a2a1a; color: #bbaa66;
       border-radius: 3px; padding: 0 4px; font-size: 10.5px;
       margin: 1px 3px 1px 0; }
.adesc { color: #cfe3cf; font-style: italic; margin: 3px 0 2px; }
.dispute { color: #ffaa33; } .undesc { color: #ff77ff; }
.chip { display: inline-block; background: #23232e; border: 1px solid #3a3a4a;
        border-radius: 8px; padding: 0 6px; font-size: 11px; margin: 1px 2px; }
.chipm { border-color: #6a8; } .chips2 { border-color: #a86; }
.crops { margin: 4px 0; }
.crops img { height: 74px; margin: 2px; border-radius: 3px; cursor: pointer;
             vertical-align: middle; }
.ehead { color: #ffe27f; margin-top: 4px; }
.erow { font-size: 12px; } .edim { opacity: 0.5; }
table { border-collapse: collapse; margin: 6px 0; }
th, td { border: 1px solid #2c2c38; padding: 2px 8px; text-align: left; }
th { background: #23232e; cursor: pointer; user-select: none; }
tr.edim td { opacity: 0.55; }
details.etable, #sec-sanity ~ details { background: #1d1d26;
    border-radius: 6px; padding: 6px 10px; margin: 8px 0; }
summary { cursor: pointer; }
#lightbox { display: none; position: fixed; inset: 0;
            background: rgba(0,0,0,.85); z-index: 50; text-align: center; }
#lightbox img { max-width: 96vw; max-height: 96vh; margin-top: 2vh; }
#toc { position: fixed; top: 8px; right: 8px; background: rgba(0,0,0,.65);
       border-radius: 6px; padding: 6px 10px; z-index: 10; }
#toc a { display: block; }
"""

JS = """
function showImg(src) {
  const lb = document.getElementById('lightbox');
  lb.querySelector('img').src = src;
  lb.style.display = 'block';
}
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('lightbox').onclick =
    e => e.currentTarget.style.display = 'none';
});
function mmToggle(t, on) {
  document.getElementById('me-' + t).style.display = on ? '' : 'none';
}
function jumpTo(id) { location.hash = 'node-' + id; }
function sortTable(th) {
  const table = th.closest('table'), tbody = table.tBodies[0];
  const idx = Array.from(th.parentNode.children).indexOf(th);
  const asc = th.dataset.asc !== '1';
  th.dataset.asc = asc ? '1' : '0';
  const rows = Array.from(tbody.rows);
  rows.sort((r1, r2) => {
    const c1 = r1.cells[idx], c2 = r2.cells[idx];
    const a = c1.dataset.v ?? c1.textContent, b = c2.dataset.v ?? c2.textContent;
    const na = parseFloat(a), nb = parseFloat(b);
    const cmp = (!isNaN(na) && !isNaN(nb)) ? na - nb
                                           : String(a).localeCompare(String(b));
    return asc ? cmp : -cmp;
  });
  rows.forEach(r => tbody.appendChild(r));
}
"""


def build_page(g, scene, scene_dir):
    nodes_by_id = {n["id"]: n for n in g["nodes"]}
    edges_by_node = {}
    for e in g["edges"]:
        edges_by_node.setdefault(e["a"], []).append(e)
        edges_by_node.setdefault(e["b"], []).append(e)
    disputes = [n for n in g["nodes"] if (n.get("appearance") or {})
                .get("label_agreement") is False]
    undescribed = [n for n in g["nodes"] if n.get("source") == "detection"
                   and not n.get("appearance")]

    toc = ('<div id="toc"><b>jump</b>'
           '<a href="#sec-minimap">minimap</a>'
           '<a href="#sec-nodes">nodes</a>'
           '<a href="#sec-edges">edges</a>'
           '<a href="#sec-sanity">sanity</a></div>')
    frame_note = (g.get("frame") or {}).get("note", "")
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>scene graph review — {esc(scene)} (Checkpoint G1)</title>",
        f"<style>{CSS}</style><script>{JS}</script></head><body>",
        toc,
        banner_html(scene),
        stats_html(g, disputes, undescribed),
        f'<p class="dim">frame: {esc(frame_note)}</p>',
        minimap_html(g, nodes_by_id),
        explorer_html(g, edges_by_node, nodes_by_id),
        edge_tables_html(g, nodes_by_id),
        sanity_html(g, nodes_by_id, scene_dir),
        f'<p class="dim">generated by graph/graph_review.py (Step 4 — '
        f'graph-review build) from scene_graph.json · '
        f'{esc(g.get("generated_by", ""))} · appearance: '
        f'{esc((g.get("appearance_meta") or {}).get("model", ""))}</p>',
        '<div id="lightbox"><img></div>',
        "</body></html>",
    ]
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    args = ap.parse_args()
    scene_dir = paths.scene_dir(args.scene)
    gp = scene_dir / "scene_graph.json"
    if not gp.exists():
        sys.exit(f"no {gp}; run graph/build_graph.py + build_edges.py first")
    g = json.loads(gp.read_text(encoding="utf-8"))
    if not g.get("edges"):
        sys.exit("scene_graph.json has no edges; run graph/build_edges.py first")
    html = build_page(g, args.scene, scene_dir)
    outp = scene_dir / "graph_review.html"
    outp.write_text(html, encoding="utf-8")
    ec = g["edge_summary"]["edge_counts"]
    print(f"[graph_review] wrote {outp}")
    print(f"[graph_review] nodes {g['counts']['nodes']} "
          f"(det {g['counts']['detection_nodes']} + env "
          f"{g['counts']['envelope_nodes']}), edges {sum(ec.values())} "
          f"{ec}, size {outp.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()

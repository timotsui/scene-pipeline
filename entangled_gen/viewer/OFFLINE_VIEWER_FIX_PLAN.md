# Offline viewer fix plan — vendor the CDN libraries

> **STATUS: DONE 2026-07-17.** Both viewers vendored + import maps repointed.
> **One thing the plan missed:** `serve.py` is a custom route-table server with
> NO static-file handler (final `else` → 404), so `/vendor/*.js` requests 404'd
> until a `/vendor/` route was added to BOTH serve.py files (serves from
> `HERE/vendor` with a `text/javascript` mime + `../` traversal guard). Verified
> live: every import-map URL returns 200 + `text/javascript` from local disk.
> `BufferGeometryUtils.js` was the one transitive dep (pulled by GLTFLoader).

---


**Problem.** The viewer goes blank with no wifi because all 3D libraries are
fetched from `unpkg.com` at page load. Localhost serving is fine; the ES-module
imports over the internet are what fail. When they fail the top-level
`import * as THREE from 'three'` throws and the whole `<script type="module">`
never runs → blank page.

**Fix.** Download the library files once (while online) into a local `vendor/`
folder next to `index.html`, and repoint the import map at those local paths.
After that the viewer is fully offline.

---

## Files affected

1. `scene-pipeline/entangled_gen/viewer/index.html`  — CANONICAL (code home)
2. `CS-8903-OVM/week7/entangled_gen/viewer/index.html` — older copy, simpler set

The canonical one is authoritative (per project convention, week folders are
data only). Decide whether the week7 copy is still used; if yes, give it the
same treatment (it needs only `three` + `OrbitControls`).

---

## Exact dependency list

### Canonical viewer needs (import map lines 68-73)
| specifier in code | current URL |
|---|---|
| `three` | `https://unpkg.com/three@0.160.0/build/three.module.js` |
| `three/addons/` (prefix) | `https://unpkg.com/three@0.160.0/examples/jsm/` |
| `gaussian-splats-3d` | `https://unpkg.com/@mkkellogg/gaussian-splats-3d@0.4.7/build/gaussian-splats-3d.module.js` |

Addon files actually imported from the `three/addons/` prefix:
- `controls/OrbitControls.js`  (static, line 77)
- `loaders/GLTFLoader.js`      (lazy, lines 524 / 612 / 645)

### Week7 viewer needs (import map lines 51-55)
- `three` (core)
- `controls/OrbitControls.js`

---

## Steps

### 1. Create the vendor folder (canonical viewer)
```
scene-pipeline/entangled_gen/viewer/vendor/
  three.module.js
  jsm/                          # mirrors three examples/jsm/ layout
    controls/OrbitControls.js
    loaders/GLTFLoader.js
    ...(any transitive addon deps found in step 2)...
  gaussian-splats-3d.module.js
```

Download (while ONLINE), pinned to the SAME versions to avoid API drift:
```bash
cd scene-pipeline/entangled_gen/viewer
mkdir -p vendor/jsm/controls vendor/jsm/loaders
curl -L -o vendor/three.module.js \
  https://unpkg.com/three@0.160.0/build/three.module.js
curl -L -o vendor/jsm/controls/OrbitControls.js \
  https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js
curl -L -o vendor/jsm/loaders/GLTFLoader.js \
  https://unpkg.com/three@0.160.0/examples/jsm/loaders/GLTFLoader.js
curl -L -o vendor/gaussian-splats-3d.module.js \
  https://unpkg.com/@mkkellogg/gaussian-splats-3d@0.4.7/build/gaussian-splats-3d.module.js
```

### 2. Resolve transitive addon imports  (IMPORTANT — do not skip)
The three addons resolve their own sub-imports at runtime:
- `import ... from 'three'`         → covered by the `three` map entry ✓
- `import ... from 'three/addons/..'`→ covered by the `three/addons/` prefix,
   BUT the referenced sibling file must also exist in `vendor/jsm/`.

GLTFLoader in particular may pull e.g. `../utils/BufferGeometryUtils.js`.
So after step 1, grep the downloaded addon files for their imports and fetch
any missing siblings, repeating until nothing new appears:
```bash
grep -REho "from ['\"][^'\"]+['\"]" vendor/jsm | sort -u
# for every 'three/addons/<path>' or relative '../<path>' seen that isn't
# already on disk, curl it from the matching examples/jsm/<path> URL into
# vendor/jsm/<path> (create subdirs). Repeat the grep after each round.
```
(Alternative if this gets tedious: vendor the whole `examples/jsm/` tree —
a few MB, guarantees every relative import resolves. Heavier but foolproof.)

`three.module.js` (core) and `gaussian-splats-3d.module.js` are self-contained
single-file bundles — no transitive fetches beyond the `three` bare import,
which the map already covers.

### 3. Repoint the import map (canonical, replace lines 68-74)
```html
<script type="importmap">
{ "imports": {
    "three": "./vendor/three.module.js",
    "three/addons/": "./vendor/jsm/",
    "gaussian-splats-3d": "./vendor/gaussian-splats-3d.module.js"
} }
</script>
```
No other code changes — every `import ... from 'three'` /
`'three/addons/...'` / `'gaussian-splats-3d'` in the body stays identical; only
where the map points changes.

### 4. Week7 viewer (if still used)
Either point its import map at the SAME vendor folder via a relative path, or
give it its own `vendor/` with just `three.module.js` +
`jsm/controls/OrbitControls.js`. Replace its lines 51-55:
```html
<script type="importmap">
{ "imports": {
    "three": "./vendor/three.module.js",
    "three/addons/": "./vendor/jsm/"
} }
</script>
```

---

## Verification (do with WIFI OFF)
1. Start the local server, open the viewer.
2. F12 → Network: confirm NO requests go to `unpkg.com` / any `https://` host;
   all module fetches are `./vendor/...` and succeed.
3. F12 → Console: no `net::ERR` / failed-import errors.
4. Base view: point cloud + grid + boxes render and orbit.
5. Toggle `hi-fi splats` → real gaussians load from `splat.ply` (line 256 lazy
   import now resolves locally).
6. Toggle `composed` / `collider` / `GLTS` → GLB overlays load (GLTFLoader
   local).
7. Sanity grep — should return nothing:
```bash
grep -nE "unpkg|https://" scene-pipeline/entangled_gen/viewer/index.html
```

---

## Notes / gotchas
- Keep the version pins (three 0.160.0, gaussian-splats-3d 0.4.7). A different
  three version can break OrbitControls/GLTFLoader API expectations.
- gaussian-splats-3d creates workers from inline blobs (sharedMemoryForWorkers
  is already false at line 258), so no extra worker-file fetch to vendor.
- `HunyuanWorld-1.0/modelviewer.html` also uses jsdelivr CDN (three 0.132 +
  PLYLoader + DRACOLoader) but is a repo-bundled file, not our viewer — out of
  scope unless you actually use it offline.
- Size budget: three core ~1.2 MB, gaussian-splats-3d ~0.2 MB, addons small.
  Total vendor folder is a few MB; fine to keep alongside the viewer.

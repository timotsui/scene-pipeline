const STAGE_TEXT = {
  input: {
    title: "The benchmark scene enters as posed RGB-D frames",
    copy: "Hypersim supplied the image sequence, exact cameras, metric depth, and visible 3D ground truth. This is benchmark preparation, not a generated scene and not a splat render."
  },
  train: {
    title: "A 3D Gaussian scene is trained from those views",
    copy: "The analyzer needs a navigable radiance field, so each scene was reconstructed as a 5,000-step Gaussian splat. This is a benchmark prerequisite outside the canonical pipeline map."
  },
  verify: {
    title: "Held-out cameras test the reconstruction",
    copy: "Five prepared views were withheld by a fixed rule. Each comparison is the saved ground-truth/render pair; PSNR is shown as a measurement, not a visual verdict."
  },
  sweep: {
    title: "The analyzer chooses standpoints and renders a sweep",
    copy: "The external side-tool branch samples the trained splat from many directions. Scrub the exact saved analyzer frames; depth is available beside RGB for every viewpoint."
  },
  detect: {
    title: "OWLv2 detections accumulate across the sweep",
    copy: "The analyzer queries the target vocabulary on rendered views, then groups observations into object hypotheses. The overlay below is drawn from interactions.json, not inferred from the pixels by this page."
  },
  native: {
    title: "Rectangles become coarse 3D object boxes",
    copy: "The native analyzer lifts 2D rectangles through rendered depth and clusters their 3D support. Toggle layers in the top-down evidence map; hover a footprint for its saved label and bounds."
  },
  mask: {
    title: "SAM replaces rectangle support with mask support",
    copy: "A development branch segmented the analyzer observations, lifted mask pixels, and robustly bounded the resulting 3D points. The scene map compares that output directly with the native lift and ground truth."
  },
  vote: {
    title: "SliceVote actively re-observes each proposal",
    copy: "The active branch renders object-centered slices, votes across those views, and updates the 3D bounds. Its output remains one prediction set per scene and is shown against the preceding global mask lift."
  },
  evaluate: {
    title: "Every output is scored against visible 3D ground truth",
    copy: "The benchmark computes scene-level detection and localization measurements. Bars report saved numbers only; they do not claim that a method is visually acceptable."
  },
  external: {
    title: "The same scenes are adapted to Zoo3D and Boxer",
    copy: "External outputs were converted into the same axis-aligned box schema and evaluated with the same ground truth. Toggle all footprints to inspect where the methods place objects."
  }
};

const LAYERS = {
  groundTruth: { label: "Ground truth", color: "#f3f2ed" },
  native: { label: "Native rect lift", color: "#ff7448" },
  global: { label: "SAM mask lift", color: "#67b8ff" },
  active: { label: "Active SliceVote", color: "#c7f36a" },
  zoo3d: { label: "Zoo3D", color: "#f587ca" },
  boxer: { label: "Boxer", color: "#ffd166" }
};

const state = { data: null, scene: 0, stage: 0 };
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[char]);
const fmt = (value, digits = 2) => value == null ? "—" : Number(value).toFixed(digits);
const pct = value => value == null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
const bytes = value => value == null ? "—" : `${(value / (1024 * 1024)).toFixed(1)} MB`;
const scene = () => state.data.scenes[state.scene];
const stage = () => state.data.stages[state.stage];

function artifactFrame(s, index, depth = false) {
  const stem = String(index).padStart(4, "0");
  const name = depth ? `depth_${stem}.png` : `frame_${stem}.png`;
  return `/benchmark-artifacts/predictions/${s.analyzer.directory}/frames/${name}`;
}

function parseUrl() {
  const params = new URLSearchParams(location.search);
  const sceneIndex = state.data.scenes.findIndex(item => item.id === params.get("scene"));
  const stageIndex = state.data.stages.findIndex(item => item.id === params.get("stage"));
  state.scene = sceneIndex >= 0 ? sceneIndex : 0;
  state.stage = stageIndex >= 0 ? stageIndex : 0;
}

function syncUrl() {
  const params = new URLSearchParams({ scene: scene().id, stage: stage().id });
  history.replaceState(null, "", `${location.pathname}?${params}`);
}

function buildNavigation() {
  $("#scene-tabs").innerHTML = state.data.scenes.map((item, index) =>
    `<button class="scene-tab ${index === state.scene ? "active" : ""}" data-scene="${index}" type="button">${esc(item.name)}</button>`
  ).join("");
  $("#stage-list").innerHTML = state.data.stages.map((item, index) =>
    `<button class="stage-button ${index === state.stage ? "active" : ""} ${item.ran !== "5/5" ? "partial" : ""}" data-stage="${index}" type="button">
      <span class="stage-number">${item.number}</span><span class="stage-name">${esc(item.name)}</span><span class="stage-ran">${item.ran}</span>
    </button>`
  ).join("");
  document.querySelectorAll("[data-scene]").forEach(button => button.addEventListener("click", () => selectScene(Number(button.dataset.scene))));
  document.querySelectorAll("[data-stage]").forEach(button => button.addEventListener("click", () => selectStage(Number(button.dataset.stage))));
}

function selectScene(index) {
  state.scene = Math.max(0, Math.min(state.data.scenes.length - 1, index));
  render();
}

function selectStage(index) {
  state.stage = Math.max(0, Math.min(state.data.stages.length - 1, index));
  render();
  $("#main").focus({preventScroll: true});
  window.scrollTo({top: 0, behavior: "smooth"});
}

function fact(label, value, detail = "") {
  return `<div class="fact"><div class="fact-label">${esc(label)}</div><div class="fact-value">${esc(value)}</div><div class="fact-detail">${esc(detail)}</div></div>`;
}

function setFacts(items) {
  $("#facts").innerHTML = items.join("");
}

function evidenceLinks(keys) {
  const labels = {
    manifest: "benchmark manifest", trainingReceipt: "training receipt", reconstructionReceipt: "reconstruction metrics",
    interactions: "interactions.json", analyzerTransforms: "analyzer cameras", nativePredictions: "native predictions",
    maskReceipt: "SAM lift receipt", samMaskIndex: "SAM mask index", globalPredictions: "SAM predictions",
    sliceMetrics: "SliceVote metrics", activePredictions: "active predictions", boxer2dCsv: "Boxer 2D detections",
    boxerPredictions: "Boxer 3D predictions", zoo3dPredictions: "Zoo3D predictions"
  };
  const links = keys
    .filter(key => scene().artifacts[key] && !(key === "maskReceipt" && !scene().sam.ran))
    .map(key => `<a href="${scene().artifacts[key]}" target="_blank" rel="noreferrer">${labels[key] || key} ↗</a>`)
    .join("");
  $("#evidence").innerHTML = `<details><summary>Saved evidence files</summary><div class="evidence-links">${links}</div></details>`;
}

function toolbar(left, right = "") {
  return `<div class="visual-toolbar"><div class="toolbar-group">${left}</div><div class="toolbar-group">${right}</div></div>`;
}

function renderDataflow() {
  const item = stage();
  $("#dataflow").innerHTML = `
    <div class="flow-cell"><span class="flow-label">Input</span><p>${esc(item.input)}</p></div>
    <div class="flow-cell"><span class="flow-label">What the module did</span><p>${esc(item.operation)}</p></div>
    <div class="flow-cell"><span class="flow-label">Saved output</span><p>${esc(item.output)}</p></div>
    <div class="flow-cell warning"><span class="flow-label">Evidence limitation</span><p>${esc(item.missing)}</p></div>`;
}

function renderDiagnostic() {
  const panel = $("#diagnostic");
  const diagnostic = scene().diagnostic;
  const relevant = diagnostic && ["sweep", "detect", "native", "mask", "vote", "evaluate"].includes(stage().id);
  panel.hidden = !relevant;
  if (!relevant) { panel.innerHTML = ""; return; }
  panel.innerHTML = `<strong>${esc(diagnostic.status)} · NOT EXPLAINED</strong><p>${esc(diagnostic.boundary)}</p>
    <div class="diagnostic-grid"><div><h3>Known from saved evidence</h3><ul>${diagnostic.known.map(item => `<li>${esc(item)}</li>`).join("")}</ul></div>
    <div><h3>Not saved / still needed</h3><ul>${diagnostic.missing.map(item => `<li>${esc(item)}</li>`).join("")}</ul></div></div>
    <p><strong style="display:inline;color:#ff9b7c">NEXT:</strong> ${esc(diagnostic.next)}</p>`;
}

function matrixHtml(matrix) {
  if (!matrix?.length) return "<span>matrix not saved</span>";
  return `<div class="matrix">${matrix.flat().map(value => `<span>${fmt(value, 4)}</span>`).join("")}</div>`;
}

function detectionSvg(entries, width = 512, height = 512, color = "#ff7448") {
  return entries.map(entry => {
    const [x1, y1, x2, y2] = normalizeBox(entry.box);
    const x = Math.max(0, x1), y = Math.max(0, y1);
    const w = Math.max(1, Math.min(width, x2) - x), h = Math.max(1, Math.min(height, y2) - y);
    return `<g><rect class="detection-box" style="stroke:${color}" x="${x}" y="${y}" width="${w}" height="${h}"><title>${esc(entry.label)} · score ${fmt(entry.score, 3)}</title></rect><text class="detection-label" style="fill:${color}" x="${x + 3}" y="${Math.max(12, y - 4)}">${esc(entry.label)} ${fmt(entry.score, 2)}</text></g>`;
  }).join("");
}

function renderInput() {
  const s = scene();
  const frames = s.manifest.sourceFrames;
  let position = 0;
  $("#visual").innerHTML = toolbar(
    `<span class="frame-readout">ALL PREPARED RGB + DEPTH</span>`,
    `<input id="input-range" class="range" type="range" min="0" max="${frames.length - 1}" value="0"><span id="input-readout" class="frame-readout"></span>`
  ) + `<div class="paired-stage">
    <figure><img id="input-rgb" class="artifact-image" alt="Prepared RGB frame"><figcaption id="input-rgb-label"></figcaption></figure>
    <figure><img id="input-depth" class="artifact-image" alt="Prepared metric depth frame"><figcaption id="input-depth-label"></figcaption></figure>
    <figure id="input-overlay-card" hidden><img id="input-overlay" class="artifact-image" alt="Saved visible ground-truth overlay"><figcaption>saved visible-GT overlay</figcaption></figure>
  </div>`;
  const update = () => {
    const frame = frames[position];
    $("#input-rgb").src = frame.rgb;
    $("#input-depth").src = frame.depth;
    $("#input-rgb-label").textContent = `RGB frame_${frame.frame}.png`;
    $("#input-depth-label").textContent = `metric depth · scan index ${frame.scanIndex}`;
    $("#input-readout").textContent = `${position + 1} / ${frames.length} · source ${frame.frame}`;
    $("#input-overlay-card").hidden = !frame.overlay;
    if (frame.overlay) $("#input-overlay").src = frame.overlay;
  };
  $("#input-range").addEventListener("input", event => { position = Number(event.target.value); update(); });
  update();
  setFacts([
    fact("Prepared views", s.manifest.frames, `${s.manifest.imageSize.join(" × ")} RGB + metric depth`),
    fact("Visible GT boxes", s.manifest.visibleTargetBoxes, `${s.manifest.allTargetBoxes} before visibility gate`),
    fact("Target vocabulary", s.manifest.targetLabels.length, s.manifest.targetLabels.join(", ")),
    fact("Initial points", Number(s.manifest.initialPoints).toLocaleString(), `camera ${s.manifest.camera}`)
  ]);
  evidenceLinks(["manifest"]);
}

function renderTrain() {
  const s = scene();
  const url = `${state.data.viewer3d}?scene=${s.id}`;
  $("#visual").innerHTML = toolbar(
    `<span class="frame-readout">TRAINED SPLAT · ${esc(s.id)}</span>`,
    `<a class="action-link" href="${url}" target="_blank" rel="noreferrer">Open interactive splat ↗</a>`
  ) + `<div class="triptych">
    <figure><img src="${s.artifacts.source}" alt="Training source frame"><figcaption>input view · not a splat render</figcaption></figure>
    <figure><img src="${s.training.heldOut[0]?.render || s.artifacts.source}" alt="Saved Gaussian render"><figcaption>trained Gaussian render · held-out camera</figcaption></figure>
    <figure><img src="${s.training.heldOut[0]?.comparison || s.artifacts.source}" alt="Saved ground truth and render comparison"><figcaption>saved GT / render comparison</figcaption></figure>
  </div>`;
  setFacts([
    fact("Optimization", `${Number(s.training.steps).toLocaleString()} steps`, `${fmt(s.training.seconds, 1)} seconds recorded`),
    fact("Splat payload", bytes(s.training.plyBytes), "loaded only when you open the 3D viewer"),
    fact("Mean held-out PSNR", `${fmt(s.training.meanPsnrDb, 2)} dB`, "measurement across five held-out cameras"),
    fact("gsplat commit", (s.training.commit || "—").slice(0, 8), s.training.commit || "not recorded")
  ]);
  evidenceLinks(["trainingReceipt", "reconstructionReceipt"]);
}

function renderVerify() {
  const s = scene();
  if (!s.training.heldOut.length) return renderEmpty("No hold-out comparison was saved for this scene.");
  let index = 0;
  const controls = s.training.heldOut.map((item, i) => `<button class="tool-button ${i === 0 ? "active" : ""}" data-held="${i}" type="button">${item.frame.replace("frame_", "")}</button>`).join("");
  $("#visual").innerHTML = toolbar(controls, `<span id="psnr" class="frame-readout"></span>`) + `
    <div class="image-stage"><img id="verify-image" class="artifact-image" alt="Saved held-out reconstruction comparison"><span id="verify-label" class="image-label"></span></div>`;
  const update = () => {
    const item = s.training.heldOut[index];
    $("#verify-image").src = item.comparison;
    $("#verify-label").textContent = `${item.frame} · saved comparison`;
    $("#psnr").textContent = `${fmt(item.psnrDb, 2)} dB PSNR`;
    document.querySelectorAll("[data-held]").forEach(button => button.classList.toggle("active", Number(button.dataset.held) === index));
  };
  document.querySelectorAll("[data-held]").forEach(button => button.addEventListener("click", () => { index = Number(button.dataset.held); update(); }));
  update();
  const values = s.training.heldOut.map(item => item.psnrDb).filter(value => value != null);
  setFacts([
    fact("Held-out views", values.length, s.training.heldOutRule),
    fact("Mean PSNR", `${fmt(s.training.meanPsnrDb, 2)} dB`, "saved reconstruction metric"),
    fact("Lowest PSNR", `${fmt(Math.min(...values), 2)} dB`, "measurement, not a quality decision"),
    fact("Highest PSNR", `${fmt(Math.max(...values), 2)} dB`, "measurement, not a quality decision")
  ]);
  evidenceLinks(["reconstructionReceipt"]);
}

function renderSweep() {
  const s = scene();
  const frames = s.analyzer.frameRecords;
  if (!frames.length) return renderEmpty("No analyzer sweep frames were found.");
  let position = 0;
  $("#visual").innerHTML = toolbar(
    `<span class="frame-readout">RGB + DEPTH + CAMERA TRANSFORM</span>`,
    `<input id="sweep-range" class="range" type="range" min="0" max="${frames.length - 1}" value="0"><span id="sweep-readout" class="frame-readout"></span>`
  ) + `<div class="paired-stage">
    <figure><img id="sweep-rgb" class="artifact-image square" alt="Saved analyzer RGB render"><figcaption id="sweep-rgb-label"></figcaption></figure>
    <figure><img id="sweep-depth" class="artifact-image square" alt="Saved analyzer depth render"><figcaption id="sweep-depth-label"></figcaption></figure>
  </div><div class="evidence-sidebar"><h3>Exact camera-to-world transform</h3><div id="sweep-matrix"></div><a id="sweep-raw" class="action-link" target="_blank" rel="noreferrer">raw metric depth .npy ↗</a></div>`;
  const update = () => {
    const record = frames[position];
    $("#sweep-rgb").src = record.rgb;
    $("#sweep-depth").src = record.depth;
    $("#sweep-rgb-label").textContent = `frame_${record.frame}.png · rendered RGB`;
    $("#sweep-depth-label").textContent = `depth_${record.frame}.png · display copy`;
    $("#sweep-readout").textContent = `${position + 1} / ${frames.length} · standpoint ${record.positionIndex}`;
    $("#sweep-matrix").innerHTML = matrixHtml(record.matrix);
    $("#sweep-raw").href = record.depthRaw;
  };
  $("#sweep-range").addEventListener("input", event => { position = Number(event.target.value); update(); });
  update();
  setFacts([
    fact("Rendered viewpoints", s.analyzer.frames.length, "exact saved analyzer sweep"),
    fact("RGB resolution", "512 × 512", "square analyzer render"),
    fact("Depth views", s.analyzer.frames.length, "paired with the RGB sweep"),
    fact("Map modules", "asp + asw", "standpoint selection → render sweep")
  ]);
  evidenceLinks(["analyzerTransforms", "interactions"]);
}

function normalizeBox(box) {
  if (Array.isArray(box)) return box.map(Number);
  return String(box).trim().split(/\s+/).map(Number);
}

function renderDetect() {
  const s = scene();
  const frames = s.analyzer.frameRecords;
  let position = 0;
  $("#visual").innerHTML = toolbar(
    `<span class="frame-readout">ALL SWEEP VIEWS · FINAL SAVED BOXES</span>`,
    `<input id="detect-range" class="range" type="range" min="0" max="${frames.length - 1}" value="0"><span id="detect-readout" class="frame-readout"></span>`
  ) + `${!s.analyzer.rawDetectionsSaved ? `<div class="missing-evidence"><strong>Raw detector evidence was not saved.</strong> These overlays show only rectangles that survived into interactions.json. An empty overlay cannot distinguish “OWLv2 returned nothing” from “later filtering/grouping removed everything.”</div>` : ""}
    <div class="paired-stage"><figure><div class="annotated-frame"><img id="detect-image" class="artifact-image square" alt="Analyzer frame with final saved detections"><svg id="detect-overlay" class="image-overlay" viewBox="0 0 512 512" aria-label="Final saved detection rectangles"></svg></div><figcaption id="detect-caption"></figcaption></figure>
    <figure><img id="detect-depth" class="artifact-image square" alt="Paired analyzer depth"><figcaption>paired depth used by the later lift</figcaption></figure></div>`;
  const update = () => {
    const record = frames[position];
    const entries = s.analyzer.annotations[record.frame] || [];
    $("#detect-image").src = record.rgb;
    $("#detect-depth").src = record.depth;
    $("#detect-readout").textContent = `${position + 1} / ${frames.length} · frame ${record.frame} · ${entries.length} final boxes`;
    $("#detect-caption").textContent = entries.length ? "final annotations saved in interactions.json" : "no final annotation saved for this view";
    $("#detect-overlay").innerHTML = detectionSvg(entries);
  };
  $("#detect-range").addEventListener("input", event => { position = Number(event.target.value); update(); });
  update();
  const observations = Object.values(s.analyzer.annotations).reduce((sum, entries) => sum + entries.length, 0);
  setFacts([
    fact("Frames with detections", s.analyzer.detectedFrames.length, `${s.analyzer.frames.length} sweep views total`),
    fact("2D observations", observations, "rectangles recorded in interactions.json"),
    fact("3D hypotheses", s.analyzer.objects, "after grouping/voting"),
    fact("Raw scores saved", s.analyzer.rawDetectionsSaved ? "yes" : "no", "required to isolate a zero before/after filtering")
  ]);
  evidenceLinks(["interactions", "analyzerTransforms"]);
}

function layerControls(selected) {
  return Object.entries(LAYERS).filter(([key]) => selected.includes(key)).map(([key, layer]) =>
    `<label class="layer-toggle"><input type="checkbox" data-layer="${key}" checked><span class="swatch" style="background:${layer.color}"></span>${layer.label}</label>`
  ).join("");
}

function topdownSvg(s, enabled) {
  const boxes = enabled.flatMap(key => s.boxes[key] || []);
  const safe = boxes.length ? boxes : [{min: [-1, 0, -1], max: [1, 0, 1]}];
  const minX = Math.min(...safe.map(box => box.min[0]));
  const maxX = Math.max(...safe.map(box => box.max[0]));
  const minZ = Math.min(...safe.map(box => box.min[2]));
  const maxZ = Math.max(...safe.map(box => box.max[2]));
  const span = Math.max(maxX - minX, maxZ - minZ, 2);
  const pad = span * .12;
  const view = [minX - pad, minZ - pad, (maxX - minX) + pad * 2, (maxZ - minZ) + pad * 2];
  const grid = [];
  for (let x = Math.floor(view[0]); x <= Math.ceil(view[0] + view[2]); x++) grid.push(`<line class="grid-line" x1="${x}" y1="${view[1]}" x2="${x}" y2="${view[1] + view[3]}"/>`);
  for (let z = Math.floor(view[1]); z <= Math.ceil(view[1] + view[3]); z++) grid.push(`<line class="grid-line" x1="${view[0]}" y1="${z}" x2="${view[0] + view[2]}" y2="${z}"/>`);
  const shapes = enabled.flatMap(key => (s.boxes[key] || []).map(box => {
    const x = box.min[0], z = box.min[2], w = Math.max(.02, box.max[0] - x), h = Math.max(.02, box.max[2] - z);
    return `<g><rect class="box-shape" x="${x}" y="${z}" width="${w}" height="${h}" fill="${LAYERS[key].color}" stroke="${LAYERS[key].color}"><title>${esc(LAYERS[key].label)} · ${esc(box.label)} · ${esc(box.id)}\nx ${fmt(box.min[0])}…${fmt(box.max[0])} m · z ${fmt(box.min[2])}…${fmt(box.max[2])} m</title></rect></g>`;
  })).join("");
  return `<svg class="topdown-canvas" viewBox="${view.join(" ")}" preserveAspectRatio="xMidYMid meet" aria-label="Top-down x-z box footprints">${grid.join("")}<line class="axis-line" x1="0" y1="${view[1]}" x2="0" y2="${view[1] + view[3]}"/><line class="axis-line" x1="${view[0]}" y1="0" x2="${view[0] + view[2]}" y2="0"/>${shapes}</svg>`;
}

function renderTopdown(keys, facts, evidence) {
  const s = scene();
  $("#visual").innerHTML = toolbar(layerControls(keys), `<span class="frame-readout">TOP DOWN · X / Z METERS</span>`) + `
    <div class="topdown-wrap"><div id="topdown"></div><aside class="legend-panel"><h3>Visible layers</h3><div id="map-legend" class="legend-list"></div><p class="map-help">Each rectangle is an exact saved axis-aligned 3D box footprint. Overlap is intentional. Hover a footprint for label, object ID, and bounds.</p></aside></div>`;
  const update = () => {
    const enabled = [...document.querySelectorAll("[data-layer]:checked")].map(input => input.dataset.layer);
    $("#topdown").innerHTML = topdownSvg(s, enabled);
    $("#map-legend").innerHTML = enabled.map(key => `<div class="legend-row"><span class="swatch" style="background:${LAYERS[key].color}"></span><span>${LAYERS[key].label}</span><span>${s.counts[key] ?? 0}</span></div>`).join("");
  };
  document.querySelectorAll("[data-layer]").forEach(input => input.addEventListener("change", update));
  update();
  setFacts(facts);
  evidenceLinks(evidence);
}

function modeTabs(active, options) {
  return options.map(([id, label]) => `<button class="tool-button ${id === active ? "active" : ""}" data-mode="${id}" type="button">${esc(label)}</button>`).join("");
}

function renderMapWithReturn(keys, facts, evidence, label, callback) {
  renderTopdown(keys, facts, evidence);
  const group = document.querySelector("#visual .toolbar-group");
  group.insertAdjacentHTML("afterbegin", `<button id="return-evidence" class="tool-button" type="button">${esc(label)}</button>`);
  $("#return-evidence").addEventListener("click", callback);
}

function nativeFacts(s) {
  return [
    fact("Native predictions", s.counts.native, `${s.labelCounts.native ? Object.keys(s.labelCounts.native).length : 0} labels`),
    fact("Visible GT", s.counts.groundTruth, "evaluation reference"),
    fact("mAP @ 0.25", pct(s.metrics.native.map25), "saved scene metric"),
    fact("Recall @ 0.25", pct(s.metrics.native.recall25), "saved scene metric")
  ];
}

function renderNative() {
  const s = scene();
  if (!s.boxes.native.length) {
    renderEmpty("No native 3D object exists to inspect. The preceding detector/grouping output is empty; inspect step 5 to scrub all 90 analyzer views and see the saved zero boundary.");
    setFacts(nativeFacts(s));
    evidenceLinks(["interactions", "nativePredictions"]);
    return;
  }
  let objectIndex = 0;
  let supportIndex = 0;
  const drawEvidence = () => {
    const box = s.boxes.native[objectIndex];
    const supports = Object.entries(s.analyzer.annotations).flatMap(([frame, entries]) =>
      entries.filter(entry => Number(entry.object) === objectIndex).map(entry => ({frame, ...entry}))
    );
    supportIndex = Math.min(supportIndex, Math.max(0, supports.length - 1));
    $("#visual").innerHTML = toolbar(
      modeTabs("evidence", [["evidence", "Supporting 2D evidence"], ["map", "3D result"]]),
      `<label>Object <select id="native-object">${s.boxes.native.map((item, index) => `<option value="${index}" ${index === objectIndex ? "selected" : ""}>${index} · ${esc(item.label)} · ${esc(item.id)}</option>`).join("")}</select></label>`
    ) + `<div class="missing-evidence"><strong>How this box was made:</strong> the saved rectangles below were back-projected through the paired depth and camera transforms, then their 3D support was clustered and bounded. Raw point clouds were not saved.</div>
      ${supports.length ? `<div class="paired-stage"><figure><div class="annotated-frame"><img id="native-rgb" class="artifact-image square" alt="Supporting analyzer frame"><svg id="native-overlay" class="image-overlay" viewBox="0 0 512 512"></svg></div><figcaption id="native-caption"></figcaption></figure><figure><img id="native-depth" class="artifact-image square" alt="Depth used to lift the rectangle"><figcaption>paired depth used for back-projection</figcaption></figure></div>
      ${toolbar(`<input id="native-range" class="range" type="range" min="0" max="${supports.length - 1}" value="${supportIndex}">`, `<span id="native-readout" class="frame-readout"></span>`)}` : `<div class="empty-state"><div><strong>No supporting rectangles retained in interactions.json</strong><p>The 3D prediction exists, but its per-view support is absent from the saved interaction record.</p></div></div>`}
      <aside class="evidence-sidebar"><h3>Saved 3D result</h3><p>${esc(box.label)} · score ${fmt(box.score, 4)}</p><pre>${esc(JSON.stringify({min: box.min, max: box.max}, null, 2))}</pre></aside>`;
    const update = () => {
      if (!supports.length) return;
      const item = supports[supportIndex];
      const record = s.analyzer.frameRecords.find(frame => frame.frame === item.frame);
      $("#native-rgb").src = record.rgb;
      $("#native-depth").src = record.depth;
      $("#native-overlay").innerHTML = detectionSvg([item]);
      $("#native-caption").textContent = `frame ${item.frame} · ${item.label} · score ${fmt(item.score, 3)}`;
      $("#native-readout").textContent = `${supportIndex + 1} / ${supports.length} supporting views`;
    };
    $("#native-object").addEventListener("change", event => { objectIndex = Number(event.target.value); supportIndex = 0; drawEvidence(); });
    $("[data-mode='map']").addEventListener("click", () => renderMapWithReturn(["groundTruth", "native"], nativeFacts(s), ["interactions", "nativePredictions"], "Supporting 2D evidence", drawEvidence));
    if (supports.length) $("#native-range").addEventListener("input", event => { supportIndex = Number(event.target.value); update(); });
    update();
  };
  drawEvidence();
  setFacts(nativeFacts(s));
  evidenceLinks(["interactions", "nativePredictions"]);
}

function renderMask() {
  const s = scene();
  const facts = [
    fact("Objects into SAM", s.sam.inputObjects, `${s.sam.observations} supporting observations`),
    fact("Saved exact masks", s.sam.savedMasks || 0, `${s.sam.processedFrames} processed frames`),
    fact("Mask-lifted", s.sam.maskLifted, `${s.sam.fallback} rectangle fallbacks`),
    fact("Global mAP @ 0.25", pct(s.metrics.global.map25), s.sam.model || "SAM")
  ];
  if (!s.sam.ran) {
    renderEmpty("SAM did not receive an input: the saved analyzer result contains zero proposals. This is a skipped downstream branch, not evidence that SAM rejected the Dining scene. Inspect step 5 for all 90 upstream views.");
    setFacts(facts);
    evidenceLinks(["interactions"]);
    return;
  }
  let frameIndex = 0;
  let observationIndex = 0;
  const drawEvidence = () => {
    const frame = s.sam.frames[frameIndex];
    const observation = frame.observations[observationIndex];
    $("#visual").innerHTML = toolbar(
      modeTabs("evidence", [["evidence", "Saved mask evidence"], ["map", "3D result"]]),
      `<label>Frame <select id="mask-frame">${s.sam.frames.map((item, index) => `<option value="${index}" ${index === frameIndex ? "selected" : ""}>${item.frame} · ${item.observations.length} masks</option>`).join("")}</select></label><label>Observation <select id="mask-observation">${frame.observations.map((item, index) => `<option value="${index}" ${index === observationIndex ? "selected" : ""}>${index} · obj ${item.object} · ${esc(item.label)}</option>`).join("")}</select></label>`
    ) + `<div class="missing-evidence"><strong>How this mask became 3D:</strong> the exact saved binary pixels were back-projected through the paired depth and camera matrix. Robust low/high bounds produced the global box; the trust vector records which bound faces were accepted.</div>
      <div class="triptych"><figure><img src="${frame.source}" class="artifact-image square" alt="Analyzer RGB supplied to SAM"><figcaption>input RGB · frame ${frame.frame}</figcaption></figure><figure><img src="${observation.mask}" class="artifact-image square mask-image" alt="Exact saved binary SAM mask"><figcaption>exact mask · ${observation.maskPixels.toLocaleString()} pixels</figcaption></figure><figure><img src="${frame.depth}" class="artifact-image square" alt="Depth used to lift the mask"><figcaption>paired depth used for back-projection</figcaption></figure></div>
      <aside class="evidence-sidebar"><h3>Observation record</h3><pre>${esc(JSON.stringify({object: observation.object, label: observation.label, score: observation.score, lifted: observation.lifted, lo: observation.lo, hi: observation.hi, trust: observation.trust}, null, 2))}</pre></aside>`;
    $("#mask-frame").addEventListener("change", event => { frameIndex = Number(event.target.value); observationIndex = 0; drawEvidence(); });
    $("#mask-observation").addEventListener("change", event => { observationIndex = Number(event.target.value); drawEvidence(); });
    $("[data-mode='map']").addEventListener("click", () => renderMapWithReturn(["groundTruth", "native", "global"], facts, ["interactions", "maskReceipt", "samMaskIndex", "globalPredictions"], "Saved mask evidence", drawEvidence));
  };
  drawEvidence();
  setFacts(facts);
  evidenceLinks(["interactions", "maskReceipt", "samMaskIndex", "globalPredictions"]);
}

function renderVote() {
  const s = scene();
  const facts = [
    fact("Active predictions", s.counts.active, "object-centered re-observation"),
    fact("Saved vote visuals", s.activeEvidence.visualFiles || 0, `${s.activeEvidence.objects?.length || 0} object records`),
    fact("mAP @ 0.25", pct(s.metrics.active.map25), `global ${pct(s.metrics.global.map25)}`),
    fact("Recall @ 0.25", pct(s.metrics.active.recall25), `global ${pct(s.metrics.global.recall25)}`)
  ];
  if (!s.counts.active) {
    renderEmpty("SliceVote had no object to re-observe because the saved detector/native branch is empty. The zero is preserved in evaluation, but it was created upstream—not by SliceVote.");
    setFacts(facts);
    evidenceLinks(["interactions"]);
    return;
  }
  let objectIndex = 0;
  const drawEvidence = () => {
    const object = s.activeEvidence.objects[objectIndex];
    const cards = [object.conemap ? {name: "conemap", url: object.conemap, kind: "object-centered cone/plan evidence"} : null, ...object.assets].filter(Boolean);
    $("#visual").innerHTML = toolbar(
      modeTabs("evidence", [["evidence", "Per-object vote evidence"], ["map", "3D result"]]),
      `<label>Object <select id="vote-object">${s.activeEvidence.objects.map((item, index) => `<option value="${index}" ${index === objectIndex ? "selected" : ""}>${item.id} · ${esc(item.name)} · ${item.assets.length + Boolean(item.conemap)} files</option>`).join("")}</select></label>`
    ) + `<div class="evidence-layout"><aside class="evidence-sidebar"><h3>${esc(object.id)} · ${esc(object.name)}</h3><p>${object.nviewsVote} vote views requested</p><pre>${esc(JSON.stringify({boxes: object.boxes, decision: object.rule}, null, 2))}</pre><div class="evidence-links">${object.row ? `<a href="${object.row}" target="_blank" rel="noreferrer">full object HTML row ↗</a>` : ""}<a href="${s.activeEvidence.report}" target="_blank" rel="noreferrer">full SliceVote report ↗</a><a href="${s.activeEvidence.preview}" target="_blank" rel="noreferrer">preview manifest ↗</a></div></aside>
      <div class="asset-gallery">${cards.map(card => `<figure class="asset-card"><a href="${card.url}" target="_blank" rel="noreferrer"><img src="${card.url}" loading="lazy" alt="${esc(card.kind)} for ${esc(object.id)}"></a><figcaption>${esc(card.kind)} · ${esc(card.name)}</figcaption></figure>`).join("")}</div></div>`;
    $("#vote-object").addEventListener("change", event => { objectIndex = Number(event.target.value); drawEvidence(); });
    $("[data-mode='map']").addEventListener("click", () => renderMapWithReturn(["groundTruth", "global", "active"], facts, ["sliceMetrics", "maskReceipt", "activePredictions"], "Per-object vote evidence", drawEvidence));
  };
  drawEvidence();
  setFacts(facts);
  evidenceLinks(["sliceMetrics", "maskReceipt", "activePredictions"]);
}

function methodTable(methods) {
  return `<table class="method-table"><thead><tr><th>Output</th><th>boxes</th><th>mAP25</th><th>recall25</th><th>mAP50</th></tr></thead><tbody>${methods.map(key => {
    const m = scene().metrics[key];
    return `<tr><td><span class="swatch" style="display:inline-block;margin-right:7px;background:${LAYERS[key].color}"></span>${LAYERS[key].label}</td><td>${scene().counts[key] ?? 0}</td><td>${pct(m.map25)}</td><td>${pct(m.recall25)}</td><td>${pct(m.map50)}</td></tr>`;
  }).join("")}</tbody></table>`;
}

function renderEvaluate() {
  const s = scene();
  const methods = ["native", "global", "active"];
  const active = s.metrics.active;
  const classes = Object.entries(active.perClass25 || {});
  $("#visual").innerHTML = toolbar("<span class=\"frame-readout\">SCENE-LEVEL SAVED METRICS</span>") + `
    <div class="metrics-grid"><aside class="metrics-summary"><strong>${pct(active.map25)}</strong><span>active mAP @ IoU 0.25<br>${s.id}</span></aside><div class="chart">
      ${methodTable(methods)}
      <h3 style="margin-top:28px">Active output · AP @ IoU 0.25 by class</h3>
      ${classes.length ? classes.map(([label, value]) => `<div class="bar-group"><div class="bar-label"><span>${esc(label)}</span><span>${pct(value.ap)}</span></div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(0, Math.min(100, Number(value.ap) * 100))}%"></div></div></div>`).join("") : "<p class=\"stage-copy\">No per-class detections for this scene.</p>"}
    </div></div>`;
  setFacts([
    fact("Visible GT", s.counts.groundTruth, "scene evaluation set"),
    fact("Active false discoveries", active.falseDiscoveries25 ?? "—", "at IoU 0.25"),
    fact("Active duplicates", active.duplicates25 ?? "—", "at IoU 0.25"),
    fact("Median paired IoU", fmt(active.medianIou, 3), "assigned label-compatible pairs")
  ]);
  evidenceLinks(["nativePredictions", "globalPredictions", "activePredictions", "sliceMetrics"]);
}

function renderExternal() {
  const s = scene();
  const facts = [
    fact("Active mAP25", pct(s.metrics.active.map25), `${s.counts.active} boxes`),
    fact("Zoo3D mAP25", pct(s.metrics.zoo3d.map25), `${s.counts.zoo3d} boxes`),
    fact("Boxer mAP25", pct(s.metrics.boxer.map25), `${s.counts.boxer} boxes`),
    fact("Evaluation ground truth", s.counts.groundTruth, "same visible boxes for all methods")
  ];
  const evidence = ["zoo3dPredictions", "boxer2dCsv", "boxerPredictions", "activePredictions"];
  let zooIndex = 0;
  let boxerIndex = 0;
  const tabs = active => modeTabs(active, [["zoo", "Zoo3D masks"], ["boxer", "Boxer 2D boxes"], ["map", "3D outputs"]]);
  const drawZoo = () => {
    const frames = s.externalEvidence.zoo3dFrames;
    const item = frames[zooIndex];
    $("#visual").innerHTML = toolbar(tabs("zoo"), `<input id="zoo-range" class="range" type="range" min="0" max="${frames.length - 1}" value="${zooIndex}"><span id="zoo-readout" class="frame-readout"></span>`) + `
      <div class="missing-evidence"><strong>What this shows:</strong> the exact adapted input and saved Zoo3D mask for every frame. The mask is an intermediate used by Zoo3D; the final 3D boxes are in the 3D-output mode and prediction JSONL.</div>
      <div class="paired-stage"><figure><img id="zoo-input" class="artifact-image square" alt="Zoo3D adapted input"><figcaption>adapted Zoo3D input</figcaption></figure><figure><img id="zoo-mask" class="artifact-image square mask-image" alt="Saved Zoo3D mask"><figcaption>saved Zoo3D mask output</figcaption></figure></div>`;
    const update = () => {
      const frame = frames[zooIndex];
      $("#zoo-input").src = frame.input;
      $("#zoo-mask").src = frame.mask;
      $("#zoo-readout").textContent = `${zooIndex + 1} / ${frames.length} · frame ${String(frame.frame).padStart(5, "0")}`;
    };
    $("#zoo-range").addEventListener("input", event => { zooIndex = Number(event.target.value); update(); });
    $("[data-mode='boxer']").addEventListener("click", drawBoxer);
    $("[data-mode='map']").addEventListener("click", drawMap);
    update();
  };
  const drawBoxer = () => {
    const frames = s.externalEvidence.boxerFrames;
    $("#visual").innerHTML = toolbar(tabs("boxer"), `<input id="boxer-range" class="range" type="range" min="0" max="${frames.length - 1}" value="${boxerIndex}"><span id="boxer-readout" class="frame-readout"></span>`) + `
      <div class="missing-evidence"><strong>Coordinate note:</strong> Boxer ran in a 960 × 960 detector coordinate system. The source below is deliberately shown square so the saved CSV rectangles line up; this is a diagnostic representation, not the source image’s native aspect ratio.</div>
      <div class="paired-stage"><figure><div class="annotated-frame boxer-square"><img id="boxer-input" class="artifact-image square" alt="Boxer input with saved 2D boxes"><svg id="boxer-overlay" class="image-overlay" viewBox="0 0 960 960"></svg></div><figcaption id="boxer-caption"></figcaption></figure><figure><img id="boxer-depth" class="artifact-image" alt="Depth paired with the Boxer input"><figcaption>paired metric depth used by the 3D proposal path</figcaption></figure></div>`;
    const update = () => {
      const frame = frames[boxerIndex];
      $("#boxer-input").src = frame.input;
      $("#boxer-depth").src = frame.depth;
      $("#boxer-overlay").innerHTML = detectionSvg(frame.detections, 960, 960, LAYERS.boxer.color);
      $("#boxer-readout").textContent = `${boxerIndex + 1} / ${frames.length} · frame ${frame.frame} · ${frame.detections.length} boxes`;
      $("#boxer-caption").textContent = "all rectangles from owl_2dbbs.csv";
    };
    $("#boxer-range").addEventListener("input", event => { boxerIndex = Number(event.target.value); update(); });
    $("[data-mode='zoo']").addEventListener("click", drawZoo);
    $("[data-mode='map']").addEventListener("click", drawMap);
    update();
  };
  const drawMap = () => {
    renderTopdown(["groundTruth", "active", "zoo3d", "boxer"], facts, evidence);
    const group = document.querySelector("#visual .toolbar-group");
    group.insertAdjacentHTML("afterbegin", modeTabs("map", [["zoo", "Zoo3D masks"], ["boxer", "Boxer 2D boxes"]]));
    $("[data-mode='zoo']").addEventListener("click", drawZoo);
    $("[data-mode='boxer']").addEventListener("click", drawBoxer);
    $("#map-legend").insertAdjacentHTML("beforeend", `<div style="margin-top:18px">${methodTable(["active", "zoo3d", "boxer"])}</div>`);
  };
  drawZoo();
  setFacts(facts);
  evidenceLinks(evidence);
}

function renderEmpty(message) {
  $("#visual").innerHTML = `<div class="empty-state"><div><strong>Saved empty branch</strong><p>${esc(message)}</p></div></div>`;
}

function render() {
  buildNavigation();
  const currentStage = stage();
  const text = STAGE_TEXT[currentStage.id];
  $("#stage-kicker").textContent = `STEP ${currentStage.number} / ${state.data.stages.length} · ${scene().name} · ${scene().status}`;
  $("#stage-title").textContent = text.title;
  $("#stage-copy").textContent = text.copy;
  $("#map-badges").innerHTML = currentStage.map.length
    ? currentStage.map.map(id => `<a class="map-badge" href="${state.data.pipelineMap}" target="_blank" rel="noreferrer" title="Open the full pipeline map">map / ${id} ↗</a>`).join("")
    : `<span class="map-badge secondary">${currentStage.kind} · outside map</span>`;
  $("#viewer-link").href = `${state.data.viewer3d}?scene=${scene().id}`;
  $("#stage-position").textContent = `${currentStage.number} / ${state.data.stages.length}`;
  $("#prev-stage").disabled = state.stage === 0;
  $("#next-stage").disabled = state.stage === state.data.stages.length - 1;
  $("#facts").innerHTML = "";
  $("#evidence").innerHTML = "";
  renderDataflow();
  renderDiagnostic();
  const renderer = {
    input: renderInput, train: renderTrain, verify: renderVerify, sweep: renderSweep, detect: renderDetect,
    native: renderNative, mask: renderMask, vote: renderVote, evaluate: renderEvaluate, external: renderExternal
  }[currentStage.id];
  renderer();
  syncUrl();
}

$("#prev-stage").addEventListener("click", () => selectStage(state.stage - 1));
$("#next-stage").addEventListener("click", () => selectStage(state.stage + 1));
window.addEventListener("keydown", event => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
  if (event.key === "ArrowLeft") selectStage(state.stage - 1);
  if (event.key === "ArrowRight") selectStage(state.stage + 1);
});

fetch("data.json")
  .then(response => {
    if (!response.ok) throw new Error(`Could not load walkthrough data (${response.status}). Run build_pipeline_walkthrough.py first.`);
    return response.json();
  })
  .then(data => {
    state.data = data;
    parseUrl();
    render();
    $("#loading").remove();
  })
  .catch(error => {
    $("#loading").remove();
    $("#error").hidden = false;
    $("#error").textContent = `Pipeline walkthrough could not start.\n\n${error.message}`;
  });

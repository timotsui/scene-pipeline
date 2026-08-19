import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const canvas = document.querySelector('#view');
const renderer = new THREE.WebGLRenderer({canvas, antialias: true});
// Match the pipeline viewer's 1:1 render resolution. Splat fill cost grows
// with pixel count; using devicePixelRatio=2 silently made this page shade
// four times as many pixels on a HiDPI display.
renderer.setPixelRatio(1);
renderer.setSize(innerWidth, innerHeight, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070a10);
scene.fog = new THREE.FogExp2(0x070a10, 0.018);
const camera = new THREE.PerspectiveCamera(52, innerWidth / innerHeight, .02, 250);
const controls = new OrbitControls(camera, canvas);

scene.add(new THREE.HemisphereLight(0xbfd8ff, 0x20283a, 1.8));
const content = new THREE.Group();
scene.add(content);

const COLORS = {
  ground_truth: 0x63e6a4,
  raw_proposals: 0xffd166,
  active: 0x41d9ff,
  zoo3d: 0xff7a59,
  boxer: 0xff5ca8,
  cameras: 0xa48bff,
};
const LAYER_NAMES = {
  ground_truth: 'Ground truth',
  raw_proposals: 'Raw proposal',
  active: 'Our final box',
  zoo3d: 'Zoo3D box',
  boxer: 'Boxer box',
};
const groups = {};
let pointCloud = null;
let pointMaterial = null;
let splatLayer = null;
let reconstructionGroup = null;
let sceneRecord = null;
let clickTargets = [];
let selectedLine = null;
let fitBounds = null;
let statusBase = '';
let frameCount = 0;
let frameWindowStart = performance.now();

// Benchmark data stay in their recorded raw frame. Like the World Labs data
// used by the pipeline viewer, physical up is raw -Y. A 180-degree display
// rotation about Z makes the scene upright without changing coordinates.
const world = a => new THREE.Vector3(a[0], a[1], a[2]);
const worldSize = a => new THREE.Vector3(a[0], a[1], a[2]);
const fmt = (value, digits = 3) => Number(value).toFixed(digits);
const esc = text => String(text).replace(/[&<>"']/g, ch =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

// Pipeline-viewer pivot: keep the orbit target 0.4 m in front of the eye,
// rather than at the distant room center. Turning then feels like looking
// around from the current position instead of swinging around the room.
function setPose(eye, look, fov = camera.fov) {
  camera.position.copy(eye);
  const direction = new THREE.Vector3().subVectors(look, eye);
  if (direction.lengthSq() > 1e-9) direction.normalize().multiplyScalar(.4);
  else direction.set(0, 0, .4);
  controls.target.copy(eye).add(direction);
  camera.fov = fov;
  camera.updateProjectionMatrix();
  controls.update();
}

function clearContent() {
  content.traverse(obj => {
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) {
      const materials = Array.isArray(obj.material) ? obj.material : [obj.material];
      materials.forEach(material => material.dispose());
    }
  });
  content.clear();
  Object.keys(groups).forEach(key => delete groups[key]);
  clickTargets = [];
  selectedLine = null;
  splatLayer = null;
  reconstructionGroup = null;
}

function addBox(entry, layer) {
  const lo = entry.aabb_min;
  const hi = entry.aabb_max;
  const centerRaw = lo.map((v, i) => (v + hi[i]) / 2);
  const sizeRaw = lo.map((v, i) => hi[i] - v);
  const geometry = new THREE.BoxGeometry(...worldSize(sizeRaw).toArray());
  const edges = new THREE.EdgesGeometry(geometry);
  const lineMaterial = new THREE.LineBasicMaterial({
    color: COLORS[layer], transparent: true,
    opacity: layer === 'ground_truth' ? .95 : .86, depthTest: false,
  });
  const line = new THREE.LineSegments(edges, lineMaterial);
  line.renderOrder = 20;
  line.position.copy(world(centerRaw));
  line.userData.baseColor = COLORS[layer];
  groups[layer].add(line);

  const hit = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
    transparent: true, opacity: .015, depthWrite: false, color: COLORS[layer],
  }));
  hit.position.copy(line.position);
  hit.userData = {entry, layer, line};
  groups[layer].add(hit);
  clickTargets.push(hit);
}

function buildBoxes(record) {
  for (const [layer, objects] of Object.entries(record.layers)) {
    groups[layer] = new THREE.Group();
    groups[layer].name = layer;
    content.add(groups[layer]);
    objects.forEach(entry => addBox(entry, layer));
  }
}

function buildCameras(record) {
  const group = new THREE.Group();
  group.name = 'cameras';
  groups.cameras = group;
  content.add(group);
  const vertices = [];
  const length = Math.max(.22, record.scene_radius * .095);
  const wing = length * .18;
  for (const item of record.cameras) {
    const origin = world(item.position);
    const forward = world(item.forward).normalize();
    const up = world(item.up).normalize();
    const right = new THREE.Vector3().crossVectors(forward, up).normalize();
    const end = origin.clone().addScaledVector(forward, length);
    vertices.push(...origin.toArray(), ...end.toArray());
    vertices.push(...end.toArray(), ...end.clone().addScaledVector(up, wing).toArray());
    vertices.push(...end.toArray(), ...end.clone().addScaledVector(right, wing).toArray());
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  group.add(new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({
    color: COLORS.cameras, transparent: true, opacity: .48, depthTest: false,
  })));

  for (const [index, position] of record.base_camera_positions.entries()) {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(length * .12, 12, 8),
      new THREE.MeshBasicMaterial({color: COLORS.cameras}));
    marker.position.copy(world(position));
    marker.userData = {cameraIndex: index};
    group.add(marker);
  }
}

async function buildPoints(record) {
  const response = await fetch(`data/${record.point_file}`);
  if (!response.ok) throw new Error(`Could not load ${record.point_file}`);
  const buffer = await response.arrayBuffer();
  const n = record.point_count;
  const rawPositions = new Float32Array(buffer, 0, n * 3);
  const rawColors = new Uint8Array(buffer, n * 12, n * 3);
  const positions = new Float32Array(n * 3);
  const colors = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    positions[i * 3] = rawPositions[i * 3];
    positions[i * 3 + 1] = rawPositions[i * 3 + 1];
    positions[i * 3 + 2] = rawPositions[i * 3 + 2];
    colors[i * 3] = rawColors[i * 3] / 255;
    colors[i * 3 + 1] = rawColors[i * 3 + 1] / 255;
    colors[i * 3 + 2] = rawColors[i * 3 + 2] / 255;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  pointMaterial = new THREE.PointsMaterial({size: .025, vertexColors: true});
  pointCloud = new THREE.Points(geometry, pointMaterial);
  reconstructionGroup = new THREE.Group();
  reconstructionGroup.name = 'reconstruction';
  reconstructionGroup.add(pointCloud);
  groups.reconstruction = reconstructionGroup;
  content.add(reconstructionGroup);
}

async function buildSplat(record) {
  const GaussianSplats3D = await import('gaussian-splats-3d');
  splatLayer = new GaussianSplats3D.DropInViewer({
    sharedMemoryForWorkers: false,
    gpuAcceleratedSort: false,
    freeIntermediateSplatData: true,
  });
  await splatLayer.addSplatScene(`splat/${record.splat_file}`, {
    showLoadingUI: false,
    progressiveLoad: true,
    splatAlphaRemovalThreshold: 5,
    format: GaussianSplats3D.SceneFormat.Ply,
  });
  reconstructionGroup.add(splatLayer);
  pointCloud.visible = false;
}

function addGrid(record) {
  const lo = world(record.bounds.p01);
  const hi = world(record.bounds.p99);
  fitBounds = new THREE.Box3(lo.clone().min(hi), lo.clone().max(hi));
  const rawSize = fitBounds.getSize(new THREE.Vector3());
  const rawCenter = fitBounds.getCenter(new THREE.Vector3());
  const size = Math.max(rawSize.x, rawSize.z) * 1.2;
  const grid = new THREE.GridHelper(size, Math.max(8, Math.round(size)), 0x344056, 0x202a3a);
  // physical floor is the high-Y side in this raw, physical-up=-Y frame
  grid.position.set(rawCenter.x, fitBounds.max.y + .015, rawCenter.z);
  grid.material.transparent = true;
  grid.material.opacity = .42;
  content.add(grid);
}

function fitScene(top = false) {
  if (!fitBounds) return;
  const displayBounds = new THREE.Box3();
  for (const x of [fitBounds.min.x, fitBounds.max.x])
    for (const y of [fitBounds.min.y, fitBounds.max.y])
      for (const z of [fitBounds.min.z, fitBounds.max.z])
        displayBounds.expandByPoint(new THREE.Vector3(x, y, z).applyEuler(content.rotation));
  const center = displayBounds.getCenter(new THREE.Vector3());
  const size = displayBounds.getSize(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z);
  const eye = top
    ? center.clone().add(new THREE.Vector3(.001, radius * 1.35, .001))
    : center.clone().add(new THREE.Vector3(radius * .78, radius * .56, radius * .92));
  camera.near = Math.max(.01, radius / 500);
  camera.far = radius * 20;
  setPose(eye, center);
}

function applyLayerVisibility() {
  document.querySelectorAll('[data-layer]').forEach(input => {
    if (groups[input.dataset.layer]) groups[input.dataset.layer].visible = input.checked;
  });
}

function updateSummary(record) {
  const counts = record.layers;
  document.querySelector('#counts').innerHTML = [
    ['GT', counts.ground_truth.length], ['raw', counts.raw_proposals.length],
    ['ours', counts.active.length], ['Zoo3D', counts.zoo3d.length],
    ['Boxer', counts.boxer.length],
  ].map(([label, value]) => `<div class="count"><strong>${value}</strong><span>${label}</span></div>`).join('');

  const finding = document.querySelector('#finding');
  if (!counts.raw_proposals.length) {
    finding.innerHTML = `<strong>Proposal-stage failure.</strong> The reconstruction contains the room and ${counts.ground_truth.length} visible target boxes, but the 90-view sweep produced no raw proposal.`;
  } else {
    const best = Math.max(0, ...counts.active.map(item => item.best_iou || 0));
    finding.innerHTML = `<strong>Proposals exist.</strong> Our system produced ${counts.raw_proposals.length} raw and ${counts.active.length} final boxes. Best same-class IoU: <strong>${best.toFixed(3)}</strong>.`;
  }
}

function inspect(target) {
  if (selectedLine) selectedLine.material.color.setHex(selectedLine.userData.baseColor);
  const {entry, layer, line} = target.userData;
  selectedLine = line;
  line.material.color.setHex(0xffffff);
  const size = entry.aabb_min.map((v, i) => entry.aabb_max[i] - v);
  const center = entry.aabb_min.map((v, i) => (entry.aabb_max[i] + v) / 2);
  const score = entry.score == null ? '—' : fmt(entry.score);
  const iou = entry.best_iou == null ? '—' : `${fmt(entry.best_iou)}${entry.best_iou >= .5 ? ' ✓ AP50 match' : entry.best_iou >= .25 ? ' ✓ AP25 match' : ''}`;
  document.querySelector('#inspection').innerHTML = `
    <h2>${esc(entry.label || 'unlabeled')}</h2>
    <span class="tag">${esc(LAYER_NAMES[layer])}</span>
    <span class="tag">${esc(entry.object_id || '')}</span>
    <dl>
      <dt>score</dt><dd>${score}</dd>
      <dt>best IoU</dt><dd>${iou}</dd>
      <dt>best GT</dt><dd>${esc(entry.best_gt || '—')}</dd>
      <dt>center</dt><dd>${center.map(v => fmt(v, 2)).join(', ')}</dd>
      <dt>size (m)</dt><dd>${size.map(v => fmt(v, 2)).join(' × ')}</dd>
    </dl>`;
}

async function loadScene(sceneId) {
  document.querySelector('#loading').hidden = false;
  selector.disabled = true;
  document.querySelector('#inspection').textContent = 'Click a colored box.';
  clearContent();
  const response = await fetch(`data/${sceneId}.json`);
  if (!response.ok) throw new Error(`Could not load scene ${sceneId}`);
  sceneRecord = await response.json();
  if (!requestedRotation && sceneRecord.display_rotation_deg) {
    sceneRecord.display_rotation_deg.forEach((value, index) => {
      if (rotationInputs[index]) rotationInputs[index].value = value;
    });
    applyDisplayRotation(false);
  }
  await buildPoints(sceneRecord);
  buildBoxes(sceneRecord);
  buildCameras(sceneRecord);
  addGrid(sceneRecord);
  updateSummary(sceneRecord);
  applyLayerVisibility();
  fitScene(false);
  const megabytes = sceneRecord.splat_bytes / (1024 * 1024);
  document.querySelector('#loading').textContent = `Streaming full Gaussian splat (${megabytes.toFixed(1)} MB)…`;
  let quality = 'full Gaussian splat';
  try {
    await buildSplat(sceneRecord);
  } catch (error) {
    console.error('Gaussian splat load failed; retaining point fallback', error);
    quality = 'point fallback — start with serve_scene3d.py for the full splat';
    document.querySelector('#finding').insertAdjacentHTML('beforeend',
      '<br><strong>Full splat unavailable.</strong> The point preview is shown instead.');
  }
  applyLayerVisibility();
  statusBase = `${sceneRecord.title} · ${quality} · metric coordinates`;
  document.querySelector('#status').textContent = statusBase;
  document.querySelector('#loading').hidden = true;
  selector.disabled = false;
  history.replaceState(null, '', `?scene=${encodeURIComponent(sceneId)}`);
}

const manifest = await (await fetch('data/manifest.json')).json();
const selector = document.querySelector('#scene-select');
for (const item of manifest.scenes) {
  const option = document.createElement('option');
  option.value = item.id;
  option.textContent = `${item.title} (${item.id})`;
  selector.appendChild(option);
}
const requested = new URLSearchParams(location.search).get('scene');
selector.value = manifest.scenes.some(item => item.id === requested) ? requested : manifest.scenes[0].id;
selector.addEventListener('change', () => {
  location.search = `?scene=${encodeURIComponent(selector.value)}`;
});
const rotationInputs = ['rx', 'ry', 'rz'].map(id => document.querySelector(`#${id}`));
const requestedRotation = new URLSearchParams(location.search).get('rot');
if (requestedRotation) requestedRotation.split(',').forEach((value, index) => {
  if (rotationInputs[index]) rotationInputs[index].value = value;
});
function applyDisplayRotation(refit = true) {
  const radians = rotationInputs.map(input => Number(input.value || 0) * Math.PI / 180);
  content.rotation.set(...radians);
  if (refit && fitBounds) fitScene(false);
}
rotationInputs.forEach(input => input.addEventListener('input', () => applyDisplayRotation(true)));
applyDisplayRotation(false);
document.querySelectorAll('[data-layer]').forEach(input => input.addEventListener('change', applyLayerVisibility));
document.querySelector('#fit').addEventListener('click', () => fitScene(false));
document.querySelector('#top').addEventListener('click', () => fitScene(true));

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
canvas.addEventListener('pointerdown', event => {
  if (event.button !== 0) return;
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const visibleTargets = clickTargets.filter(target => target.parent.visible);
  const hits = raycaster.intersectObjects(visibleTargets, false);
  if (hits.length) inspect(hits[0].object);
});

addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
});

// Same fly controls as the pipeline paper viewer. Camera and orbit target move
// together, so mouse orbiting continues naturally from the new position.
const keys = new Set();
addEventListener('keydown', event => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName)) return;
  keys.add(event.key.toLowerCase());
});
addEventListener('keyup', event => keys.delete(event.key.toLowerCase()));
addEventListener('blur', () => keys.clear());
const clock = new THREE.Clock();
function flyStep() {
  const dt = Math.min(clock.getDelta(), .1);
  if (!keys.size) return;
  const speed = (keys.has('shift') ? 4.5 : 1.5) * dt;
  const forward = new THREE.Vector3().subVectors(controls.target, camera.position);
  forward.projectOnPlane(camera.up).normalize();
  if (forward.lengthSq() < 1e-9) return;
  const right = new THREE.Vector3().crossVectors(forward, camera.up).normalize();
  const movement = new THREE.Vector3();
  if (keys.has('w')) movement.add(forward);
  if (keys.has('s')) movement.sub(forward);
  if (keys.has('d')) movement.add(right);
  if (keys.has('a')) movement.sub(right);
  if (keys.has('e') || keys.has('r')) movement.add(camera.up);
  if (keys.has('q') || keys.has('f')) movement.sub(camera.up);
  if (!movement.lengthSq()) return;
  movement.normalize().multiplyScalar(speed);
  camera.position.add(movement);
  controls.target.add(movement);
}

renderer.setAnimationLoop(() => {
  flyStep();
  controls.update();
  renderer.render(scene, camera);
  frameCount += 1;
  const now = performance.now();
  if (statusBase && now - frameWindowStart >= 1000) {
    const fps = Math.round(frameCount * 1000 / (now - frameWindowStart));
    document.querySelector('#status').textContent = `${statusBase} · ${fps} fps`;
    frameCount = 0;
    frameWindowStart = now;
  }
});
loadScene(selector.value).catch(error => {
  document.querySelector('#loading').textContent = error.message;
  console.error(error);
});

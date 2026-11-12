// Visor 3D de Barranquilla (Gran Malecón, Vía 40, Buenavista) para la simulación multiagente.
// Coordenadas: SUMO (x este, y norte, metros) -> Three.js (x, altura, -y).
//
// Render: tonemapping ACES, reflejos del cielo (mapa de entorno generado con el mismo
// shader del cielo, así el atardecer rosado se refleja en vidrios y carros), bloom para las
// luces de noche, sombras del sol (calidad alta) y niebla. Calidad Alta/Media/Baja con
// ajuste automático según los cuadros por segundo.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { MODELOS, elegirModelo, colorModelo, partesPersona, PIEL, ROPA, PANTALON, PELO, geometriasPuestos, fusionar, caja } from './modelos.js';
import { iniciarHitos, construirHito, dibujarPantallas } from './hitos.js';

const $ = (id) => document.getElementById(id);
const carga = (t) => { $('cargaTxt').textContent = t; };
const lerp = (a, b, f) => a + (b - a) * f;
const suave = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const pref = { leer(k) { try { return localStorage.getItem('bq3d.' + k); } catch { return null; } }, guardar(k, v) { try { localStorage.setItem('bq3d.' + k, v); } catch { /* sin almacenamiento */ } } };
const azar = (n, s = 0) => { const x = Math.sin(n * 12.9898 + s * 78.233) * 43758.5453; return x - Math.floor(x); };

// ================================================================ escena y render
const CALIDADES = { alta: { pr: 2, sombras: true, bloom: true }, media: { pr: 1.25, sombras: false, bloom: true }, baja: { pr: 1, sombras: false, bloom: false } };
let calidad = pref.leer('calidad') || 'alta'; let calidadAuto = !pref.leer('calidad');
const lienzo = $('lienzo');
const renderer = new THREE.WebGLRenderer({ canvas: lienzo, antialias: false, powerPreference: 'high-performance' });
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0xe9c9a3, 700, 3600);
const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.5, 9000);
camera.position.set(0, 400, 600);
const controls = new OrbitControls(camera, lienzo);
controls.enableDamping = true; controls.maxPolarAngle = Math.PI * 0.495; controls.enabled = false;
window.__visor = { scene, camera, controls, THREE, renderer };

const rt = new THREE.WebGLRenderTarget(innerWidth, innerHeight, { type: THREE.HalfFloatType, samples: 4 });
const composer = new EffectComposer(renderer, rt);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.5, 0.55, 0.82);
composer.addPass(bloom);
composer.addPass(new OutputPass());

const hemi = new THREE.HemisphereLight(0xcfe6ff, 0x5b4c3c, 0.9);
const sol = new THREE.DirectionalLight(0xffe2b8, 2.2);
sol.shadow.mapSize.set(2048, 2048); sol.shadow.bias = -0.0003; sol.shadow.normalBias = 0.5;
Object.assign(sol.shadow.camera, { left: -260, right: 260, top: 260, bottom: -260, near: 10, far: 4000 });
const luna = new THREE.DirectionalLight(0x9fb6ff, 0.0);
scene.add(hemi, sol, sol.target, luna, luna.target);

function aplicarCalidad(nombre) {
  calidad = nombre; const q = CALIDADES[nombre];
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, q.pr));
  composer.setPixelRatio(Math.min(window.devicePixelRatio || 1, q.pr));
  composer.setSize(innerWidth, innerHeight);
  bloom.enabled = q.bloom;
  if (renderer.shadowMap.enabled !== q.sombras) {
    renderer.shadowMap.enabled = q.sombras; sol.castShadow = q.sombras;
    scene.traverse((o) => { if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => { m.needsUpdate = true; }); });
  }
  if ($('calidad')) $('calidad').value = nombre;
}

// ================================================================ cielo con nubes
// Paleta por hora: [hora, cénit, medio, horizonte]. El atardecer barranquillero
// (17:30-18:30) pasa por el rosado y el lila sobre un azul profundo.
const CIELO = [
  [0.0, '#03060f', '#07102a', '#101a38'], [4.6, '#040a1c', '#0d1838', '#1e2448'], [5.4, '#14214a', '#3d3a6e', '#b0607a'],
  [6.0, '#2c4f92', '#8a86b8', '#ffae7a'], [6.8, '#3a74c4', '#8ab8e6', '#ffd8b0'], [9.0, '#2e6fca', '#7fb3ea', '#cfe6fb'],
  [15.5, '#2f6dc6', '#80b2e6', '#d6e9f8'], [16.8, '#3567b8', '#8eaede', '#ffe2b8'], [17.4, '#3a5cae', '#a796d4', '#ffbfa8'],
  [17.85, '#33519f', '#c58fcf', '#ff9cc6'], [18.3, '#283f86', '#9b74bf', '#f48fb8'], [18.75, '#18265c', '#4b3c80', '#a05a8e'],
  [19.3, '#0a1230', '#18204a', '#2c2450'], [20.0, '#05091a', '#0a1330', '#141c3a'], [24.0, '#03060f', '#07102a', '#101a38'],
].map(([h, ...c]) => [h, ...c.map((x) => new THREE.Color().setStyle(x, THREE.LinearSRGBColorSpace))]);
function luminosidad(h) {  // igual que config.luminosidad en Python
  h = ((h % 24) + 24) % 24;
  const rampa = (x, a, b) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return 0.5 - 0.5 * Math.cos(Math.PI * t); };
  return rampa(h, 5.33, 6.67) * (1 - rampa(h, 17.5, 18.83));
}
function paletaCielo(h, lluvia) {
  h = ((h % 24) + 24) % 24;
  let i = 0; while (i < CIELO.length - 2 && CIELO[i + 1][0] <= h) i++;
  const [h0, a0, b0, c0] = CIELO[i], [h1, a1, b1, c1] = CIELO[i + 1]; const f = (h - h0) / (h1 - h0 || 1);
  const out = [a0.clone().lerp(a1, f), b0.clone().lerp(b1, f), c0.clone().lerp(c1, f)];
  if (lluvia) { const gris = new THREE.Color(0.42, 0.45, 0.49).multiplyScalar(0.25 + 0.75 * luminosidad(h)); out.forEach((c) => c.lerp(gris, 0.7)); }
  return out;
}
const cieloMat = new THREE.ShaderMaterial({
  uniforms: {
    cenit: { value: new THREE.Color() }, medio: { value: new THREE.Color() }, horizonte: { value: new THREE.Color() },
    solDir: { value: new THREE.Vector3(0, 1, 0) }, lunaDir: { value: new THREE.Vector3(0, -1, 0) }, solColor: { value: new THREE.Color(1, 0.9, 0.7) },
    lluvia: { value: 0 }, oscuridad: { value: 0 }, tiempo: { value: 0 }, nubes: { value: 0.42 },
  },
  vertexShader: 'varying vec3 vDir; void main(){ vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform vec3 cenit, medio, horizonte, solDir, lunaDir, solColor; uniform float lluvia, oscuridad, tiempo, nubes; varying vec3 vDir;
    float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float ruido(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }
    float fbm(vec2 p){ float v = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { v += a * ruido(p); p = p * 2.03 + 17.1; a *= 0.5; } return v; }
    void main(){
      vec3 d = normalize(vDir); float e = d.y; float dia = 1.0 - oscuridad;
      vec3 c = e > 0.0 ? mix(mix(horizonte, medio, smoothstep(0.0, 0.22, e)), cenit, smoothstep(0.22, 0.85, e)) : horizonte * (1.0 + e * 1.6);
      float s = max(dot(d, normalize(solDir)), 0.0);
      c += solColor * (pow(s, 900.0) * 3.0 * (1.0 - lluvia) + pow(s, 8.0) * 0.3 * (1.0 - lluvia * 0.8));
      float m = max(dot(d, normalize(lunaDir)), 0.0);
      c += vec3(0.9, 0.93, 1.0) * (pow(m, 3000.0) * 2.5 + pow(m, 60.0) * 0.06) * oscuridad * (1.0 - lluvia);
      if (e > 0.0) {  // cúmulos del Caribe proyectados sobre una capa plana que se desplaza
        vec2 p = d.xz / (e + 0.1) * 1.4 + vec2(tiempo * 0.010, tiempo * 0.004);
        float n = fbm(p);
        float cob = smoothstep(1.0 - nubes, 1.0 - nubes + 0.32, n) * smoothstep(0.0, 0.1, e);
        vec3 noche = vec3(0.07, 0.08, 0.12) + vec3(0.25, 0.13, 0.07) * (1.0 - smoothstep(0.0, 0.35, e));  // brillo naranja de la ciudad
        vec3 diaN = mix(horizonte, vec3(1.0), 0.55) + solColor * 0.4 * pow(s, 3.0);
        vec3 cn = mix(noche, diaN, dia);
        cn = mix(cn, vec3(0.42, 0.44, 0.48) * (0.25 + 0.75 * dia), lluvia * 0.85);
        cn *= 0.7 + 0.4 * smoothstep(0.35, 0.9, n);
        c = mix(c, cn, cob * 0.93);
      }
      gl_FragColor = vec4(c, 1.0);
    }`,
  side: THREE.BackSide, depthWrite: false, fog: false,
});
const cielo = new THREE.Mesh(new THREE.SphereGeometry(4200, 48, 24), cieloMat);
cielo.renderOrder = -2; cielo.frustumCulled = false; scene.add(cielo);
const estrellas = (() => {
  const n = 2200, p = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { const u = Math.random() * Math.PI * 2, v = Math.acos(Math.random() * 0.95);
    p.set([4000 * Math.sin(v) * Math.cos(u), 4000 * Math.cos(v), 4000 * Math.sin(v) * Math.sin(u)], i * 3); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  const m = new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0, fog: false, depthWrite: false }));
  m.renderOrder = -1; m.frustumCulled = false; scene.add(m); return m;
})();
// mapa de entorno: el mismo cielo, para reflejos en vidrios, carros y agua
const pmrem = new THREE.PMREMGenerator(renderer);
const escenaEntorno = new THREE.Scene(); escenaEntorno.add(new THREE.Mesh(new THREE.SphereGeometry(100, 48, 24), cieloMat));
let entornoRT = null, entornoClave = '';
function actualizarEntorno(h, lluvia) {
  const clave = `${(Math.round(h * 12) / 12).toFixed(2)}|${lluvia}`; if (clave === entornoClave) return; entornoClave = clave;
  const nuevo = pmrem.fromScene(escenaEntorno, 0, 0.1, 1000); scene.environment = nuevo.texture;
  if (entornoRT) entornoRT.dispose(); entornoRT = nuevo;
}

// ================================================================ utilidades geométricas
function tira(pos, idx, pts, w, y, uv, escalaUV = 0, desp = 0) {
  // franja de ancho w a lo largo de la polilínea (desplazada lateralmente desp: + a la derecha)
  const n = pts.length / 2; if (n < 2) return;
  const base = pos.length / 3; let acum = 0;
  for (let i = 0; i < n; i++) {
    const a = Math.max(i - 1, 0), b = Math.min(i + 1, n - 1);
    let tx = pts[2 * b] - pts[2 * a], ty = pts[2 * b + 1] - pts[2 * a + 1];
    const L = Math.hypot(tx, ty) || 1; tx /= L; ty /= L;
    const nx = -ty, ny = tx;  // normal a la izquierda
    const x = pts[2 * i] - nx * desp, yy = pts[2 * i + 1] - ny * desp;
    if (i > 0) acum += Math.hypot(pts[2 * i] - pts[2 * i - 2], pts[2 * i + 1] - pts[2 * i - 1]);
    pos.push(x + nx * w / 2, y, -(yy + ny * w / 2), x - nx * w / 2, y, -(yy - ny * w / 2));
    if (uv) { if (escalaUV) uv.push(acum / escalaUV, 1, acum / escalaUV, 0); else uv.push((x + nx * w / 2) / 7, (yy + ny * w / 2) / 7, (x - nx * w / 2) / 7, (yy - ny * w / 2) / 7); }
  }
  for (let i = 0; i < n - 1; i++) { const k = base + 2 * i; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
}
function puntos2(plano) { const c = []; for (let i = 0; i < plano.length; i += 2) c.push(new THREE.Vector2(plano[i], plano[i + 1])); return c; }
function poligono(pos, idx, plano, y, uv) {
  const c = puntos2(plano); if (c.length < 3) return;
  const tri = THREE.ShapeUtils.triangulateShape(c, []); const base = pos.length / 3;
  for (const p of c) { pos.push(p.x, y, -p.y); if (uv) uv.push(p.x / 7, p.y / 7); }
  for (const t of tri) idx.push(base + t[0], base + t[1], base + t[2]);
}
function malla(pos, idx, mat, extra) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  if (extra) for (const [k, v, n] of extra) g.setAttribute(k, new THREE.Float32BufferAttribute(v, n));
  g.setIndex(idx); g.computeVertexNormals();
  const m = new THREE.Mesh(g, mat); m.matrixAutoUpdate = false; return m;
}
function extruir(plano, h, y0 = 0) {  // paredes con UV de fachada (módulos de 3.5 m × pisos de 3.1 m) + techo
  const pos = [], idx = [], uv = [];
  const n = plano.length / 2; let u = 0;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n, ax = plano[2 * i], ay = plano[2 * i + 1], bx = plano[2 * j], by = plano[2 * j + 1];
    const L = Math.hypot(bx - ax, by - ay), b0 = pos.length / 3;
    pos.push(ax, y0, -ay, bx, y0, -by, bx, y0 + h, -by, ax, y0 + h, -ay);
    uv.push(u / 3.5, 0, (u + L) / 3.5, 0, (u + L) / 3.5, h / 3.1, u / 3.5, h / 3.1);
    idx.push(b0, b0 + 1, b0 + 2, b0, b0 + 2, b0 + 3); u += L;
  }
  const paredes = new THREE.BufferGeometry();
  paredes.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); paredes.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  paredes.setIndex(idx); paredes.computeVertexNormals();
  const pr = [], ir = []; poligono(pr, ir, plano, y0 + h);
  const techo = new THREE.BufferGeometry(); techo.setAttribute('position', new THREE.Float32BufferAttribute(pr, 3)); techo.setIndex(ir); techo.computeVertexNormals();
  return { paredes, techo };
}
function lienzoTextura(w, h, dibujar, srgb = true) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h; dibujar(cv.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(cv); if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}
function etiqueta(texto, color = '#fff', fondo = 'rgba(10,16,24,.72)', tam = 30) {
  const cv = document.createElement('canvas'); const g = cv.getContext('2d');
  g.font = `600 ${tam}px Segoe UI, sans-serif`;
  const w = Math.ceil(g.measureText(texto).width) + 24; cv.width = w; cv.height = tam + 18;
  g.font = `600 ${tam}px Segoe UI, sans-serif`;
  g.fillStyle = fondo; g.beginPath(); g.roundRect(0, 0, w, tam + 18, 10); g.fill();
  g.fillStyle = color; g.textBaseline = 'middle'; g.fillText(texto, 12, (tam + 18) / 2 + 1);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthTest: false, transparent: true, fog: false, toneMapped: false }));
  s.userData.aspecto = w / (tam + 18); s.renderOrder = 10; return s;
}
const ruidoTex = (base, var_, w = 256) => lienzoTextura(w, w, (g) => {
  const img = g.createImageData(w, w);
  for (let i = 0; i < w * w; i++) { const r = (Math.random() - 0.5) * var_; img.data.set([base[0] + r, base[1] + r, base[2] + r, 255], i * 4); }
  g.putImageData(img, 0, 0);
});
// materiales que ignoran el color de instancia (vidrios, llantas, luces de los carros)
function sinColorInstancia(m) {
  m.onBeforeCompile = (s) => { s.vertexShader = s.vertexShader.replace('#include <color_vertex>',
    '#if defined( USE_COLOR ) || defined( USE_INSTANCING_COLOR )\n vColor = vec3( 1.0 );\n#endif\n#ifdef USE_COLOR\n vColor *= color;\n#endif'); };
  m.customProgramCacheKey = () => 'sinColorInstancia'; return m;
}

// ================================================================ fachadas (atlas procedural)
// 6 estilos × (piso tipo, planta baja). Máscara aparte: blanco = vidrio.
const N_FILAS = 12;
const [atlasFachadas, mascaraFachadas] = (() => {
  const W = 256, F = 128;
  const col = document.createElement('canvas'), mas = document.createElement('canvas');
  col.width = mas.width = W; col.height = mas.height = F * N_FILAS;
  const gc = col.getContext('2d'), gm = mas.getContext('2d');
  gm.fillStyle = '#000'; gm.fillRect(0, 0, W, F * N_FILAS);
  const fila = (r, f) => { const y0 = (N_FILAS - 1 - r) * F; gc.save(); gm.save(); gc.translate(0, y0); gm.translate(0, y0); f(gc, gm); gc.restore(); gm.restore(); };
  const pared = (g, tono = 242, var_ = 10) => { g.fillStyle = `rgb(${tono},${tono},${tono})`; g.fillRect(0, 0, W, F);
    for (let i = 0; i < 500; i++) { const v = tono - Math.random() * var_; g.fillStyle = `rgba(${v},${v},${v},.5)`; g.fillRect(Math.random() * W, Math.random() * F, 3, 3); } };
  const vidrio = (g, m, x, y, w, h, c1 = '#2b3c4c', c2 = '#5e7a90') => { const gr = g.createLinearGradient(x, y, x + w * 0.4, y + h); gr.addColorStop(0, c2); gr.addColorStop(1, c1);
    g.fillStyle = gr; g.fillRect(x, y, w, h); m.fillStyle = '#fff'; m.fillRect(x, y, w, h); };
  const marco = (g, x, y, w, h, c = '#d9d9d9', e = 4) => { g.strokeStyle = c; g.lineWidth = e; g.strokeRect(x, y, w, h); };
  // 0: torre de vidrio (muro cortina)
  fila(0, (g, m) => { pared(g, 200); vidrio(g, m, 4, 6, W - 8, F - 18, '#21384a', '#7fa4bf'); g.fillStyle = '#c8cdd2'; g.fillRect(0, F - 12, W, 12); g.fillRect(W / 2 - 3, 0, 6, F); });
  fila(1, (g, m) => { pared(g, 200); vidrio(g, m, 6, 8, W - 12, F - 10, '#1f3140', '#8fb2c8'); g.fillStyle = '#9aa2aa'; g.fillRect(W / 2 - 4, 8, 8, F - 8); });
  // 1: torre residencial con balcones
  fila(2, (g, m) => { pared(g); vidrio(g, m, 22, 18, 92, 78); vidrio(g, m, 142, 18, 92, 78); marco(g, 22, 18, 92, 78, '#bdbdbd');
    marco(g, 142, 18, 92, 78, '#bdbdbd'); g.fillStyle = '#9da3a8'; g.fillRect(0, F - 22, W, 10); g.fillStyle = 'rgba(160,190,210,.75)'; g.fillRect(0, F - 34, W, 12); });
  fila(3, (g, m) => { pared(g, 225); vidrio(g, m, 16, 24, W - 32, F - 24, '#2a3a46', '#9bb7c9'); g.fillStyle = '#7a7f84'; g.fillRect(W / 2 - 3, 24, 6, F); });
  // 2: edificio medio (pastel)
  fila(4, (g, m) => { pared(g); for (const x of [26, 146]) { vidrio(g, m, x, 26, 84, 66); marco(g, x, 26, 84, 66, '#ffffff', 5); g.fillStyle = 'rgba(0,0,0,.12)'; g.fillRect(x - 4, 94, 92, 6); } });
  fila(5, (g, m) => { pared(g, 236); vidrio(g, m, 12, 22, 150, F - 22, '#26323b', '#a8c3d4'); g.fillStyle = '#5b3b2a'; g.fillRect(180, 30, 56, F - 30);
    g.fillStyle = '#c0392b'; g.fillRect(0, 6, W, 12); });
  // 3: casa popular de colores (ventana con reja, puerta)
  fila(6, (g, m) => { pared(g, 245, 18); vidrio(g, m, 70, 30, 116, 64, '#2b2b2b', '#55606a'); g.strokeStyle = '#1b1b1b'; g.lineWidth = 4;
    for (let x = 70; x <= 186; x += 16) { g.beginPath(); g.moveTo(x, 30); g.lineTo(x, 94); g.stroke(); } g.beginPath(); g.moveTo(70, 62); g.lineTo(186, 62); g.stroke();
    g.fillStyle = 'rgba(0,0,0,.18)'; g.fillRect(0, F - 8, W, 8); });
  fila(7, (g, m) => { pared(g, 245, 18); g.fillStyle = '#6d4c33'; g.fillRect(28, 24, 64, F - 24); g.fillStyle = '#2b2b2b'; g.fillRect(36, 34, 48, 30);
    vidrio(g, m, 132, 34, 96, 56, '#2b2b2b', '#55606a'); g.strokeStyle = '#1b1b1b'; g.lineWidth = 4; for (let x = 132; x <= 228; x += 16) { g.beginPath(); g.moveTo(x, 34); g.lineTo(x, 90); g.stroke(); }
    g.fillStyle = 'rgba(0,0,0,.25)'; g.fillRect(0, F - 10, W, 10); });
  // 4: bodega (lámina ondulada)
  fila(8, (g, m) => { pared(g, 210); g.fillStyle = 'rgba(0,0,0,.1)'; for (let x = 0; x < W; x += 8) g.fillRect(x, 0, 3, F); vidrio(g, m, 0, 14, W, 18, '#3a4652', '#8aa0b2'); });
  fila(9, (g, m) => { pared(g, 205); g.fillStyle = '#7d8790'; g.fillRect(30, 20, 196, F - 20); g.fillStyle = 'rgba(0,0,0,.18)'; for (let y = 24; y < F; y += 7) g.fillRect(30, y, 196, 2); });
  // 5: casa o edificio bajo elegante (estratos 5 y 6)
  fila(10, (g, m) => { pared(g, 248, 6); vidrio(g, m, 18, 16, 220, 86, '#22313d', '#9fbfd3'); g.fillStyle = '#f8f8f8'; g.fillRect(124, 16, 8, 86); g.fillStyle = '#8b6b4a'; g.fillRect(0, F - 16, W, 6); });
  fila(11, (g, m) => { pared(g, 248, 6); vidrio(g, m, 14, 18, 228, F - 18, '#1e2b35', '#a9c8db'); g.fillStyle = '#e6e6e6'; for (const x of [84, 170]) g.fillRect(x, 18, 6, F - 18); });
  const t1 = new THREE.CanvasTexture(col); t1.colorSpace = THREE.SRGBColorSpace; t1.anisotropy = 8;
  const t2 = new THREE.CanvasTexture(mas); t2.anisotropy = 8;
  return [t1, t2];
})();
const unifFachada = { uMascara: { value: mascaraFachadas }, uNoche: { value: 0 }, uEncendidas: { value: 0 } };
function materialEdificio(fijo = null, color = 0xffffff) {
  const m = new THREE.MeshStandardMaterial({ map: atlasFachadas, color, vertexColors: fijo === null, roughness: 0.82, metalness: 0.05 });
  if (fijo !== null) m.defines = { ESTILO_FIJO: fijo };
  m.onBeforeCompile = (s) => {
    Object.assign(s.uniforms, unifFachada);
    s.vertexShader = s.vertexShader.replace('#include <common>', `#include <common>
      #ifndef ESTILO_FIJO
      attribute float estilo; attribute float semilla;
      #endif
      varying float vEstilo; varying float vSemilla; varying vec2 vFach;`)
      .replace('#include <uv_vertex>', `#include <uv_vertex>
      vFach = uv;
      #ifdef ESTILO_FIJO
      vEstilo = float(ESTILO_FIJO); vSemilla = 0.37;
      #else
      vEstilo = estilo; vSemilla = semilla;
      #endif`);
    s.fragmentShader = s.fragmentShader.replace('#include <common>', `#include <common>
      uniform sampler2D uMascara; uniform float uNoche; uniform float uEncendidas;
      varying float vEstilo; varying float vSemilla; varying vec2 vFach; float gVidrio = 0.0;`)
      .replace('#include <map_fragment>', `{
        const float NF = ${N_FILAS}.0;
        vec2 celda = fract(vFach);
        float fila = floor(vEstilo + 0.5) * 2.0 + (vFach.y < 1.0 ? 1.0 : 0.0);
        vec2 uvA = vec2(celda.x, (fila + 0.02 + celda.y * 0.96) / NF);
        vec2 gx = dFdx(vFach) * vec2(1.0, 0.96 / NF), gy = dFdy(vFach) * vec2(1.0, 0.96 / NF);
        vec4 tx = textureGrad(map, uvA, gx, gy);
        gVidrio = textureGrad(uMascara, uvA, gx, gy).r;
        diffuseColor.rgb *= tx.rgb;
      }`)
      .replace('#include <color_fragment>', `#if defined( USE_COLOR )
        diffuseColor.rgb *= mix(vColor, vec3(1.0), gVidrio);
      #endif`)
      .replace('#include <roughnessmap_fragment>', 'float roughnessFactor = mix(roughness, 0.07, gVidrio);')
      .replace('#include <metalnessmap_fragment>', 'float metalnessFactor = mix(metalness, 0.75, gVidrio);')
      .replace('#include <emissivemap_fragment>', `{
        vec2 vent = floor(vFach * vec2(2.0, 1.0));
        float hz = fract(sin(dot(vent + vec2(vSemilla * 91.7, vSemilla * 37.3), vec2(12.9898, 78.233))) * 43758.5453);
        float baja = vFach.y < 1.0 ? 1.6 : 1.0;
        float on = step(hz, uEncendidas * baja) * step(0.5, gVidrio);
        vec3 tono = mix(vec3(1.0, 0.72, 0.4), vec3(0.8, 0.9, 1.0), step(0.72, fract(hz * 7.31)));
        totalEmissiveRadiance += tono * on * uNoche * 1.7;
      }`);
  };
  m.customProgramCacheKey = () => 'fachada' + (fijo === null ? 'v' : fijo);
  return m;
}
const matEdificios = materialEdificio();
const MATS_ENTORNO = new Set([matEdificios]);  // materiales cuyo reflejo del cielo se atenúa de noche

// ================================================================ ciudad
const ciudadGrupo = new THREE.Group(); scene.add(ciudadGrupo);
const etiquetas = new THREE.Group(); scene.add(etiquetas);
const animados = [];          // funciones (t, oscuridad) que se llaman cada cuadro
let aguaMat, CIUDAD, asfaltoMat, bulbosMat, halos, charcosMat, HITOS = {};
const semaforo = { cajas: null, lamparas: null, ultimo: null };
iniciarHitos({ scene, animados, etiquetas, etiqueta, lienzoTextura, poligono, malla, puntos2, extruir,
  materialFachada: (color, estilo) => materialEdificio(estilo, color) });

// estrato aproximado en un punto (barrio más cercano), para elegir carros y estilos
function estratoEn(x, y) {
  let mejor = 1e18, est = 3; for (const [bx, by, e] of CIUDAD.barrios || []) { const d = (bx - x) ** 2 + (by - y) ** 2; if (d < mejor) { mejor = d; est = e; } } return est;
}

async function cargarCiudad() {
  carga('Descargando la red vial, los edificios y los árboles…');
  CIUDAD = await (await fetch('datos/ciudad.json')).json();
  carga('Construyendo vías, edificios, el río y el Malecón…');
  await new Promise((r) => setTimeout(r, 20));
  const [x0, y0, x1, y1] = CIUDAD.limites;
  // suelo
  const tierra = ruidoTex([138, 130, 108], 26); tierra.wrapS = tierra.wrapT = THREE.RepeatWrapping; tierra.repeat.set(900, 900);
  const suelo = new THREE.Mesh(new THREE.PlaneGeometry(12000, 12000), new THREE.MeshStandardMaterial({ map: tierra, roughness: 1 }));
  suelo.rotation.x = -Math.PI / 2; suelo.position.set((x0 + x1) / 2, -0.05, -(y0 + y1) / 2); suelo.receiveShadow = true; ciudadGrupo.add(suelo);
  // río Magdalena: agua café verdosa con ondas, reflejo del cielo (fresnel) y destello del sol
  aguaMat = new THREE.ShaderMaterial({
    uniforms: { t: { value: 0 }, cielo: { value: new THREE.Color() }, horiz: { value: new THREE.Color() }, base: { value: new THREE.Color(0.24, 0.2, 0.12) },
      luz: { value: 1 }, solDir: { value: new THREE.Vector3(0, 1, 0) }, solColor: { value: new THREE.Color(1, 0.9, 0.7) }, lluvia: { value: 0 } },
    vertexShader: 'varying vec3 vP; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vP = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }',
    fragmentShader: `uniform float t, luz, lluvia; uniform vec3 cielo, horiz, base, solDir, solColor; varying vec3 vP;
      float h(vec2 p){ return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5); }
      float n(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f); return mix(mix(h(i), h(i+vec2(1,0)), f.x), mix(h(i+vec2(0,1)), h(i+vec2(1,1)), f.x), f.y); }
      void main(){
        vec2 q = vP.xz * 0.06; float a = n(q + vec2(t*0.25, t*0.1)) + 0.5*n(q*2.3 - vec2(t*0.4, -t*0.2)) + 0.25*n(q*5.1 + t*0.7);
        vec3 nor = normalize(vec3((a - 0.9) * 0.35, 1.0, (n(q.yx + t*0.2) - 0.5) * 0.35));
        vec3 v = normalize(cameraPosition - vP); float fres = pow(1.0 - max(dot(v, nor), 0.0), 4.0);
        vec3 r = reflect(-v, nor); float sp = pow(max(dot(r, normalize(solDir)), 0.0), 220.0) * (1.0 - lluvia);
        vec3 refl = mix(horiz, cielo, clamp(r.y * 2.0, 0.0, 1.0));
        vec3 c = mix(base * (0.2 + 0.8 * luz), refl, 0.18 + 0.6 * fres) + solColor * sp * 2.5 * luz;
        float dist = length(cameraPosition - vP); c = mix(c, horiz, smoothstep(900.0, 3600.0, dist) * 0.8);
        gl_FragColor = vec4(c, 1.0); }`,
  });
  { const pos = [], idx = []; for (const p of CIUDAD.agua) poligono(pos, idx, p, 0.0); ciudadGrupo.add(malla(pos, idx, aguaMat)); }
  // parques con pasto
  { const pasto = ruidoTex([96, 140, 72], 40); pasto.wrapS = pasto.wrapT = THREE.RepeatWrapping;
    const pos = [], idx = [], uv = []; for (const [, p] of CIUDAD.parques) poligono(pos, idx, p, 0.03, uv);
    const m = malla(pos, idx, new THREE.MeshStandardMaterial({ map: pasto, roughness: 1, side: THREE.DoubleSide }), [['uv', uv, 2]]); m.receiveShadow = true; ciudadGrupo.add(m); }
  construirVias();
  construirEdificios();
  construirVegetacion();
  construirAlumbrado();
  construirSemaforos();
  construirPuestos();
  for (const h of CIUDAD.hitos || []) { HITOS[h.id] = h; try { construirHito(h); } catch (err) { console.warn('hito', h.id, err); } }
  // nombres de vías principales y lugares
  const cuenta = {};
  const principal = /V[ií]a 40|Avenida|Rotonda|Calle (72|76|79|84|98|99)$|Carrera (46|51B|53|54)$/;
  const lugarDestacado = /Malec|Gastron|Bosque Urbano/i;
  for (const [tipo, nombre, x, y] of CIUDAD.etiquetas) {
    if (tipo === 'via' && !principal.test(nombre)) continue;
    if (tipo === 'lugar' && !lugarDestacado.test(nombre)) continue;
    cuenta[nombre] = (cuenta[nombre] || 0) + 1; if (cuenta[nombre] > (tipo === 'via' ? 2 : 1)) continue;
    const s = etiqueta(nombre, tipo === 'agua' ? '#bfe6ff' : tipo === 'lugar' ? '#c9f7c1' : '#ffffff', 'rgba(10,16,24,.66)', tipo === 'via' ? 26 : 30);
    s.position.set(x, tipo === 'via' ? 18 : 40, -y); s.userData.base = tipo === 'via' ? 0.022 : 0.026; etiquetas.add(s);
  }
}

function construirVias() {
  const pa = [], ia = [], ua = [];          // asfalto (UV del mundo)
  const pb = [], ib = [], ub = [];          // andenes
  const pc = [], ic = [];                   // cebras
  const pd = [], id = [], ud = [];          // líneas discontinuas entre carriles
  const pw = [], iw = [];                   // líneas blancas de borde
  const py = [], iy = [];                   // línea central amarilla
  for (const p of CIUDAD.cruces) poligono(pa, ia, p, 0.06, ua);
  for (const arista of CIUDAD.carriles) {
    for (const [w, pts] of arista.l) tira(pa, ia, pts, w + 0.05, 0.07, ua);
    if (arista.interno) continue;
    const L = arista.l;
    for (let k = 0; k < L.length - 1; k++) {  // separadores (los carriles van de derecha a izquierda)
      const A = L[k][1], B = L[k + 1][1]; if (A.length !== B.length) continue;
      tira(pd, id, A.map((v, i) => (v + B[i]) / 2), 0.13, 0.085, ud, 6);
    }
    const [w0, p0] = L[0], [wn, pn] = L[L.length - 1];
    tira(pw, iw, p0, 0.14, 0.086, null, 0, w0 / 2 - 0.25);
    if (arista.o) tira(py, iy, pn, 0.13, 0.086, null, 0, -(wn / 2 - 0.12));
    else tira(pw, iw, pn, 0.14, 0.086, null, 0, -(wn / 2 - 0.25));
  }
  for (const [w, pts] of CIUDAD.andenes) tira(pb, ib, pts, w, 0.16, ub);
  for (const [w, pts] of CIUDAD.cebras) tira(pc, ic, pts, w * 0.9, 0.1);
  const asf = lienzoTextura(512, 512, (g, W) => {
    const img = g.createImageData(W, W);
    for (let i = 0; i < W * W; i++) { const r = 52 + (Math.random() - 0.5) * 22 + (Math.random() < 0.01 ? 25 : 0); img.data.set([r, r + 1, r + 4, 255], i * 4); }
    g.putImageData(img, 0, 0); g.strokeStyle = 'rgba(20,20,22,.45)'; g.lineWidth = 1.2;
    for (let i = 0; i < 6; i++) { g.beginPath(); let x = Math.random() * W, y = Math.random() * W; g.moveTo(x, y); for (let k = 0; k < 8; k++) { x += (Math.random() - 0.5) * 40; y += (Math.random() - 0.5) * 40; g.lineTo(x, y); } g.stroke(); }
  });
  asf.wrapS = asf.wrapT = THREE.RepeatWrapping;
  asfaltoMat = new THREE.MeshStandardMaterial({ map: asf, roughness: 0.92, metalness: 0.0, side: THREE.DoubleSide });
  const via = malla(pa, ia, asfaltoMat, [['uv', ua, 2]]); via.receiveShadow = true; ciudadGrupo.add(via);
  const baldosa = lienzoTextura(128, 128, (g) => { g.fillStyle = '#cfc9bd'; g.fillRect(0, 0, 128, 128); g.strokeStyle = '#b3ad9f'; g.lineWidth = 3;
    for (let i = 0; i <= 128; i += 32) { g.beginPath(); g.moveTo(i, 0); g.lineTo(i, 128); g.moveTo(0, i); g.lineTo(128, i); g.stroke(); } });
  baldosa.wrapS = baldosa.wrapT = THREE.RepeatWrapping; baldosa.repeat.set(3, 3);
  const anden = malla(pb, ib, new THREE.MeshStandardMaterial({ map: baldosa, roughness: 0.9, side: THREE.DoubleSide }), [['uv', ub, 2]]); anden.receiveShadow = true; ciudadGrupo.add(anden);
  const cebra = lienzoTextura(16, 64, (g) => { g.fillStyle = '#3b3f45'; g.fillRect(0, 0, 16, 64); g.fillStyle = '#f2f2f2'; g.fillRect(0, 0, 16, 32); });
  cebra.wrapS = cebra.wrapT = THREE.RepeatWrapping; cebra.repeat.set(1, 4);
  ciudadGrupo.add(malla(pc, ic, new THREE.MeshStandardMaterial({ color: 0xffffff, map: cebra, roughness: 0.7, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -1 })));
  const raya = lienzoTextura(64, 8, (g) => { g.clearRect(0, 0, 64, 8); g.fillStyle = '#fff'; g.fillRect(0, 0, 32, 8); });
  raya.wrapS = THREE.RepeatWrapping;
  const marca = { roughness: 0.6, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2 };
  ciudadGrupo.add(malla(pd, id, new THREE.MeshStandardMaterial({ color: 0xf2f2f2, map: raya, alphaTest: 0.5, ...marca }), [['uv', ud, 2]]));
  ciudadGrupo.add(malla(pw, iw, new THREE.MeshStandardMaterial({ color: 0xeeeeee, ...marca })));
  ciudadGrupo.add(malla(py, iy, new THREE.MeshStandardMaterial({ color: 0xf2c200, ...marca })));
}

// paletas de pared por estilo (los vidrios conservan su color)
const PALETAS = [
  [0xe9edf1, 0xd5dbe1, 0xc9cfd6, 0xf4f4f4],                                                       // 0 torre de vidrio (marcos)
  [0xf4f1ea, 0xeee6d8, 0xe2dfd8, 0xf7f7f7, 0xd9cfc1, 0xc9b49a],                                   // 1 torre residencial
  [0xf6e7c8, 0xeed8c4, 0xdce9ef, 0xf1dcd3, 0xe4efe0, 0xfff4d6, 0xd9d4cc, 0xf5d5e0, 0xd6e6f2],     // 2 pastel
  [0xff6f91, 0x1abc9c, 0xf7dc6f, 0xf39c12, 0x58d68d, 0x5dade2, 0xbb8fce, 0xe74c3c, 0xfdfefe, 0x48c9b0, 0xf5b041, 0xec7063], // 3 Caribe
  [0xb8c0c8, 0x9fb3c8, 0xc9c9c9, 0x8fa6b8],                                                       // 4 bodega
  [0xfbfaf7, 0xf3eee4, 0xeceae6, 0xe8dccb],                                                       // 5 elegante
].map((p) => p.map((c) => new THREE.Color(c)));
const TECHOS = [0x8a9096, 0xb9b4aa, 0xa6a097, 0x9e4b33, 0x8d8a85, 0xcfcac2].map((c) => new THREE.Color(c));
function construirEdificios() {
  // por baldosas de 700 m para que la cámara descarte lo que no ve
  const TAM = 700, grupos = new Map(), tanques = [];
  // los edificios dentro del predio de la Puerta de Oro se dibujan aparte, con fachada dorada
  const predios = (CIUDAD.hitos || []).filter((h) => h.tipo === 'puerta_oro' && h.poligono).map((h) => { h.edificios = []; return h; });
  const dentro = (pl, x, y) => { let c = false; for (let i = 0, j = pl.length / 2 - 1; i < pl.length / 2; j = i++) {
    const xi = pl[2 * i], yi = pl[2 * i + 1], xj = pl[2 * j], yj = pl[2 * j + 1];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
  CIUDAD.edificios.forEach((b, k) => {
    const p = b[2]; let cx = 0, cy = 0; const n = p.length / 2; for (let i = 0; i < n; i++) { cx += p[2 * i]; cy += p[2 * i + 1]; } cx /= n; cy /= n;
    const predio = predios.find((h) => dentro(h.poligono, cx, cy)); if (predio) { predio.edificios.push(b); return; }
    const clave = `${Math.floor(cx / TAM)},${Math.floor(cy / TAM)}`; if (!grupos.has(clave)) grupos.set(clave, []); grupos.get(clave).push([b, k, cx, cy]);
  });
  for (const lista of grupos.values()) {
    const pos = [], idx = [], uv = [], col = [], est = [], sem = [], pr = [], ir = [], cr = [];
    for (const [[h, , p, , estilo = 2], k, cx, cy] of lista) {
      const pal = PALETAS[estilo] || PALETAS[2]; const c = pal[Math.floor(azar(k, 3) * pal.length)];
      const altoPiso = estilo === 4 ? 4.5 : 3.1; const s = azar(k, 5);
      const n = p.length / 2; let u = 0;
      for (let i = 0; i < n; i++) {
        const j = (i + 1) % n, ax = p[2 * i], ay = p[2 * i + 1], bx = p[2 * j], by = p[2 * j + 1];
        const L = Math.hypot(bx - ax, by - ay), b0 = pos.length / 3;
        pos.push(ax, 0, -ay, bx, 0, -by, bx, h, -by, ax, h, -ay);
        uv.push(u / 3.5, 0, (u + L) / 3.5, 0, (u + L) / 3.5, h / altoPiso, u / 3.5, h / altoPiso);
        for (let q = 0; q < 4; q++) { col.push(c.r, c.g, c.b); est.push(estilo); sem.push(s); }
        idx.push(b0, b0 + 1, b0 + 2, b0, b0 + 2, b0 + 3); u += L;
      }
      const b1 = pr.length / 3; poligono(pr, ir, p, h);
      const tc = estilo === 3 ? TECHOS[azar(k, 7) < 0.35 ? 3 : 1] : estilo === 5 ? TECHOS[azar(k, 7) < 0.4 ? 3 : 5] : estilo <= 1 ? TECHOS[0] : TECHOS[1 + Math.floor(azar(k, 7) * 3) % 3];
      for (let q = b1; q < pr.length / 3; q++) cr.push(tc.r, tc.g, tc.b);
      if ((estilo === 3 || estilo === 2) && h < 11 && azar(k, 9) < 0.35) tanques.push([cx, cy, h]);  // tanque de agua negro en la terraza
    }
    const paredes = malla(pos, idx, matEdificios, [['uv', uv, 2], ['color', col, 3], ['estilo', est, 1], ['semilla', sem, 1]]);
    paredes.castShadow = paredes.receiveShadow = true; paredes.geometry.computeBoundingSphere(); ciudadGrupo.add(paredes);
    const techos = malla(pr, ir, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9, side: THREE.DoubleSide }), [['color', cr, 3]]);
    techos.receiveShadow = true; ciudadGrupo.add(techos);
  }
  const g = new THREE.CylinderGeometry(0.62, 0.62, 1.15, 12).translate(0, 0.58, 0);
  const im = new THREE.InstancedMesh(g, new THREE.MeshStandardMaterial({ color: 0x151515, roughness: 0.5 }), tanques.length);
  const M = new THREE.Matrix4(); tanques.forEach(([x, y, h], i) => { M.makeTranslation(x, h, -y); im.setMatrixAt(i, M); });
  im.castShadow = true; ciudadGrupo.add(im);
}

function construirVegetacion() {
  // sin vegetación encima de los monumentos
  const RADIO = { estatua_shakira: 12, estatua_sofia: 12, rueda: 34, carrusel: 11, plaza_luces: 28, caiman: 32, ventana_mundo: 26, aleta_tiburon: 26, ventana_campeones: 26 };
  const libres = (CIUDAD.hitos || []).filter((h) => RADIO[h.tipo]);
  const dentroDe = (p, x, y) => { let c = false; for (let i = 0, j = p.length / 2 - 1; i < p.length / 2; j = i++) {
    const xi = p[2 * i], yi = p[2 * i + 1], xj = p[2 * j], yj = p[2 * j + 1];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
  const conPoligono = (CIUDAD.hitos || []).filter((h) => h.poligono);
  const libre = ([x, y]) => libres.every((h) => Math.hypot(x - h.x, y - h.y) > RADIO[h.tipo]) && conPoligono.every((h) => !dentroDe(h.poligono, x, y));
  const palmas = CIUDAD.palmeras.filter(libre).map(([x, y, h]) => [x, y, h]);
  const arboles = (CIUDAD.arboles || []).filter(libre);
  for (const a of arboles) if (a[3] === 4) palmas.push([a[0], a[1], a[2] + 2]);
  // palmeras
  { const tronco = new THREE.CylinderGeometry(0.16, 0.28, 1, 7); tronco.translate(0, 0.5, 0);
    const hojas = []; for (let i = 0; i < 9; i++) { const h = new THREE.ConeGeometry(0.55, 4.6, 3); h.scale(1, 1, 0.22);
      h.rotateZ(-Math.PI / 2 - 0.25 - (i % 2) * 0.25); h.translate(2.2, -0.5, 0); h.rotateY((i / 9) * Math.PI * 2); hojas.push(h.toNonIndexed()); }
    const n = palmas.length;
    const mt = new THREE.InstancedMesh(tronco, new THREE.MeshStandardMaterial({ color: 0x8b6b4a, roughness: 0.95 }), n);
    const geoHojas = new THREE.BufferGeometry(); { const arr = hojas.flatMap((h) => [...h.attributes.position.array]); geoHojas.setAttribute('position', new THREE.Float32BufferAttribute(arr, 3)); geoHojas.computeVertexNormals(); }
    const mc = new THREE.InstancedMesh(geoHojas, new THREE.MeshStandardMaterial({ color: 0x3f8f3a, roughness: 0.8, side: THREE.DoubleSide }), n);
    const M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), col = new THREE.Color();
    palmas.forEach(([x, y, h], i) => {
      M.compose(new THREE.Vector3(x, 0, -y), q.identity(), new THREE.Vector3(1, h, 1)); mt.setMatrixAt(i, M);
      M.compose(new THREE.Vector3(x, h, -y), q.setFromEuler(e.set(0, i * 1.7, 0)), new THREE.Vector3(1, 1, 1)); mc.setMatrixAt(i, M);
      mc.setColorAt(i, col.setHSL(0.28 + azar(i, 1) * 0.05, 0.5, 0.3 + azar(i, 2) * 0.1));
    });
    mt.castShadow = mc.castShadow = true; ciudadGrupo.add(mt, mc); }
  // árboles de copa (mango, almendro, roble morado, guayacán amarillo, matarratón)
  { const lista = arboles.filter((a) => a[3] !== 4); const n = lista.length;
    const tronco = new THREE.CylinderGeometry(0.14, 0.24, 1, 6).translate(0, 0.5, 0);
    const copa = new THREE.IcosahedronGeometry(1, 1); const pp = copa.attributes.position;
    for (let i = 0; i < pp.count; i++) { const v = new THREE.Vector3().fromBufferAttribute(pp, i); const k = 0.82 + 0.3 * azar(Math.floor((v.x + 2) * 7 + (v.y + 2) * 13 + (v.z + 2) * 29), 4); v.multiplyScalar(k); v.y *= 0.78; pp.setXYZ(i, v.x, v.y, v.z); }
    copa.computeVertexNormals();
    const mt = new THREE.InstancedMesh(tronco, new THREE.MeshStandardMaterial({ color: 0x6b4f36, roughness: 0.95 }), n);
    const mc = new THREE.InstancedMesh(copa, new THREE.MeshStandardMaterial({ roughness: 0.85, flatShading: true }), n);
    const COPAS = [[0.3, 0.55, 0.22], [0.27, 0.45, 0.32], [0.86, 0.45, 0.62], [0.13, 0.85, 0.55], [0.3, 0.45, 0.3], [0.31, 0.5, 0.36]];
    const M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), col = new THREE.Color();
    lista.forEach(([x, y, h, esp], i) => {
      const tr = h * 0.45; M.compose(new THREE.Vector3(x, 0, -y), q.identity(), new THREE.Vector3(1, tr + 1, 1)); mt.setMatrixAt(i, M);
      const r = h * (0.3 + 0.12 * azar(i, 6)); M.compose(new THREE.Vector3(x, tr + r * 0.72, -y), q.setFromEuler(e.set(0, azar(i, 7) * 6, 0)), new THREE.Vector3(r, r, r)); mc.setMatrixAt(i, M);
      const [hh, ss, ll] = COPAS[esp] || COPAS[0]; mc.setColorAt(i, col.setHSL(hh + (azar(i, 8) - 0.5) * 0.04, ss, ll * (0.85 + 0.3 * azar(i, 9))));
    });
    mt.castShadow = mc.castShadow = true; mc.receiveShadow = true; ciudadGrupo.add(mt, mc); }
}

function construirAlumbrado() {
  const n = CIUDAD.faroles.length;
  const gPoste = new THREE.CylinderGeometry(0.09, 0.13, 9, 6).translate(0, 4.5, 0);
  const gBrazo = new THREE.BoxGeometry(2.4, 0.1, 0.1).translate(1.2, 9, 0);
  const geo = new THREE.BufferGeometry(); { const a = gPoste.toNonIndexed(), b = gBrazo.toNonIndexed();
    geo.setAttribute('position', new THREE.Float32BufferAttribute([...a.attributes.position.array, ...b.attributes.position.array], 3)); geo.computeVertexNormals(); }
  const mPoste = new THREE.InstancedMesh(geo, new THREE.MeshStandardMaterial({ color: 0x55595e, metalness: 0.6, roughness: 0.45 }), n);
  bulbosMat = new THREE.MeshBasicMaterial({ color: 0x777777, toneMapped: false });
  const mBulbo = new THREE.InstancedMesh(new THREE.BoxGeometry(0.7, 0.18, 0.35).translate(2.3, 8.9, 0), bulbosMat, n);
  const hp = new Float32Array(n * 3); const M = new THREE.Matrix4(), q = new THREE.Quaternion(), Y = new THREE.Vector3(0, 1, 0);
  const halo = lienzoTextura(64, 64, (c) => { const gr = c.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,214,150,1)'); gr.addColorStop(0.35, 'rgba(255,180,90,.45)'); gr.addColorStop(1, 'rgba(255,160,60,0)'); c.fillStyle = gr; c.fillRect(0, 0, 64, 64); });
  charcosMat = new THREE.MeshBasicMaterial({ map: halo, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, color: 0xffc98a, polygonOffset: true, polygonOffsetFactor: -4 });
  const charco = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), charcosMat, n);
  CIUDAD.faroles.forEach(([x, y, r], i) => {
    M.compose(new THREE.Vector3(x, 0, -y), q.setFromAxisAngle(Y, r), new THREE.Vector3(1, 1, 1));
    mPoste.setMatrixAt(i, M); mBulbo.setMatrixAt(i, M);
    const bx = x + Math.cos(r) * 2.3, by = y + Math.sin(r) * 2.3; hp.set([bx, 8.7, -by], i * 3);
    M.compose(new THREE.Vector3(bx, 0.12, -by), q.identity(), new THREE.Vector3(16, 1, 16)); charco.setMatrixAt(i, M);
  });
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(hp, 3));
  halos = new THREE.Points(g, new THREE.PointsMaterial({ map: halo, size: 9, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, fog: true, toneMapped: false }));
  mPoste.castShadow = true; ciudadGrupo.add(mPoste, mBulbo, halos, charco);
}

function construirSemaforos() {
  // poste con brazo y caja de tres luces que mira al tráfico que llega; los enlaces del mismo
  // carril (giro, recto) comparten cabeza: se deja una por posición
  // una cabeza por acceso (mismo semáforo y misma dirección de llegada): la del borde derecho
  const accesos = new Map();
  for (const s of CIUDAD.semaforos) {
    const [tls, , x, y, ang] = s; const k = `${tls}|${Math.round(((ang + 7 * Math.PI) % (2 * Math.PI)) / 0.35)}`;
    const derecha = x * Math.sin(ang) - y * Math.cos(ang); const previo = accesos.get(k);
    if (!previo || derecha > previo[0]) accesos.set(k, [derecha, s]);
  }
  CIUDAD.semaforos = [...accesos.values()].map(([, s]) => s);
  const n = CIUDAD.semaforos.length;
  // brazo hacia la vía (eje -x local) y caja colgada sobre el carril
  const geoPoste = fusionar([caja(0.16, 5.4, 0.16, 0, 2.7, 0, 0x2b2f33), caja(2.3, 0.12, 0.12, -1.1, 5.3, 0, 0x2b2f33)]);
  const geoCaja = fusionar([caja(0.42, 1.25, 0.35, 0, 0, 0, 0x1c1f22), caja(0.5, 1.35, 0.04, 0, 0, 0.19, 0x111111)]);
  const poste = new THREE.InstancedMesh(geoPoste, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.6 }), n);
  semaforo.cajas = new THREE.InstancedMesh(geoCaja, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.5 }), n);
  semaforo.lamparas = new THREE.InstancedMesh(new THREE.SphereGeometry(0.15, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false }), n);
  semaforo.base = [];
  const M = new THREE.Matrix4(), q = new THREE.Quaternion(), Y = new THREE.Vector3(0, 1, 0);
  CIUDAD.semaforos.forEach(([, , x, y, ang], k) => {
    // el poste está a la derecha del carril; la cara (+z local) mira a los carros que llegan
    const rot = q.setFromAxisAngle(Y, ang - Math.PI / 2).clone();
    M.compose(new THREE.Vector3(x, 0, -y), rot, new THREE.Vector3(1, 1, 1)); poste.setMatrixAt(k, M);
    const centro = new THREE.Vector3(x - Math.sin(ang) * 2.1, 4.7, -(y + Math.cos(ang) * 2.1));
    M.compose(centro, rot, new THREE.Vector3(1, 1, 1)); semaforo.cajas.setMatrixAt(k, M);
    semaforo.base.push({ centro, rot }); semaforo.lamparas.setColorAt(k, new THREE.Color(0x222222));
  });
  poste.castShadow = true; ciudadGrupo.add(poste, semaforo.cajas, semaforo.lamparas);
}

const personasEstaticas = [];  // [x, y, rumbo, semilla]: vendedores y clientes en los puestos
function construirPuestos() {
  const geos = geometriasPuestos(); const por = [[], [], [], []];
  for (const p of CIUDAD.puestos || []) por[p[3]]?.push(p);
  const M = new THREE.Matrix4(), q = new THREE.Quaternion(), Y = new THREE.Vector3(0, 1, 0);
  geos.forEach((g, tipo) => {
    const lista = por[tipo]; if (!lista.length) return;
    const im = new THREE.InstancedMesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.7 }), lista.length);
    lista.forEach(([x, y, r], i) => { M.compose(new THREE.Vector3(x, 0.16, -y), q.setFromAxisAngle(Y, r), new THREE.Vector3(1, 1, 1)); im.setMatrixAt(i, M);
      // el vendedor detrás del puesto (-z local) mirando a los clientes que están al frente (+z local)
      const fx = Math.sin(r), fy = -Math.cos(r);  // +z local en coordenadas de SUMO
      const rumboVendedor = 180 - r * 180 / Math.PI;
      personasEstaticas.push([x - fx * 1.1, y - fy * 1.1, rumboVendedor, i * 7 + tipo]);
      const nCli = Math.floor(azar(i, tipo + 11) * (tipo === 3 ? 4 : 3));
      for (let c = 0; c < nCli; c++) { const d = 1.5 + c * 0.7, lat = (azar(i, c) - 0.5) * 2.2;
        personasEstaticas.push([x + fx * d + fy * lat, y + fy * d - fx * lat, rumboVendedor + 180 + (azar(i, c + 5) - 0.5) * 50, i * 13 + c]); }
    });
    im.castShadow = true; ciudadGrupo.add(im);
  });
  // gente en las entradas de los centros comerciales y en el Malecón
  for (const h of CIUDAD.hitos || []) {
    const n = h.tipo === 'mall' ? 26 : h.tipo === 'rueda' ? 30 : h.tipo === 'carrusel' ? 16 : h.tipo === 'plaza_luces' ? 22 : 0;
    for (let i = 0; i < n; i++) { const a = azar(i, h.x) * Math.PI * 2, r = (h.tipo === 'mall' ? 26 : 16) + azar(h.y, i) * 18;
      personasEstaticas.push([h.x + Math.cos(a) * r, h.y + Math.sin(a) * r, azar(i, 3) * 360, i * 31 + Math.round(h.x)]); }
  }
}

// ================================================================ vehículos
const matPintura = new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: 0.45, roughness: 0.32, clearcoat: 1.0, clearcoatRoughness: 0.06 });
const matPinturaMetal = new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: 0.95, roughness: 0.38, clearcoat: 0.2 });
const matVidrio = sinColorInstancia(new THREE.MeshPhysicalMaterial({ vertexColors: true, metalness: 0.3, roughness: 0.05, clearcoat: 1, envMapIntensity: 1.6 }));
const matDetalle = sinColorInstancia(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.55, metalness: 0.35 }));
const matLuces = sinColorInstancia(new THREE.MeshBasicMaterial({ vertexColors: true, toneMapped: false }));
for (const [m, k] of [[matPintura, 1.2], [matPinturaMetal, 1.2], [matVidrio, 1.6], [matDetalle, 0.8]]) { m.userData.env = k; MATS_ENTORNO.add(m); }
function geometriaModelo(m) {  // una geometría con 4 grupos: pintura, vidrio, detalle, luces
  const partes = [fusionar(m.pintura), fusionar(m.vidrio), fusionar(m.detalle), fusionar(m.luces)];
  const pos = [], nor = [], col = []; const g = new THREE.BufferGeometry(); let inicio = 0;
  partes.forEach((p, k) => { const n = p.attributes.position.count; pos.push(...p.attributes.position.array); nor.push(...p.attributes.normal.array); col.push(...p.attributes.color.array);
    g.addGroup(inicio, n, k); inicio += n; });
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.computeBoundingSphere(); return g;
}
const flota = {};
for (const [clave, def] of Object.entries(MODELOS)) {
  if (clave === 'porsche') continue;
  const m = def.crear(); const geo = geometriaModelo(m);
  const im = new THREE.InstancedMesh(geo, [def.metal ? matPinturaMetal : matPintura, matVidrio, matDetalle, matLuces], def.max);
  im.count = 0; im.frustumCulled = false; im.castShadow = true; im.receiveShadow = true;
  im.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(def.max * 3).fill(1), 3);
  scene.add(im); flota[clave] = { im, def, L: m.L, W: m.W, n: 0 };
}
// vehículo instructor: Porsche 911 GT color cherry blossom
const COLOR_EGO = new THREE.Color('#f4a3bf');
const egoMalla = (() => { const m = MODELOS.porsche.crear(); const geo = geometriaModelo(m);
  const pintura = new THREE.MeshPhysicalMaterial({ color: COLOR_EGO, metalness: 0.35, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.04, sheen: 0.4, sheenColor: new THREE.Color('#ffd6e4') });
  const mesh = new THREE.Mesh(geo, [pintura, matVidrio, matDetalle, matLuces.clone()]); mesh.castShadow = true; mesh.userData.L = m.L; return mesh; })();
egoMalla.material[3].onBeforeCompile = matLuces.onBeforeCompile; egoMalla.material[3].customProgramCacheKey = matLuces.customProgramCacheKey;
scene.add(egoMalla);
const farosEgo = new THREE.SpotLight(0xfff1d8, 0, 70, 0.55, 0.5, 1.4); farosEgo.position.set(0, 0.8, 0.1);
farosEgo.target.position.set(0, 0, -30); egoMalla.add(farosEgo, farosEgo.target);
const anillo = new THREE.Mesh(new THREE.RingGeometry(3.4, 3.9, 48), new THREE.MeshBasicMaterial({ color: 0xff8fb8, transparent: true, opacity: 0.85, side: THREE.DoubleSide, toneMapped: false }));
anillo.rotation.x = -Math.PI / 2; scene.add(anillo);
let egoEtiqueta = etiqueta('Porsche 911 GT · instructor', '#ffb6cf', 'rgba(10,16,24,.8)', 26); egoEtiqueta.userData.base = 0.02; scene.add(egoEtiqueta);
function nombreEgo(texto) {
  scene.remove(egoEtiqueta); egoEtiqueta.material.map.dispose();
  egoEtiqueta = etiqueta(texto, '#ffb6cf', 'rgba(10,16,24,.8)', 26); egoEtiqueta.userData.base = 0.02; scene.add(egoEtiqueta);
}
// luz de faros sobre el pavimento (de noche) para todos los vehículos
const texHaz = lienzoTextura(64, 128, (g) => { const gr = g.createRadialGradient(32, 110, 2, 32, 70, 64); gr.addColorStop(0, 'rgba(255,240,210,.9)'); gr.addColorStop(1, 'rgba(255,240,210,0)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 128); });
const matHaz = new THREE.MeshBasicMaterial({ map: texHaz, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, polygonOffset: true, polygonOffsetFactor: -4 });
const haces = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2).translate(0, 0, -0.5), matHaz, 1500);
haces.count = 0; haces.frustumCulled = false; scene.add(haces);
const sensorMat = new THREE.MeshBasicMaterial({ color: 0x4fb3ff, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false });
const sensor = new THREE.Mesh(new THREE.CircleGeometry(90, 40, Math.PI / 2 - Math.PI / 3, (2 * Math.PI) / 3), sensorMat);
sensor.rotation.x = -Math.PI / 2; scene.add(sensor);
let alcanceActual = 90;
const lineasDet = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9, toneMapped: false }));
lineasDet.frustumCulled = false; scene.add(lineasDet);
const infoVeh = new Map();  // id -> { clave, color } (el modelo se elige una vez, según el estrato donde aparece)

// ================================================================ personas (cuerpo articulado e instanciado)
const PERS = partesPersona(); const MAXP = 2600;
const matPersona = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85 });
const persona = Object.fromEntries(['torso', 'piernaI', 'piernaD', 'brazoI', 'brazoD', 'cabeza', 'pelo'].map((k) => {
  const geo = { piernaI: PERS.pierna, piernaD: PERS.pierna, brazoI: PERS.brazo, brazoD: PERS.brazo }[k] || PERS[k];
  const im = new THREE.InstancedMesh(geo, matPersona, MAXP); im.count = 0; im.frustumCulled = false; im.castShadow = true;
  im.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAXP * 3).fill(1), 3); scene.add(im); return [k, im];
}));
const posPrevPersona = new Map();
const PM = new THREE.Matrix4(), PB = new THREE.Matrix4(), PT = new THREE.Matrix4(), PR = new THREE.Matrix4(), PQ = new THREE.Quaternion(), PV = new THREE.Vector3(), PC = new THREE.Color();
function ponerPersona(i, x, y, angGrados, semilla, paso, t) {
  PQ.setFromAxisAngle(EJE_Y, -angGrados * Math.PI / 180); PV.set(x, 0.16, -y); PB.compose(PV, PQ, UNO);
  const giro = paso ? Math.sin(t * 7.5 + semilla) * 0.55 : 0;
  persona.torso.setMatrixAt(i, PB); persona.cabeza.setMatrixAt(i, PB); persona.pelo.setMatrixAt(i, PB);
  for (const [k, dx, dy, s] of [['piernaI', -0.1, 0.92, 1], ['piernaD', 0.1, 0.92, -1], ['brazoI', -0.26, 1.45, -0.8], ['brazoD', 0.26, 1.45, 0.8]]) {
    PT.makeTranslation(dx, dy, 0); PR.makeRotationX(giro * s); PM.multiplyMatrices(PB, PT).multiply(PR); persona[k].setMatrixAt(i, PM);
  }
  const r = Math.abs(Math.floor(semilla));
  persona.torso.setColorAt(i, PC.setHex(ROPA[r % ROPA.length])); persona.brazoI.setColorAt(i, PC); persona.brazoD.setColorAt(i, PC);
  persona.piernaI.setColorAt(i, PC.setHex(PANTALON[(r >> 2) % PANTALON.length])); persona.piernaD.setColorAt(i, PC);
  persona.cabeza.setColorAt(i, PC.setHex(PIEL[(r >> 4) % PIEL.length])); persona.pelo.setColorAt(i, PC.setHex(PELO[(r >> 3) % PELO.length]));
}
function cerrarPersonas(n) { for (const im of Object.values(persona)) { im.count = n; im.instanceMatrix.needsUpdate = true; im.instanceColor.needsUpdate = true; } }
// figura no instanciada (para imprevistos: peatón imprudente, vendedor de semáforo)
function figuraPersona(semilla, extra = []) {
  const r = semilla; const recolor = (g, c) => { const n = g.clone(); const col = n.attributes.color; const cc = new THREE.Color(c);
    for (let i = 0; i < col.count; i++) col.setXYZ(i, col.getX(i) * cc.r, col.getY(i) * cc.g, col.getZ(i) * cc.b); return n; };
  const mov = (g, x, y) => g.clone().translate(x, y, 0);
  return fusionar([recolor(PERS.torso, ROPA[r % ROPA.length]), recolor(mov(PERS.pierna, -0.1, 0.92), PANTALON[r % PANTALON.length]), recolor(mov(PERS.pierna, 0.1, 0.92), PANTALON[r % PANTALON.length]),
    recolor(mov(PERS.brazo, -0.26, 1.45), ROPA[r % ROPA.length]), recolor(mov(PERS.brazo, 0.26, 1.45), ROPA[r % ROPA.length]),
    recolor(PERS.cabeza, PIEL[r % PIEL.length]), recolor(PERS.pelo, PELO[r % PELO.length]), ...extra]);
}
const FIGURAS = {
  peaton: () => figuraPersona(6),
  vendedor: () => figuraPersona(3, [caja(0.5, 0.36, 0.34, 0, 0.95, -0.32, 0xf4f4f4), caja(0.52, 0.06, 0.36, 0, 1.15, -0.32, 0x1f6fd1), caja(0.36, 0.08, 0.36, 0, 1.86, 0, 0xf5c518)]),
  perro: () => fusionar([caja(0.32, 0.4, 0.9, 0, 0.45, 0.45, 0x8a5a2b), caja(0.28, 0.3, 0.32, 0, 0.72, -0.05, 0x7a4a20), caja(0.08, 0.32, 0.08, 0.1, 0.16, 0.15, 0x6b3f1a), caja(0.08, 0.32, 0.08, -0.1, 0.16, 0.75, 0x6b3f1a), caja(0.08, 0.32, 0.08, -0.1, 0.16, 0.15, 0x6b3f1a), caja(0.08, 0.32, 0.08, 0.1, 0.16, 0.75, 0x6b3f1a)]),
  iguana: () => fusionar([caja(0.22, 0.14, 0.7, 0, 0.08, 0.35, 0x3fae49), caja(0.12, 0.08, 0.9, 0, 0.05, 1.1, 0x2f8a37), caja(0.16, 0.12, 0.18, 0, 0.1, -0.05, 0x56c35f)]),
};
const matFigura = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.8 });
const objetos = new Map();
function figuraConos() { const g = new THREE.Group(); const cono = new THREE.ConeGeometry(0.28, 0.8, 12).translate(0, 0.4, 0);
  const m1 = new THREE.MeshStandardMaterial({ color: 0xff6a00, emissive: 0x401800, roughness: 0.6 });
  const franja = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x333333 });
  for (let i = 0; i < 6; i++) { const c = new THREE.Mesh(cono, m1); c.position.set(0, 0, i * 2.6); g.add(c);
    const f = new THREE.Mesh(new THREE.CylinderGeometry(0.17, 0.2, 0.12, 12), franja); f.position.set(0, 0.45, i * 2.6); g.add(f); }
  g.add(new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.9, 0.12).translate(0, 0.45, -0.4), new THREE.MeshStandardMaterial({ color: 0xff8c00, roughness: 0.6 }))); return g; }

// ================================================================ lluvia
const gotas = (() => { const n = 6000, p = new Float32Array(n * 6);
  for (let i = 0; i < n; i++) { const x = (Math.random() - 0.5) * 500, y = Math.random() * 140, z = (Math.random() - 0.5) * 500; p.set([x, y, z, x + 0.3, y - 2.2, z], i * 6); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  const l = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0xaac4dd, transparent: true, opacity: 0.42 }));
  l.visible = false; l.frustumCulled = false; scene.add(l); return l; })();

// ================================================================ ambiente (hora, luz, lluvia)
let horaVisual = 17.5, lluviaVisual = false;
const solDir = new THREE.Vector3(), lunaDir = new THREE.Vector3(), tmpC = new THREE.Color();
function aplicarAmbiente(h, lluvia, t) {
  const L = luminosidad(h), osc = 1 - L;
  const [cen, med, hor] = paletaCielo(h, lluvia);
  const u = cieloMat.uniforms; u.cenit.value.copy(cen); u.medio.value.copy(med); u.horizonte.value.copy(hor);
  // el sol sale por el río (este) y se pone detrás de la ciudad (oeste); a 11° N pasa algo al sur
  const th = Math.PI * (h - 6.05) / 12.2;
  solDir.set(Math.cos(th), Math.sin(th), 0.22).normalize(); lunaDir.set(-Math.cos(th), -Math.sin(th) * 0.9 + 0.15, 0.3).normalize();
  u.solDir.value.copy(solDir); u.lunaDir.value.copy(lunaDir);
  u.solColor.value.setRGB(1, 0.55 + 0.4 * Math.max(0, solDir.y), 0.35 + 0.5 * Math.max(0, solDir.y));
  u.lluvia.value = lluvia ? 1 : 0; u.oscuridad.value = osc; u.tiempo.value = t; u.nubes.value = lluvia ? 0.92 : 0.3;
  const elev = Math.max(0, solDir.y);
  sol.position.copy(solDir).multiplyScalar(1500).add(controls.target); sol.target.position.copy(controls.target);
  sol.intensity = (lluvia ? 0.6 : 2.6) * L * Math.min(1, elev * 4 + 0.15);
  sol.color.setRGB(1, 0.7 + 0.28 * Math.min(1, elev * 2.5), 0.5 + 0.45 * Math.min(1, elev * 2.5));
  luna.position.copy(lunaDir).multiplyScalar(1500).add(controls.target); luna.target.position.copy(controls.target);
  luna.intensity = 0.35 * osc * (lluvia ? 0.4 : 1);
  hemi.intensity = (lluvia ? 0.45 : 0.3) * (0.25 + 0.75 * L) + 0.08;
  tmpC.setRGB(med.r, med.g, med.b, THREE.SRGBColorSpace); hemi.color.copy(tmpC).lerp(new THREE.Color(0xffffff), 0.35);
  scene.fog.color.setRGB(hor.r, hor.g, hor.b, THREE.SRGBColorSpace);
  scene.fog.near = lluvia ? 220 : 700; scene.fog.far = lluvia ? 1400 : (L < 0.3 ? 2600 : 3800);
  renderer.toneMappingExposure = 0.78 + 0.4 * osc;
  const kEnv = 0.25 + 0.55 * L; for (const m of MATS_ENTORNO) m.envMapIntensity = kEnv * (m.userData.env ?? 1);
  estrellas.material.opacity = Math.max(0, osc - 0.25) * (lluvia ? 0.15 : 1);
  unifFachada.uNoche.value = suave(0.2, 0.8, osc); unifFachada.uEncendidas.value = 0.12 + 0.5 * suave(0.2, 0.9, osc);
  if (bulbosMat) { const k = suave(0.2, 0.6, osc); bulbosMat.color.setRGB(0.45 + 2.6 * k, 0.45 + 2.0 * k, 0.45 + 0.9 * k); }
  if (halos) halos.material.opacity = 0.95 * suave(0.25, 0.7, osc);
  if (charcosMat) charcosMat.opacity = 0.32 * suave(0.25, 0.7, osc);
  if (aguaMat) { const a = aguaMat.uniforms; a.cielo.value.copy(med); a.horiz.value.copy(hor); a.luz.value = 0.15 + 0.85 * L; a.solDir.value.copy(solDir); a.solColor.value.copy(u.solColor.value); a.lluvia.value = lluvia ? 1 : 0; }
  if (asfaltoMat) { asfaltoMat.roughness = lluvia ? 0.3 : 0.92; asfaltoMat.color.setScalar(lluvia ? 0.7 : 1); }
  const kLuz = suave(0.25, 0.75, osc);
  for (const m of [matLuces, egoMalla.material[3]]) m.color.setScalar(0.75 + 2.6 * kLuz);
  matHaz.opacity = 0.5 * kLuz; haces.visible = kLuz > 0.02;
  farosEgo.intensity = 60 * kLuz;
  bloom.strength = 0.15 + 0.42 * osc; bloom.threshold = 0.9 - 0.08 * osc; bloom.radius = 0.45;
  gotas.visible = lluvia;
  actualizarEntorno(h, lluvia);
  return osc;
}
function textoHora(h) { h = ((h % 24) + 24) % 24; const hh = Math.floor(h), mm = Math.floor((h - hh) * 60); return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`; }

// ================================================================ reproducción
let REC = null, t = 0, jugando = true, velRep = 1, camModo = 'seguir', fuente = null, egoFreno = 0;
window.__visor.estado = () => ({ vivo: !!REC?.vivo, cuadros: REC?.cuadros.length ?? 0, t, conectado: !!fuente, calidad,
  ultimo: REC?.cuadros.at(-1) ? { h: REC.cuadros.at(-1).h, kmh: REC.cuadros.at(-1).ego.kmh, dom: REC.cuadros.at(-1).ego.dom, motivo: REC.cuadros.at(-1).ego.motivo } : null });
const DT = () => (REC ? REC.dt : 0.5);
const NOMBRES_ACC = ['frenado de emergencia', 'frenado fuerte', 'frenado moderado', 'frenado suave', 'mantener', 'acelerar suave', 'acelerar'];
const ICONO = { auto: '🚗', taxi: '🚕', moto: '🏍️', bus: '🚌', camion: '🚚', camioneta: '🛻', peaton: '🚶', vendedor: '🧃', perro: '🐕', iguana: '🦎', conos: '🚧' };
const COLOR_EVENTO = { choque: '#ff3b3b', casi_choque: '#ffb000', peaton: '#e04f8a', vendedor: '#1f6fd1', perro: '#a0703a', iguana: '#3fae49', conos: '#ff6a00', frenada_lider: '#4fb3ff', pare_violado: '#ff3b3b', semaforo_rojo: '#ff3b3b' };
function indexar(c) { c.vm = new Map(c.v.map((v) => [v[0], v])); c.pm = new Map(c.p.map((p) => [p[0], p])); c.om = new Map(c.o.map((o) => [o[0], o])); return c; }

let turnoCarga = 0;  // si el usuario arranca otra cosa mientras un recorrido carga, ese recorrido se descarta
async function cargarRecorrido(archivo) {
  detenerVivo();
  const turno = ++turnoCarga;
  carga('Cargando el recorrido grabado…'); $('carga').style.display = 'grid';
  const resp = await fetch('datos/' + archivo);
  const datos = archivo.endsWith('.gz') && typeof DecompressionStream !== 'undefined' && resp.headers.get('content-encoding') !== 'gzip'
    ? await new Response(resp.body.pipeThrough(new DecompressionStream('gzip'))).json() : await resp.json();
  if (turno !== turnoCarga || fuente) { $('carga').style.display = 'none'; return; }
  REC = datos; infoVeh.clear(); posPrevPersona.clear(); dibujarRuta(null);
  REC.cuadros.forEach(indexar); t = 0; nombreEgo('Porsche 911 GT · instructor');
  const ep = REC.episodios[0] || {};
  $('subtitulo').textContent = `${ep.ruta || REC.via || ''} · ${REC.lluvia ? 'lluvia · ' : ''}${textoHora(REC.hora ?? 15)}`;
  const marcas = $('marcas'); marcas.innerHTML = '';
  const dur = REC.cuadros.length * DT();
  for (const e of (ep.eventos || [])) {
    const tipo = e.evento || e.tipo; const rel = (e.t || 0) - (ep.t0 || 0);
    const i = document.createElement('i'); i.title = `${tipo} · ${rel.toFixed(0)} s`; i.style.background = COLOR_EVENTO[tipo] || '#999';
    i.style.left = `${Math.max(0, Math.min(100, (rel / dur) * 100))}%`; marcas.appendChild(i);
  }
  $('carga').style.display = 'none';
}

function interpAng(a, b, f) { const d = ((b - a + 540) % 360) - 180; return a + d * f; }
const M4 = new THREE.Matrix4(), Q = new THREE.Quaternion(), EJE_Y = new THREE.Vector3(0, 1, 0), V3 = new THREE.Vector3(), UNO = new THREE.Vector3(1, 1, 1);
const colTmp = new THREE.Color(); const egoPos = new THREE.Vector3(); let egoAng = 0;

function cuadroActual() {
  if (!REC || !REC.cuadros.length) return null;
  const n = REC.cuadros.length; const k = Math.min(n - 1, Math.floor(t / DT())); const f = Math.min(1, Math.max(0, t / DT() - k));
  return { A: REC.cuadros[k], B: REC.cuadros[Math.min(n - 1, k + 1)], f, n };
}
const ESCALA_HAZ = new THREE.Vector3();
function dibujar(tReal) {
  const c = cuadroActual(); if (!c) return;
  const { A, B, f, n } = c;
  for (const fl of Object.values(flota)) fl.n = 0;
  let nh = 0;
  for (const v of A.v) {
    const [id, cod, x, y, ang] = v; const w = B.vm.get(id) || v;
    const xi = x + (w[2] - x) * f, yi = y + (w[3] - y) * f, ai = interpAng(ang, w[4], f);
    Q.setFromAxisAngle(EJE_Y, -ai * Math.PI / 180); V3.set(xi, 0, -yi);
    if (cod === 9) { egoPos.copy(V3); egoAng = ai; egoMalla.position.copy(V3); egoMalla.quaternion.copy(Q); continue; }
    let info = infoVeh.get(id);
    if (!info) { const clave = elegirModelo(cod, id, estratoEn(x, y)); info = { clave, color: new THREE.Color(colorModelo(clave, id)) }; infoVeh.set(id, info); }
    const fl = flota[info.clave]; if (!fl || fl.n >= fl.def.max) continue;
    M4.compose(V3, Q, UNO); fl.im.setMatrixAt(fl.n, M4); fl.im.setColorAt(fl.n, info.color); fl.n++;
    if (haces.visible && nh < 1500) { ESCALA_HAZ.set(fl.W * 2.4, 1, 14); M4.compose(V3.setY(0.11), Q, ESCALA_HAZ); haces.setMatrixAt(nh++, M4); }
  }
  for (const fl of Object.values(flota)) { fl.im.count = fl.n; fl.im.instanceMatrix.needsUpdate = true; fl.im.instanceColor.needsUpdate = true; }
  if (haces.visible) { ESCALA_HAZ.set(4.5, 1, 22); M4.compose(V3.copy(egoPos).setY(0.11), egoMalla.quaternion, ESCALA_HAZ); haces.setMatrixAt(nh++, M4); }
  haces.count = nh; haces.instanceMatrix.needsUpdate = true;
  // personas que caminan (SUMO) y gente quieta en puestos y plazas
  let np = 0;
  for (const p of A.p) { const [id, x, y, ang] = p; const w = B.pm.get(id) || p;
    const xi = x + (w[1] - x) * f, yi = y + (w[2] - y) * f; const camina = Math.hypot(w[1] - x, w[2] - y) > 0.05;
    ponerPersona(np, xi, yi, interpAng(ang, w[3], f), id * 7.31, camina, tReal); if (++np >= MAXP - 400) break; }
  for (const [x, y, r, s] of personasEstaticas) {
    if (np >= MAXP) break; if (Math.abs(x - egoPos.x) > 420 || Math.abs(-y - egoPos.z) > 420) continue;
    ponerPersona(np++, x, y, r, s, false, tReal);
  }
  cerrarPersonas(np);
  // imprevistos
  const vivos = new Set();
  for (const o of A.o) { const [id, tipo, x, y, rumbo] = o; const w = B.om.get(id) || o; vivos.add(id);
    let m = objetos.get(id);
    if (!m) { m = tipo === 'conos' ? figuraConos() : new THREE.Mesh((FIGURAS[tipo] || FIGURAS.peaton)(), matFigura); m.castShadow = true; scene.add(m); objetos.set(id, m);
      const s = etiqueta((ICONO[tipo] || '•') + ' ' + tipo, '#fff', 'rgba(120,20,40,.75)', 24); s.userData.base = 0.016; s.position.y = 4; m.add(s); }
    m.position.set(x + (w[2] - x) * f, 0.12, -(y + (w[3] - y) * f)); m.rotation.y = rumbo - Math.PI / 2; }
  for (const [id, m] of objetos) if (!vivos.has(id)) { scene.remove(m); objetos.delete(id); }
  // semáforos: se enciende la luz que corresponde (roja arriba, amarilla al medio, verde abajo)
  if (semaforo.lamparas && A.s && semaforo.ultimo !== A) {
    semaforo.ultimo = A; const off = new THREE.Vector3();
    CIUDAD.semaforos.forEach(([tls, idx], i) => { const st = A.s[tls]; const ch = st ? st[idx] : 'o'; const b = semaforo.base[i];
      const dy = ch === 'r' || ch === 'R' ? 0.4 : ch === 'y' || ch === 'Y' ? 0 : ch === 'g' || ch === 'G' ? -0.4 : 0;
      off.set(0, dy, 0.2).applyQuaternion(b.rot).add(b.centro); M4.compose(off, b.rot, UNO); semaforo.lamparas.setMatrixAt(i, M4);
      colTmp.setHex(ch === 'r' || ch === 'R' ? 0xff1a1a : ch === 'y' || ch === 'Y' ? 0xffb000 : ch === 'g' || ch === 'G' ? 0x18e070 : 0x222222).multiplyScalar(ch === 'o' ? 1 : 3);
      semaforo.lamparas.setColorAt(i, colTmp); });
    semaforo.lamparas.instanceMatrix.needsUpdate = true; semaforo.lamparas.instanceColor.needsUpdate = true;
  }
  anillo.position.set(egoPos.x, 0.2, egoPos.z); egoEtiqueta.position.set(egoPos.x, 6, egoPos.z);
  const e = A.ego;
  egoFreno = lerp(egoFreno, e.a < -0.6 ? 1 : 0, 0.2);
  if (e.alcance && Math.abs(e.alcance - alcanceActual) > 2) { alcanceActual = e.alcance; sensor.geometry.dispose();
    sensor.geometry = new THREE.CircleGeometry(alcanceActual, 40, Math.PI / 2 - Math.PI / 3, (2 * Math.PI) / 3); }
  sensor.position.set(egoPos.x, 0.25, egoPos.z); sensor.rotation.z = -egoAng * Math.PI / 180;
  const lp = [], lc = [];
  if ($('btnSensores').classList.contains('on')) for (const d of e.det) { const [, , , tray, dx, dy] = d;
    lp.push(egoPos.x, 1.2, egoPos.z, dx, 1.0, -dy); const cc = tray ? [1, 0.25, 0.25] : [1, 0.75, 0.2]; lc.push(...cc, ...cc); }
  lineasDet.geometry.setAttribute('position', new THREE.Float32BufferAttribute(lp, 3));
  lineasDet.geometry.setAttribute('color', new THREE.Float32BufferAttribute(lc, 3));
  hud(e, A);
  const dur = n * DT();
  $('reloj').textContent = REC.vivo ? `en vivo · ${t.toFixed(0)} s` : `${t.toFixed(1)} / ${dur.toFixed(0)} s`;
  if (!REC.vivo) $('barra').value = Math.round((t / dur) * 1000);
}

let hudPrev = '', infoInicio = null;
function hud(e, A) {
  const clave = `${e.kmh}|${e.dom}|${e.motivo}|${e.det.length}|${e.r}|${A.h}|${e.adel}`; if (clave === hudPrev) return; hudPrev = clave;
  $('kmh').textContent = Math.round(e.kmh); $('limite').textContent = e.lim;
  $('accion').textContent = `${NOMBRES_ACC[e.acc]} (${e.a >= 0 ? '+' : ''}${e.a.toFixed(1)} m/s²)`;
  const pico = infoInicio?.hora_pico ? ` · <b style="color:var(--rosa)">hora pico ×${infoInicio.factor_demanda}</b>` : '';
  $('ambienteTxt').innerHTML = A.h !== undefined ? `${textoHora(A.h)} · ${e.clima || ''} · sensores ${Math.round(e.alcance || 0)} m${pico}` : '';
  const s = e.senal; const sen = $('senal');
  if (!s) sen.innerHTML = '<span>sin señal<br>próxima</span>';
  else if (s[0] === 'pare') sen.innerHTML = `<div class="pare" style="margin:auto">PARE</div>${s[2].toFixed(0)} m`;
  else { const on = { rojo: 0, amarillo: 1, verde: 2 }[s[1]]; const cols = ['#ff2a2a', '#ffc000', '#29e070'];
    sen.innerHTML = `<div class="semaforo">${[0, 1, 2].map((i) => `<i style="background:${i === on ? cols[i] : '#333'}"></i>`).join('')}</div><div>${s[2].toFixed(0)} m</div>`; }
  for (const el of document.querySelectorAll('.ag')) {
    const ag = el.dataset.ag; const txt = ag === 'percepcion' ? `${e.det.length} objetos` : (e.prop[ag] || '—');
    el.querySelector('span').textContent = txt.length > 46 ? txt.slice(0, 44) + '…' : txt;
    el.classList.toggle('activo', e.dom === ag); el.classList.toggle('alerta', ag === 'seguridad' && e.dom === 'seguridad');
  }
  const inter = e.interv ? ` <b style="color:var(--rojo)">[intervino ${e.interv}]</b>` : '';
  $('motivo').innerHTML = `<b style="color:var(--acento)">Coordinador → ${e.dom}</b>: ${e.motivo || 'vía libre'}${inter}`;
  $('det').innerHTML = e.det.slice(0, 6).map((d) => `<span>${ICONO[d[0]] || '•'}</span><span class="${d[3] ? 'tray' : ''}">${d[0]}${d[3] ? ' · en trayectoria' : ''}</span><span>${d[1].toFixed(0)} m</span><span>${d[2] < 99 ? 'TTC ' + d[2].toFixed(1) + ' s' : ''}</span>`).join('') || '<span></span><span style="color:var(--suave)">nada en el alcance</span>';
  $('mChoques').textContent = e.choques; $('mCasi').textContent = e.casi; $('mBruscas').textContent = e.bruscas; $('mAdel').textContent = e.adel ?? 0; $('mR').textContent = e.r.toFixed(0);
}

// ================================================================ ruta (como un GPS) y marcadores
let rutaMalla = null; const texRuta = lienzoTextura(64, 16, (g) => { g.fillStyle = 'rgba(80,200,255,.85)'; g.fillRect(0, 0, 64, 16); g.fillStyle = 'rgba(255,255,255,.95)'; g.beginPath(); g.moveTo(20, 2); g.lineTo(36, 8); g.lineTo(20, 14); g.fill(); });
texRuta.wrapS = THREE.RepeatWrapping;
function dibujarRuta(camino) {
  if (rutaMalla) { scene.remove(rutaMalla); rutaMalla.geometry.dispose(); rutaMalla = null; }
  if (!camino || camino.length < 4) return;
  const pos = [], idx = [], uv = []; tira(pos, idx, camino, 1.6, 0.2, uv, 5);
  rutaMalla = malla(pos, idx, new THREE.MeshBasicMaterial({ map: texRuta, transparent: true, opacity: 0.8, depthWrite: false, side: THREE.DoubleSide, toneMapped: false }), [['uv', uv, 2]]);
  rutaMalla.renderOrder = 2; scene.add(rutaMalla);
}
const marcadores = new Map();
function marcador(clave, x, y, texto, color) {
  quitarMarcador(clave);
  const g = new THREE.Group(); g.position.set(x, 0, -y);
  const haz = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 60, 12, 1, true), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.45, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
  haz.position.y = 30; g.add(haz);
  const s = etiqueta(texto, '#fff', color === 0x3cff8f ? 'rgba(10,90,40,.85)' : color === 0xff5ca8 ? 'rgba(120,20,70,.85)' : 'rgba(20,60,120,.85)', 26);
  s.position.y = 64; s.userData.base = 0.022; g.add(s); scene.add(g); marcadores.set(clave, g);
}
function quitarMarcador(clave) { const g = marcadores.get(clave); if (g) { scene.remove(g); marcadores.delete(clave); } }

// ================================================================ modo en vivo
let LUGARES = [], partidaMapa = null, eligiendo = false; const ordenPaso = [];
async function revisarServidor() {
  try {
    const r = await fetch('api/estado', { cache: 'no-store' }); if (!r.ok) throw new Error();
    const e = await r.json();
    $('tabVivo').disabled = false; $('tabVivo').title = '';
    if (!$('viaVivo').options.length) {
      $('viaVivo').innerHTML = e.vias.map((v) => `<option value="${v.id}">${v.nombre}</option>`).join('');
      $('agenteVivo').innerHTML = e.agentes.map((a) => `<option value="${a.id}">${a.nombre}</option>`).join('');
    }
    if (e.lugares?.length && !LUGARES.length) prepararLugares(e.lugares);
    if (!e.listo) { $('estadoVivo').textContent = e.error ? 'Error: ' + e.error : 'Arrancando SUMO y llenando la ciudad de tráfico (≈ 1 min)…'; setTimeout(revisarServidor, 2500); }
    else if (!fuente) $('estadoVivo').textContent = 'Listo. Elija el recorrido y pulse Conducir.';
    return true;
  } catch { return false; }
}
function prepararLugares(lugares) {
  LUGARES = lugares;
  $('partida').innerHTML = '<option value="__mapa">📍 Elegir en el mapa…</option>' + lugares.map((l) => `<option value="${l.id}">${l.nombre}</option>`).join('');
  $('partida').value = 'buenavista';
  $('destino').innerHTML = '<option value="">Seguir por una vía principal</option>' + lugares.map((l) => `<option value="${l.id}">${l.nombre}</option>`).join('');
  $('pasaPor').innerHTML = lugares.filter((l) => l.monumento).map((l) =>
    `<label class="chip"><input type="checkbox" value="${l.id}"><span>${l.nombre.replace(/ \(.*\)/, '')}${l.rotonda ? ' <em>glorieta</em>' : ''}</span><b></b></label>`).join('');
  for (const ch of $('pasaPor').querySelectorAll('input')) ch.onchange = () => {
    const i = ordenPaso.indexOf(ch.value); if (ch.checked && i < 0) ordenPaso.push(ch.value); if (!ch.checked && i >= 0) ordenPaso.splice(i, 1);
    actualizarMarcadoresRuta(); };
  $('partida').onchange = () => { if ($('partida').value === '__mapa') elegirEnMapa(); else { eligiendo = false; $('pistaMapa').hidden = true; } actualizarMarcadoresRuta(); };
  $('destino').onchange = actualizarMarcadoresRuta;
  actualizarMarcadoresRuta();
}
function lugar(id) { return LUGARES.find((l) => l.id === id); }
function actualizarMarcadoresRuta() {
  for (const k of [...marcadores.keys()]) quitarMarcador(k);
  if ($('tipoRuta').value !== 'medida') return;
  const p = $('partida').value === '__mapa' ? (partidaMapa && { x: partidaMapa[0], y: partidaMapa[1], nombre: 'Partida' }) : lugar($('partida').value);
  if (p) marcador('partida', p.x, p.y, '🏁 ' + (p.nombre || 'Partida').replace(/ \(.*\)/, ''), 0x3cff8f);
  ordenPaso.forEach((id, i) => { const l = lugar(id); if (l) marcador('paso' + i, l.x, l.y, `${i + 1}. ${l.nombre.replace(/ \(.*\)/, '')}`, 0x4fb3ff); });
  const d = lugar($('destino').value); if (d) marcador('destino', d.x, d.y, '🎯 ' + d.nombre.replace(/ \(.*\)/, ''), 0xff5ca8);
  $('pasaPor').querySelectorAll('label').forEach((lb) => { const i = ordenPaso.indexOf(lb.querySelector('input').value); lb.querySelector('b').textContent = i >= 0 ? i + 1 : ''; });
}
function elegirEnMapa() {
  eligiendo = true; $('pistaMapa').hidden = false; $('pistaMapa').textContent = 'Haga clic sobre una vía del mapa para fijar el punto de partida.';
  ponerCamara('mapa');
}
const raycaster = new THREE.Raycaster(), planoSuelo = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0); let abajo = null;
lienzo.addEventListener('pointerdown', (e) => { abajo = [e.clientX, e.clientY]; });
lienzo.addEventListener('pointerup', (e) => {
  if (!eligiendo || !abajo || Math.hypot(e.clientX - abajo[0], e.clientY - abajo[1]) > 6) return;
  raycaster.setFromCamera(new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1), camera);
  const p = new THREE.Vector3(); if (!raycaster.ray.intersectPlane(planoSuelo, p)) return;
  partidaMapa = [p.x, -p.z]; eligiendo = false;
  $('pistaMapa').textContent = `Partida fijada (${Math.round(p.x)}, ${Math.round(-p.z)}). El vehículo saldrá de la vía más cercana.`;
  actualizarMarcadoresRuta();
});
function cambiarModo(vivo) {
  $('tabVivo').classList.toggle('on', vivo); $('tabGrabados').classList.toggle('on', !vivo);
  $('modoVivo').hidden = !vivo; $('modoGrabados').hidden = vivo;
  if (!vivo && REC?.vivo) { detenerVivo(); if ($('recorrido').value) cargarRecorrido($('recorrido').value); }
  actualizarMarcadoresRuta();
}
function iniciarVivo() {
  detenerVivo();
  const q = new URLSearchParams({ via: $('viaVivo').value, agente: $('agenteVivo').value, velocidad: $('velVivo').value,
    guardrail: $('guardVivo').checked ? 1 : 0, hora: $('hora').value, lluvia: $('lluvia').checked ? 1 : 0,
    ciclo: $('ciclo').checked ? 1.5 : 0, duracion: 600 });
  if ($('tipoRuta').value === 'medida') {
    if ($('partida').value === '__mapa') { if (!partidaMapa) { $('estadoVivo').textContent = 'Primero haga clic en el mapa para elegir la partida.'; elegirEnMapa(); return; }
      q.set('partida_x', partidaMapa[0].toFixed(1)); q.set('partida_y', partidaMapa[1].toFixed(1)); }
    else q.set('partida', $('partida').value);
    if (ordenPaso.length) q.set('pasar_por', ordenPaso.join(','));
    if ($('destino').value) q.set('destino', $('destino').value);
  }
  turnoCarga++; $('carga').style.display = 'none';
  const sesion = { vivo: true, dt: 0.5, cuadros: [], episodios: [{}] };
  REC = sesion; t = 0; $('marcas').innerHTML = ''; infoVeh.clear(); posPrevPersona.clear(); infoInicio = null;
  $('sincro').checked = true; $('estadoVivo').textContent = 'Preparando el recorrido (con horas pico la ciudad se reacomoda unos segundos)…';
  $('btnConducir').disabled = true; $('btnDetener').disabled = false;
  if (camModo === 'mapa') ponerCamara('seguir');
  fuente = new EventSource('api/simular?' + q.toString());
  fuente.addEventListener('inicio', (ev) => { const i = JSON.parse(ev.data); infoInicio = i;
    $('subtitulo').textContent = `En vivo · ${i.ruta}`;
    $('estadoVivo').innerHTML = `Conduciendo: ${i.ruta} (${(i.largo_ruta_m / 1000).toFixed(1)} km)${i.hora_pico ? ' · <b style="color:var(--rosa)">hora pico</b>' : ''}`;
    nombreEgo(i.agente === 'reglas' ? 'Porsche 911 GT · conductor de reglas' : 'Porsche 911 GT · instructor'); dibujarRuta(i.camino); });
  fuente.addEventListener('cuadro', (ev) => { sesion.cuadros.push(indexar(JSON.parse(ev.data))); });
  fuente.addEventListener('fin', (ev) => { const m = JSON.parse(ev.data);
    $('estadoVivo').textContent = `Terminó: ${m.llego ? 'llegó al destino' : m.choques ? 'choque' : 'fin del tiempo'} · ${m.vel_media_kmh} km/h · ${m.adelantamientos ?? 0} adelantamientos · ${m.casi_choques} casi-choques`; });
  fuente.addEventListener('error', (ev) => { if (ev.data) { try { $('estadoVivo').textContent = 'Error: ' + JSON.parse(ev.data).mensaje; } catch { /* */ } } if (fuente && fuente.readyState === 2) terminarVivo(); });
  fuente.addEventListener('cerrar', terminarVivo);
}
function terminarVivo() { if (fuente) { fuente.close(); fuente = null; } $('btnConducir').disabled = false; $('btnDetener').disabled = true; }
function detenerVivo() { if (fuente) { fetch('api/detener').catch(() => {}); terminarVivo(); $('estadoVivo').textContent = 'Detenido.'; } }

// ================================================================ cámara
const camObj = new THREE.Vector3(), camMira = new THREE.Vector3();
function orbitar(h, radio, alto, vel = 0.00003) {
  const a = performance.now() * vel; camObj.set(h.x + radio * Math.cos(a), alto, -(h.y + radio * Math.sin(a))); camMira.set(h.x, alto * 0.25, -h.y);
}
function ponerCamara(modo) {
  camModo = modo; controls.enabled = modo === 'libre' || modo === 'mapa';
  document.querySelectorAll('[data-cam]').forEach((x) => x.classList.toggle('on', x.dataset.cam === modo));
  if (modo === 'mapa') { const [x0, y0, x1, y1] = CIUDAD.limites; const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    camera.position.set(cx, 3200, -cy + 900); controls.target.set(cx, 0, -cy); camera.lookAt(controls.target); }
}
function actualizarCamara(dt) {
  if (camModo === 'libre' || camModo === 'mapa') { controls.update(); return; }
  const a = egoAng * Math.PI / 180; const fx = Math.sin(a), fz = -Math.cos(a);
  if (camModo === 'seguir') { camObj.set(egoPos.x - fx * 20, 8.5, egoPos.z - fz * 20); camMira.set(egoPos.x + fx * 25, 1.5, egoPos.z + fz * 25); }
  else if (camModo === 'cabina') { camObj.set(egoPos.x + fx * 2.3, 1.12, egoPos.z + fz * 2.3); camMira.set(egoPos.x + fx * 40, 1.0, egoPos.z + fz * 40);
    camera.position.copy(camObj); controls.target.copy(camMira); camera.lookAt(camMira); return; }
  else if (camModo === 'cenital') { camObj.set(egoPos.x, 240, egoPos.z + 45); camMira.copy(egoPos); }
  else if (camModo === 'malecon') orbitar(HITOS.luna || { x: 0, y: 0 }, 330, 110);
  else if (camModo === 'buenavista') orbitar(HITOS.bv1 || { x: 0, y: 0 }, 230, 75, 0.00004);
  else if (camModo === 'ventana') orbitar(HITOS.ventana_mundo || { x: 0, y: 0 }, 120, 45, 0.00005);
  else if (camModo === 'aleta') orbitar(HITOS.ventana_campeones || { x: 0, y: 0 }, 110, 40, 0.00005);
  const k = 1 - Math.pow(0.02, dt); camera.position.lerp(camObj, k); controls.target.lerp(camMira, k); camera.lookAt(controls.target);
}

// ================================================================ eventos de la interfaz
$('play').onclick = () => { jugando = !jugando; $('play').textContent = jugando ? '⏸' : '▶'; };
$('velocidad').onchange = (e) => { velRep = Number(e.target.value); };
$('barra').oninput = (e) => { if (REC && !REC.vivo) t = (Number(e.target.value) / 1000) * REC.cuadros.length * DT(); };
for (const b of document.querySelectorAll('[data-cam]')) b.onclick = () => ponerCamara(b.dataset.cam);
$('btnSensores').onclick = (e) => { e.target.classList.toggle('on'); sensor.visible = e.target.classList.contains('on'); };
$('btnEtiquetas').onclick = (e) => { e.target.classList.toggle('on'); etiquetas.visible = e.target.classList.contains('on'); };
$('hora').oninput = () => { $('sincro').checked = false; horaVisual = Number($('hora').value); };
$('lluvia').onchange = () => { $('sincro').checked = false; lluviaVisual = $('lluvia').checked; };
$('ciclo').onchange = () => { if ($('ciclo').checked) $('sincro').checked = false; };
$('tabGrabados').onclick = () => cambiarModo(false);
$('tabVivo').onclick = () => { if (!$('tabVivo').disabled) cambiarModo(true); };
$('tipoRuta').onchange = () => { const m = $('tipoRuta').value === 'medida'; $('cfgVia').hidden = m; $('cfgMedida').hidden = !m; actualizarMarcadoresRuta(); };
$('btnConducir').onclick = iniciarVivo;
$('btnDetener').onclick = detenerVivo;
$('calidad').onchange = (e) => { calidadAuto = false; pref.guardar('calidad', e.target.value); aplicarCalidad(e.target.value); };
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight); });
function alternarPaneles() {  // para presentar: deja solo la escena (H o Esc los vuelve a mostrar)
  const ocultar = !document.body.classList.contains('sin-paneles');
  document.body.classList.toggle('sin-paneles', ocultar);
  for (const p of document.querySelectorAll('.panel')) p.style.display = ocultar ? 'none' : '';
}
$('btnPaneles').onclick = alternarPaneles;
addEventListener('keydown', (e) => {
  if (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT' && e.target.type !== 'checkbox' && e.target.type !== 'range') return;
  if (e.code === 'Space') { e.preventDefault(); $('play').click(); }
  else if (e.code === 'KeyH' || (e.code === 'Escape' && document.body.classList.contains('sin-paneles'))) alternarPaneles();
  else if (e.code === 'KeyC') ponerCamara(camModo === 'cabina' ? 'seguir' : 'cabina');
});

// ================================================================ bucle
const reloj = new THREE.Clock(); let tGlobal = 0, fpsAcum = 0, fpsN = 0, fpsDesde = 0;
function bucle() {
  const dt = Math.min(0.1, reloj.getDelta()); tGlobal += dt;
  if (REC && jugando) {
    t += dt * (REC.vivo ? 1 : velRep);
    const n = REC.cuadros.length, dur = n * DT();
    if (REC.vivo) { const max = Math.max(0, (n - 1.2) * DT()); if (t > max) t = max; if (max - t > 3) t = max - 0.5; }
    else if (t >= dur - DT()) t = 0;
  }
  // ambiente: la hora sale de la simulación o del panel (con ciclo opcional, 1 día ≈ 4 min)
  const c = cuadroActual();
  if ($('sincro').checked && c && c.A.h !== undefined) { horaVisual = c.A.h + ((c.B.h ?? c.A.h) - c.A.h + (c.B.h < c.A.h ? 24 : 0)) * c.f; lluviaVisual = !!c.A.ll; }
  else if ($('ciclo').checked) horaVisual = (horaVisual + dt * 0.1) % 24;
  if (document.activeElement !== $('hora')) $('hora').value = horaVisual.toFixed(2);
  $('lluvia').checked = lluviaVisual; $('horaTxt').textContent = textoHora(horaVisual);
  const osc = aplicarAmbiente(horaVisual, lluviaVisual, tGlobal);
  if (aguaMat) aguaMat.uniforms.t.value += dt;
  if (gotas.visible) gotas.position.set(camera.position.x, camera.position.y - 70 - ((tGlobal * 120) % 40), camera.position.z);
  for (const f of animados) f(tGlobal, osc);
  dibujarPantallas(tGlobal, horaVisual, osc);
  egoMalla.material[3].color.multiplyScalar(1 + egoFreno * 0.6);
  texRuta.offset.x = -tGlobal * 0.8;
  dibujar(tGlobal); actualizarCamara(dt);
  cielo.position.copy(camera.position); estrellas.position.copy(camera.position);
  for (const s of [...etiquetas.children, egoEtiqueta, ...[...objetos.values(), ...marcadores.values()].flatMap((m) => m.children.filter((x) => x.isSprite))]) {
    const p = s.getWorldPosition(V3); const d = camera.position.distanceTo(p); const b = s.userData.base || 0.02;
    s.scale.set(d * b * s.userData.aspecto, d * b, 1); if (s.parent && s.parent !== scene && s.parent !== etiquetas) s.scale.divide(s.parent.scale);
  }
  composer.render();
  // calidad automática: si en los primeros segundos va lento, se baja un nivel
  fpsAcum += dt; fpsN++;
  if (!calidadAuto && fpsAcum > 2) { $('fps').textContent = `${Math.round(fpsN / fpsAcum)} fps`; fpsAcum = 0; fpsN = 0; }
  if (calidadAuto && tGlobal > 3) {
    if (fpsAcum > 4) { const fps = fpsN / fpsAcum; fpsAcum = 0; fpsN = 0; fpsDesde++;
      $('fps').textContent = `${Math.round(fps)} fps`;
      if (fps < (calidad === 'alta' ? 20 : 14) && calidad !== 'baja') aplicarCalidad(calidad === 'alta' ? 'media' : 'baja');
      if (fpsDesde > 3) calidadAuto = false; } }
  requestAnimationFrame(bucle);
}

// ================================================================ inicio
(async () => {
  try {
    aplicarCalidad(calidad);
    await cargarCiudad();
    let lista = [];
    try { lista = await (await fetch('datos/recorridos.json')).json(); } catch { lista = []; }
    const sel = $('recorrido');
    sel.innerHTML = lista.map((r) => `<option value="${r.archivo}">${r.via.length > 48 ? r.via.slice(0, 46) + '…' : r.via} · ${textoHora(r.hora)}${r.lluvia ? ' · lluvia' : ''} · ${Math.round(r.duracion_s)}s</option>`).join('') || '<option value="">(sin recorridos)</option>';
    sel.onchange = () => cargarRecorrido(sel.value);
    const hayServidor = await revisarServidor();
    if (lista.length) await cargarRecorrido(lista[0].archivo); else { $('carga').style.display = 'none'; camModo = 'malecon'; }
    if (hayServidor && !lista.length) cambiarModo(true);
    bucle();
  } catch (err) { carga('Error: ' + err.message + ' — sirva la carpeta con: python -m bq_sim vivo  (o python -m http.server -d visor 8000)'); console.error(err); }
})();

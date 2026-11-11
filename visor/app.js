// Visor 3D de Barranquilla (Gran Malecón, Vía 40, Buenavista) para la simulación multiagente.
// Coordenadas: SUMO (x este, y norte, metros) -> Three.js (x, altura, -y).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = (id) => document.getElementById(id);
const carga = (t) => { $('cargaTxt').textContent = t; };
const lerp = (a, b, f) => a + (b - a) * f;
const suave = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// ================================================================ escena
const lienzo = $('lienzo');
const renderer = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0xe9c9a3, 700, 3600);
const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 1, 9000);
camera.position.set(0, 400, 600);
const controls = new OrbitControls(camera, lienzo);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.495;
controls.enabled = false;
window.__visor = { scene, camera, controls, THREE };

const hemi = new THREE.HemisphereLight(0xcfe6ff, 0x5b4c3c, 0.9);
const sol = new THREE.DirectionalLight(0xffe2b8, 1.6);
const luna = new THREE.DirectionalLight(0x9fb6ff, 0.0);
scene.add(hemi, sol, sol.target, luna, luna.target);

// ================================================================ cielo
// Paleta por hora: [hora, cénit, medio, horizonte]. El atardecer barranquillero
// (17:30-18:30) pasa por el rosado y el lila sobre un azul profundo.
const CIELO = [
  [0.0, '#03060f', '#07102a', '#101a38'],
  [4.6, '#040a1c', '#0d1838', '#1e2448'],
  [5.4, '#14214a', '#3d3a6e', '#b0607a'],
  [6.0, '#2c4f92', '#8a86b8', '#ffae7a'],
  [6.8, '#3a74c4', '#8ab8e6', '#ffd8b0'],
  [9.0, '#2e6fca', '#7fb3ea', '#cfe6fb'],
  [15.5, '#2f6dc6', '#80b2e6', '#d6e9f8'],
  [16.8, '#3567b8', '#8eaede', '#ffe2b8'],
  [17.4, '#3a5cae', '#a796d4', '#ffbfa8'],
  [17.85, '#33519f', '#c58fcf', '#ff9cc6'],
  [18.3, '#283f86', '#9b74bf', '#f48fb8'],
  [18.75, '#18265c', '#4b3c80', '#a05a8e'],
  [19.3, '#0a1230', '#18204a', '#2c2450'],
  [20.0, '#05091a', '#0a1330', '#141c3a'],
  [24.0, '#03060f', '#07102a', '#101a38'],
].map(([h, ...c]) => [h, ...c.map((x) => new THREE.Color().setStyle(x, THREE.LinearSRGBColorSpace))]);

function luminosidad(h) {  // igual que config.luminosidad en Python
  h = ((h % 24) + 24) % 24;
  const rampa = (x, a, b) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return 0.5 - 0.5 * Math.cos(Math.PI * t); };
  return rampa(h, 5.33, 6.67) * (1 - rampa(h, 17.5, 18.83));
}
function paletaCielo(h, lluvia) {
  h = ((h % 24) + 24) % 24;
  let i = 0; while (i < CIELO.length - 2 && CIELO[i + 1][0] <= h) i++;
  const [h0, a0, b0, c0] = CIELO[i], [h1, a1, b1, c1] = CIELO[i + 1];
  const f = (h - h0) / (h1 - h0 || 1);
  const out = [a0.clone().lerp(a1, f), b0.clone().lerp(b1, f), c0.clone().lerp(c1, f)];
  if (lluvia) {
    const gris = new THREE.Color(0.42, 0.45, 0.49).multiplyScalar(0.25 + 0.75 * luminosidad(h));
    out.forEach((c) => c.lerp(gris, 0.7));
  }
  return out;
}
const cieloMat = new THREE.ShaderMaterial({
  uniforms: {
    cenit: { value: new THREE.Color() }, medio: { value: new THREE.Color() }, horizonte: { value: new THREE.Color() },
    solDir: { value: new THREE.Vector3(0, 1, 0) }, lunaDir: { value: new THREE.Vector3(0, -1, 0) },
    solColor: { value: new THREE.Color(1, 0.9, 0.7) }, lluvia: { value: 0 }, oscuridad: { value: 0 },
  },
  vertexShader: 'varying vec3 vDir; void main(){ vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
  fragmentShader: `uniform vec3 cenit, medio, horizonte, solDir, lunaDir, solColor; uniform float lluvia, oscuridad; varying vec3 vDir;
    void main(){
      vec3 d = normalize(vDir); float e = d.y;
      vec3 c = e > 0.0 ? mix(mix(horizonte, medio, smoothstep(0.0, 0.2, e)), cenit, smoothstep(0.2, 0.8, e)) : horizonte * (1.0 + e * 1.6);
      float s = max(dot(d, normalize(solDir)), 0.0);
      c += solColor * (pow(s, 900.0) * 3.0 + pow(s, 10.0) * 0.30) * (1.0 - lluvia * 0.85);
      float m = max(dot(d, normalize(lunaDir)), 0.0);
      c += vec3(0.9, 0.93, 1.0) * (pow(m, 3000.0) * 2.5 + pow(m, 60.0) * 0.06) * oscuridad * (1.0 - lluvia);
      gl_FragColor = vec4(c, 1.0);
    }`,
  side: THREE.BackSide, depthWrite: false, fog: false,
});
const cielo = new THREE.Mesh(new THREE.SphereGeometry(4200, 48, 24), cieloMat);
cielo.renderOrder = -2; cielo.frustumCulled = false;
scene.add(cielo);
const estrellas = (() => {
  const n = 1800, p = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const u = Math.random() * Math.PI * 2, v = Math.acos(Math.random() * 0.95);
    p.set([4000 * Math.sin(v) * Math.cos(u), 4000 * Math.cos(v), 4000 * Math.sin(v) * Math.sin(u)], i * 3);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  const m = new THREE.Points(g, new THREE.PointsMaterial({ color: 0xffffff, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0, fog: false, depthWrite: false }));
  m.renderOrder = -1; m.frustumCulled = false; scene.add(m); return m;
})();

// ================================================================ utilidades
function tira(pos, idx, pts, w, y) {
  const n = pts.length / 2; if (n < 2) return;
  const base = pos.length / 3;
  for (let i = 0; i < n; i++) {
    const a = Math.max(i - 1, 0), b = Math.min(i + 1, n - 1);
    let tx = pts[2 * b] - pts[2 * a], ty = pts[2 * b + 1] - pts[2 * a + 1];
    const L = Math.hypot(tx, ty) || 1; tx /= L; ty /= L;
    const nx = -ty * w / 2, ny = tx * w / 2, x = pts[2 * i], yy = pts[2 * i + 1];
    pos.push(x + nx, y, -(yy + ny), x - nx, y, -(yy - ny));
  }
  for (let i = 0; i < n - 1; i++) { const k = base + 2 * i; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
}
function puntos2(plano) { const c = []; for (let i = 0; i < plano.length; i += 2) c.push(new THREE.Vector2(plano[i], plano[i + 1])); return c; }
function poligono(pos, idx, plano, y) {
  const c = puntos2(plano); if (c.length < 3) return;
  const tri = THREE.ShapeUtils.triangulateShape(c, []);
  const base = pos.length / 3;
  for (const p of c) pos.push(p.x, y, -p.y);
  for (const t of tri) idx.push(base + t[0], base + t[1], base + t[2]);
}
function malla(pos, idx, mat, extra) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  if (extra) for (const [k, v, n] of extra) g.setAttribute(k, new THREE.Float32BufferAttribute(v, n));
  g.setIndex(idx); g.computeVertexNormals();
  const m = new THREE.Mesh(g, mat); m.matrixAutoUpdate = false; return m;
}
// extruye un polígono (paredes + techo) en una sola geometría con UV para texturas de fachada
function extruir(plano, h, y0 = 0) {
  const pos = [], idx = [], uv = [];
  const n = plano.length / 2; let u = 0;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n, ax = plano[2 * i], ay = plano[2 * i + 1], bx = plano[2 * j], by = plano[2 * j + 1];
    const L = Math.hypot(bx - ax, by - ay), b0 = pos.length / 3;
    pos.push(ax, y0, -ay, bx, y0, -by, bx, y0 + h, -by, ax, y0 + h, -ay);
    uv.push(u / 4, 0, (u + L) / 4, 0, (u + L) / 4, h / 3.2, u / 4, h / 3.2);
    idx.push(b0, b0 + 1, b0 + 2, b0, b0 + 2, b0 + 3); u += L;
  }
  const paredes = new THREE.BufferGeometry();
  paredes.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  paredes.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  paredes.setIndex(idx); paredes.computeVertexNormals();
  const pr = [], ir = []; poligono(pr, ir, plano, y0 + h);
  const techo = new THREE.BufferGeometry(); techo.setAttribute('position', new THREE.Float32BufferAttribute(pr, 3));
  techo.setIndex(ir); techo.computeVertexNormals();
  return { paredes, techo };
}
function lienzoTextura(w, h, dibujar) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h; dibujar(cv.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
function texturaVentanas(encendidas) {
  const t = lienzoTextura(128, 128, (g) => {
    g.fillStyle = encendidas ? '#000' : '#fff'; g.fillRect(0, 0, 128, 128);
    for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) {
      g.fillStyle = encendidas ? (Math.random() < 0.6 ? '#ffd58a' : '#141414') : '#8fa7b8';
      g.fillRect(14 + i * 64, 18 + j * 64, 36, 30);
    }
  });
  t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}
function etiqueta(texto, color = '#fff', fondo = 'rgba(10,16,24,.72)', tam = 30) {
  const cv = document.createElement('canvas'); const g = cv.getContext('2d');
  g.font = `600 ${tam}px Segoe UI, sans-serif`;
  const w = Math.ceil(g.measureText(texto).width) + 24; cv.width = w; cv.height = tam + 18;
  g.font = `600 ${tam}px Segoe UI, sans-serif`;
  g.fillStyle = fondo; g.beginPath(); g.roundRect(0, 0, w, tam + 18, 10); g.fill();
  g.fillStyle = color; g.textBaseline = 'middle'; g.fillText(texto, 12, (tam + 18) / 2 + 1);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthTest: false, transparent: true, fog: false }));
  s.userData.aspecto = w / (tam + 18); s.renderOrder = 10; return s;
}
function mergeGeoms(gs) {
  const pos = [], idx = []; let off = 0;
  for (const g of gs) { const p = g.attributes.position.array;
    for (let i = 0; i < p.length; i++) pos.push(p[i]);
    if (g.index) for (const v of g.index.array) idx.push(v + off); else for (let i = 0; i < p.length / 3; i++) idx.push(i + off);
    off += p.length / 3; }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  g.computeVertexNormals(); return g;
}
function caja(w, h, l, x, y, z, color) { const g = new THREE.BoxGeometry(w, h, l); g.translate(x, y, z);
  const c = new THREE.Color(color); const n = g.attributes.position.count; const col = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { col[3 * i] = c.r; col[3 * i + 1] = c.g; col[3 * i + 2] = c.b; }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3)); return g; }
function unir(partes) {
  const pos = [], col = [], idx = []; let off = 0;
  for (const g of partes) { const ng = g.index ? g.toNonIndexed() : g; const p = ng.attributes.position.array, c = ng.attributes.color.array;
    for (let i = 0; i < p.length; i++) { pos.push(p[i]); col.push(c[i]); }
    for (let i = 0; i < p.length / 3; i++) idx.push(off + i); off += p.length / 3; }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); g.setIndex(idx); g.computeVertexNormals(); return g; }

// ================================================================ ciudad
const ciudadGrupo = new THREE.Group(); scene.add(ciudadGrupo);
const etiquetas = new THREE.Group(); scene.add(etiquetas);
const animados = [];          // funciones (t, oscuridad) que se llaman cada cuadro
let matVentanas, aguaMat, CIUDAD, semaforoLamparas, bulbosMat, halos, HITOS = {};

async function cargarCiudad() {
  carga('Descargando la red vial y los edificios…');
  CIUDAD = await (await fetch('datos/ciudad.json')).json();
  carga('Construyendo vías, edificios, el río y el Malecón…');
  await new Promise((r) => setTimeout(r, 20));
  const [x0, y0, x1, y1] = CIUDAD.limites;
  const suelo = new THREE.Mesh(new THREE.PlaneGeometry(12000, 12000), new THREE.MeshLambertMaterial({ color: 0xb2a98f }));
  suelo.rotation.x = -Math.PI / 2; suelo.position.set((x0 + x1) / 2, -0.05, -(y0 + y1) / 2);
  ciudadGrupo.add(suelo);
  // río Magdalena
  aguaMat = new THREE.ShaderMaterial({
    uniforms: { t: { value: 0 }, cielo: { value: new THREE.Color() }, base: { value: new THREE.Color(0.30, 0.42, 0.43) }, luz: { value: 1 } },
    vertexShader: 'varying vec3 vP; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vP = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }',
    fragmentShader: `uniform float t, luz; uniform vec3 cielo; uniform vec3 base; varying vec3 vP;
      void main(){ float o = sin(vP.x*0.045+t*0.9)*0.5 + sin(vP.z*0.06-t*1.3)*0.5 + sin((vP.x+vP.z)*0.11+t*2.1)*0.25;
        vec3 vista = normalize(cameraPosition - vP); float fres = pow(1.0 - max(vista.y,0.0), 3.0);
        vec3 c = mix(base * (0.25 + 0.75*luz), cielo, 0.25 + 0.5*fres) + vec3(0.05)*o*(0.3+0.7*luz);
        gl_FragColor = vec4(c, 1.0); }`,
  });
  { const pos = [], idx = []; for (const p of CIUDAD.agua) poligono(pos, idx, p, 0.0); ciudadGrupo.add(malla(pos, idx, aguaMat)); }
  { const pos = [], idx = []; for (const [, p] of CIUDAD.parques) poligono(pos, idx, p, 0.03);
    ciudadGrupo.add(malla(pos, idx, new THREE.MeshLambertMaterial({ color: 0x6fa35a, side: THREE.DoubleSide }))); }
  // vías, andenes, cebras y líneas
  { const pa = [], ia = [], pb = [], ib = [], pc = [], ic = [], pm = [], im = [];
    for (const p of CIUDAD.cruces) poligono(pa, ia, p, 0.06);
    for (const arista of CIUDAD.carriles) {
      for (const [w, pts] of arista.l) tira(pa, ia, pts, w + 0.05, 0.07);
      if (!arista.interno && arista.l.length > 1) for (let k = 0; k < arista.l.length - 1; k++) {
        const A = arista.l[k][1], B = arista.l[k + 1][1]; if (A.length !== B.length) continue;
        tira(pm, im, A.map((v, i) => (v + B[i]) / 2), 0.15, 0.09);
      }
    }
    for (const [w, pts] of CIUDAD.andenes) tira(pb, ib, pts, w, 0.16);
    for (const [w, pts] of CIUDAD.cebras) tira(pc, ic, pts, w * 0.9, 0.1);
    ciudadGrupo.add(malla(pa, ia, new THREE.MeshLambertMaterial({ color: 0x3b3f45, side: THREE.DoubleSide })));
    ciudadGrupo.add(malla(pb, ib, new THREE.MeshLambertMaterial({ color: 0xc9c4b8, side: THREE.DoubleSide })));
    const cebra = lienzoTextura(16, 64, (g) => { g.fillStyle = '#3b3f45'; g.fillRect(0, 0, 16, 64); g.fillStyle = '#f2f2f2'; g.fillRect(0, 0, 16, 32); });
    cebra.wrapS = cebra.wrapT = THREE.RepeatWrapping; cebra.repeat.set(1, 4);
    ciudadGrupo.add(malla(pc, ic, new THREE.MeshLambertMaterial({ color: 0xffffff, side: THREE.DoubleSide, map: cebra })));
    ciudadGrupo.add(malla(pm, im, new THREE.MeshBasicMaterial({ color: 0xe8e8e8, side: THREE.DoubleSide }))); }
  // edificios: paredes con ventanas (que se encienden de noche) + techos
  { const pos = [], idx = [], uv = [], col = [], pr = [], ir = [], cr = [];
    const paleta = [0xf3efe6, 0xf6e7c8, 0xeed8c4, 0xdce9ef, 0xf1dcd3, 0xe4efe0, 0xfff4d6, 0xd9d4cc].map((c) => new THREE.Color(c));
    let k = 0;
    for (const [h, , p] of CIUDAD.edificios) {
      const n = p.length / 2; const c = paleta[(k++ * 7) % paleta.length]; let u = 0;
      for (let i = 0; i < n; i++) {
        const j = (i + 1) % n, ax = p[2 * i], ay = p[2 * i + 1], bx = p[2 * j], by = p[2 * j + 1];
        const L = Math.hypot(bx - ax, by - ay), b0 = pos.length / 3;
        pos.push(ax, 0, -ay, bx, 0, -by, bx, h, -by, ax, h, -ay);
        uv.push(u / 4, 0, (u + L) / 4, 0, (u + L) / 4, h / 3.2, u / 4, h / 3.2);
        for (let q = 0; q < 4; q++) col.push(c.r, c.g, c.b);
        idx.push(b0, b0 + 1, b0 + 2, b0, b0 + 2, b0 + 3); u += L;
      }
      const b1 = pr.length / 3; poligono(pr, ir, p, h);
      const f = h > 12 ? 0.82 : 0.74; for (let q = b1; q < pr.length / 3; q++) cr.push(c.r * f, c.g * f, c.b * f);
    }
    matVentanas = new THREE.MeshLambertMaterial({ vertexColors: true, map: texturaVentanas(false), side: THREE.DoubleSide,
      emissive: 0xffffff, emissiveMap: texturaVentanas(true), emissiveIntensity: 0 });
    ciudadGrupo.add(malla(pos, idx, matVentanas, [['uv', uv, 2], ['color', col, 3]]));
    ciudadGrupo.add(malla(pr, ir, new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide }), [['color', cr, 3]])); }
  // palmeras
  { const tronco = new THREE.CylinderGeometry(0.16, 0.28, 1, 6); tronco.translate(0, 0.5, 0);
    const hojas = []; for (let i = 0; i < 7; i++) { const h = new THREE.ConeGeometry(0.5, 4.2, 3); h.scale(1, 1, 0.25);
      h.rotateZ(-Math.PI / 2 - 0.35); h.translate(2.0, -0.4, 0); h.rotateY((i / 7) * Math.PI * 2); hojas.push(h); }
    // sin palmeras encima de los monumentos (estatuas, rueda, carrusel, plaza, Caimán)
    const RADIO = { estatua_shakira: 12, estatua_sofia: 12, rueda: 34, carrusel: 11, plaza_luces: 28, caiman: 32, ventana_mundo: 20, ventana_campeones: 25 };
    const libres = (CIUDAD.hitos || []).filter((h) => RADIO[h.tipo]);
    const dentroDe = (p, x, y) => { let c = false; for (let i = 0, j = p.length / 2 - 1; i < p.length / 2; j = i++) {
      const xi = p[2 * i], yi = p[2 * i + 1], xj = p[2 * j], yj = p[2 * j + 1];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
    const conPoligono = (CIUDAD.hitos || []).filter((h) => h.poligono);
    CIUDAD.palmeras = CIUDAD.palmeras.filter(([x, y]) => libres.every((h) => Math.hypot(x - h.x, y - h.y) > RADIO[h.tipo])
      && conPoligono.every((h) => !dentroDe(h.poligono, x, y)));
    const n = CIUDAD.palmeras.length;
    const mt = new THREE.InstancedMesh(tronco, new THREE.MeshLambertMaterial({ color: 0x8b6b4a }), n);
    const mc = new THREE.InstancedMesh(mergeGeoms(hojas), new THREE.MeshLambertMaterial({ color: 0x3f8f3a, side: THREE.DoubleSide }), n);
    const M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    CIUDAD.palmeras.forEach(([x, y, h], i) => {
      M.compose(new THREE.Vector3(x, 0, -y), q.identity(), new THREE.Vector3(1, h, 1)); mt.setMatrixAt(i, M);
      M.compose(new THREE.Vector3(x, h, -y), q.setFromEuler(e.set(0, i * 1.7, 0)), new THREE.Vector3(1, 1, 1)); mc.setMatrixAt(i, M);
    });
    ciudadGrupo.add(mt, mc); }
  // alumbrado público: poste + brazo + bombillo y halo que se encienden al oscurecer
  { const n = CIUDAD.faroles.length;
    const gPoste = new THREE.CylinderGeometry(0.09, 0.13, 9, 5).translate(0, 4.5, 0);
    const gBrazo = new THREE.BoxGeometry(2.4, 0.1, 0.1).translate(1.2, 9, 0);
    const gBulbo = new THREE.BoxGeometry(0.7, 0.18, 0.35).translate(2.3, 8.9, 0);
    const mPoste = new THREE.InstancedMesh(mergeGeoms([gPoste, gBrazo]), new THREE.MeshLambertMaterial({ color: 0x55595e }), n);
    bulbosMat = new THREE.MeshBasicMaterial({ color: 0x777777 });
    const mBulbo = new THREE.InstancedMesh(gBulbo, bulbosMat, n);
    const hp = new Float32Array(n * 3); const M = new THREE.Matrix4(), q = new THREE.Quaternion(), Y = new THREE.Vector3(0, 1, 0);
    CIUDAD.faroles.forEach(([x, y, r], i) => {
      M.compose(new THREE.Vector3(x, 0, -y), q.setFromAxisAngle(Y, r), new THREE.Vector3(1, 1, 1));
      mPoste.setMatrixAt(i, M); mBulbo.setMatrixAt(i, M);
      hp.set([x + Math.cos(r) * 2.3, 8.7, -(y + Math.sin(r) * 2.3)], i * 3);
    });
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(hp, 3));
    const halo = lienzoTextura(64, 64, (c) => { const gr = c.createRadialGradient(32, 32, 0, 32, 32, 32);
      gr.addColorStop(0, 'rgba(255,214,150,1)'); gr.addColorStop(0.35, 'rgba(255,180,90,.45)'); gr.addColorStop(1, 'rgba(255,160,60,0)');
      c.fillStyle = gr; c.fillRect(0, 0, 64, 64); });
    halos = new THREE.Points(g, new THREE.PointsMaterial({ map: halo, size: 9, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, fog: true }));
    ciudadGrupo.add(mPoste, mBulbo, halos); }
  // semáforos
  { const n = CIUDAD.semaforos.length;
    const poste = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.08, 0.1, 4.2, 5).translate(0, 2.1, 0), new THREE.MeshLambertMaterial({ color: 0x2b2f33 }), n);
    semaforoLamparas = new THREE.InstancedMesh(new THREE.SphereGeometry(0.42, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffffff }), n);
    const M = new THREE.Matrix4();
    CIUDAD.semaforos.forEach(([, , x, y], k) => { M.makeTranslation(x, 0, -y); poste.setMatrixAt(k, M);
      M.makeTranslation(x, 4.5, -y); semaforoLamparas.setMatrixAt(k, M); semaforoLamparas.setColorAt(k, new THREE.Color(0x333333)); });
    ciudadGrupo.add(poste, semaforoLamparas); }
  // lugares emblemáticos
  for (const h of CIUDAD.hitos || []) { HITOS[h.id] = h; try { construirHito(h); } catch (err) { console.warn('hito', h.id, err); } }
  // nombres de vías principales y lugares
  { const cuenta = {};
    const principal = /V[ií]a 40|Avenida|Rotonda|Calle (72|76|79|84|98|99)$|Carrera (46|51B|53|54)$/;
    const lugarDestacado = /Malec|Puerta de Oro|Gastron|Ventana|Bosque Urbano/i;
    for (const [tipo, nombre, x, y] of CIUDAD.etiquetas) {
      if (tipo === 'via' && !principal.test(nombre)) continue;
      if (tipo === 'lugar' && !lugarDestacado.test(nombre)) continue;  // sin saturar con cada parque
      cuenta[nombre] = (cuenta[nombre] || 0) + 1; if (cuenta[nombre] > (tipo === 'via' ? 2 : 1)) continue;
      const s = etiqueta(nombre, tipo === 'agua' ? '#bfe6ff' : tipo === 'lugar' ? '#c9f7c1' : '#ffffff', 'rgba(10,16,24,.66)', tipo === 'via' ? 26 : 30);
      s.position.set(x, tipo === 'via' ? 18 : 40, -y); s.userData.base = tipo === 'via' ? 0.022 : 0.026; etiquetas.add(s);
    } }
}

// ================================================================ lugares emblemáticos
const bronce = new THREE.MeshStandardMaterial({ color: 0x9a6a3a, metalness: 0.65, roughness: 0.38 });
const bronceDorado = new THREE.MeshStandardMaterial({ color: 0xb98a46, metalness: 0.7, roughness: 0.32 });
const piedra = new THREE.MeshLambertMaterial({ color: 0xd8d2c4 });
function cil(r1, r2, h, mat, x, y, z) { const m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, h, 14), mat); m.position.set(x, y, z); return m; }
function esf(r, mat, x, y, z, sx = 1, sy = 1, sz = 1) { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), mat); m.position.set(x, y, z); m.scale.set(sx, sy, sz); return m; }
function miembro(mat, a, b, r) {  // cilindro de a a b (Vector3)
  const d = new THREE.Vector3().subVectors(b, a); const m = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.85, r, d.length(), 10), mat);
  m.position.copy(a).addScaledVector(d, 0.5); m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize()); return m;
}
// Figuras estilizadas (no retratos): silueta de bailarina con brazos en alto (Shakira) y figura con vestido saludando (Sofía Vergara)
function figuraEstatua(tipo, alto) {
  const g = new THREE.Group(); const mat = tipo === 'estatua_shakira' ? bronce : bronceDorado; const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const s = alto / 1.75; g.scale.setScalar(s);
  if (tipo === 'estatua_shakira') {
    g.add(miembro(mat, V(-0.11, 0, 0.04), V(-0.08, 0.84, 0), 0.085), miembro(mat, V(0.14, 0, -0.06), V(0.09, 0.84, 0), 0.085));
    g.add(esf(0.2, mat, 0.03, 0.92, 0, 1.15, 0.8, 0.85));                      // cadera ladeada
    const falda = new THREE.Mesh(new THREE.ConeGeometry(0.3, 0.3, 20, 1, true), mat); falda.position.y = 0.86; falda.rotation.z = 0.12; g.add(falda);
    for (let i = 0; i < 10; i++) { const a = (i / 10) * Math.PI * 2;  // flecos de la falda
      g.add(miembro(mat, V(0.27 * Math.cos(a), 0.75, 0.27 * Math.sin(a)), V(0.3 * Math.cos(a), 0.6, 0.3 * Math.sin(a)), 0.02)); }
    g.add(esf(0.15, mat, 0.01, 1.08, 0, 0.9, 1.0, 0.75));                      // cintura
    g.add(esf(0.17, mat, 0.0, 1.3, 0.01, 1.05, 0.95, 0.8));                    // pecho y hombros
    g.add(miembro(mat, V(0, 1.42, 0), V(0, 1.5, 0), 0.05));                    // cuello
    g.add(esf(0.115, mat, -0.01, 1.6, 0.01));                                  // cabeza
    g.add(esf(0.15, mat, -0.01, 1.47, -0.07, 0.95, 1.6, 0.55));                // melena larga
    g.add(miembro(mat, V(-0.17, 1.4, 0), V(-0.24, 1.66, 0.02), 0.055), miembro(mat, V(-0.24, 1.66, 0.02), V(-0.03, 1.86, 0.02), 0.045));
    g.add(miembro(mat, V(0.16, 1.4, 0), V(0.23, 1.66, 0.02), 0.055), miembro(mat, V(0.23, 1.66, 0.02), V(0.01, 1.86, 0.02), 0.045));
  } else {
    g.add(new THREE.Mesh(new THREE.ConeGeometry(0.34, 1.0, 22), mat).translateY(0.5));  // vestido largo
    g.add(esf(0.15, mat, 0, 1.05, 0, 0.95, 0.8, 0.75));
    g.add(esf(0.17, mat, 0, 1.27, 0.01, 1.05, 0.95, 0.8));                     // pecho y hombros
    g.add(miembro(mat, V(0, 1.38, 0), V(0, 1.46, 0), 0.05));
    g.add(esf(0.11, mat, 0, 1.56, 0));
    g.add(esf(0.15, mat, 0, 1.43, -0.07, 1.0, 1.5, 0.55));                     // cabello largo
    g.add(miembro(mat, V(0.16, 1.36, 0), V(0.3, 1.56, 0), 0.055), miembro(mat, V(0.3, 1.56, 0), V(0.33, 1.82, 0.06), 0.045)); // saluda
    g.add(miembro(mat, V(-0.16, 1.36, 0), V(-0.27, 1.13, 0.04), 0.055), miembro(mat, V(-0.27, 1.13, 0.04), V(-0.13, 1.02, 0.08), 0.045)); // mano en la cintura
  }
  return g;
}
function ponerEtiquetaHito(h, alto, color = '#ffe8b0') {
  const s = etiqueta(h.nombre, color, 'rgba(40,20,10,.78)', 28); s.position.set(h.x, alto, -h.y); s.userData.base = 0.024; etiquetas.add(s);
}
function construirHito(h) {
  const grupo = new THREE.Group(); grupo.position.set(h.x, 0, -h.y); scene.add(grupo);
  if (h.tipo === 'estatua_shakira' || h.tipo === 'estatua_sofia') {
    grupo.add(cil(2.4, 2.8, 1.2, piedra, 0, 0.6, 0));
    const f = figuraEstatua(h.tipo, h.altura); f.position.y = 1.2; grupo.add(f);
    grupo.rotation.y = h.rumbo + Math.PI / 2;  // mira hacia la avenida
    ponerEtiquetaHito(h, h.altura + 6);
  } else if (h.tipo === 'rueda') {
    // La Luna del Río: rueda panorámica con luces LED que cambian de color de noche
    const R = 25, cy = 30; grupo.rotation.y = h.rumbo;
    const rueda = new THREE.Group(); rueda.position.y = cy; grupo.add(rueda);
    const ledMat = new THREE.MeshStandardMaterial({ color: 0x8a9099, metalness: 0.6, roughness: 0.3, emissive: 0xffffff, emissiveIntensity: 0, toneMapped: false });
    const acero = new THREE.MeshStandardMaterial({ color: 0xe8edf2, metalness: 0.7, roughness: 0.35 });
    for (const z of [-1.6, 1.6]) { const t = new THREE.Mesh(new THREE.TorusGeometry(R, 0.35, 8, 120), ledMat); t.position.z = z; rueda.add(t);
      for (let i = 0; i < 32; i++) { const a = (i / 32) * Math.PI * 2; rueda.add(miembro(acero, new THREE.Vector3(0, 0, z), new THREE.Vector3(R * Math.cos(a), R * Math.sin(a), z), 0.08)); } }
    rueda.add(cil(1.2, 1.2, 4.2, acero, 0, 0, 0).rotateX(Math.PI / 2));
    for (const [dx, dz] of [[-11, -5], [11, -5], [-11, 5], [11, 5]]) grupo.add(miembro(acero, new THREE.Vector3(dx, 0, dz), new THREE.Vector3(0, cy, Math.sign(dz) * 1.8), 0.45));
    const cabinas = []; const colores = [0xff5a7a, 0x4fb3ff, 0xffd34f, 0x5ee6a0, 0xc58fcf, 0xff9c4a];
    for (let i = 0; i < 24; i++) { const c = new THREE.Mesh(new THREE.CylinderGeometry(1.3, 1.3, 2.2, 12), new THREE.MeshLambertMaterial({ color: colores[i % colores.length] }));
      grupo.add(c); cabinas.push(c); }
    animados.push((t, osc) => {
      const giro = t * 0.025; rueda.rotation.z = giro;
      cabinas.forEach((c, i) => { const a = giro + (i / 24) * Math.PI * 2; c.position.set(R * Math.cos(a), cy + R * Math.sin(a) - 1.6, 0); });
      ledMat.emissive.setHSL((t * 0.05) % 1, 1.0, 0.5); ledMat.emissiveIntensity = 0.1 + 0.9 * osc;
    });
    ponerEtiquetaHito(h, 64);
  } else if (h.tipo === 'carrusel') {
    const c = new THREE.Group(); grupo.add(c);
    c.add(cil(6, 6, 0.6, new THREE.MeshLambertMaterial({ color: 0xfff1d6 }), 0, 0.3, 0));
    const techo = new THREE.Mesh(new THREE.ConeGeometry(6.6, 3, 16), new THREE.MeshLambertMaterial({ color: 0xe0405c })); techo.position.y = 5.5; c.add(techo);
    for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; c.add(cil(0.08, 0.08, 4, new THREE.MeshLambertMaterial({ color: 0xffd34f }), 5 * Math.cos(a), 2.5, 5 * Math.sin(a)));
      c.add(new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.8, 1.2), new THREE.MeshLambertMaterial({ color: [0xffffff, 0x4fb3ff, 0xff9cc6][i % 3] })).translateX(5 * Math.cos(a)).translateY(2 + 0.4 * Math.sin(i)).translateZ(5 * Math.sin(a))); }
    animados.push((t) => { c.rotation.y = t * 0.4; });
  } else if (h.tipo === 'plaza_luces') {
    grupo.position.set(0, 0, 0);
    const pos = [], idx = []; poligono(pos, idx, h.poligono, 0.12);
    grupo.add(malla(pos, idx, new THREE.MeshLambertMaterial({ color: 0xe9e4da, side: THREE.DoubleSide })));
    const pts = puntos2(h.poligono); const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const luces = []; const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const dentro = (x, y) => { let c = false; for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      if ((pts[i].y > y) !== (pts[j].y > y) && x < (pts[j].x - pts[i].x) * (y - pts[i].y) / (pts[j].y - pts[i].y) + pts[i].x) c = !c; } return c; };
    for (let i = 0; i < 120 && luces.length < 40; i++) { const x = lerp(Math.min(...xs), Math.max(...xs), Math.random()), y = lerp(Math.min(...ys), Math.max(...ys), Math.random());
      if (!dentro(x, y)) continue;
      const poste = cil(0.06, 0.06, 5, new THREE.MeshLambertMaterial({ color: 0x777777 }), x, 2.5, -y); grupo.add(poste);
      const b = new THREE.Mesh(new THREE.SphereGeometry(0.35, 8, 6), mat.clone()); b.position.set(x, 5.2, -y); grupo.add(b); luces.push(b); }
    animados.push((t, osc) => luces.forEach((b, i) => b.material.color.setHSL(((t * 0.03) + i * 0.07) % 1, 0.85, 0.35 + 0.35 * osc)));
  } else if (h.tipo === 'caiman') {
    grupo.position.set(0, 0, 0);
    const { paredes, techo } = extruir(h.poligono, h.altura);
    grupo.add(new THREE.Mesh(paredes, new THREE.MeshLambertMaterial({ color: 0xd8b48a, map: texturaVentanas(false), emissive: 0xffc070, emissiveMap: texturaVentanas(true), emissiveIntensity: 0 })));
    grupo.add(new THREE.Mesh(techo, new THREE.MeshLambertMaterial({ color: 0x3e7b45, side: THREE.DoubleSide })));
    const verde = new THREE.MeshLambertMaterial({ color: 0x2f7a3c });
    const caiman = new THREE.Group(); caiman.position.set(h.x, h.altura + 1.2, -h.y); grupo.add(caiman);
    caiman.add(esf(1, verde, 0, 0, 0, 5, 0.9, 1.6), new THREE.Mesh(new THREE.ConeGeometry(1.2, 6, 10), verde).rotateZ(Math.PI / 2).translateY(-7.5));
    caiman.add(new THREE.Mesh(new THREE.BoxGeometry(4, 0.8, 1.6), verde).translateX(6.5).translateY(-0.1));
    for (const [dx, dz] of [[-2.5, 1.5], [2.5, 1.5], [-2.5, -1.5], [2.5, -1.5]]) caiman.add(cil(0.35, 0.3, 1.4, verde, dx, -0.8, dz));
    ponerEtiquetaHito(h, h.altura + 14, '#c9f7c1');
    const mats = grupo.children[0].material; animados.push((t, osc) => { mats.emissiveIntensity = 0.9 * osc; });
  } else if (h.tipo === 'mall') {
    grupo.position.set(0, 0, 0);
    const { paredes, techo } = extruir(h.poligono, h.altura);
    const vidrio = new THREE.MeshLambertMaterial({ color: 0x9fb7c9, map: texturaVentanas(false), emissive: 0xffffff, emissiveMap: texturaVentanas(true), emissiveIntensity: 0 });
    grupo.add(new THREE.Mesh(paredes, vidrio), new THREE.Mesh(techo, new THREE.MeshLambertMaterial({ color: 0xd9dde2, side: THREE.DoubleSide })));
    animados.push((t, osc) => { vidrio.emissiveIntensity = 0.85 * osc; });
    if (h.fachada) pantallas(grupo, h);
    ponerEtiquetaHito(h, h.altura + 10, '#ffffff');
  } else if (h.tipo === 'ventana_mundo') {
    grupo.position.set(0, 0, 0);
    const pts = puntos2(h.poligono); const c = pts.reduce((a, p) => a.add(p), new THREE.Vector2()).multiplyScalar(1 / pts.length);
    let ang = 0, largo = 8; for (let i = 0; i < pts.length; i++) { const d = new THREE.Vector2().subVectors(pts[(i + 1) % pts.length], pts[i]); if (d.length() > largo) { largo = d.length(); ang = Math.atan2(d.y, d.x); } }
    const mosaico = lienzoTextura(64, 256, (g, w, hh) => { for (let y = 0; y < hh; y += 8) for (let x = 0; x < w; x += 8) { g.fillStyle = `hsl(${(Math.random() * 360) | 0},85%,${50 + Math.random() * 15}%)`; g.fillRect(x, y, 8, 8); } });
    const mat = new THREE.MeshLambertMaterial({ map: mosaico, emissive: 0xffffff, emissiveMap: mosaico, emissiveIntensity: 0.05 });
    const w = Math.max(largo, 10), H = h.altura, p = w * 0.32, prof = 4;
    const torre = new THREE.Group(); torre.position.set(c.x, 0, -c.y); torre.rotation.y = ang; grupo.add(torre);
    torre.add(new THREE.Mesh(new THREE.BoxGeometry(p, H, prof), mat).translateX(-(w - p) / 2).translateY(H / 2));
    torre.add(new THREE.Mesh(new THREE.BoxGeometry(p, H, prof), mat).translateX((w - p) / 2).translateY(H / 2));
    torre.add(new THREE.Mesh(new THREE.BoxGeometry(w, H * 0.22, prof), mat).translateY(H * 0.89));
    torre.add(new THREE.Mesh(new THREE.BoxGeometry(w, H * 0.3, prof), mat).translateY(H * 0.15));
    animados.push((t, osc) => { mat.emissiveIntensity = 0.05 + 0.7 * osc; });
    ponerEtiquetaHito(h, H + 10, '#ffffff');
  } else if (h.tipo === 'ventana_campeones') {
    grupo.position.set(0, 0, 0);
    const pts = puntos2(h.poligono); const c = pts.reduce((a, p) => a.add(p), new THREE.Vector2()).multiplyScalar(1 / pts.length);
    const blanco = new THREE.MeshStandardMaterial({ color: 0xf4f4f2, metalness: 0.2, roughness: 0.5 });
    const H = h.altura, arco = new THREE.Group(); arco.position.set(c.x, 0, -c.y); grupo.add(arco);
    arco.add(new THREE.Mesh(new THREE.BoxGeometry(3, H, 3), blanco).translateX(-8).translateY(H / 2).rotateZ(0.12));
    arco.add(new THREE.Mesh(new THREE.BoxGeometry(3, H * 0.85, 3), blanco).translateX(8).translateY(H * 0.42).rotateZ(-0.05));
    arco.add(new THREE.Mesh(new THREE.BoxGeometry(22, 3, 3), blanco).translateY(H - 1).translateX(-2).rotateZ(-0.08));
    ponerEtiquetaHito(h, H + 10, '#ffffff');
  }
}

// ----- pantallas LED tipo Times Square (texto genérico, sin marcas)
const MENSAJES = [
  ['BARRANQUILLA', 'Puerta de Oro de Colombia', ['#ff2d75', '#ffb000']],
  ['¡QUIEN LO VIVE', 'ES QUIEN LO GOZA!', ['#00c2ff', '#7b2bff']],
  ['CARNAVAL', 'Patrimonio de la Humanidad', ['#ffde00', '#ff2d2d']],
  ['__RELOJ__', 'Calle 98 · Buenavista', ['#0f2027', '#2c5364']],
  ['SIMULACIÓN', 'multiagente · SUMO + DQN', ['#11998e', '#38ef7d']],
  ['GRAN MALECÓN', 'del Río Magdalena', ['#f857a6', '#ff5858']],
];
const pantallasActivas = [];
function crearPantalla(ancho, alto, desfase) {
  const cv = document.createElement('canvas'); cv.width = 512; cv.height = Math.round(512 * alto / ancho);
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  const p = { cv, g: cv.getContext('2d'), tex, desfase, ultimo: -1 };
  pantallasActivas.push(p);
  return new THREE.Mesh(new THREE.PlaneGeometry(ancho, alto), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false, fog: false }));
}
function dibujarPantallas(t, hora) {
  for (const p of pantallasActivas) {
    const k = Math.floor((t * 8) % 1e9); if (k === p.ultimo) continue; p.ultimo = k;
    const { g, cv } = p, W = cv.width, H = cv.height;
    const idx = Math.floor((t / 5 + p.desfase)) % MENSAJES.length, [t1, t2, [c1, c2]] = MENSAJES[idx];
    const gr = g.createLinearGradient(0, 0, W, H); gr.addColorStop(0, c1); gr.addColorStop(1, c2); g.fillStyle = gr; g.fillRect(0, 0, W, H);
    g.globalAlpha = 0.25; for (let i = 0; i < 12; i++) { g.fillStyle = i % 2 ? '#fff' : '#000'; g.beginPath(); g.arc((i * 97 + t * 60) % W, (i * 53) % H, 6 + (i % 5) * 4, 0, 7); g.fill(); } g.globalAlpha = 1;
    const hh = Math.floor(hora), mm = Math.floor((hora - hh) * 60);
    const titulo = t1 === '__RELOJ__' ? `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}  31 °C` : t1;
    g.fillStyle = '#fff'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.shadowColor = 'rgba(0,0,0,.5)'; g.shadowBlur = 8;
    g.font = `800 ${Math.round(H * 0.3)}px Segoe UI, sans-serif`; g.fillText(titulo, W / 2, H * 0.42, W * 0.92);
    g.font = `600 ${Math.round(H * 0.12)}px Segoe UI, sans-serif`; g.fillText(t2, W / 2, H * 0.72, W * 0.92);
    g.shadowBlur = 0; g.fillStyle = 'rgba(0,0,0,.55)'; g.fillRect(0, H * 0.86, W, H * 0.14);
    g.fillStyle = '#ffd34f'; g.font = `600 ${Math.round(H * 0.08)}px Segoe UI, sans-serif`; g.textAlign = 'left';
    g.fillText('  BARRANQUILLA · GRAN MALECÓN · VÍA 40 · CALLE 98 · BUENAVISTA · PLAZA DEL PARQUE ·  ', W - ((t * 90) % (W * 2.2)), H * 0.93);
    p.tex.needsUpdate = true;
  }
}
function pantallas(grupo, h) {
  const [x1, y1, x2, y2] = h.fachada; const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy);
  let nx = dy / L, ny = -dx / L;  // normal de la fachada, orientada hacia afuera del edificio
  if (((x1 + x2) / 2 - h.x) * nx + ((y1 + y2) / 2 - h.y) * ny < 0) { nx = -nx; ny = -ny; }
  const grande = h.id === 'bv1';
  const ancho = Math.min(L * 0.85, grande ? 38 : 22), alto = grande ? 14 : 8;
  const pantalla = crearPantalla(ancho, alto, pantallasActivas.length * 2.37 + 0.5);
  pantalla.position.set((x1 + x2) / 2 + nx * 0.6, Math.max(alto / 2 + 3, h.altura * 0.55), -((y1 + y2) / 2 + ny * 0.6));
  pantalla.lookAt(pantalla.position.x + nx, pantalla.position.y, pantalla.position.z - ny);  // la cara (+z) mira afuera
  grupo.add(pantalla);
  if (grande) {  // dos pantallas más, en esquina, al estilo Times Square
    for (const s of [-1, 1]) { const p2 = crearPantalla(12, 18, pantallasActivas.length * 2.37 + 1.3);
      const px = (x1 + x2) / 2 + s * (dx / L) * (ancho / 2 + 7) + nx * 0.6, py = (y1 + y2) / 2 + s * (dy / L) * (ancho / 2 + 7) + ny * 0.6;
      p2.position.set(px, h.altura * 0.6 + 4, -py); p2.lookAt(px + nx, h.altura * 0.6 + 4, -py - ny); grupo.add(p2); }
  }
}

// ================================================================ vehículos y objetos
const VIDRIO = 0x22303c, BLANCO = 0xffffff;
function geomAuto(L, W, H) { return unir([caja(W, H * 0.5, L, 0, 0.45, L / 2, BLANCO), caja(W * 0.86, H * 0.42, L * 0.5, 0, 0.45 + H * 0.46, L * 0.55, VIDRIO),
  caja(0.5, 0.18, 0.06, -W * 0.3, 0.6, -0.01, 0xfff6c0), caja(0.5, 0.18, 0.06, W * 0.3, 0.6, -0.01, 0xfff6c0),
  caja(0.4, 0.16, 0.06, -W * 0.32, 0.62, L + 0.01, 0xd01818), caja(0.4, 0.16, 0.06, W * 0.32, 0.62, L + 0.01, 0xd01818)]); }
const GEOM = [
  geomAuto(4.5, 1.8, 1.45),
  unir([geomAuto(4.3, 1.75, 1.45), caja(0.6, 0.22, 0.25, 0, 1.55, 2.3, 0xffffff)]),
  unir([caja(0.5, 0.8, 2.0, 0, 0.6, 1.0, BLANCO), caja(0.45, 0.75, 0.45, 0, 1.45, 1.2, 0x1e2a5a), caja(0.32, 0.3, 0.32, 0, 2.0, 1.15, 0xdddddd)]),
  unir([caja(2.5, 2.6, 12, 0, 1.55, 6, BLANCO), caja(2.52, 0.9, 11.4, 0, 2.15, 6.1, VIDRIO), caja(2.4, 0.9, 0.05, 0, 2.0, -0.01, VIDRIO)]),
  unir([caja(2.4, 2.4, 2.6, 0, 1.5, 1.3, BLANCO), caja(2.5, 3.0, 6.2, 0, 1.9, 5.8, 0xd8d8d8), caja(2.2, 0.9, 0.05, 0, 2.1, -0.01, VIDRIO)]),
];
const COLORES_AUTO = [0xd9dde3, 0x9aa3ad, 0x2d3640, 0xb81d24, 0x1f4e8c, 0xf2f2f2, 0x5b6770, 0x7a1f1f];
const COLOR_TIPO = [null, 0xffd600, 0x2b2b2b, 0x18a058, 0xc4512f];
const vehMat = new THREE.MeshLambertMaterial({ vertexColors: true });
const flota = GEOM.map((g) => { const m = new THREE.InstancedMesh(g, vehMat, 900); m.count = 0; m.frustumCulled = false; scene.add(m); return m; });
const egoMalla = new THREE.Mesh(geomAuto(4.5, 1.8, 1.45), new THREE.MeshLambertMaterial({ vertexColors: true, color: 0xffb000, emissive: 0x4a2a00 }));
scene.add(egoMalla);
const faros = new THREE.Mesh(new THREE.ConeGeometry(4, 22, 20, 1, true), new THREE.MeshBasicMaterial({ color: 0xfff1c4, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
faros.geometry.rotateX(Math.PI / 2).translate(0, 0.8, -11); egoMalla.add(faros);  // haz de luz hacia adelante
const anillo = new THREE.Mesh(new THREE.RingGeometry(3.2, 3.8, 40), new THREE.MeshBasicMaterial({ color: 0xffb000, transparent: true, opacity: 0.85, side: THREE.DoubleSide }));
anillo.rotation.x = -Math.PI / 2; scene.add(anillo);
let egoEtiqueta = etiqueta('Vehículo instructor', '#ffb000', 'rgba(10,16,24,.8)', 26); egoEtiqueta.userData.base = 0.02; scene.add(egoEtiqueta);
function nombreEgo(texto) {
  scene.remove(egoEtiqueta); egoEtiqueta.material.map.dispose();
  egoEtiqueta = etiqueta(texto, '#ffb000', 'rgba(10,16,24,.8)', 26); egoEtiqueta.userData.base = 0.02; scene.add(egoEtiqueta);
}
const sensorMat = new THREE.MeshBasicMaterial({ color: 0x4fb3ff, transparent: true, opacity: 0.13, side: THREE.DoubleSide, depthWrite: false });
const sensor = new THREE.Mesh(new THREE.CircleGeometry(90, 32, Math.PI / 2 - Math.PI / 3, (2 * Math.PI) / 3), sensorMat);
sensor.rotation.x = -Math.PI / 2; scene.add(sensor);
let alcanceActual = 90;
const lineasDet = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 }));
lineasDet.frustumCulled = false; scene.add(lineasDet);
const geomPersona = unir([caja(0.45, 1.1, 0.3, 0, 0.75, 0, 0x3b5b8c), caja(0.32, 0.32, 0.3, 0, 1.5, 0, 0xc68e62)]);
const personas = new THREE.InstancedMesh(geomPersona, vehMat, 800); personas.count = 0; personas.frustumCulled = false; scene.add(personas);
const FIGURAS = {
  peaton: () => unir([caja(0.5, 1.15, 0.32, 0, 0.78, 0, 0xe04f8a), caja(0.34, 0.34, 0.32, 0, 1.55, 0, 0xc68e62), caja(0.42, 0.7, 0.3, 0, 0.35, 0, 0x2c3e66)]),
  perro: () => unir([caja(0.32, 0.4, 0.9, 0, 0.45, 0.45, 0x8a5a2b), caja(0.28, 0.3, 0.32, 0, 0.72, -0.05, 0x7a4a20), caja(0.08, 0.32, 0.08, 0.1, 0.16, 0.15, 0x6b3f1a), caja(0.08, 0.32, 0.08, -0.1, 0.16, 0.75, 0x6b3f1a)]),
  iguana: () => unir([caja(0.22, 0.14, 0.7, 0, 0.08, 0.35, 0x3fae49), caja(0.12, 0.08, 0.7, 0, 0.05, 1.0, 0x2f8a37), caja(0.16, 0.12, 0.18, 0, 0.1, -0.05, 0x56c35f)]),
};
const objetos = new Map();
function figuraConos() { const g = new THREE.Group(); const cono = new THREE.ConeGeometry(0.28, 0.8, 10).translate(0, 0.4, 0);
  const m1 = new THREE.MeshLambertMaterial({ color: 0xff6a00, emissive: 0x401800 });
  for (let i = 0; i < 6; i++) { const c = new THREE.Mesh(cono, m1); c.position.set(0, 0, i * 2.6); g.add(c); }
  g.add(new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.9, 0.12).translate(0, 0.45, -0.4), new THREE.MeshLambertMaterial({ color: 0xff8c00 }))); return g; }

// ================================================================ lluvia
const gotas = (() => { const n = 5000, p = new Float32Array(n * 6);
  for (let i = 0; i < n; i++) { const x = (Math.random() - 0.5) * 500, y = Math.random() * 140, z = (Math.random() - 0.5) * 500; p.set([x, y, z, x + 0.3, y - 2.2, z], i * 6); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  const l = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0xaac4dd, transparent: true, opacity: 0.45 }));
  l.visible = false; l.frustumCulled = false; scene.add(l); return l; })();

// ================================================================ ambiente (hora, luz, lluvia)
let horaVisual = 17.5, lluviaVisual = false;
const solDir = new THREE.Vector3(), lunaDir = new THREE.Vector3(), tmpC = new THREE.Color();
function aplicarAmbiente(h, lluvia) {
  const L = luminosidad(h), osc = 1 - L;
  const [cen, med, hor] = paletaCielo(h, lluvia);
  cieloMat.uniforms.cenit.value.copy(cen); cieloMat.uniforms.medio.value.copy(med); cieloMat.uniforms.horizonte.value.copy(hor);
  // el sol sale por el río (este) y se pone detrás de la ciudad (oeste); a 11° N pasa algo al sur
  const th = Math.PI * (h - 6.05) / 12.2;
  solDir.set(Math.cos(th), Math.sin(th), 0.22).normalize(); lunaDir.set(-Math.cos(th), -Math.sin(th) * 0.9 + 0.15, 0.3).normalize();
  cieloMat.uniforms.solDir.value.copy(solDir); cieloMat.uniforms.lunaDir.value.copy(lunaDir);
  cieloMat.uniforms.solColor.value.setRGB(1, 0.55 + 0.4 * Math.max(0, solDir.y), 0.35 + 0.5 * Math.max(0, solDir.y));
  cieloMat.uniforms.lluvia.value = lluvia ? 1 : 0; cieloMat.uniforms.oscuridad.value = osc;
  const elev = Math.max(0, solDir.y);
  sol.position.copy(solDir).multiplyScalar(1500).add(controls.target); sol.target.position.copy(controls.target);
  sol.intensity = (lluvia ? 0.45 : 1.75) * L * Math.min(1, elev * 4 + 0.15);
  sol.color.setRGB(1, 0.7 + 0.28 * Math.min(1, elev * 2.5), 0.5 + 0.45 * Math.min(1, elev * 2.5));
  luna.position.copy(lunaDir).multiplyScalar(1500).add(controls.target); luna.target.position.copy(controls.target);
  luna.intensity = 0.32 * osc * (lluvia ? 0.4 : 1);
  hemi.intensity = (lluvia ? 0.55 : 0.8) * (0.2 + 0.8 * L) + 0.12;
  tmpC.setRGB(med.r, med.g, med.b, THREE.SRGBColorSpace); hemi.color.copy(tmpC).lerp(new THREE.Color(0xffffff), 0.35);
  scene.fog.color.setRGB(hor.r, hor.g, hor.b, THREE.SRGBColorSpace);
  scene.fog.near = lluvia ? 250 : 700; scene.fog.far = lluvia ? 1500 : (L < 0.3 ? 2600 : 3800);
  renderer.toneMappingExposure = 1.0 + 0.35 * osc;
  estrellas.material.opacity = Math.max(0, osc - 0.25) * (lluvia ? 0.15 : 1);
  if (matVentanas) matVentanas.emissiveIntensity = 0.95 * suave(0.25, 0.85, osc);
  if (bulbosMat) bulbosMat.color.setRGB(0.45 + 0.55 * suave(0.2, 0.6, osc), 0.45 + 0.4 * suave(0.2, 0.6, osc), 0.45 + 0.15 * suave(0.2, 0.6, osc));
  if (halos) halos.material.opacity = 0.95 * suave(0.25, 0.7, osc);
  if (aguaMat) { aguaMat.uniforms.cielo.value.setRGB(med.r, med.g, med.b); aguaMat.uniforms.luz.value = 0.15 + 0.85 * L; }
  faros.material.opacity = 0.16 * suave(0.3, 0.8, osc);
  gotas.visible = lluvia;
  egoMalla.material.emissive.set(osc > 0.5 ? 0x8a5200 : 0x4a2a00);
  return osc;
}
function textoHora(h) { h = ((h % 24) + 24) % 24; const hh = Math.floor(h), mm = Math.floor((h - hh) * 60); return `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`; }

// ================================================================ reproducción
let REC = null, t = 0, jugando = true, velRep = 1, camModo = 'seguir', fuente = null;
const DT = () => (REC ? REC.dt : 0.5);
const NOMBRES_ACC = ['frenado de emergencia', 'frenado fuerte', 'frenado moderado', 'frenado suave', 'mantener', 'acelerar suave', 'acelerar'];
const ICONO = { auto: '🚗', taxi: '🚕', moto: '🏍️', bus: '🚌', camion: '🚚', peaton: '🚶', perro: '🐕', iguana: '🦎', conos: '🚧' };
const COLOR_EVENTO = { choque: '#ff3b3b', casi_choque: '#ffb000', peaton: '#e04f8a', perro: '#a0703a', iguana: '#3fae49', conos: '#ff6a00', frenada_lider: '#4fb3ff', pare_violado: '#ff3b3b', semaforo_rojo: '#ff3b3b' };
function indexar(c) { c.vm = new Map(c.v.map((v) => [v[0], v])); c.pm = new Map(c.p.map((p) => [p[0], p])); c.om = new Map(c.o.map((o) => [o[0], o])); return c; }

async function cargarRecorrido(archivo) {
  detenerVivo();
  carga('Cargando el recorrido grabado…'); $('carga').style.display = 'grid';
  REC = await (await fetch('datos/' + archivo)).json();
  REC.cuadros.forEach(indexar); t = 0; nombreEgo('Vehículo instructor');
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
function dibujar() {
  const c = cuadroActual(); if (!c) return;
  const { A, B, f, n } = c; const cuentas = [0, 0, 0, 0, 0];
  for (const v of A.v) {
    const [id, cod, x, y, ang] = v; const w = B.vm.get(id) || v;
    const xi = x + (w[2] - x) * f, yi = y + (w[3] - y) * f, ai = interpAng(ang, w[4], f);
    Q.setFromAxisAngle(EJE_Y, -ai * Math.PI / 180); V3.set(xi, 0, -yi);
    if (cod === 9) { egoPos.copy(V3); egoAng = ai; egoMalla.position.copy(V3); egoMalla.quaternion.copy(Q); continue; }
    const m = flota[cod]; const i = cuentas[cod]++; if (i >= 900) continue;
    M4.compose(V3, Q, UNO); m.setMatrixAt(i, M4);
    colTmp.setHex(cod === 0 ? COLORES_AUTO[id % COLORES_AUTO.length] : COLOR_TIPO[cod]); m.setColorAt(i, colTmp);
  }
  flota.forEach((m, k) => { m.count = cuentas[k]; m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true; });
  let np = 0;
  for (const p of A.p) { const [id, x, y, ang] = p; const w = B.pm.get(id) || p;
    Q.setFromAxisAngle(EJE_Y, -interpAng(ang, w[3], f) * Math.PI / 180); V3.set(x + (w[1] - x) * f, 0.15, -(y + (w[2] - y) * f));
    M4.compose(V3, Q, UNO); personas.setMatrixAt(np, M4); colTmp.setHSL((id * 0.137) % 1, 0.45, 0.45); personas.setColorAt(np, colTmp); if (++np >= 800) break; }
  personas.count = np; personas.instanceMatrix.needsUpdate = true; if (personas.instanceColor) personas.instanceColor.needsUpdate = true;
  const vivos = new Set();
  for (const o of A.o) { const [id, tipo, x, y, rumbo] = o; const w = B.om.get(id) || o; vivos.add(id);
    let m = objetos.get(id);
    if (!m) { m = tipo === 'conos' ? figuraConos() : new THREE.Mesh(FIGURAS[tipo](), vehMat); scene.add(m); objetos.set(id, m);
      const s = etiqueta(ICONO[tipo] + ' ' + tipo, '#fff', 'rgba(120,20,40,.75)', 24); s.userData.base = 0.016; s.position.y = 4; m.add(s); }
    m.position.set(x + (w[2] - x) * f, 0.12, -(y + (w[3] - y) * f)); m.rotation.y = rumbo - Math.PI / 2; }
  for (const [id, m] of objetos) if (!vivos.has(id)) { scene.remove(m); objetos.delete(id); }
  if (semaforoLamparas && A.s) {
    CIUDAD.semaforos.forEach(([tls, idx], i) => { const st = A.s[tls]; const ch = st ? st[idx] : 'o';
      colTmp.setHex(ch === 'r' || ch === 'R' ? 0xff2a2a : ch === 'y' || ch === 'Y' ? 0xffc000 : ch === 'g' || ch === 'G' ? 0x29e070 : 0x333333);
      semaforoLamparas.setColorAt(i, colTmp); });
    semaforoLamparas.instanceColor.needsUpdate = true;
  }
  anillo.position.set(egoPos.x, 0.2, egoPos.z); egoEtiqueta.position.set(egoPos.x, 6, egoPos.z);
  const e = A.ego;
  if (e.alcance && Math.abs(e.alcance - alcanceActual) > 2) { alcanceActual = e.alcance; sensor.geometry.dispose();
    sensor.geometry = new THREE.CircleGeometry(alcanceActual, 32, Math.PI / 2 - Math.PI / 3, (2 * Math.PI) / 3); }
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

let hudPrev = '';
function hud(e, A) {
  const clave = `${e.kmh}|${e.dom}|${e.motivo}|${e.det.length}|${e.r}|${A.h}`; if (clave === hudPrev) return; hudPrev = clave;
  $('kmh').textContent = Math.round(e.kmh); $('limite').textContent = e.lim;
  $('accion').textContent = `${NOMBRES_ACC[e.acc]} (${e.a >= 0 ? '+' : ''}${e.a.toFixed(1)} m/s²)`;
  $('ambienteTxt').textContent = A.h !== undefined ? `${textoHora(A.h)} · ${e.clima || ''} · sensores ${Math.round(e.alcance || 0)} m` : '';
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
  $('mChoques').textContent = e.choques; $('mCasi').textContent = e.casi; $('mBruscas').textContent = e.bruscas; $('mR').textContent = e.r.toFixed(0);
}

// ================================================================ modo en vivo
async function revisarServidor() {
  try {
    const r = await fetch('api/estado', { cache: 'no-store' }); if (!r.ok) throw new Error();
    const e = await r.json();
    $('tabVivo').disabled = false; $('tabVivo').title = '';
    if (!$('viaVivo').options.length) {
      $('viaVivo').innerHTML = e.vias.map((v) => `<option value="${v.id}">${v.nombre}</option>`).join('');
      $('agenteVivo').innerHTML = e.agentes.map((a) => `<option value="${a.id}">${a.nombre}</option>`).join('');
    }
    if (!e.listo) { $('estadoVivo').textContent = e.error ? 'Error: ' + e.error : 'Arrancando SUMO (≈ 30 s)…'; setTimeout(revisarServidor, 2500); }
    else if (!fuente) $('estadoVivo').textContent = 'Listo. Elija la vía y pulse Conducir.';
    return true;
  } catch { return false; }
}
function cambiarModo(vivo) {
  $('tabVivo').classList.toggle('on', vivo); $('tabGrabados').classList.toggle('on', !vivo);
  $('modoVivo').hidden = !vivo; $('modoGrabados').hidden = vivo;
  if (!vivo && REC?.vivo) { detenerVivo(); if ($('recorrido').value) cargarRecorrido($('recorrido').value); }
}
function iniciarVivo() {
  detenerVivo();
  const q = new URLSearchParams({ via: $('viaVivo').value, agente: $('agenteVivo').value, velocidad: $('velVivo').value,
    guardrail: $('guardVivo').checked ? 1 : 0, hora: $('hora').value, lluvia: $('lluvia').checked ? 1 : 0,
    ciclo: $('ciclo').checked ? 1.5 : 0, duracion: 600 });
  REC = { vivo: true, dt: 0.5, cuadros: [], episodios: [{}] }; t = 0; $('marcas').innerHTML = '';
  $('sincro').checked = true; $('estadoVivo').textContent = 'Preparando el recorrido…';
  $('btnConducir').disabled = true; $('btnDetener').disabled = false;
  fuente = new EventSource('api/simular?' + q.toString());
  fuente.addEventListener('inicio', (ev) => { const i = JSON.parse(ev.data);
    $('subtitulo').textContent = `En vivo · ${i.ruta}`; $('estadoVivo').textContent = `Conduciendo: ${i.ruta} (${Math.round(i.largo_ruta_m)} m)`;
    nombreEgo(i.agente === 'reglas' ? 'Conductor de reglas' : 'Vehículo instructor'); });
  fuente.addEventListener('cuadro', (ev) => { REC.cuadros.push(indexar(JSON.parse(ev.data))); });
  fuente.addEventListener('fin', (ev) => { const m = JSON.parse(ev.data);
    $('estadoVivo').textContent = `Terminó: ${m.llego ? 'llegó al destino' : m.choques ? 'choque' : 'fin del tiempo'} · ${m.vel_media_kmh} km/h · ${m.casi_choques} casi-choques`; });
  fuente.addEventListener('error', () => { if (fuente && fuente.readyState === 2) terminarVivo(); });
  fuente.addEventListener('cerrar', terminarVivo);
}
function terminarVivo() { if (fuente) { fuente.close(); fuente = null; } $('btnConducir').disabled = false; $('btnDetener').disabled = true; }
function detenerVivo() { if (fuente) { fetch('api/detener').catch(() => {}); terminarVivo(); $('estadoVivo').textContent = 'Detenido.'; } }

// ================================================================ cámara
const camObj = new THREE.Vector3(), camMira = new THREE.Vector3();
function orbitar(h, radio, alto, vel = 0.00003) {
  const a = performance.now() * vel; camObj.set(h.x + radio * Math.cos(a), alto, -(h.y + radio * Math.sin(a))); camMira.set(h.x, alto * 0.25, -h.y);
}
function actualizarCamara(dt) {
  if (camModo === 'libre') { controls.update(); return; }
  const a = egoAng * Math.PI / 180; const fx = Math.sin(a), fz = -Math.cos(a);
  if (camModo === 'seguir') { camObj.set(egoPos.x - fx * 22, 10, egoPos.z - fz * 22); camMira.set(egoPos.x + fx * 25, 1.5, egoPos.z + fz * 25); }
  else if (camModo === 'cenital') { camObj.set(egoPos.x, 240, egoPos.z + 45); camMira.copy(egoPos); }
  else if (camModo === 'malecon') orbitar(HITOS.luna || { x: 0, y: 0 }, 330, 110);
  else if (camModo === 'buenavista') orbitar(HITOS.bv1 || { x: 0, y: 0 }, 230, 75, 0.00004);
  const k = 1 - Math.pow(0.02, dt); camera.position.lerp(camObj, k); controls.target.lerp(camMira, k); camera.lookAt(controls.target);
}

// ================================================================ eventos de la interfaz
$('play').onclick = () => { jugando = !jugando; $('play').textContent = jugando ? '⏸' : '▶'; };
$('velocidad').onchange = (e) => { velRep = Number(e.target.value); };
$('barra').oninput = (e) => { if (REC && !REC.vivo) t = (Number(e.target.value) / 1000) * REC.cuadros.length * DT(); };
for (const b of document.querySelectorAll('[data-cam]')) b.onclick = () => {
  camModo = b.dataset.cam; controls.enabled = camModo === 'libre';
  document.querySelectorAll('[data-cam]').forEach((x) => x.classList.toggle('on', x === b)); };
$('btnSensores').onclick = (e) => { e.target.classList.toggle('on'); sensor.visible = e.target.classList.contains('on'); };
$('btnEtiquetas').onclick = (e) => { e.target.classList.toggle('on'); etiquetas.visible = e.target.classList.contains('on'); };
$('hora').oninput = () => { $('sincro').checked = false; horaVisual = Number($('hora').value); };
$('lluvia').onchange = () => { $('sincro').checked = false; lluviaVisual = $('lluvia').checked; };
$('ciclo').onchange = () => { if ($('ciclo').checked) $('sincro').checked = false; };
$('tabGrabados').onclick = () => cambiarModo(false);
$('tabVivo').onclick = () => { if (!$('tabVivo').disabled) cambiarModo(true); };
$('btnConducir').onclick = iniciarVivo;
$('btnDetener').onclick = detenerVivo;
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
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
});

// ================================================================ bucle
const reloj = new THREE.Clock(); let tGlobal = 0;
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
  const osc = aplicarAmbiente(horaVisual, lluviaVisual);
  if (aguaMat) aguaMat.uniforms.t.value += dt;
  if (gotas.visible) { gotas.position.set(camera.position.x, camera.position.y - 70 - ((tGlobal * 120) % 40), camera.position.z); }
  for (const f of animados) f(tGlobal, osc);
  dibujarPantallas(tGlobal, horaVisual);
  dibujar(); actualizarCamara(dt);
  cielo.position.copy(camera.position); estrellas.position.copy(camera.position);
  for (const s of [...etiquetas.children, egoEtiqueta, ...[...objetos.values()].flatMap((m) => m.children.filter((x) => x.isSprite))]) {
    const p = s.getWorldPosition(V3); const d = camera.position.distanceTo(p); const b = s.userData.base || 0.02;
    s.scale.set(d * b * s.userData.aspecto, d * b, 1); if (s.parent && s.parent !== scene && s.parent !== etiquetas) s.scale.divide(s.parent.scale);
  }
  renderer.render(scene, camera);
  requestAnimationFrame(bucle);
}

// ================================================================ inicio
(async () => {
  try {
    await cargarCiudad();
    let lista = [];
    try { lista = await (await fetch('datos/recorridos.json')).json(); } catch { lista = []; }
    const sel = $('recorrido');
    sel.innerHTML = lista.map((r) => `<option value="${r.archivo}">${r.via} · ${textoHora(r.hora)}${r.lluvia ? ' · lluvia' : ''} · ${r.duracion_s}s</option>`).join('') || '<option value="">(sin recorridos)</option>';
    sel.onchange = () => cargarRecorrido(sel.value);
    const hayServidor = await revisarServidor();
    if (lista.length) await cargarRecorrido(lista[0].archivo); else { $('carga').style.display = 'none'; camModo = 'malecon'; }
    if (hayServidor && !lista.length) cambiarModo(true);
    bucle();
  } catch (err) { carga('Error: ' + err.message + ' — sirva la carpeta con: python -m bq_sim vivo  (o python -m http.server -d visor 8000)'); console.error(err); }
})();

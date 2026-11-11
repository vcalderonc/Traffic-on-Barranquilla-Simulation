// Visor 3D del Gran Malecón (Barranquilla) para la simulación multiagente.
// Coordenadas: SUMO (x este, y norte, metros) -> Three.js (x, altura, -y).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = (id) => document.getElementById(id);
const carga = (t) => { $('cargaTxt').textContent = t; };

// ------------------------------------------------------------------ escena
const lienzo = $('lienzo');
const renderer = new THREE.WebGLRenderer({ canvas: lienzo, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 1, 9000);
camera.position.set(0, 400, 600);
const controls = new OrbitControls(camera, lienzo);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.495;
controls.enabled = false;

window.__visor = { scene, camera, controls, THREE };  // acceso para depuración desde la consola

const hemi = new THREE.HemisphereLight(0xcfe6ff, 0x6b5a45, 0.9);
scene.add(hemi);
const sol = new THREE.DirectionalLight(0xffe2b8, 1.6);
sol.position.set(-900, 700, 400);
scene.add(sol);

// cielo con degradado (atardecer caribeño, lluvia o noche)
const CIELOS = {
  despejado: { arriba: '#3a78c2', medio: '#f5b77a', abajo: '#ffd9a8', niebla: 0xe9c9a3, luz: 1.6, hemi: 0.95, exp: 1.05 },
  lluvia: { arriba: '#5d6874', medio: '#8d98a3', abajo: '#aab3bb', niebla: 0x8f9aa5, luz: 0.55, hemi: 0.75, exp: 0.95 },
  noche: { arriba: '#050a18', medio: '#0f1d3a', abajo: '#2a2440', niebla: 0x101830, luz: 0.12, hemi: 0.22, exp: 1.25 },
};
function texturaCielo(c) {
  const cv = document.createElement('canvas'); cv.width = 4; cv.height = 256;
  const g = cv.getContext('2d'); const gr = g.createLinearGradient(0, 0, 0, 256);
  gr.addColorStop(0, c.arriba); gr.addColorStop(0.62, c.medio); gr.addColorStop(1, c.abajo);
  g.fillStyle = gr; g.fillRect(0, 0, 4, 256);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; return t;
}
const cieloMat = new THREE.MeshBasicMaterial({ side: THREE.BackSide, depthWrite: false, fog: false });
const cielo = new THREE.Mesh(new THREE.SphereGeometry(4200, 32, 16), cieloMat);
cielo.renderOrder = -1;
scene.add(cielo);   // la esfera del cielo sigue a la cámara (ver bucle) para no salirse del plano lejano

// ------------------------------------------------------------ utilidades
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
function poligono(pos, idx, plano, y) {
  const c = []; for (let i = 0; i < plano.length; i += 2) c.push(new THREE.Vector2(plano[i], plano[i + 1]));
  if (c.length < 3) return;
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
function texturaVentanas(encendidas) {
  const cv = document.createElement('canvas'); cv.width = 128; cv.height = 128;
  const g = cv.getContext('2d');
  g.fillStyle = encendidas ? '#000' : '#fff'; g.fillRect(0, 0, 128, 128);
  for (let i = 0; i < 2; i++) for (let j = 0; j < 2; j++) {
    const luz = encendidas ? (Math.random() < 0.55 ? '#ffd58a' : '#1a1a1a') : '#8fa7b8';
    g.fillStyle = luz; g.fillRect(14 + i * 64, 18 + j * 64, 36, 30);
  }
  const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
}
function etiqueta(texto, color = '#fff', fondo = 'rgba(10,16,24,.72)', tam = 30) {
  const cv = document.createElement('canvas'); const g = cv.getContext('2d');
  g.font = `600 ${tam}px Segoe UI, sans-serif`;
  const w = Math.ceil(g.measureText(texto).width) + 24; cv.width = w; cv.height = tam + 18;
  g.font = `600 ${tam}px Segoe UI, sans-serif`;
  g.fillStyle = fondo; g.beginPath(); g.roundRect(0, 0, w, tam + 18, 10); g.fill();
  g.fillStyle = color; g.textBaseline = 'middle'; g.fillText(texto, 12, (tam + 18) / 2 + 1);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthTest: false, transparent: true }));
  s.userData.aspecto = w / (tam + 18); s.renderOrder = 10; return s;
}

// --------------------------------------------------------------- ciudad
const ciudadGrupo = new THREE.Group(); scene.add(ciudadGrupo);
const etiquetas = new THREE.Group(); scene.add(etiquetas);
let matVentanas, matVentanasNoche, aguaMat, CIUDAD, semaforoLamparas, centroMalecon, centroRio;

async function cargarCiudad() {
  carga('Descargando la red vial y los edificios…');
  CIUDAD = await (await fetch('datos/ciudad.json')).json();
  carga('Construyendo vías, edificios y el río…');
  await new Promise((r) => setTimeout(r, 20));
  const [x0, y0, x1, y1] = CIUDAD.limites;
  // terreno
  const suelo = new THREE.Mesh(new THREE.PlaneGeometry(9000, 9000),
    new THREE.MeshLambertMaterial({ color: 0xb8ae94 }));
  suelo.rotation.x = -Math.PI / 2; suelo.position.set((x0 + x1) / 2, -0.05, -(y0 + y1) / 2);
  ciudadGrupo.add(suelo);
  // agua (río Magdalena)
  aguaMat = new THREE.ShaderMaterial({
    uniforms: { t: { value: 0 }, cielo: { value: new THREE.Color(0xf5b77a) }, base: { value: new THREE.Color(0x4c6b6e) } },
    vertexShader: `varying vec3 vP; void main(){ vec4 w = modelMatrix*vec4(position,1.0); vP = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`,
    fragmentShader: `uniform float t; uniform vec3 cielo; uniform vec3 base; varying vec3 vP;
      void main(){ float o = sin(vP.x*0.045+t*0.9)*0.5 + sin(vP.z*0.06-t*1.3)*0.5 + sin((vP.x+vP.z)*0.11+t*2.1)*0.25;
        vec3 vista = normalize(cameraPosition - vP); float fres = pow(1.0 - max(vista.y,0.0), 3.0);
        vec3 c = mix(base, cielo, 0.25 + 0.45*fres) + vec3(0.06)*o;
        gl_FragColor = vec4(c, 1.0); }`,
  });
  { const pos = [], idx = []; for (const p of CIUDAD.agua) poligono(pos, idx, p, 0.0);
    const m = malla(pos, idx, aguaMat); ciudadGrupo.add(m);
    let sx = 0, sy = 0, n = 0; for (const p of CIUDAD.agua) for (let i = 0; i < p.length; i += 2) { sx += p[i]; sy += p[i + 1]; n++; }
    centroRio = n ? new THREE.Vector2(sx / n, sy / n) : new THREE.Vector2(x1, 0); }
  // parques (el Malecón)
  { const pos = [], idx = []; let mejor = null, area = 0;
    for (const [nombre, p] of CIUDAD.parques) { poligono(pos, idx, p, 0.03);
      if (/Malec/i.test(nombre)) { const a = Math.abs(THREE.ShapeUtils.area(p.reduce((acc, v, i) => (i % 2 ? acc : acc.concat([new THREE.Vector2(v, p[i + 1])])), [])));
        if (a > area) { area = a; mejor = p; } } }
    ciudadGrupo.add(malla(pos, idx, new THREE.MeshLambertMaterial({ color: 0x6fa35a, side: THREE.DoubleSide })));
    if (mejor) { let sx = 0, sy = 0; for (let i = 0; i < mejor.length; i += 2) { sx += mejor[i]; sy += mejor[i + 1]; }
      centroMalecon = new THREE.Vector2(sx / (mejor.length / 2), sy / (mejor.length / 2)); } }
  // vías
  { const pa = [], ia = [], pb = [], ib = [], pc = [], ic = [], pm = [], im = [];
    for (const p of CIUDAD.cruces) poligono(pa, ia, p, 0.06);
    for (const arista of CIUDAD.carriles) {
      for (const [w, pts] of arista.l) tira(pa, ia, pts, w + 0.05, 0.07);
      if (!arista.interno && arista.l.length > 1) {   // líneas entre carriles
        for (let k = 0; k < arista.l.length - 1; k++) {
          const A = arista.l[k][1], B = arista.l[k + 1][1]; if (A.length !== B.length) continue;
          const mid = A.map((v, i) => (v + B[i]) / 2); tira(pm, im, mid, 0.15, 0.09);
        }
      }
    }
    for (const [w, pts] of CIUDAD.andenes) tira(pb, ib, pts, w, 0.16);
    for (const [w, pts] of CIUDAD.cebras) tira(pc, ic, pts, w * 0.9, 0.1);
    ciudadGrupo.add(malla(pa, ia, new THREE.MeshLambertMaterial({ color: 0x3b3f45, side: THREE.DoubleSide })));
    ciudadGrupo.add(malla(pb, ib, new THREE.MeshLambertMaterial({ color: 0xc9c4b8, side: THREE.DoubleSide })));
    const cebraTex = (() => { const cv = document.createElement('canvas'); cv.width = 16; cv.height = 64; const g = cv.getContext('2d');
      g.fillStyle = '#3b3f45'; g.fillRect(0, 0, 16, 64); g.fillStyle = '#f2f2f2'; g.fillRect(0, 0, 16, 32);
      const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(1, 4); return t; })();
    ciudadGrupo.add(malla(pc, ic, new THREE.MeshLambertMaterial({ color: 0xffffff, side: THREE.DoubleSide, map: cebraTex })));
    ciudadGrupo.add(malla(pm, im, new THREE.MeshBasicMaterial({ color: 0xe8e8e8, side: THREE.DoubleSide }))); }
  // edificios: paredes con ventanas + techos
  { const pos = [], idx = [], uv = [], col = [], pr = [], ir = [], cr = [];
    const paleta = [0xf3efe6, 0xf6e7c8, 0xeed8c4, 0xdce9ef, 0xf1dcd3, 0xe4efe0, 0xfff4d6, 0xd9d4cc].map((c) => new THREE.Color(c));
    let k = 0;
    for (const [h, _tipo, p] of CIUDAD.edificios) {
      const n = p.length / 2; const c = paleta[(k++ * 7) % paleta.length];
      let u = 0;
      for (let i = 0; i < n; i++) {
        const j = (i + 1) % n; const ax = p[2 * i], ay = p[2 * i + 1], bx = p[2 * j], by = p[2 * j + 1];
        const L = Math.hypot(bx - ax, by - ay); const b0 = pos.length / 3;
        pos.push(ax, 0, -ay, bx, 0, -by, bx, h, -by, ax, h, -ay);
        uv.push(u / 4, 0, (u + L) / 4, 0, (u + L) / 4, h / 3.2, u / 4, h / 3.2);
        for (let q = 0; q < 4; q++) col.push(c.r, c.g, c.b);
        idx.push(b0, b0 + 1, b0 + 2, b0, b0 + 2, b0 + 3); u += L;
      }
      const b1 = pr.length / 3; poligono(pr, ir, p, h);
      const techo = h > 12 ? 0.82 : 0.74; for (let q = b1; q < pr.length / 3; q++) cr.push(c.r * techo, c.g * techo, c.b * techo);
    }
    matVentanas = new THREE.MeshLambertMaterial({ vertexColors: true, map: texturaVentanas(false), side: THREE.DoubleSide });
    matVentanasNoche = texturaVentanas(true);
    ciudadGrupo.add(malla(pos, idx, matVentanas, [['uv', uv, 2], ['color', col, 3]]));
    ciudadGrupo.add(malla(pr, ir, new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide }), [['color', cr, 3]])); }
  // palmeras (instanciadas)
  { const tronco = new THREE.CylinderGeometry(0.16, 0.28, 1, 6); tronco.translate(0, 0.5, 0);
    const hojas = []; for (let i = 0; i < 7; i++) { const h = new THREE.ConeGeometry(0.5, 4.2, 3); h.scale(1, 1, 0.25);
      h.rotateZ(-Math.PI / 2 - 0.35); h.translate(2.0, -0.4, 0); h.rotateY((i / 7) * Math.PI * 2); hojas.push(h); }
    const copa = mergeGeoms(hojas);
    const n = CIUDAD.palmeras.length;
    const mt = new THREE.InstancedMesh(tronco, new THREE.MeshLambertMaterial({ color: 0x8b6b4a }), n);
    const mc = new THREE.InstancedMesh(copa, new THREE.MeshLambertMaterial({ color: 0x3f8f3a, side: THREE.DoubleSide }), n);
    const M = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    CIUDAD.palmeras.forEach(([x, y, h], i) => {
      M.compose(new THREE.Vector3(x, 0, -y), q.setFromEuler(e.set(0, 0, 0)), new THREE.Vector3(1, h, 1)); mt.setMatrixAt(i, M);
      M.compose(new THREE.Vector3(x, h, -y), q.setFromEuler(e.set(0, i * 1.7, 0)), new THREE.Vector3(1, 1, 1)); mc.setMatrixAt(i, M);
    });
    ciudadGrupo.add(mt, mc); }
  // semáforos: poste + lámpara de color por enlace
  { const n = CIUDAD.semaforos.length;
    const poste = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.08, 0.1, 4.2, 5).translate(0, 2.1, 0),
      new THREE.MeshLambertMaterial({ color: 0x2b2f33 }), n);
    semaforoLamparas = new THREE.InstancedMesh(new THREE.SphereGeometry(0.42, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffffff }), n);
    const M = new THREE.Matrix4();
    CIUDAD.semaforos.forEach(([_t, _i, x, y], k) => {
      M.makeTranslation(x, 0, -y); poste.setMatrixAt(k, M);
      M.makeTranslation(x, 4.5, -y); semaforoLamparas.setMatrixAt(k, M);
      semaforoLamparas.setColorAt(k, new THREE.Color(0x333333));
    });
    ciudadGrupo.add(poste, semaforoLamparas); }
  // nombres: solo vías principales (avenidas, Vía 40, calles anchas) y lugares; máximo 2 por nombre
  { const cuenta = {};
    const principal = /V[ií]a 40|Avenida|Rotonda|Calle (72|76|79|80|84|85)$|Carrera (46|50|51B|53|54|58)$/;
    for (const [tipo, nombre, x, y] of CIUDAD.etiquetas) {
      if (tipo === 'via' && !principal.test(nombre)) continue;
      cuenta[nombre] = (cuenta[nombre] || 0) + 1; if (cuenta[nombre] > (tipo === 'via' ? 2 : 1)) continue;
      const color = tipo === 'agua' ? '#bfe6ff' : tipo === 'lugar' ? '#c9f7c1' : '#ffffff';
      const s = etiqueta(nombre, color, 'rgba(10,16,24,.66)', tipo === 'via' ? 26 : 32);
      const alto = tipo === 'via' ? 18 : 40; s.position.set(x, alto, -y);
      s.userData.base = tipo === 'via' ? 0.022 : 0.03; etiquetas.add(s);
    } }
}
function mergeGeoms(gs) {
  const pos = [], idx = []; let off = 0;
  for (const g of gs) { const gi = g.index ? g : g; const p = gi.attributes.position.array;
    for (let i = 0; i < p.length; i++) pos.push(p[i]);
    if (gi.index) for (const v of gi.index.array) idx.push(v + off); else for (let i = 0; i < p.length / 3; i++) idx.push(i + off);
    off += p.length / 3; }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  g.computeVertexNormals(); return g;
}

// ------------------------------------------------------------ vehículos
function caja(w, h, l, x, y, z, color) { const g = new THREE.BoxGeometry(w, h, l); g.translate(x, y, z);
  const c = new THREE.Color(color); const n = g.attributes.position.count; const col = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { col[3 * i] = c.r; col[3 * i + 1] = c.g; col[3 * i + 2] = c.b; }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3)); return g; }
function unir(partes) { // une cajas con color por vértice
  const pos = [], col = [], idx = []; let off = 0;
  for (const g of partes) { const ng = g.toNonIndexed(); const p = ng.attributes.position.array, c = ng.attributes.color.array;
    for (let i = 0; i < p.length; i++) { pos.push(p[i]); col.push(c[i]); }
    for (let i = 0; i < p.length / 3; i++) idx.push(off + i); off += p.length / 3; }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); g.setIndex(idx); g.computeVertexNormals(); return g; }
// el frente del vehículo está en z=0 y la carrocería se extiende hacia +z (SUMO da la posición del parachoques delantero)
const VIDRIO = 0x22303c, BLANCO = 0xffffff;
function geomAuto(L, W, H) { return unir([caja(W, H * 0.5, L, 0, 0.45, L / 2, BLANCO), caja(W * 0.86, H * 0.42, L * 0.5, 0, 0.45 + H * 0.46, L * 0.55, VIDRIO),
  caja(0.5, 0.18, 0.06, -W * 0.3, 0.6, -0.01, 0xfff6c0), caja(0.5, 0.18, 0.06, W * 0.3, 0.6, -0.01, 0xfff6c0)]); }
const GEOM = [
  geomAuto(4.5, 1.8, 1.45),
  unir([geomAuto(4.3, 1.75, 1.45), caja(0.6, 0.22, 0.25, 0, 1.55, 2.3, 0xffffff)]),
  unir([caja(0.5, 0.8, 2.0, 0, 0.6, 1.0, BLANCO), caja(0.45, 0.75, 0.45, 0, 1.45, 1.2, 0x1e2a5a), caja(0.32, 0.3, 0.32, 0, 2.0, 1.15, 0xdddddd)]),
  unir([caja(2.5, 2.6, 12, 0, 1.55, 6, BLANCO), caja(2.52, 0.9, 11.4, 0, 2.15, 6.1, VIDRIO), caja(2.4, 0.9, 0.05, 0, 2.0, -0.01, VIDRIO)]),
  unir([caja(2.4, 2.4, 2.6, 0, 1.5, 1.3, BLANCO), caja(2.5, 3.0, 6.2, 0, 1.9, 5.8, 0xd8d8d8), caja(2.2, 0.9, 0.05, 0, 2.1, -0.01, VIDRIO)]),
];
const COLORES_AUTO = [0xd9dde3, 0x9aa3ad, 0x2d3640, 0xb81d24, 0x1f4e8c, 0xf2f2f2, 0x5b6770, 0x7a1f1f];
const COLOR_TIPO = [null, 0xffd600, 0x2b2b2b, 0x18a058, 0xc4512f];
const vehMats = new THREE.MeshLambertMaterial({ vertexColors: true });
const flota = GEOM.map((g) => { const m = new THREE.InstancedMesh(g, vehMats, 700); m.count = 0; m.frustumCulled = false; scene.add(m); return m; });
const egoMalla = new THREE.Mesh(geomAuto(4.5, 1.8, 1.45), new THREE.MeshLambertMaterial({ vertexColors: true, color: 0xffb000, emissive: 0x4a2a00 }));
scene.add(egoMalla);
const anillo = new THREE.Mesh(new THREE.RingGeometry(3.2, 3.8, 40), new THREE.MeshBasicMaterial({ color: 0xffb000, transparent: true, opacity: 0.85, side: THREE.DoubleSide }));
anillo.rotation.x = -Math.PI / 2; scene.add(anillo);
const egoEtiqueta = etiqueta('Vehículo instructor', '#ffb000', 'rgba(10,16,24,.8)', 26); egoEtiqueta.userData.base = 0.02; scene.add(egoEtiqueta);
// cono de sensores (alcance según clima) y líneas a lo detectado
const sensorMat = new THREE.MeshBasicMaterial({ color: 0x4fb3ff, transparent: true, opacity: 0.13, side: THREE.DoubleSide, depthWrite: false });
let sensor = new THREE.Mesh(new THREE.CircleGeometry(90, 32, Math.PI / 2 - Math.PI / 3, (2 * Math.PI) / 3), sensorMat);
sensor.rotation.x = -Math.PI / 2; scene.add(sensor);
const lineasDet = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 }));
lineasDet.frustumCulled = false; scene.add(lineasDet);
// personas de SUMO
const geomPersona = unir([caja(0.45, 1.1, 0.3, 0, 0.75, 0, 0x3b5b8c), caja(0.32, 0.32, 0.3, 0, 1.5, 0, 0xc68e62)]);
const personas = new THREE.InstancedMesh(geomPersona, vehMats, 600); personas.count = 0; personas.frustumCulled = false; scene.add(personas);
// imprevistos (peatón imprudente, perro, iguana, conos)
const FIGURAS = {
  peaton: () => unir([caja(0.5, 1.15, 0.32, 0, 0.78, 0, 0xe04f8a), caja(0.34, 0.34, 0.32, 0, 1.55, 0, 0xc68e62), caja(0.42, 0.7, 0.3, 0, 0.35, 0, 0x2c3e66)]),
  perro: () => unir([caja(0.32, 0.4, 0.9, 0, 0.45, 0.45, 0x8a5a2b), caja(0.28, 0.3, 0.32, 0, 0.72, -0.05, 0x7a4a20), caja(0.08, 0.32, 0.08, 0.1, 0.16, 0.15, 0x6b3f1a), caja(0.08, 0.32, 0.08, -0.1, 0.16, 0.75, 0x6b3f1a)]),
  iguana: () => unir([caja(0.22, 0.14, 0.7, 0, 0.08, 0.35, 0x3fae49), caja(0.12, 0.08, 0.7, 0, 0.05, 1.0, 0x2f8a37), caja(0.16, 0.12, 0.18, 0, 0.1, -0.05, 0x56c35f)]),
};
const objetos = new Map();
function figuraConos() { const g = new THREE.Group(); const cono = new THREE.ConeGeometry(0.28, 0.8, 10).translate(0, 0.4, 0);
  const m1 = new THREE.MeshLambertMaterial({ color: 0xff6a00, emissive: 0x401800 });
  for (let i = 0; i < 6; i++) { const c = new THREE.Mesh(cono, m1); c.position.set(0, 0, i * 2.6); g.add(c); }
  const valla = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.9, 0.12).translate(0, 0.45, 0), new THREE.MeshLambertMaterial({ color: 0xff8c00 }));
  valla.position.z = -0.4; g.add(valla); return g; }

// -------------------------------------------------------------- lluvia
const gotas = (() => { const n = 5000, p = new Float32Array(n * 6);
  for (let i = 0; i < n; i++) { const x = (Math.random() - 0.5) * 500, y = Math.random() * 140, z = (Math.random() - 0.5) * 500;
    p.set([x, y, z, x + 0.3, y - 2.2, z], i * 6); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  const l = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0xaac4dd, transparent: true, opacity: 0.45 }));
  l.visible = false; l.frustumCulled = false; scene.add(l); return l; })();

function aplicarClima(c) {
  const k = CIELOS[c] || CIELOS.despejado;
  cieloMat.map = texturaCielo(k); cieloMat.needsUpdate = true;
  scene.fog = new THREE.Fog(k.niebla, c === 'despejado' ? 700 : 350, c === 'despejado' ? 3600 : 1800);
  sol.intensity = k.luz; hemi.intensity = k.hemi; renderer.toneMappingExposure = k.exp;
  if (aguaMat) { aguaMat.uniforms.cielo.value.set(k.medio); aguaMat.uniforms.base.value.set(c === 'noche' ? 0x0d1a24 : c === 'lluvia' ? 0x46585c : 0x4c6b6e); }
  if (matVentanas) { matVentanas.emissiveMap = c === 'noche' ? matVentanasNoche : null; matVentanas.emissive = new THREE.Color(c === 'noche' ? 0xffffff : 0x000000);
    matVentanas.emissiveIntensity = c === 'noche' ? 0.9 : 0; matVentanas.needsUpdate = true; }
  gotas.visible = c === 'lluvia';
  const alcance = { despejado: 90, lluvia: 55, noche: 45 }[c] || 90;
  sensor.geometry.dispose(); sensor.geometry = new THREE.CircleGeometry(alcance, 32, Math.PI / 2 - Math.PI / 3, (2 * Math.PI) / 3);
  egoMalla.material.emissive.set(c === 'noche' ? 0x8a5200 : 0x4a2a00);
}

// -------------------------------------------------------- reproducción
let REC = null, t = 0, jugando = true, velRep = 1, camModo = 'seguir';
const DT = () => REC.dt;
const NOMBRES_ACC = ['frenado de emergencia', 'frenado fuerte', 'frenado moderado', 'frenado suave', 'mantener', 'acelerar suave', 'acelerar'];
const ICONO = { auto: '🚗', taxi: '🚕', moto: '🏍️', bus: '🚌', camion: '🚚', peaton: '🚶', perro: '🐕', iguana: '🦎', conos: '🚧' };
const COLOR_EVENTO = { choque: '#ff3b3b', casi_choque: '#ffb000', peaton: '#e04f8a', perro: '#a0703a', iguana: '#3fae49', conos: '#ff6a00', frenada_lider: '#4fb3ff', pare_violado: '#ff3b3b', semaforo_rojo: '#ff3b3b' };

async function cargarRecorrido(archivo) {
  carga('Cargando el recorrido grabado…'); $('carga').style.display = 'grid';
  REC = await (await fetch('datos/' + archivo)).json();
  for (const c of REC.cuadros) { c.vm = new Map(c.v.map((v) => [v[0], v])); c.pm = new Map(c.p.map((p) => [p[0], p])); c.om = new Map(c.o.map((o) => [o[0], o])); }
  t = 0; aplicarClima(REC.clima);
  const ep = REC.episodios[0] || {};
  $('subtitulo').textContent = `${ep.ruta || ''} · clima: ${REC.clima} · zona: Gran Malecón`;
  // marcas de eventos en la línea de tiempo (los tiempos de SUMO son absolutos: se restan del inicio)
  const marcas = $('marcas'); marcas.innerHTML = '';
  const dur = REC.cuadros.length * DT();
  for (const e of (ep.eventos || [])) {
    const tipo = e.evento || e.tipo; const rel = (e.t || 0) - (ep.t0 || 0);
    const i = document.createElement('i'); i.title = `${tipo} · ${rel.toFixed(0)} s`;
    i.style.background = COLOR_EVENTO[tipo] || '#999';
    i.style.left = `${Math.max(0, Math.min(100, (rel / dur) * 100))}%`; marcas.appendChild(i);
  }
  $('carga').style.display = 'none';
}

function interpAng(a, b, f) { let d = ((b - a + 540) % 360) - 180; return a + d * f; }
const M4 = new THREE.Matrix4(), Q = new THREE.Quaternion(), EJE_Y = new THREE.Vector3(0, 1, 0), V3 = new THREE.Vector3(), UNO = new THREE.Vector3(1, 1, 1);
const colTmp = new THREE.Color();
let egoPos = new THREE.Vector3(), egoAng = 0;

function dibujar() {
  if (!REC || !REC.cuadros.length) return;
  const n = REC.cuadros.length; const k = Math.min(n - 1, Math.floor(t / DT())); const f = Math.min(1, t / DT() - k);
  const A = REC.cuadros[k], B = REC.cuadros[Math.min(n - 1, k + 1)];
  const cuentas = [0, 0, 0, 0, 0];
  for (const v of A.v) {
    const [id, cod, x, y, ang] = v; const w = B.vm.get(id) || v;
    const xi = x + (w[2] - x) * f, yi = y + (w[3] - y) * f, ai = interpAng(ang, w[4], f);
    Q.setFromAxisAngle(EJE_Y, -ai * Math.PI / 180); V3.set(xi, 0, -yi);
    if (cod === 9) { egoPos.copy(V3); egoAng = ai; egoMalla.position.copy(V3); egoMalla.quaternion.copy(Q); continue; }
    const m = flota[cod]; const i = cuentas[cod]++; if (i >= 700) continue;
    M4.compose(V3, Q, UNO); m.setMatrixAt(i, M4);
    colTmp.setHex(cod === 0 ? COLORES_AUTO[id % COLORES_AUTO.length] : COLOR_TIPO[cod]); m.setColorAt(i, colTmp);
  }
  flota.forEach((m, c) => { m.count = cuentas[c]; m.instanceMatrix.needsUpdate = true; if (m.instanceColor) m.instanceColor.needsUpdate = true; });
  let np = 0;
  for (const p of A.p) { const [id, x, y, ang] = p; const w = B.pm.get(id) || p;
    Q.setFromAxisAngle(EJE_Y, -interpAng(ang, w[3], f) * Math.PI / 180); V3.set(x + (w[1] - x) * f, 0.15, -(y + (w[2] - y) * f));
    M4.compose(V3, Q, UNO); personas.setMatrixAt(np, M4); colTmp.setHSL((id * 0.137) % 1, 0.45, 0.45); personas.setColorAt(np, colTmp); if (++np >= 600) break; }
  personas.count = np; personas.instanceMatrix.needsUpdate = true; if (personas.instanceColor) personas.instanceColor.needsUpdate = true;
  // imprevistos
  const vivos = new Set();
  for (const o of A.o) { const [id, tipo, x, y, rumbo] = o; const w = B.om.get(id) || o; vivos.add(id);
    let m = objetos.get(id);
    if (!m) { m = tipo === 'conos' ? figuraConos() : new THREE.Mesh(FIGURAS[tipo](), vehMats); scene.add(m); objetos.set(id, m);
      const s = etiqueta(ICONO[tipo] + ' ' + tipo, '#fff', 'rgba(120,20,40,.75)', 24); s.userData.base = 0.016; s.position.y = 4; m.add(s); }
    m.position.set(x + (w[2] - x) * f, 0.12, -(y + (w[3] - y) * f));
    // rumbo: ángulo matemático en el plano SUMO; el modelo mira hacia -z, así que se gira rumbo - 90°
    m.rotation.y = rumbo - Math.PI / 2;
  }
  for (const [id, m] of objetos) if (!vivos.has(id)) { scene.remove(m); objetos.delete(id); }
  // semáforos
  if (semaforoLamparas && A.s) {
    CIUDAD.semaforos.forEach(([tls, idx], i) => { const st = A.s[tls]; const ch = st ? st[idx] : 'o';
      colTmp.setHex(ch === 'r' || ch === 'R' ? 0xff2a2a : ch === 'y' || ch === 'Y' ? 0xffc000 : ch === 'g' || ch === 'G' ? 0x29e070 : 0x333333);
      semaforoLamparas.setColorAt(i, colTmp); });
    semaforoLamparas.instanceColor.needsUpdate = true;
  }
  // instructor: anillo, etiqueta, sensores y detecciones
  anillo.position.set(egoPos.x, 0.2, egoPos.z); egoEtiqueta.position.set(egoPos.x, 6, egoPos.z);
  sensor.position.set(egoPos.x, 0.25, egoPos.z); sensor.rotation.z = -egoAng * Math.PI / 180;
  const e = A.ego; const lp = [], lc = [];
  if ($('btnSensores').classList.contains('on')) for (const d of e.det) { const [, , , tray, dx, dy] = d;
    lp.push(egoPos.x, 1.2, egoPos.z, dx, 1.0, -dy); const c = tray ? [1, 0.25, 0.25] : [1, 0.75, 0.2]; lc.push(...c, ...c); }
  lineasDet.geometry.setAttribute('position', new THREE.Float32BufferAttribute(lp, 3));
  lineasDet.geometry.setAttribute('color', new THREE.Float32BufferAttribute(lc, 3));
  hud(e);
  $('reloj').textContent = `${t.toFixed(1)} / ${(n * DT()).toFixed(0)} s`;
  $('barra').value = Math.round((t / (n * DT())) * 1000);
}

let hudPrev = '';
function hud(e) {
  const clave = `${e.kmh}|${e.dom}|${e.motivo}|${e.det.length}|${e.r}`; if (clave === hudPrev) return; hudPrev = clave;
  $('kmh').textContent = Math.round(e.kmh); $('limite').textContent = e.lim;
  $('accion').textContent = `${NOMBRES_ACC[e.acc]} (${e.a >= 0 ? '+' : ''}${e.a.toFixed(1)} m/s²)`;
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

// ---------------------------------------------------------------- cámara
const camObj = new THREE.Vector3(), camMira = new THREE.Vector3();
function actualizarCamara(dt) {
  if (camModo === 'libre') { controls.update(); return; }
  const a = egoAng * Math.PI / 180; const fx = Math.sin(a), fz = -Math.cos(a);
  if (camModo === 'seguir') { camObj.set(egoPos.x - fx * 22, 10, egoPos.z - fz * 22); camMira.set(egoPos.x + fx * 25, 1.5, egoPos.z + fz * 25); }
  else if (camModo === 'cenital') { camObj.set(egoPos.x + 1, 260, egoPos.z + 1); camMira.copy(egoPos); }
  else if (camModo === 'malecon') {
    const c = centroMalecon || new THREE.Vector2(0, 0); const r = centroRio || new THREE.Vector2(c.x + 500, c.y);
    const dir = new THREE.Vector2(r.x - c.x, r.y - c.y).normalize(); const ang = performance.now() * 0.00003;
    const ox = dir.x * Math.cos(ang) - dir.y * Math.sin(ang), oy = dir.x * Math.sin(ang) + dir.y * Math.cos(ang);
    camObj.set(c.x + ox * 520, 140, -(c.y + oy * 520)); camMira.set(c.x, 10, -c.y);
  }
  const k = 1 - Math.pow(0.02, dt); camera.position.lerp(camObj, k);
  controls.target.lerp(camMira, k); camera.lookAt(controls.target);
}

// --------------------------------------------------------------- eventos UI
$('play').onclick = () => { jugando = !jugando; $('play').textContent = jugando ? '⏸' : '▶'; };
$('velocidad').onchange = (e) => { velRep = Number(e.target.value); };
$('barra').oninput = (e) => { if (REC) t = (Number(e.target.value) / 1000) * REC.cuadros.length * DT(); };
for (const b of document.querySelectorAll('[data-cam]')) b.onclick = () => {
  camModo = b.dataset.cam; controls.enabled = camModo === 'libre';
  document.querySelectorAll('[data-cam]').forEach((x) => x.classList.toggle('on', x === b)); };
$('btnSensores').onclick = (e) => { e.target.classList.toggle('on'); sensor.visible = e.target.classList.contains('on'); };
$('btnEtiquetas').onclick = (e) => { e.target.classList.toggle('on'); etiquetas.visible = e.target.classList.contains('on'); };
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
addEventListener('keydown', (e) => { if (e.code === 'Space') { e.preventDefault(); $('play').click(); } });

// ------------------------------------------------------------------ bucle
const reloj = new THREE.Clock();
function bucle() {
  const dt = Math.min(0.1, reloj.getDelta());
  if (REC && jugando) { t += dt * velRep; const dur = REC.cuadros.length * DT(); if (t >= dur - DT()) t = 0; }
  if (aguaMat) aguaMat.uniforms.t.value += dt;
  if (gotas.visible) { gotas.position.set(camera.position.x, camera.position.y - 70, camera.position.z); gotas.position.y = (gotas.position.y - ((performance.now() * 0.12) % 40)); }
  dibujar(); actualizarCamara(dt); cielo.position.copy(camera.position);
  // etiquetas de tamaño constante en pantalla
  for (const s of [...etiquetas.children, egoEtiqueta, ...[...objetos.values()].flatMap((m) => m.children.filter((c) => c.isSprite))]) {
    const p = s.getWorldPosition(V3); const d = camera.position.distanceTo(p); const b = s.userData.base || 0.02;
    s.scale.set(d * b * s.userData.aspecto, d * b, 1); if (s.parent && s.parent !== scene && s.parent !== etiquetas) s.scale.divide(s.parent.scale);
  }
  renderer.render(scene, camera);
  requestAnimationFrame(bucle);
}

// ------------------------------------------------------------------ inicio
(async () => {
  try {
    await cargarCiudad();
    aplicarClima('despejado');
    let lista = [];
    try { lista = await (await fetch('datos/recorridos.json')).json(); } catch { lista = []; }
    const sel = $('recorrido');
    sel.innerHTML = lista.map((r) => `<option value="${r.archivo}">${r.clima} · ${r.ruta} · ${r.duracion_s}s</option>`).join('') || '<option>(sin recorridos: ejecute python -m bq_sim visor)</option>';
    sel.onchange = () => cargarRecorrido(sel.value);
    if (lista.length) await cargarRecorrido(lista[0].archivo);
    else { $('carga').style.display = 'none'; camModo = 'malecon'; }
    bucle();
  } catch (err) { carga('Error: ' + err.message + ' — sirva la carpeta con: python -m http.server -d visor 8000'); console.error(err); }
})();

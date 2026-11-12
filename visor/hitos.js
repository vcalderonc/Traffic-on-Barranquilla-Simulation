// Lugares emblemáticos de Barranquilla en el visor 3D.
// Estatuas (figuras estilizadas, no retratos), La Luna del Río, el carrusel, la plaza de
// luces, el Caimán del Río, los centros comerciales con pantallas LED tipo Times Square,
// y los monumentos sobre glorietas: Ventana al Mundo (mosaico de colores y torre de vidrio
// azul), Aleta del Tiburón · Ventana de Campeones (paneles LED con el rojo y blanco del
// Junior y el tricolor de Colombia) y el Centro de Eventos Puerta de Oro (fachada dorada).
// De noche todos se iluminan como en la realidad.
import * as THREE from 'three';

let C;  // contexto: { scene, animados, etiquetas, etiqueta, lienzoTextura, poligono, malla, puntos2, extruir, materialFachada }
export function iniciarHitos(contexto) { C = contexto; }

const lerp = (a, b, f) => a + (b - a) * f;
const bronce = new THREE.MeshStandardMaterial({ color: 0x9a6a3a, metalness: 0.75, roughness: 0.32 });
const bronceDorado = new THREE.MeshStandardMaterial({ color: 0xc09048, metalness: 0.8, roughness: 0.28 });
const piedra = new THREE.MeshStandardMaterial({ color: 0xd8d2c4, roughness: 0.85 });
function cil(r1, r2, h, mat, x, y, z, seg = 20) { const m = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, h, seg), mat); m.position.set(x, y, z); return m; }
function esf(r, mat, x, y, z, sx = 1, sy = 1, sz = 1) { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 20, 14), mat); m.position.set(x, y, z); m.scale.set(sx, sy, sz); return m; }
function miembro(mat, a, b, r) {
  const d = new THREE.Vector3().subVectors(b, a); const m = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.85, r, d.length(), 12), mat);
  m.position.copy(a).addScaledVector(d, 0.5); m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize()); return m;
}
function sombras(obj) { obj.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } }); return obj; }

// Figuras estilizadas: bailarina con brazos en alto (Shakira) y figura con vestido saludando (Sofía Vergara)
function figuraEstatua(tipo, alto) {
  const g = new THREE.Group(); const mat = tipo === 'estatua_shakira' ? bronce : bronceDorado; const V = (x, y, z) => new THREE.Vector3(x, y, z);
  g.scale.setScalar(alto / 1.75);
  if (tipo === 'estatua_shakira') {
    g.add(miembro(mat, V(-0.11, 0, 0.04), V(-0.08, 0.84, 0), 0.085), miembro(mat, V(0.14, 0, -0.06), V(0.09, 0.84, 0), 0.085));
    g.add(esf(0.2, mat, 0.03, 0.92, 0, 1.15, 0.8, 0.85));
    const falda = new THREE.Mesh(new THREE.ConeGeometry(0.3, 0.3, 24, 1, true), mat); falda.position.y = 0.86; falda.rotation.z = 0.12; g.add(falda);
    for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2;
      g.add(miembro(mat, V(0.27 * Math.cos(a), 0.75, 0.27 * Math.sin(a)), V(0.31 * Math.cos(a), 0.58, 0.31 * Math.sin(a)), 0.02)); }
    g.add(esf(0.15, mat, 0.01, 1.08, 0, 0.9, 1.0, 0.75), esf(0.17, mat, 0.0, 1.3, 0.01, 1.05, 0.95, 0.8));
    g.add(miembro(mat, V(0, 1.42, 0), V(0, 1.5, 0), 0.05), esf(0.115, mat, -0.01, 1.6, 0.01), esf(0.15, mat, -0.01, 1.47, -0.07, 0.95, 1.6, 0.55));
    g.add(miembro(mat, V(-0.17, 1.4, 0), V(-0.24, 1.66, 0.02), 0.055), miembro(mat, V(-0.24, 1.66, 0.02), V(-0.03, 1.86, 0.02), 0.045));
    g.add(miembro(mat, V(0.16, 1.4, 0), V(0.23, 1.66, 0.02), 0.055), miembro(mat, V(0.23, 1.66, 0.02), V(0.01, 1.86, 0.02), 0.045));
  } else {
    g.add(new THREE.Mesh(new THREE.ConeGeometry(0.34, 1.0, 28), mat).translateY(0.5));
    g.add(esf(0.15, mat, 0, 1.05, 0, 0.95, 0.8, 0.75), esf(0.17, mat, 0, 1.27, 0.01, 1.05, 0.95, 0.8));
    g.add(miembro(mat, V(0, 1.38, 0), V(0, 1.46, 0), 0.05), esf(0.11, mat, 0, 1.56, 0), esf(0.15, mat, 0, 1.43, -0.07, 1.0, 1.5, 0.55));
    g.add(miembro(mat, V(0.16, 1.36, 0), V(0.3, 1.56, 0), 0.055), miembro(mat, V(0.3, 1.56, 0), V(0.33, 1.82, 0.06), 0.045));
    g.add(miembro(mat, V(-0.16, 1.36, 0), V(-0.27, 1.13, 0.04), 0.055), miembro(mat, V(-0.27, 1.13, 0.04), V(-0.13, 1.02, 0.08), 0.045));
  }
  return g;
}
function etiquetaHito(h, alto, color = '#ffe8b0') {
  const s = C.etiqueta(h.nombre, color, 'rgba(40,20,10,.78)', 28); s.position.set(h.x, alto, -h.y); s.userData.base = 0.024; C.etiquetas.add(s);
}
// reflector que ilumina el monumento desde abajo (un cono aditivo de luz)
function reflector(grupo, x, z, alto, color, ancho = 6) {
  const m = new THREE.Mesh(new THREE.ConeGeometry(ancho, alto, 24, 1, true),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, toneMapped: false }));
  m.position.set(x, alto / 2, z); m.rotation.x = Math.PI; grupo.add(m); return m.material;
}
function centroYAngulo(h) {
  const pts = C.puntos2(h.poligono); const c = pts.reduce((a, p) => a.add(p), new THREE.Vector2()).multiplyScalar(1 / pts.length);
  return { c, ang: h.rumbo ?? 0 };
}

export function construirHito(h) {
  const grupo = new THREE.Group(); grupo.position.set(h.x, 0, -h.y); C.scene.add(grupo);
  const anima = (f) => C.animados.push(f);
  if (h.tipo === 'estatua_shakira' || h.tipo === 'estatua_sofia') {
    grupo.add(cil(2.4, 2.8, 1.2, piedra, 0, 0.6, 0), cil(2.9, 3.1, 0.3, piedra, 0, 0.15, 0));
    const f = figuraEstatua(h.tipo, h.altura); f.position.y = 1.2; grupo.add(f);
    grupo.rotation.y = h.rumbo + Math.PI / 2;
    const luz = reflector(grupo, 0, 0, h.altura + 2, 0xffd9a0, 3.2);
    anima((t, osc) => { luz.opacity = 0.16 * osc; });
    etiquetaHito(h, h.altura + 6);
  } else if (h.tipo === 'rueda') {
    // La Luna del Río: rueda panorámica con LED que cambian de color de noche
    const R = 25, cy = 30; grupo.rotation.y = h.rumbo;
    const rueda = new THREE.Group(); rueda.position.y = cy; grupo.add(rueda);
    const ledMat = new THREE.MeshStandardMaterial({ color: 0x8a9099, metalness: 0.6, roughness: 0.3, emissive: 0xffffff, emissiveIntensity: 0 });
    const acero = new THREE.MeshStandardMaterial({ color: 0xe8edf2, metalness: 0.8, roughness: 0.3 });
    for (const z of [-1.6, 1.6]) { const t = new THREE.Mesh(new THREE.TorusGeometry(R, 0.35, 8, 140), ledMat); t.position.z = z; rueda.add(t);
      for (let i = 0; i < 32; i++) { const a = (i / 32) * Math.PI * 2; rueda.add(miembro(acero, new THREE.Vector3(0, 0, z), new THREE.Vector3(R * Math.cos(a), R * Math.sin(a), z), 0.08)); } }
    rueda.add(cil(1.2, 1.2, 4.2, acero, 0, 0, 0).rotateX(Math.PI / 2));
    for (const [dx, dz] of [[-11, -5], [11, -5], [-11, 5], [11, 5]]) grupo.add(miembro(acero, new THREE.Vector3(dx, 0, dz), new THREE.Vector3(0, cy, Math.sign(dz) * 1.8), 0.45));
    const cabinas = []; const colores = [0xff5a7a, 0x4fb3ff, 0xffd34f, 0x5ee6a0, 0xc58fcf, 0xff9c4a];
    for (let i = 0; i < 24; i++) { const c = new THREE.Mesh(new THREE.CylinderGeometry(1.3, 1.3, 2.2, 14), new THREE.MeshStandardMaterial({ color: colores[i % colores.length], roughness: 0.4, emissive: colores[i % colores.length], emissiveIntensity: 0 }));
      grupo.add(c); cabinas.push(c); }
    anima((t, osc) => {
      const giro = t * 0.025; rueda.rotation.z = giro;
      cabinas.forEach((c, i) => { const a = giro + (i / 24) * Math.PI * 2; c.position.set(R * Math.cos(a), cy + R * Math.sin(a) - 1.6, 0); c.material.emissiveIntensity = 0.35 * osc; });
      ledMat.emissive.setHSL((t * 0.05) % 1, 1.0, 0.5); ledMat.emissiveIntensity = 0.15 + 2.2 * osc;
    });
    etiquetaHito(h, 64);
  } else if (h.tipo === 'carrusel') {
    const c = new THREE.Group(); grupo.add(c);
    c.add(cil(6, 6, 0.6, new THREE.MeshStandardMaterial({ color: 0xfff1d6 }), 0, 0.3, 0));
    const focos = new THREE.MeshStandardMaterial({ color: 0xe0405c, emissive: 0xff8a50, emissiveIntensity: 0 });
    const techo = new THREE.Mesh(new THREE.ConeGeometry(6.6, 3, 24), focos); techo.position.y = 5.5; c.add(techo);
    for (let i = 0; i < 12; i++) { const a = (i / 12) * Math.PI * 2; c.add(cil(0.08, 0.08, 4, new THREE.MeshStandardMaterial({ color: 0xffd34f, metalness: 0.7, roughness: 0.3 }), 5 * Math.cos(a), 2.5, 5 * Math.sin(a)));
      c.add(new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.8, 1.2), new THREE.MeshStandardMaterial({ color: [0xffffff, 0x4fb3ff, 0xff9cc6][i % 3] })).translateX(5 * Math.cos(a)).translateY(2 + 0.4 * Math.sin(i)).translateZ(5 * Math.sin(a))); }
    anima((t, osc) => { c.rotation.y = t * 0.4; focos.emissiveIntensity = 0.9 * osc; });
  } else if (h.tipo === 'plaza_luces') {
    grupo.position.set(0, 0, 0);
    const pos = [], idx = []; C.poligono(pos, idx, h.poligono, 0.12);
    grupo.add(C.malla(pos, idx, new THREE.MeshStandardMaterial({ color: 0xe9e4da, roughness: 0.7, side: THREE.DoubleSide })));
    const pts = C.puntos2(h.poligono); const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const luces = [];
    const dentro = (x, y) => { let c = false; for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      if ((pts[i].y > y) !== (pts[j].y > y) && x < (pts[j].x - pts[i].x) * (y - pts[i].y) / (pts[j].y - pts[i].y) + pts[i].x) c = !c; } return c; };
    for (let i = 0; i < 160 && luces.length < 48; i++) { const x = lerp(Math.min(...xs), Math.max(...xs), Math.random()), y = lerp(Math.min(...ys), Math.max(...ys), Math.random());
      if (!dentro(x, y)) continue;
      grupo.add(cil(0.06, 0.06, 5, new THREE.MeshStandardMaterial({ color: 0x777777, metalness: 0.6 }), x, 2.5, -y, 6));
      const b = new THREE.Mesh(new THREE.SphereGeometry(0.35, 10, 8), new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false })); b.position.set(x, 5.2, -y); grupo.add(b); luces.push(b); }
    anima((t, osc) => luces.forEach((b, i) => b.material.color.setHSL(((t * 0.03) + i * 0.07) % 1, 0.9, 0.3 + 0.45 * osc).multiplyScalar(0.6 + 2.4 * osc)));
  } else if (h.tipo === 'caiman') {
    grupo.position.set(0, 0, 0);
    const { paredes, techo } = C.extruir(h.poligono, h.altura);
    const mat = C.materialFachada(0xd8b48a, 2);
    grupo.add(sombras(new THREE.Mesh(paredes, mat)), new THREE.Mesh(techo, new THREE.MeshStandardMaterial({ color: 0x3e7b45, side: THREE.DoubleSide })));
    const verde = new THREE.MeshStandardMaterial({ color: 0x2f7a3c, roughness: 0.5, metalness: 0.1 });
    const caiman = new THREE.Group(); caiman.position.set(h.x, h.altura + 1.2, -h.y); grupo.add(caiman);
    caiman.add(esf(1, verde, 0, 0, 0, 5, 0.9, 1.6), new THREE.Mesh(new THREE.ConeGeometry(1.2, 6, 12), verde).rotateZ(Math.PI / 2).translateY(-7.5));
    caiman.add(new THREE.Mesh(new THREE.BoxGeometry(4, 0.8, 1.6), verde).translateX(6.5).translateY(-0.1));
    for (const [dx, dz] of [[-2.5, 1.5], [2.5, 1.5], [-2.5, -1.5], [2.5, -1.5]]) caiman.add(cil(0.35, 0.3, 1.4, verde, dx, -0.8, dz));
    for (let i = 0; i < 14; i++) caiman.add(new THREE.Mesh(new THREE.ConeGeometry(0.25, 0.6, 5), verde).translateX(-4 + i * 0.6).translateY(0.85));
    etiquetaHito(h, h.altura + 14, '#c9f7c1');
  } else if (h.tipo === 'mall') {
    grupo.position.set(0, 0, 0);
    const { paredes, techo } = C.extruir(h.poligono, h.altura);
    grupo.add(sombras(new THREE.Mesh(paredes, C.materialFachada(0xb9cbd8, 0))), new THREE.Mesh(techo, new THREE.MeshStandardMaterial({ color: 0x9fa4aa, roughness: 0.8, side: THREE.DoubleSide })));
    if (h.fachada) pantallas(grupo, h);
    etiquetaHito(h, h.altura + 10, '#ffffff');
  } else if (h.tipo === 'ventana_mundo') {
    ventanaAlMundo(grupo, h);
  } else if (h.tipo === 'aleta_tiburon' || h.tipo === 'ventana_campeones') {
    aletaTiburon(grupo, h);
  } else if (h.tipo === 'puerta_oro') {
    puertaDeOro(grupo, h);
  }
  return grupo;
}

// ------------------------------------------------ Ventana al Mundo (glorieta de la Vía 40 con Circunvalar)
function ventanaAlMundo(grupo, h) {
  grupo.position.set(0, 0, 0);
  const { c, ang } = centroYAngulo(h);
  const H = h.altura, W = 22, p = 4.2, prof = 4.2;
  // mosaico de triángulos de colores (los colores del Carnaval) y torre de vidrio azul
  const mosaico = C.lienzoTextura(256, 1024, (g, w, hh) => {
    const s = 32; for (let y = 0; y < hh; y += s) for (let x = 0; x < w; x += s) for (const k of [0, 1]) {
      g.fillStyle = `hsl(${[350, 45, 200, 130, 280, 20, 55, 185][Math.floor(Math.random() * 8)]},${70 + Math.random() * 25}%,${45 + Math.random() * 20}%)`;
      g.beginPath(); if (k) { g.moveTo(x, y); g.lineTo(x + s, y); g.lineTo(x, y + s); } else { g.moveTo(x + s, y); g.lineTo(x + s, y + s); g.lineTo(x, y + s); } g.fill();
    }
    g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 2; for (let y = 0; y < hh; y += s) for (let x = 0; x < w; x += s) { g.beginPath(); g.moveTo(x + s, y); g.lineTo(x, y + s); g.stroke(); g.strokeRect(x, y, s, s); }
  });
  mosaico.wrapS = mosaico.wrapT = THREE.RepeatWrapping;
  const matMosaico = new THREE.MeshStandardMaterial({ map: mosaico, emissive: 0xffffff, emissiveMap: mosaico, emissiveIntensity: 0.0, roughness: 0.25, metalness: 0.2 });
  const azul = C.lienzoTextura(128, 512, (g, w, hh) => {
    const gr = g.createLinearGradient(0, 0, w, 0); gr.addColorStop(0, '#0b3d91'); gr.addColorStop(0.5, '#1f6fe0'); gr.addColorStop(1, '#0a3478');
    g.fillStyle = gr; g.fillRect(0, 0, w, hh); g.fillStyle = 'rgba(200,230,255,.35)';
    for (let y = 0; y < hh; y += 16) g.fillRect(0, y, w, 2); for (let x = 0; x < w; x += 32) g.fillRect(x, 0, 2, hh);
  });
  const matAzul = new THREE.MeshStandardMaterial({ map: azul, emissive: 0x2b7bff, emissiveIntensity: 0, roughness: 0.06, metalness: 0.85 });
  const marco = new THREE.Group(); marco.position.set(c.x, 0, -c.y); marco.rotation.y = ang; grupo.add(marco);
  const pilarIzq = new THREE.Mesh(new THREE.BoxGeometry(p, H, prof), matMosaico); pilarIzq.position.set(-(W - p) / 2, H / 2, 0);
  const pilarDer = new THREE.Mesh(new THREE.BoxGeometry(p, H * 1.04, prof), matAzul); pilarDer.position.set((W - p) / 2, H * 0.52, 0);
  const dintel = new THREE.Mesh(new THREE.BoxGeometry(W, H * 0.13, prof), matMosaico); dintel.position.set(0, H * 0.935, 0);
  const base = new THREE.Mesh(new THREE.BoxGeometry(W + 2, 1.2, prof + 3), piedra); base.position.y = 0.6;
  marco.add(sombras(pilarIzq), sombras(pilarDer), sombras(dintel), base);
  pilarIzq.geometry.attributes.uv.array.forEach((v, i, a) => { a[i] = i % 2 ? v * 4 : v; }); pilarIzq.geometry.attributes.uv.needsUpdate = true;
  // glorieta: jardín circular con borde
  const isla = new THREE.Mesh(new THREE.CircleGeometry(19, 48), new THREE.MeshStandardMaterial({ color: 0x5f9a4a, roughness: 0.95 }));
  isla.rotation.x = -Math.PI / 2; isla.position.set(c.x, 0.2, -c.y); grupo.add(isla);
  const luzA = reflector(marco, -(W - p) / 2, 0, H, 0xffd8f0, 4.5), luzB = reflector(marco, (W - p) / 2, 0, H, 0x5aa0ff, 4.5);
  C.animados.push((t, osc) => {
    matMosaico.emissiveIntensity = 0.04 + 0.8 * osc * (0.85 + 0.15 * Math.sin(t * 1.3));
    matAzul.emissiveIntensity = 0.9 * osc * (0.75 + 0.25 * Math.sin(t * 0.8));
    matAzul.emissive.setHSL(0.6 + 0.03 * Math.sin(t * 0.3), 1, 0.5);
    luzA.opacity = 0.1 * osc; luzB.opacity = 0.13 * osc;
  });
  etiquetaHito(h, H + 10, '#ffffff');
}

// ------------------------------------------------ Aleta del Tiburón · Ventana de Campeones
function aletaTiburon(grupo, h) {
  grupo.position.set(0, 0, 0);
  const { c, ang } = centroYAngulo(h);
  const H = h.altura, L = 22;
  // silueta de aleta dorsal: borde de ataque convexo, punta hacia atrás, borde de fuga cóncavo
  const s = new THREE.Shape(); s.moveTo(-L / 2, 0); s.quadraticCurveTo(-L * 0.2, H * 0.72, L * 0.34, H);
  s.quadraticCurveTo(L * 0.22, H * 0.38, L / 2, 0); s.lineTo(-L / 2, 0);
  const g = new THREE.ExtrudeGeometry(s, { depth: 3.2, bevelEnabled: true, bevelThickness: 0.9, bevelSize: 0.5, bevelSegments: 4, curveSegments: 36 });
  g.translate(0, 0, -1.6);
  const pos = g.attributes.position, uv = new Float32Array(pos.count * 2);
  for (let i = 0; i < pos.count; i++) {  // se adelgaza hacia la punta y lleva UV planas para los paneles LED
    const x = pos.getX(i), y = pos.getY(i); pos.setZ(i, pos.getZ(i) * (1 - 0.82 * Math.min(1, y / H)));
    uv[2 * i] = (x + L / 2) / L; uv[2 * i + 1] = y / H;
  }
  g.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); g.computeVertexNormals();
  // paneles de vidrio de día; de noche, show LED animado en un lienzo
  const cv = document.createElement('canvas'); cv.width = 256; cv.height = 256; const gx = cv.getContext('2d');
  const led = new THREE.CanvasTexture(cv); led.colorSpace = THREE.SRGBColorSpace;
  const panel = C.lienzoTextura(256, 256, (q, w, hh) => { q.fillStyle = '#9fb3c4'; q.fillRect(0, 0, w, hh);
    for (let y = 0; y < hh; y += 16) for (let x = 0; x < w; x += 16) { q.fillStyle = `rgba(${170 + Math.random() * 40},${190 + Math.random() * 40},${210 + Math.random() * 30},1)`; q.fillRect(x + 1, y + 1, 14, 14); } });
  const mat = new THREE.MeshStandardMaterial({ map: panel, emissive: 0xffffff, emissiveMap: led, emissiveIntensity: 0, roughness: 0.12, metalness: 0.7 });
  const aleta = sombras(new THREE.Mesh(g, mat)); aleta.position.set(c.x, 0, -c.y); aleta.rotation.y = ang; grupo.add(aleta);
  const isla = new THREE.Mesh(new THREE.CircleGeometry(20, 48), new THREE.MeshStandardMaterial({ color: 0x5f9a4a, roughness: 0.95 }));
  isla.rotation.x = -Math.PI / 2; isla.position.set(c.x, 0.2, -c.y); grupo.add(isla);
  const pedestal = new THREE.Mesh(new THREE.CylinderGeometry(13, 13.5, 1.0, 48), piedra); pedestal.position.set(c.x, 0.5, -c.y); grupo.add(pedestal);
  let ultimo = -1;
  C.animados.push((t, osc) => {
    mat.emissiveIntensity = 0.02 + 0.85 * osc;
    const k = Math.floor(t * 10); if (k === ultimo || osc < 0.05) return; ultimo = k;
    const fase = Math.floor(t / 12) % 3, W = 256;
    if (fase === 0) {  // franjas rojas y blancas del Junior, en diagonal y en movimiento
      for (let x = -W; x < W * 2; x += 32) { gx.fillStyle = (Math.floor(x / 32) % 2) ? '#ffffff' : '#d4001c';
        gx.beginPath(); const d = (t * 40) % 64; gx.moveTo(x + d, W); gx.lineTo(x + d + 32, W); gx.lineTo(x + d + 32 + W * 0.6, 0); gx.lineTo(x + d + W * 0.6, 0); gx.fill(); }
    } else if (fase === 1) {  // tricolor de Colombia que sube y ondea
      const o = Math.sin(t * 2) * 10; gx.fillStyle = '#c8102e'; gx.fillRect(0, 0, W, W);
      gx.fillStyle = '#0033a0'; gx.fillRect(0, 0, W, W * 0.5 + o); gx.fillStyle = '#ffd100'; gx.fillRect(0, 0, W, W * 0.25 + o * 0.5);
    } else {  // destellos blancos y azules de "agua"
      gx.fillStyle = '#04122e'; gx.fillRect(0, 0, W, W);
      for (let i = 0; i < 90; i++) { const x = (i * 53 + t * 30) % W, y = (i * 97 + Math.sin(t + i) * 40 + W) % W; gx.fillStyle = i % 3 ? '#4fc3ff' : '#ffffff'; gx.fillRect(x, y, 10, 10); }
    }
    gx.strokeStyle = 'rgba(0,0,0,.35)'; gx.lineWidth = 2; for (let i = 0; i <= W; i += 16) { gx.beginPath(); gx.moveTo(i, 0); gx.lineTo(i, W); gx.moveTo(0, i); gx.lineTo(W, i); gx.stroke(); }
    led.needsUpdate = true;
  });
  etiquetaHito(h, H + 10, '#ffffff');
}

// ------------------------------------------------ Centro de Eventos Puerta de Oro (Vía 40)
function puertaDeOro(grupo, h) {
  grupo.position.set(0, 0, 0);
  // el polígono de OSM es el predio: plazoleta clara; los edificios del predio llevan lamas doradas
  const pos = [], idx = []; C.poligono(pos, idx, h.poligono, 0.1);
  const plaza = C.malla(pos, idx, new THREE.MeshStandardMaterial({ color: 0xd9d2c3, roughness: 0.75, side: THREE.DoubleSide })); plaza.receiveShadow = true; grupo.add(plaza);
  const lamas = C.lienzoTextura(256, 256, (g, w, hh) => {
    g.fillStyle = '#20262c'; g.fillRect(0, 0, w, hh);
    for (let x = 0; x < w; x += 16) { const gr = g.createLinearGradient(x, 0, x + 10, 0); gr.addColorStop(0, '#8a6417'); gr.addColorStop(0.5, '#f1c75b'); gr.addColorStop(1, '#9c741f');
      g.fillStyle = gr; g.fillRect(x, 0, 10, hh); }
  });
  lamas.wrapS = lamas.wrapT = THREE.RepeatWrapping;
  const brillo = C.lienzoTextura(64, 256, (g, w, hh) => { const gr = g.createLinearGradient(0, hh, 0, 0); gr.addColorStop(0, '#ffcf5a'); gr.addColorStop(0.55, '#7a5410'); gr.addColorStop(1, '#1a1206'); g.fillStyle = gr; g.fillRect(0, 0, w, hh); });
  const mat = new THREE.MeshStandardMaterial({ map: lamas, metalness: 0.75, roughness: 0.3, emissive: 0xffffff, emissiveMap: brillo, emissiveIntensity: 0 });
  const techoMat = new THREE.MeshStandardMaterial({ color: 0xe9e4da, roughness: 0.6, side: THREE.DoubleSide });
  const edificios = h.edificios?.length ? h.edificios : [[h.altura, '', h.poligono]];
  for (const [alto, , plano] of edificios) {
    const H = Math.max(alto, 14); const { paredes, techo } = C.extruir(plano, H);
    const uv = paredes.attributes.uv.array; for (let i = 1; i < uv.length; i += 2) uv[i] = uv[i] * 3.1 / H;  // brillo de abajo hacia arriba
    grupo.add(sombras(new THREE.Mesh(paredes, mat)), new THREE.Mesh(techo, techoMat));
  }
  const anima = [];
  if (h.fachada) {  // portal dorado frente a la Vía 40, con el nombre
    const [x1, y1, x2, y2] = h.fachada; const dx = x2 - x1, dy = y2 - y1, Lf = Math.hypot(dx, dy);
    let nx = dy / Lf, ny = -dx / Lf; if (((x1 + x2) / 2 - h.x) * nx + ((y1 + y2) / 2 - h.y) * ny < 0) { nx = -nx; ny = -ny; }
    const oro = new THREE.MeshStandardMaterial({ color: 0xd4a437, metalness: 0.95, roughness: 0.22, emissive: 0xffb02e, emissiveIntensity: 0 });
    const portal = new THREE.Group(); const Wp = Math.max(26, Lf), Hp = h.altura + 8;
    portal.position.set((x1 + x2) / 2 + nx * 9, 0, -((y1 + y2) / 2 + ny * 9)); portal.rotation.y = Math.atan2(dy, dx); grupo.add(portal);
    portal.add(sombras(new THREE.Mesh(new THREE.BoxGeometry(2.2, Hp, 2.2), oro).translateX(-Wp / 2).translateY(Hp / 2)));
    portal.add(sombras(new THREE.Mesh(new THREE.BoxGeometry(2.2, Hp, 2.2), oro).translateX(Wp / 2).translateY(Hp / 2)));
    portal.add(sombras(new THREE.Mesh(new THREE.BoxGeometry(Wp + 2.2, 3.2, 2.6), oro).translateY(Hp)));
    const letrero = C.lienzoTextura(1024, 128, (g, w, hh) => { g.fillStyle = '#1a1206'; g.fillRect(0, 0, w, hh); g.fillStyle = '#ffd35a'; g.font = '800 84px Segoe UI, sans-serif';
      g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText('PUERTA DE ORO', w / 2, hh / 2 + 4); });
    const cartel = new THREE.Mesh(new THREE.PlaneGeometry(Wp * 0.8, Wp * 0.1), new THREE.MeshStandardMaterial({ map: letrero, emissive: 0xffffff, emissiveMap: letrero, emissiveIntensity: 0.3 }));
    cartel.position.set(0, Hp, 1.35); portal.add(cartel);
    const cartel2 = cartel.clone(); cartel2.rotation.y = Math.PI; cartel2.position.z = -1.35; portal.add(cartel2);
    const luz = reflector(portal, 0, 0, Hp, 0xffc04d, Wp * 0.45);
    anima.push((osc) => { oro.emissiveIntensity = 0.55 * osc; cartel.material.emissiveIntensity = 0.3 + 1.6 * osc; luz.opacity = 0.09 * osc; });
  }
  C.animados.push((t, osc) => { mat.emissiveIntensity = 0.9 * osc; anima.forEach((f) => f(osc)); });
  etiquetaHito(h, h.altura + 16, '#ffe08a');
}

// ------------------------------------------------ pantallas LED tipo Times Square (sin marcas)
const MENSAJES = [
  ['BARRANQUILLA', 'Puerta de Oro de Colombia', ['#ff2d75', '#ffb000']],
  ['¡QUIEN LO VIVE', 'ES QUIEN LO GOZA!', ['#00c2ff', '#7b2bff']],
  ['CARNAVAL', 'Patrimonio de la Humanidad', ['#ffde00', '#ff2d2d']],
  ['__RELOJ__', 'Calle 98 · Buenavista', ['#0f2027', '#2c5364']],
  ['SIMULACIÓN', 'multiagente · SUMO + DQN', ['#11998e', '#38ef7d']],
  ['GRAN MALECÓN', 'del Río Magdalena', ['#f857a6', '#ff5858']],
  ['JUNIOR', 'Tu Papá · Barranquilla', ['#d4001c', '#ffffff']],
];
const pantallasActivas = [];
function crearPantalla(ancho, alto, desfase) {
  const cv = document.createElement('canvas'); cv.width = 512; cv.height = Math.round(512 * alto / ancho);
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  pantallasActivas.push({ cv, g: cv.getContext('2d'), tex, desfase, ultimo: -1 });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(ancho, alto), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false, fog: false }));
  m.userData.pantalla = true; return m;
}
export function dibujarPantallas(t, hora, osc) {
  for (const p of pantallasActivas) {
    const k = Math.floor((t * 8) % 1e9); if (k === p.ultimo) continue; p.ultimo = k;
    const { g, cv } = p, W = cv.width, H = cv.height;
    const idx = Math.floor((t / 5 + p.desfase)) % MENSAJES.length, [t1, t2, [c1, c2]] = MENSAJES[idx];
    const gr = g.createLinearGradient(0, 0, W, H); gr.addColorStop(0, c1); gr.addColorStop(1, c2); g.fillStyle = gr; g.fillRect(0, 0, W, H);
    g.globalAlpha = 0.25; for (let i = 0; i < 12; i++) { g.fillStyle = i % 2 ? '#fff' : '#000'; g.beginPath(); g.arc((i * 97 + t * 60) % W, (i * 53) % H, 6 + (i % 5) * 4, 0, 7); g.fill(); } g.globalAlpha = 1;
    const hh = Math.floor(hora), mm = Math.floor((hora - hh) * 60);
    const titulo = t1 === '__RELOJ__' ? `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}  31 °C` : t1;
    g.fillStyle = c2 === '#ffffff' ? '#d4001c' : '#fff'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.shadowColor = 'rgba(0,0,0,.5)'; g.shadowBlur = 8;
    g.font = `800 ${Math.round(H * 0.3)}px Segoe UI, sans-serif`; g.fillText(titulo, W / 2, H * 0.42, W * 0.92);
    g.font = `600 ${Math.round(H * 0.12)}px Segoe UI, sans-serif`; g.fillText(t2, W / 2, H * 0.72, W * 0.92);
    g.shadowBlur = 0; g.fillStyle = 'rgba(0,0,0,.55)'; g.fillRect(0, H * 0.86, W, H * 0.14);
    g.fillStyle = '#ffd34f'; g.font = `600 ${Math.round(H * 0.08)}px Segoe UI, sans-serif`; g.textAlign = 'left';
    g.fillText('  BARRANQUILLA · GRAN MALECÓN · VÍA 40 · CALLE 98 · BUENAVISTA · PLAZA DEL PARQUE ·  ', W - ((t * 90) % (W * 2.2)), H * 0.93);
    // de día la pantalla se ve más apagada por el sol
    if (osc < 0.5) { g.fillStyle = `rgba(255,255,255,${0.12 * (1 - osc * 2)})`; g.fillRect(0, 0, W, H); }
    p.tex.needsUpdate = true;
  }
}
function pantallas(grupo, h) {
  const [x1, y1, x2, y2] = h.fachada; const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy);
  let nx = dy / L, ny = -dx / L;
  if (((x1 + x2) / 2 - h.x) * nx + ((y1 + y2) / 2 - h.y) * ny < 0) { nx = -nx; ny = -ny; }
  const grande = h.id === 'bv1';
  const ancho = Math.min(L * 0.85, grande ? 38 : 22), alto = grande ? 14 : 8;
  const pantalla = crearPantalla(ancho, alto, pantallasActivas.length * 2.37 + 0.5);
  pantalla.position.set((x1 + x2) / 2 + nx * 0.6, Math.max(alto / 2 + 3, h.altura * 0.55), -((y1 + y2) / 2 + ny * 0.6));
  pantalla.lookAt(pantalla.position.x + nx, pantalla.position.y, pantalla.position.z - ny);
  grupo.add(pantalla);
  if (grande) {
    for (const s of [-1, 1]) { const p2 = crearPantalla(12, 18, pantallasActivas.length * 2.37 + 1.3);
      const px = (x1 + x2) / 2 + s * (dx / L) * (ancho / 2 + 7) + nx * 0.6, py = (y1 + y2) / 2 + s * (dy / L) * (ancho / 2 + 7) + ny * 0.6;
      p2.position.set(px, h.altura * 0.6 + 4, -py); p2.lookAt(px + nx, h.altura * 0.6 + 4, -py - ny); grupo.add(p2); }
  }
}

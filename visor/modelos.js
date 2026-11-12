// Modelos 3D procedurales del visor: vehículos, personas y puestos de vendedores.
//
// Los carros se construyen extruyendo su perfil lateral (silueta real de cada modelo)
// con biselado, más vidrios, ruedas, luces y placas. Cada modelo devuelve cuatro
// geometrías que se dibujan como InstancedMesh separados:
//   pintura (toma el color de cada instancia), vidrio, detalle (llantas, rines,
//   plásticos, placas) y luces (faros y stops, que se encienden de noche).
// Convención: el frente del vehículo está en z = 0 y la cola en z = +L (SUMO ubica el
// vehículo por su parachoques delantero); el ancho va en x centrado y la altura en y.
// No se usan logos ni marcas: son siluetas inspiradas en cada modelo.
import * as THREE from 'three';

// ------------------------------------------------------------------ utilidades
function aNoIndexada(g) { const n = g.index ? g.toNonIndexed() : g; if (!n.attributes.normal) n.computeVertexNormals(); return n; }
export function parte(g, color) {
  const n = aNoIndexada(g); const c = new THREE.Color(color); const k = n.attributes.position.count;
  const col = new Float32Array(k * 3); for (let i = 0; i < k; i++) { col[3 * i] = c.r; col[3 * i + 1] = c.g; col[3 * i + 2] = c.b; }
  n.setAttribute('color', new THREE.BufferAttribute(col, 3)); n.deleteAttribute('uv'); return n;
}
export function fusionar(partes) {
  const pos = [], nor = [], col = [];
  for (const g of partes) {
    if (!g) continue;
    pos.push(...g.attributes.position.array); nor.push(...g.attributes.normal.array); col.push(...g.attributes.color.array);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.computeBoundingSphere(); return g;
}
export const caja = (w, h, l, x, y, z, color = 0xffffff) => parte(new THREE.BoxGeometry(w, h, l).translate(x, y, z), color);
const cilX = (r, w, x, y, z, color, seg = 14) => parte(new THREE.CylinderGeometry(r, r, w, seg).rotateZ(Math.PI / 2).translate(x, y, z), color);
const cilY = (r1, r2, h, x, y, z, color, seg = 10) => parte(new THREE.CylinderGeometry(r1, r2, h, seg).translate(x, y + h / 2, z), color);
const esfera = (r, x, y, z, color, sx = 1, sy = 1, sz = 1) => parte(new THREE.SphereGeometry(r, 12, 8).scale(sx, sy, sz).translate(x, y, z), color);

// Extruye una silueta lateral [[u, v], ...] (u = metros desde el frente, v = altura)
function perfil(puntos, ancho, bisel = 0.07, color = 0xffffff, curva = 4) {
  const s = new THREE.Shape(); puntos.forEach(([u, v], i) => (i ? s.lineTo(-u, v) : s.moveTo(-u, v)));
  const prof = Math.max(0.05, ancho - 2 * bisel);
  const g = new THREE.ExtrudeGeometry(s, { depth: prof, bevelEnabled: bisel > 0, bevelThickness: bisel, bevelSize: bisel * 0.8, bevelSegments: curva, curveSegments: 6 });
  g.rotateY(Math.PI / 2); g.translate(-prof / 2, 0, 0);
  return parte(g, color);
}
// Vidrios: polígonos de ventana un poco más anchos que la carrocería (se ven por los lados
// y su borde inclinado forma el parabrisas y el vidrio trasero)
function vidrios(poligonos, ancho, color = 0x1a242e) { return poligonos.map((p) => perfil(p, ancho + 0.05, 0, color)); }
function ruedas(r, ancho, ejes, W, opciones = {}) {
  const { rin = 0x9aa0a6, llanta = 0x161616, w = 0.24, rinR = 0.62 } = opciones; const out = [];
  for (const z of ejes) for (const s of [-1, 1]) {
    const x = s * (W / 2 - w / 2 + 0.03);
    out.push(cilX(r, w, x, r, z, llanta, 18), cilX(r * rinR, w + 0.03, x, r, z, rin, 12), cilX(r * 0.18, w + 0.06, x, r, z, 0x2a2a2a, 8));
  }
  return out;
}
function placa(z, y, publico = false, atras = true) {  // placas colombianas: amarillas (particular) o blancas (servicio público)
  return [caja(0.52, 0.17, 0.03, 0, y, z + (atras ? 0.02 : -0.02), publico ? 0xf2f2f2 : 0xf5c518), caja(0.4, 0.05, 0.035, 0, y, z + (atras ? 0.025 : -0.025), 0x222222)];
}
function espejos(W, z, y) { return [caja(0.2, 0.12, 0.1, -W / 2 - 0.08, y, z), caja(0.2, 0.12, 0.1, W / 2 + 0.08, y, z)]; }
const FARO = 0xfff4dc, STOP = 0xd8141c, DIREC = 0xff9a1a, NEGRO = 0x141414, GRIS = 0x3a3d40, CROMO = 0xc9ced3;

// ------------------------------------------------------------------ vehículos
function porsche911() {  // Porsche 911 GT (inspiración): faros redondos, cola fastback, alerón GT
  const L = 4.57, W = 1.86;
  const sil = [[0.02, 0.3], [0.0, 0.5], [0.12, 0.66], [0.55, 0.74], [1.15, 0.84], [1.6, 1.02], [2.05, 1.26], [2.55, 1.28],
    [3.05, 1.18], [3.75, 0.98], [4.4, 0.86], [4.57, 0.76], [4.55, 0.32], [3.95, 0.24], [0.6, 0.24]];
  const pintura = [perfil(sil, W, 0.11, 0xffffff, 5), ...espejos(W, 1.75, 0.98),
    caja(0.05, 0.5, 0.05, -0.62, 1.12, 4.22), caja(0.05, 0.5, 0.05, 0.62, 1.12, 4.22)];
  const vidrio = vidrios([[[1.6, 0.98], [2.06, 1.22], [2.52, 1.24], [2.6, 0.98]], [[2.66, 0.98], [2.56, 1.22], [3.0, 1.15], [3.55, 0.98]]], W);
  const detalle = [...ruedas(0.34, W, [1.08, 3.72], W + 0.04, { rin: 0x2b2b2b, w: 0.28 }),
    caja(1.85, 0.06, 0.42, 0, 1.38, 4.25, NEGRO),                                  // alerón GT
    caja(1.2, 0.12, 0.08, 0, 0.36, 0.02, NEGRO), caja(1.5, 0.08, 0.2, 0, 0.27, 0.15, NEGRO),  // tomas y labio
    caja(1.1, 0.14, 0.06, 0, 0.42, 4.58, NEGRO), ...placa(4.56, 0.48), ...placa(0.0, 0.42, false, false)];
  const luces = [esfera(0.15, -0.6, 0.72, 0.38, FARO, 1, 1.1, 0.6), esfera(0.15, 0.6, 0.72, 0.38, FARO, 1, 1.1, 0.6),
    caja(1.72, 0.06, 0.04, 0, 0.83, 4.5, STOP), caja(0.22, 0.1, 0.04, -0.72, 0.8, 4.49, STOP), caja(0.22, 0.1, 0.04, 0.72, 0.8, 4.49, STOP),
    caja(0.16, 0.05, 0.05, -0.68, 0.5, 0.0, DIREC), caja(0.16, 0.05, 0.05, 0.68, 0.5, 0.0, DIREC)];
  return { L, W, pintura, vidrio, detalle, luces };
}
function cybertruck() {  // Cybertruck (inspiración): triángulo de acero, barra de luz de lado a lado
  const L = 5.68, W = 2.0;
  const sil = [[0.0, 0.48], [0.0, 0.98], [2.35, 1.8], [5.68, 1.26], [5.68, 0.5], [4.9, 0.42], [0.7, 0.42]];
  const pintura = [perfil(sil, W, 0.025, 0xffffff, 1), ...espejos(W, 1.75, 1.3)];
  const vidrio = vidrios([[[1.05, 1.32], [2.3, 1.76], [3.55, 1.6], [3.4, 1.3]]], W);
  const detalle = [...ruedas(0.43, W, [1.15, 4.55], W + 0.06, { rin: 0x8c9196, w: 0.32, rinR: 0.7 }),
    caja(W + 0.08, 0.18, 4.9, 0, 0.5, 2.85, 0x2c2e30), ...placa(5.68, 0.62)];
  const luces = [caja(W - 0.1, 0.035, 0.04, 0, 0.97, 0.02, FARO), caja(W - 0.1, 0.05, 0.04, 0, 1.24, 5.68, STOP)];
  return { L, W, pintura, vidrio, detalle, luces };
}
function modeloY() {  // Model Y (inspiración): crossover liso con techo de vidrio
  const L = 4.75, W = 1.92;
  const sil = [[0.0, 0.42], [0.02, 0.62], [0.28, 0.78], [1.0, 0.93], [1.55, 1.18], [2.15, 1.6], [3.3, 1.6], [4.1, 1.38],
    [4.62, 1.14], [4.75, 1.0], [4.73, 0.42], [4.1, 0.3], [0.65, 0.3]];
  const pintura = [perfil(sil, W, 0.12, 0xffffff, 5), ...espejos(W, 1.65, 1.08)];
  const vidrio = vidrios([[[1.5, 1.08], [2.12, 1.62], [3.32, 1.62], [3.95, 1.36], [4.1, 1.08]]], W);
  const detalle = [...ruedas(0.36, W, [1.0, 3.92], W, { rin: 0x3a3d42, w: 0.26 }), caja(1.6, 0.1, 0.06, 0, 0.36, 0.02, NEGRO),
    caja(0.04, 0.42, 0.05, -W / 2 - 0.02, 1.25, 2.72, NEGRO), caja(0.04, 0.42, 0.05, W / 2 + 0.02, 1.25, 2.72, NEGRO), ...placa(4.74, 0.62)];
  const luces = [caja(0.42, 0.05, 0.06, -0.62, 0.8, 0.22, FARO), caja(0.42, 0.05, 0.06, 0.62, 0.8, 0.22, FARO),
    caja(0.5, 0.07, 0.04, -0.66, 1.1, 4.72, STOP), caja(0.5, 0.07, 0.04, 0.66, 1.1, 4.72, STOP)];
  return { L, W, pintura, vidrio, detalle, luces };
}
function mustang() {  // Mustang (inspiración): capó largo, fastback y stops de tres barras
  const L = 4.8, W = 1.92;
  const sil = [[0.0, 0.38], [0.0, 0.72], [0.25, 0.86], [1.7, 0.98], [2.15, 1.18], [2.6, 1.38], [3.1, 1.38], [3.9, 1.12],
    [4.5, 1.06], [4.62, 1.1], [4.8, 0.98], [4.78, 0.36], [4.2, 0.3], [0.6, 0.3]];
  const pintura = [perfil(sil, W, 0.09, 0xffffff, 4), ...espejos(W, 2.25, 1.1)];
  const vidrio = vidrios([[[2.1, 1.08], [2.6, 1.34], [3.08, 1.34], [3.75, 1.1]]], W);
  const detalle = [...ruedas(0.36, W, [1.25, 3.95], W, { rin: 0x2a2a2a, w: 0.27 }), caja(1.2, 0.22, 0.06, 0, 0.6, 0.0, NEGRO),
    caja(1.5, 0.08, 0.22, 0, 0.28, 0.12, NEGRO), ...placa(4.79, 0.6), ...placa(0.0, 0.4, false, false)];
  const luces = [caja(0.34, 0.08, 0.06, -0.66, 0.76, 0.06, FARO), caja(0.34, 0.08, 0.06, 0.66, 0.76, 0.06, FARO)];
  for (const s of [-1, 1]) for (let k = 0; k < 3; k++) luces.push(caja(0.06, 0.2, 0.04, s * (0.5 + k * 0.1), 0.86, 4.79, STOP));
  return { L, W, pintura, vidrio, detalle, luces };
}
function pradoTXL() {  // Toyota Prado TXL (inspiración): camioneta cuadrada y alta, rieles de techo
  const L = 4.84, W = 1.9;
  const sil = [[0.0, 0.45], [0.0, 1.0], [0.1, 1.12], [1.2, 1.18], [1.85, 1.82], [4.75, 1.84], [4.84, 1.7], [4.84, 0.48], [4.2, 0.4], [0.6, 0.4]];
  const pintura = [perfil(sil, W, 0.08, 0xffffff, 3), ...espejos(W, 1.95, 1.3)];
  const vidrio = vidrios([[[1.62, 1.22], [1.9, 1.76], [2.85, 1.76], [2.85, 1.22]], [[2.95, 1.22], [2.95, 1.76], [4.7, 1.76], [4.72, 1.22]]], W);
  const detalle = [...ruedas(0.39, W, [1.0, 3.95], W + 0.06, { rin: 0xb5b9bd, w: 0.28 }),
    caja(1.35, 0.3, 0.06, 0, 0.82, 0.0, CROMO), caja(W + 0.04, 0.2, 0.25, 0, 0.5, 0.05, GRIS), caja(W + 0.04, 0.2, 0.25, 0, 0.52, 4.8, GRIS),
    caja(0.06, 0.06, 2.6, -0.75, 1.9, 3.2, NEGRO), caja(0.06, 0.06, 2.6, 0.75, 1.9, 3.2, NEGRO), ...placa(4.86, 0.85)];
  const luces = [caja(0.42, 0.14, 0.05, -0.68, 0.98, 0.02, FARO), caja(0.42, 0.14, 0.05, 0.68, 0.98, 0.02, FARO),
    caja(0.14, 0.35, 0.05, -0.86, 1.15, 4.84, STOP), caja(0.14, 0.35, 0.05, 0.86, 1.15, 4.84, STOP)];
  return { L, W, pintura, vidrio, detalle, luces };
}
function hilux() {  // Toyota Hilux (inspiración): cabina doble y platón
  const L = 5.3, W = 1.86;
  const sil = [[0.0, 0.48], [0.0, 1.0], [0.1, 1.1], [1.3, 1.16], [1.95, 1.8], [3.25, 1.8], [3.3, 1.14], [5.3, 1.14], [5.3, 0.5], [4.6, 0.42], [0.6, 0.42]];
  const pintura = [perfil(sil, W, 0.06, 0xffffff, 3), ...espejos(W, 2.0, 1.3)];
  const vidrio = vidrios([[[1.68, 1.2], [1.98, 1.74], [2.55, 1.74], [2.55, 1.2]], [[2.62, 1.2], [2.62, 1.74], [3.2, 1.74], [3.2, 1.2]]], W);
  const detalle = [...ruedas(0.38, W, [1.05, 4.2], W + 0.06, { rin: 0xa9adb1, w: 0.27 }),
    caja(W - 0.24, 0.05, 1.9, 0, 1.15, 4.3, 0x1c1c1c),                              // fondo del platón
    caja(1.3, 0.32, 0.06, 0, 0.82, 0.0, NEGRO), caja(W + 0.04, 0.18, 0.2, 0, 0.5, 0.05, CROMO), ...placa(5.31, 0.75)];
  const luces = [caja(0.42, 0.12, 0.05, -0.66, 0.98, 0.02, FARO), caja(0.42, 0.12, 0.05, 0.66, 0.98, 0.02, FARO),
    caja(0.12, 0.38, 0.05, -0.86, 0.85, 5.3, STOP), caja(0.12, 0.38, 0.05, 0.86, 0.85, 5.3, STOP)];
  return { L, W, pintura, vidrio, detalle, luces };
}
function sedan(L = 4.5, W = 1.78, lujo = false) {  // sedán genérico (y versión de lujo más baja y larga)
  const k = L / 4.5, h = lujo ? 0.97 : 1;
  const sil = [[0.0, 0.36], [0.0, 0.66], [0.2, 0.78], [1.15 * k, 0.9 * h], [1.75 * k, 1.38 * h], [3.0 * k, 1.42 * h], [3.65 * k, 1.0 * h],
    [4.42 * k, 0.96], [4.5 * k, 0.86], [4.48 * k, 0.36], [3.9 * k, 0.28], [0.6, 0.28]];
  const pintura = [perfil(sil, W, 0.1, 0xffffff, 4), ...espejos(W, 1.65 * k, 1.0)];
  const vidrio = vidrios([[[1.38 * k, 0.98 * h], [1.75 * k, 1.36 * h], [2.38 * k, 1.38 * h], [2.38 * k, 0.98 * h]],
    [[2.45 * k, 0.98 * h], [2.45 * k, 1.38 * h], [2.98 * k, 1.38 * h], [3.55 * k, 0.98 * h]]], W);
  const detalle = [...ruedas(0.32, W, [1.05 * k, 3.6 * k], W, { rin: lujo ? 0x3d4146 : 0xa0a5aa }),
    caja(lujo ? 0.75 : 1.0, lujo ? 0.3 : 0.18, 0.06, 0, 0.56, 0.0, lujo ? 0x101010 : NEGRO), ...placa(4.5 * k, 0.55), ...placa(0, 0.38, false, false)];
  const luces = [caja(0.4, 0.09, 0.06, -0.6, 0.72, 0.08, FARO), caja(0.4, 0.09, 0.06, 0.6, 0.72, 0.08, FARO),
    caja(0.42, 0.1, 0.05, -0.6, 0.82, 4.47 * k, STOP), caja(0.42, 0.1, 0.05, 0.6, 0.82, 4.47 * k, STOP)];
  if (lujo) luces.push(caja(1.0, 0.03, 0.05, 0, 0.84, 4.48 * k, STOP));
  return { L: 4.5 * k, W, pintura, vidrio, detalle, luces };
}
function hatchback(L = 3.7, W = 1.66, taxi = false) {  // compacto (Spark, Picanto, Atos…) y el taxi amarillo
  const k = L / 3.7;
  const sil = [[0.0, 0.38], [0.0, 0.7], [0.22, 0.82], [0.85 * k, 0.9], [1.45 * k, 1.44], [3.2 * k, 1.48], [3.62 * k, 1.12], [3.7 * k, 0.9], [3.69 * k, 0.38], [3.1 * k, 0.3], [0.5, 0.3]];
  const pintura = [perfil(sil, W, 0.1, 0xffffff, 4), ...espejos(W, 1.35 * k, 1.02)];
  const vidrio = vidrios([[[1.08 * k, 0.98], [1.45 * k, 1.42], [2.15 * k, 1.44], [2.15 * k, 0.98]], [[2.22 * k, 0.98], [2.22 * k, 1.44], [3.18 * k, 1.44], [3.48 * k, 1.04], [3.48 * k, 0.98]]], W);
  const detalle = [...ruedas(0.3, W, [0.78 * k, 3.0 * k], W, { rin: 0x9a9fa4, w: 0.2 }), caja(0.9, 0.16, 0.06, 0, 0.55, 0.0, NEGRO),
    ...placa(3.7 * k, 0.55, taxi), ...placa(0, 0.4, taxi, false)];
  if (taxi) {  // aviso TAXI en el techo y franja de cuadros en las puertas
    detalle.push(caja(0.62, 0.2, 0.28, 0, 1.6, 2.3 * k, 0xf4f4f4), caja(0.64, 0.06, 0.3, 0, 1.52, 2.3 * k, 0x222222));
    for (const s of [-1, 1]) for (let i = 0; i < 12; i++) detalle.push(caja(0.02, 0.07, 0.14, s * (W / 2 + 0.035), 0.82 + (i % 2) * 0.07, 1.25 * k + i * 0.14, i % 2 ? 0x111111 : 0xf2f2f2));
  }
  const luces = [caja(0.36, 0.1, 0.06, -0.55, 0.74, 0.08, FARO), caja(0.36, 0.1, 0.06, 0.55, 0.74, 0.08, FARO),
    caja(0.16, 0.3, 0.05, -0.68, 1.0, 3.68 * k, STOP), caja(0.16, 0.3, 0.05, 0.68, 1.0, 3.68 * k, STOP)];
  if (taxi) luces.push(caja(0.5, 0.12, 0.3, 0, 1.65, 2.3 * k, 0xfff2a0));
  return { L: 3.7 * k, W, pintura, vidrio, detalle, luces };
}
function suvGenerica() {  // camioneta compacta (Duster, Tracker, CX-5…)
  const L = 4.45, W = 1.82;
  const sil = [[0.0, 0.45], [0.0, 0.8], [0.25, 0.92], [1.0, 1.02], [1.6, 1.58], [3.6, 1.62], [4.35, 1.42], [4.45, 1.2], [4.44, 0.45], [3.8, 0.36], [0.6, 0.36]];
  const pintura = [perfil(sil, W, 0.1, 0xffffff, 4), ...espejos(W, 1.75, 1.15)];
  const vidrio = vidrios([[[1.38, 1.1], [1.62, 1.54], [2.55, 1.56], [2.55, 1.1]], [[2.62, 1.1], [2.62, 1.56], [3.6, 1.56], [4.15, 1.36], [4.2, 1.1]]], W);
  const detalle = [...ruedas(0.35, W, [0.98, 3.6], W + 0.04, { rin: 0x9ea3a8, w: 0.24 }), caja(W + 0.04, 0.16, 0.2, 0, 0.45, 0.05, GRIS),
    caja(1.1, 0.24, 0.06, 0, 0.72, 0.0, NEGRO), caja(0.05, 0.05, 2.2, -0.72, 1.68, 2.6, NEGRO), caja(0.05, 0.05, 2.2, 0.72, 1.68, 2.6, NEGRO), ...placa(4.45, 0.7)];
  const luces = [caja(0.4, 0.1, 0.06, -0.62, 0.88, 0.08, FARO), caja(0.4, 0.1, 0.06, 0.62, 0.88, 0.08, FARO),
    caja(0.15, 0.3, 0.05, -0.78, 1.15, 4.43, STOP), caja(0.15, 0.3, 0.05, 0.78, 1.15, 4.43, STOP)];
  return { L, W, pintura, vidrio, detalle, luces };
}
function moto() {  // moto con conductor (casco del color de la moto)
  const L = 2.1, W = 0.8;
  const pintura = [caja(0.32, 0.26, 0.6, 0, 0.92, 0.75), caja(0.28, 0.2, 0.42, 0, 0.82, 1.38), esfera(0.16, 0, 1.78, 1.18, 0xffffff, 1, 1.05, 1.1)];
  const vidrio = [caja(0.3, 0.12, 0.04, 0, 1.16, 0.36, 0x26323d)];
  const detalle = [cilX(0.31, 0.1, 0, 0.31, 0.3, NEGRO, 16), cilX(0.31, 0.1, 0, 0.31, 1.8, NEGRO, 16), cilX(0.18, 0.12, 0, 0.31, 0.3, 0x8a8f94, 8), cilX(0.18, 0.12, 0, 0.31, 1.8, 0x8a8f94, 8),
    caja(0.1, 0.5, 0.1, 0, 0.62, 0.35, GRIS), caja(0.62, 0.04, 0.04, 0, 1.12, 0.48, NEGRO), caja(0.14, 0.12, 1.0, 0, 0.55, 1.2, GRIS),
    // conductor: torso, brazos y piernas
    caja(0.38, 0.55, 0.26, 0, 1.38, 1.2, 0x2b3a55), caja(0.1, 0.1, 0.5, -0.24, 1.32, 0.88, 0x2b3a55), caja(0.1, 0.1, 0.5, 0.24, 1.32, 0.88, 0x2b3a55),
    caja(0.13, 0.13, 0.5, -0.17, 0.98, 1.05, 0x23262b), caja(0.13, 0.13, 0.5, 0.17, 0.98, 1.05, 0x23262b),
    caja(0.12, 0.42, 0.13, -0.2, 0.7, 0.85, 0x23262b), caja(0.12, 0.42, 0.13, 0.2, 0.7, 0.85, 0x23262b),
    caja(0.3, 0.1, 0.04, 0, 1.78, 1.02, 0x101418), caja(0.2, 0.1, 0.03, 0, 0.62, 2.05, 0xf5c518)];
  const luces = [esfera(0.08, 0, 1.0, 0.3, FARO), caja(0.14, 0.06, 0.04, 0, 0.88, 1.62, STOP)];
  return { L, W, pintura, vidrio, detalle, luces };
}
function bus() {  // buseta urbana de colores vivos
  const L = 12, W = 2.5, H = 3.1;
  const pintura = [perfil([[0, 0.45], [0, 2.6], [0.25, 3.05], [11.9, 3.1], [12, 2.9], [12, 0.45]], W, 0.1, 0xffffff, 3)];
  const vidrio = [perfil([[-0.03, 1.35], [-0.03, 2.62], [0.24, 3.0], [0.4, 3.0], [0.4, 1.35]], W + 0.03, 0, 0x1d2a33),
    perfil([[1.1, 1.55], [1.1, 2.62], [11.6, 2.62], [11.6, 1.55]], W + 0.05, 0, 0x1d2a33)];
  const detalle = [...ruedas(0.5, W, [2.2, 9.6], W + 0.04, { rin: 0xc0c4c8, w: 0.32 }),
    perfil([[0.3, 1.2], [0.3, 1.35], [11.9, 1.35], [11.9, 1.2]], W + 0.06, 0, 0xffd400), perfil([[0.3, 0.95], [0.3, 1.1], [11.9, 1.1], [11.9, 0.95]], W + 0.06, 0, 0xe0202a),
    perfil([[0.2, 2.75], [0.2, 3.05], [11.9, 3.1], [11.9, 2.75]], W + 0.04, 0, 0xf2f2f2),
    caja(W + 0.02, 0.35, 0.1, 0, 0.62, 0.0, GRIS), caja(0.9, 0.06, 0.6, -0.4, 0.4, 12.0, NEGRO), ...placa(12.01, 0.85, true), ...placa(0, 0.8, true, false)];
  const luces = [caja(0.32, 0.18, 0.05, -0.95, 0.85, -0.01, FARO), caja(0.32, 0.18, 0.05, 0.95, 0.85, -0.01, FARO),
    caja(1.6, 0.25, 0.06, 0, H - 0.18, 0.12, 0xff9a1a), caja(0.2, 0.4, 0.05, -1.05, 1.0, 12.0, STOP), caja(0.2, 0.4, 0.05, 1.05, 1.0, 12.0, STOP)];
  return { L, W, pintura, vidrio, detalle, luces };
}
function camion() {  // camión de carga: cabina del color de la instancia y furgón blanco
  const L = 9, W = 2.45;
  const pintura = [perfil([[0, 0.55], [0, 2.3], [0.35, 2.75], [2.3, 2.8], [2.3, 0.55]], W, 0.08, 0xffffff, 3)];
  const vidrio = [perfil([[-0.03, 1.55], [-0.03, 2.25], [0.33, 2.68], [0.5, 2.68], [0.5, 1.55]], W + 0.03, 0, 0x1d2a33),
    perfil([[0.75, 1.6], [0.75, 2.4], [1.6, 2.4], [1.6, 1.6]], W + 0.05, 0, 0x1d2a33)];
  const detalle = [...ruedas(0.5, W, [1.3, 6.6, 7.8], W + 0.04, { rin: 0xb8bcc0, w: 0.34 }),
    caja(W + 0.05, 2.9, 6.5, 0, 2.15, 5.65, 0xe9e9e6), caja(W + 0.07, 0.2, 6.5, 0, 0.75, 5.65, 0xc0392b),
    caja(W, 0.3, 0.1, 0, 0.7, 0.0, GRIS), caja(1.4, 0.4, 0.05, 0, 1.15, 0.0, NEGRO), ...placa(8.91, 0.9, true)];
  const luces = [caja(0.3, 0.18, 0.05, -0.9, 0.95, -0.01, FARO), caja(0.3, 0.18, 0.05, 0.9, 0.95, -0.01, FARO),
    caja(0.18, 0.3, 0.05, -1.05, 1.05, 8.91, STOP), caja(0.18, 0.3, 0.05, 1.05, 1.05, 8.91, STOP)];
  return { L, W, pintura, vidrio, detalle, luces };
}

// Catálogo de modelos y paletas de pintura (colores reales de cada tipo de carro)
export const MODELOS = {
  porsche: { crear: porsche911, nombre: 'Porsche 911 GT', max: 2 },
  cybertruck: { crear: cybertruck, nombre: 'Cybertruck', paleta: [0xb8bdc2, 0xa9aeb3, 0x2b2d30], max: 40, metal: true },
  modeloY: { crear: modeloY, nombre: 'Model Y', paleta: [0xf2f3f5, 0x111214, 0x6b7077, 0xa3a9b0, 0xa8141c, 0x1d3f8a], max: 160 },
  mustang: { crear: mustang, nombre: 'Mustang', paleta: [0xc01a1a, 0x0d0d0f, 0xf2c200, 0x1f4fa6, 0x8c949c, 0xf3f3f3, 0x1f5f3a], max: 120 },
  prado: { crear: pradoTXL, nombre: 'Prado TXL', paleta: [0xf3f4f5, 0xb9bec4, 0x17181a, 0x55595e, 0x5a1a1a, 0x2c3e50], max: 160 },
  hilux: { crear: hilux, nombre: 'Hilux', paleta: [0xf4f4f4, 0xb8bcc1, 0x5f6368, 0x1b1c1e, 0x7a1d1d], max: 140 },
  sedan: { crear: () => sedan(), nombre: 'sedán', paleta: [0xd9dde2, 0xa4abb3, 0x2f363e, 0xb81d24, 0x1f4e8c, 0xf4f4f4, 0x5b6770, 0x6e2c2c, 0x7b8a5c], max: 420 },
  sedanLujo: { crear: () => sedan(4.92, 1.86, true), nombre: 'sedán de lujo', paleta: [0x0e0f11, 0xf4f5f6, 0x5a6068, 0x1b2a44, 0x9ea6ae], max: 220 },
  hatch: { crear: () => hatchback(), nombre: 'compacto', paleta: [0xe3e6ea, 0xb0b6bd, 0xc0392b, 0x2e86c1, 0x27ae60, 0xf39c12, 0x34495e, 0x8e44ad, 0xd35400], max: 420 },
  taxi: { crear: () => hatchback(3.75, 1.66, true), nombre: 'taxi', paleta: [0xffcc00, 0xffd21a, 0xf7c600], max: 320 },
  suv: { crear: suvGenerica, nombre: 'camioneta', paleta: [0xe7e9ec, 0x9aa1a8, 0x2a2f35, 0x8b1e1e, 0x2e5e8c, 0xc96a1b, 0x4b5320], max: 300 },
  moto: { crear: moto, nombre: 'moto', paleta: [0xd01f2f, 0x1f4fbf, 0x111111, 0xf2f2f2, 0x2e9e4f, 0xf2a900], max: 420 },
  bus: { crear: bus, nombre: 'buseta', paleta: [0x1e88e5, 0x43a047, 0xe53935, 0xfdd835, 0x8e24aa, 0xfb8c00, 0x00acc1], max: 90 },
  camion: { crear: camion, nombre: 'camión', paleta: [0xc0392b, 0x2471a3, 0xf2f2f2, 0x1e8449, 0xd68910], max: 90 },
};

// Elección del modelo según la clase de SUMO y el estrato de la zona (determinista por id)
function azar(id, sal) { let x = Math.sin(id * 12.9898 + sal * 78.233) * 43758.5453; return x - Math.floor(x); }
export function elegirModelo(cod, id, estrato) {
  const r = azar(id, 1), rico = estrato >= 5, medio = estrato >= 3;
  switch (cod) {
    case 1: return 'taxi';
    case 2: return 'moto';
    case 3: return 'bus';
    case 4: return 'camion';
    case 6: return rico ? (r < 0.4 ? 'modeloY' : r < 0.8 ? 'prado' : 'suv') : medio ? (r < 0.2 ? 'modeloY' : r < 0.45 ? 'prado' : 'suv') : (r < 0.1 ? 'prado' : 'suv');
    case 7: return rico && r < 0.18 ? 'cybertruck' : 'hilux';
    case 8: return 'cybertruck';
    case 5: return rico ? (r < 0.3 ? 'mustang' : r < 0.65 ? 'sedanLujo' : 'sedan') : medio ? (r < 0.1 ? 'mustang' : r < 0.3 ? 'sedanLujo' : 'sedan') : (r < 0.05 ? 'mustang' : 'sedan');
    default: return rico && r < 0.25 ? 'sedan' : 'hatch';
  }
}
export function colorModelo(clave, id) { const p = MODELOS[clave].paleta || [0xffffff]; return p[Math.floor(azar(id, 2) * p.length)]; }

// ------------------------------------------------------------------ personas
// Cuerpo articulado (piernas y brazos aparte para animar la caminata). Mira hacia -z.
export function partesPersona() {
  return {
    torso: fusionar([caja(0.4, 0.56, 0.23, 0, 1.2, 0), caja(0.36, 0.14, 0.21, 0, 0.92, 0)]),
    pierna: fusionar([caja(0.15, 0.82, 0.17, 0, -0.41, 0), caja(0.15, 0.08, 0.26, 0, -0.84, -0.05, 0x1d1d1d)]),  // pivote en la cadera
    brazo: fusionar([caja(0.1, 0.58, 0.11, 0, -0.29, 0)]),                                                     // pivote en el hombro
    cabeza: fusionar([caja(0.08, 0.08, 0.08, 0, 1.5, 0), esfera(0.115, 0, 1.62, 0, 0xffffff, 0.95, 1.1, 1.0)]),
    pelo: fusionar([esfera(0.122, 0, 1.66, 0.015, 0xffffff, 1.0, 0.85, 1.05)]),
  };
}
export const PIEL = [0x5c3b25, 0x7a4e30, 0x8d5b3a, 0xa86f48, 0xc68e62, 0xd9a47c, 0xe8bf98, 0x3e2a1c];
export const ROPA = [0xffffff, 0xf2f2f2, 0x1f4e8c, 0xd23a3a, 0xf5c518, 0x2e9e4f, 0xff7aa8, 0x7d3c98, 0x111111, 0x5dade2, 0xf39c12, 0x00a19a, 0xe74c3c, 0xbdc3c7];
export const PANTALON = [0x1f2a44, 0x2c3e50, 0x111111, 0x7f8c8d, 0xd5c4a1, 0x34495e, 0x5d6d7e, 0xffffff];
export const PELO = [0x111111, 0x1b120c, 0x2a1b10, 0x4a3020, 0x6b4a2a, 0x0d0d0d, 0x8a6a3a];

// ------------------------------------------------------------------ puestos de vendedores
function sombrilla(x, z, colores, h = 2.2, r = 1.25) {
  const out = [parte(new THREE.CylinderGeometry(0.025, 0.025, h, 5).translate(x, h / 2, z), 0x8a8a8a)];
  colores.forEach((c, i) => {  // gajos de colores
    const g = new THREE.ConeGeometry(r, 0.45, 8, 1, true, (i / colores.length) * Math.PI * 2, (Math.PI * 2) / colores.length);
    out.push(parte(g.translate(x, h + 0.1, z), c));
  });
  return out;
}
export function geometriasPuestos() {
  const fruta = [0xff3b30, 0xffcc00, 0x34c759, 0xff9500, 0xaf52de];
  const carrito = fusionar([caja(1.2, 0.6, 0.7, 0, 0.75, 0, 0x2f80ed), caja(1.25, 0.08, 0.75, 0, 1.08, 0, 0xdfe6ee),
    ...[[-0.45, -0.2], [-0.15, 0.15], [0.2, -0.15], [0.45, 0.2]].map(([x, z], i) => esfera(0.12, x, 1.2, z, fruta[i % fruta.length])),
    cilX(0.2, 0.06, -0.62, 0.2, 0, 0x222222), cilX(0.2, 0.06, 0.62, 0.2, 0, 0x222222), caja(0.05, 0.05, 0.6, 0.85, 0.9, 0, 0x777777),
    ...sombrilla(0, 0, [0xff3b30, 0xffffff, 0x0a84ff, 0xffcc00, 0xff3b30, 0xffffff, 0x0a84ff, 0xffcc00])]);
  const toldo = fusionar([...[[-1, -0.7], [1, -0.7], [-1, 0.7], [1, 0.7]].map(([x, z]) => caja(0.05, 2.2, 0.05, x, 1.1, z, 0x9a9a9a)),
    caja(2.3, 0.06, 1.7, 0, 2.25, 0, 0xe63946), caja(2.3, 0.25, 0.03, 0, 2.1, -0.86, 0xffffff), caja(1.9, 0.08, 1.0, 0, 0.85, 0, 0x8d6e4f),
    ...Array.from({ length: 10 }, (_, i) => esfera(0.11, -0.8 + (i % 5) * 0.4, 0.98, -0.25 + Math.floor(i / 5) * 0.4, fruta[i % fruta.length])),
    caja(0.6, 0.35, 0.4, 0.6, 0.18, 0.5, 0x1d6fd1)]);
  const tinto = fusionar([caja(0.7, 0.5, 0.45, 0, 0.55, 0, 0xc0392b), cilX(0.14, 0.05, -0.37, 0.14, 0, 0x222222), cilX(0.14, 0.05, 0.37, 0.14, 0, 0x222222),
    cilY(0.07, 0.07, 0.32, -0.18, 0.8, 0, 0xd0d4d8), cilY(0.07, 0.07, 0.32, 0.05, 0.8, 0, 0xd0d4d8), cilY(0.07, 0.07, 0.32, 0.26, 0.8, 0, 0xc8102e),
    ...sombrilla(0, 0.1, [0xffcc00, 0x0033a0, 0xc8102e, 0xffcc00, 0x0033a0, 0xc8102e], 1.9, 0.9)]);
  const kiosco = fusionar([caja(2.4, 1.0, 1.6, 0, 0.5, 0, 0xf4f1ea), caja(2.5, 0.08, 1.7, 0, 1.04, 0, 0x6d4c41),
    ...[[-1.15, -0.75], [1.15, -0.75], [-1.15, 0.75], [1.15, 0.75]].map(([x, z]) => caja(0.07, 1.4, 0.07, x, 1.75, z, 0x6d4c41)),
    parte(new THREE.ConeGeometry(1.9, 0.8, 4).rotateY(Math.PI / 4).scale(1, 1, 0.75).translate(0, 2.85, 0), 0xc0392b),
    caja(2.0, 0.35, 0.05, 0, 2.25, -0.82, 0xffd166), ...Array.from({ length: 4 }, (_, i) => cilY(0.18, 0.18, 0.5, -1.2 + i * 0.8, 0, -1.6, 0xb0b0b0, 8))]);
  return [carrito, toldo, tinto, kiosco];
}

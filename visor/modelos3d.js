// Modelos 3D externos (.glb / .gltf) para vehículos, el instructor y las personas.
//
// Se configuran en visor/modelos3d/config.json. Si el archivo no existe, o un modelo no
// carga, el visor sigue usando las figuras procedurales de modelos.js: nada se rompe.
//
// Vehículos: cada material del modelo se dibuja como un InstancedMesh (una llamada de
// dibujo por material), así que cientos de carros cuestan lo mismo que con las figuras.
// La "pintura" (el material de la carrocería) toma el color de cada carro.
//
// Personas: el visor necesita miles de personas a la vez, y three.js no instancia mallas
// con esqueleto. Por eso la animación de caminar se "hornea": se toman N poses del clip y
// cada pose se vuelve una malla instanciada; cada persona se dibuja con la pose que le
// toca en ese instante.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const CARPETA = 'modelos3d/';
const RE_PINTURA = /paint|body|carroc|pintura|exterior|car_?colou?r|chassis|shell/i;
const RE_VIDRIO = /glass|vidrio|window|ventan|windshield|parabrisas/i;

function cargador() {
  const l = new GLTFLoader();
  const draco = new DRACOLoader(); draco.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');
  l.setDRACOLoader(draco); l.setMeshoptDecoder(MeshoptDecoder);
  return l;
}

// Copia un atributo (posiblemente intercalado o cuantizado) a un Float32 simple
function plano(attr) {
  const n = attr.count, k = attr.itemSize, out = new Float32Array(n * k);
  for (let i = 0; i < n; i++) {
    out[i * k] = attr.getX(i); if (k > 1) out[i * k + 1] = attr.getY(i);
    if (k > 2) out[i * k + 2] = attr.getZ(i); if (k > 3) out[i * k + 3] = attr.getW(i);
  }
  return new THREE.BufferAttribute(out, k);
}
// Geometría limpia: position, normal, uv (y color si se pide), sin índice
function limpia(geo, posicion = null, conColor = false) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', posicion || plano(geo.attributes.position));
  if (geo.attributes.uv) g.setAttribute('uv', plano(geo.attributes.uv));
  else g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(geo.attributes.position.count * 2), 2));
  if (conColor && geo.attributes.color) {
    const c = plano(geo.attributes.color);
    g.setAttribute('color', c.itemSize === 3 ? c : (() => { const a = new Float32Array(c.count * 3);
      for (let i = 0; i < c.count; i++) { a[3 * i] = c.getX(i); a[3 * i + 1] = c.getY(i); a[3 * i + 2] = c.getZ(i); } return new THREE.BufferAttribute(a, 3); })());
  }
  if (geo.index) g.setIndex(Array.from(geo.index.array));
  const n = g.index ? g.toNonIndexed() : g; n.computeVertexNormals(); return n;
}
function materiales(m) { return Array.isArray(m) ? m : [m]; }
function luminancia(m) { const c = m.color || new THREE.Color(1, 1, 1); return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b; }
function area(g) {
  const p = g.attributes.position; let s = 0; const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (let i = 0; i + 2 < p.count; i += 3) { a.fromBufferAttribute(p, i); b.fromBufferAttribute(p, i + 1); c.fromBufferAttribute(p, i + 2);
    s += b.sub(a).cross(c.sub(a)).length() / 2; }
  return s;
}

// Matriz que lleva el modelo a la convención del visor:
//   frente en z = 0, cola en z = +L (mira hacia -z), centrado en x, ruedas/pies en y = 0.
// glTF usa +z como "adelante", así que por defecto se gira 180°; `girar` corrige otros casos.
function normalizar(caja, { girar = null, largo = null, altura = null, ancho = null }) {
  if (girar === null || girar === undefined) {  // sin indicación: si el modelo es más largo en x que en z, viene de lado
    const t = caja.getSize(new THREE.Vector3()); girar = largo && t.x > 1.3 * t.z ? 90 : 0;
  }
  const R = new THREE.Matrix4().makeRotationY(((180 + girar) * Math.PI) / 180);
  const c = caja.clone().applyMatrix4(R); const tam = c.getSize(new THREE.Vector3());
  const s = largo ? largo / Math.max(1e-6, tam.z) : altura ? altura / Math.max(1e-6, tam.y) : 1;
  const sx = ancho ? ancho / Math.max(1e-6, tam.x) : s;  // `ancho` corrige modelos con proporciones de juguete
  const T = new THREE.Matrix4().makeTranslation(-(c.min.x + c.max.x) / 2 * sx, -c.min.y * s, largo ? -c.min.z * s : -(c.min.z + c.max.z) / 2 * s);
  return { M: T.multiply(new THREE.Matrix4().makeScale(sx, s, s)).multiply(R), L: tam.z * s, W: tam.x * sx, H: tam.y * s };
}

// ------------------------------------------------------------------ vehículos
// Devuelve [{ geo, material, tinte }] ya normalizados, uno por material del modelo
function prepararVehiculo(gltf, cfg, Lpordefecto) {
  const raiz = gltf.scene; raiz.updateMatrixWorld(true);
  const grupos = new Map(); const caja = new THREE.Box3();
  raiz.traverse((o) => {
    if (!o.isMesh || !o.visible) return;
    const mats = materiales(o.material); const geoBase = o.geometry;
    const partes = mats.length > 1 && geoBase.groups.length ? geoBase.groups.map((gr) => [gr, mats[gr.materialIndex]]) : [[null, mats[0]]];
    for (const [gr, mat] of partes) {
      let g = limpia(geoBase, null, !!mat.vertexColors);
      if (gr) { const ini = gr.start, n = Math.min(gr.count, g.attributes.position.count - ini);  // tras toNonIndexed, el grupo son vértices seguidos
        const sub = new THREE.BufferGeometry(); for (const [k, a] of Object.entries(g.attributes)) sub.setAttribute(k, new THREE.BufferAttribute(a.array.slice(ini * a.itemSize, (ini + n) * a.itemSize), a.itemSize)); g = sub; }
      g.applyMatrix4(o.matrixWorld); g.computeBoundingBox(); caja.union(g.boundingBox);
      const nombre = `${mat.name || ''} ${o.name || ''}`;
      if (!grupos.has(mat.uuid)) grupos.set(mat.uuid, { mat, nombre, geos: [] });
      grupos.get(mat.uuid).geos.push(g);
    }
  });
  if (!grupos.size) throw new Error('el modelo no tiene mallas');
  const { M, L, W } = normalizar(caja, { girar: cfg.girar, largo: cfg.largo || Lpordefecto, ancho: cfg.ancho });
  const lista = [...grupos.values()].map((gr) => {
    const conColor = gr.geos.every((g) => g.attributes.color);
    if (!conColor) gr.geos.forEach((g) => g.deleteAttribute('color'));
    const geo = mergeGeometries(gr.geos, false); geo.applyMatrix4(M); geo.computeBoundingSphere();
    return { geo, mat: gr.mat, nombre: gr.nombre, area: area(geo) };
  });
  // ¿qué materiales son la pintura?
  let pintura;
  if (cfg.pintura === false) pintura = new Set();
  else if (Array.isArray(cfg.pintura)) pintura = new Set(lista.filter((p) => cfg.pintura.some((t) => p.nombre.toLowerCase().includes(String(t).toLowerCase()))));
  else {
    pintura = new Set(lista.filter((p) => RE_PINTURA.test(p.nombre) && !RE_VIDRIO.test(p.nombre)));
    if (!pintura.size) {  // la superficie más grande que no sea vidrio ni negra
      const cand = lista.filter((p) => !RE_VIDRIO.test(p.nombre) && !p.mat.transparent && luminancia(p.mat) > 0.12).sort((a, b) => b.area - a.area);
      if (cand.length) pintura.add(cand[0]);
    }
  }
  const tris = lista.reduce((s, p) => s + p.geo.attributes.position.count / 3, 0);
  return { partes: lista.map((p) => ({ geo: p.geo, mat: p.mat, tinte: pintura.has(p), nombre: p.nombre })), L, W, tris };
}
function materialPintura(mat) {  // el color de cada carro se multiplica por el del material: se deja en blanco
  const m = mat.clone(); if (m.color) m.color.set(0xffffff); return m;
}

// Conductor: una persona en la última pose de un clip (p. ej. SitDown), puesta sobre el vehículo
function prepararJinete(gltf, cfg) {
  const raiz = gltf.scene; const mallas = [];
  raiz.traverse((o) => { if (o.isMesh && o.visible) mallas.push({ o, mat: materiales(o.material)[0] }); });
  raiz.updateMatrixWorld(true);
  const parado = capturar(mallas); const cajaP = new THREE.Box3(); for (const p of parado) { p.geo.computeBoundingBox(); cajaP.union(p.geo.boundingBox); }
  const clip = buscarClip(gltf.animations, cfg.animacion || 'SitDown', /sit/i);
  let pose = parado;
  if (clip) { const mixer = new THREE.AnimationMixer(raiz); mixer.clipAction(clip).play(); mixer.setTime(clip.duration * (cfg.momento ?? 0.999)); raiz.updateMatrixWorld(true); pose = capturar(mallas); }
  // escala por la estatura de pie; luego se apoya la cadera en (0, y, z) del vehículo
  const alto = cajaP.getSize(new THREE.Vector3()).y; const s = (cfg.altura || 1.7) / Math.max(1e-6, alto);
  const R = new THREE.Matrix4().makeRotationY(((180 + (cfg.girar || 0)) * Math.PI) / 180);
  const caja = new THREE.Box3(); for (const p of pose) { p.geo.applyMatrix4(R); p.geo.scale(s, s, s); p.geo.computeBoundingBox(); caja.union(p.geo.boundingBox); }
  const c = caja.getCenter(new THREE.Vector3());
  for (const p of pose) p.geo.translate(-c.x + (cfg.x || 0), -caja.min.y + (cfg.y ?? 0.35), -c.z + (cfg.z ?? 1.0));
  return fusionarPose(pose).map(({ geo, mat }) => ({ geo, mat, tinte: false, nombre: 'conductor' }));
}

// ------------------------------------------------------------------ personas
function buscarClip(clips, nombre, patron) {
  if (!clips.length) return null;
  if (nombre) { const n = String(nombre).toLowerCase();
    return clips.find((c) => c.name.toLowerCase() === n) || clips.find((c) => c.name.toLowerCase().includes(n)) || null; }
  return clips.find((c) => patron.test(c.name) && !/carry|hold/i.test(c.name)) || clips.find((c) => patron.test(c.name)) || null;
}
// Captura la pose actual de todas las mallas (con esqueleto aplicado) en coordenadas del mundo
function capturar(mallas) {
  const v = new THREE.Vector3();
  return mallas.map(({ o, mat }) => {
    const geo = o.geometry; const n = geo.attributes.position.count; const pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      if (o.isSkinnedMesh) o.getVertexPosition(i, v); else v.fromBufferAttribute(geo.attributes.position, i);
      v.applyMatrix4(o.matrixWorld); pos[3 * i] = v.x; pos[3 * i + 1] = v.y; pos[3 * i + 2] = v.z;
    }
    return { geo: limpia(geo, new THREE.BufferAttribute(pos, 3), !!mat.vertexColors), mat };
  });
}
// Si ningún material usa textura, una pose se vuelve UNA geometría con el color de cada
// material horneado en los vértices: una sola llamada de dibujo por pose.
const matUnico = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85 });
function fusionarPose(pose) {
  if (pose.some(({ mat }) => mat.map)) return pose;
  const geos = pose.map(({ geo, mat }) => { const g = geo.clone(); const n = g.attributes.position.count; const c = mat.color || new THREE.Color(1, 1, 1);
    const col = new Float32Array(n * 3); const prev = g.attributes.color;
    for (let i = 0; i < n; i++) { const k = prev ? [prev.getX(i), prev.getY(i), prev.getZ(i)] : [1, 1, 1]; col[3 * i] = c.r * k[0]; col[3 * i + 1] = c.g * k[1]; col[3 * i + 2] = c.b * k[2]; }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3)); return g; });
  const g = mergeGeometries(geos, false); g.computeBoundingSphere(); return [{ geo: g, mat: matUnico }];
}
function prepararPersona(gltf, cfg) {
  const raiz = gltf.scene; const mallas = [];
  raiz.traverse((o) => { if (o.isMesh && o.visible) for (const mat of materiales(o.material)) { mallas.push({ o, mat }); break; } });
  if (!mallas.length) throw new Error('el modelo no tiene mallas');
  const N = Math.max(2, Math.min(24, cfg.cuadros || 10));
  const mixer = new THREE.AnimationMixer(raiz);
  // si el modelo trae un solo clip sin nombre reconocible, se asume que es el de caminar
  const caminar = buscarClip(gltf.animations, cfg.animacion, /walk|camin|andar/i) || (!cfg.animacion && gltf.animations.length === 1 ? gltf.animations[0] : null);
  const quieto = buscarClip(gltf.animations, cfg.quieto, /idle|quiet|stand|parad|reposo/i);
  const poses = (clip, n) => {
    if (!clip) { raiz.updateMatrixWorld(true); return [capturar(mallas)]; }
    const accion = mixer.clipAction(clip); accion.reset().play(); const out = [];
    for (let k = 0; k < n; k++) { mixer.setTime((clip.duration * k) / n); raiz.updateMatrixWorld(true); out.push(capturar(mallas)); }
    accion.stop(); return out;
  };
  // pose de referencia para medir: la primera de caminar (o la de reposo si no hay clip)
  const paso = poses(caminar, N);
  let parado;
  if (quieto) parado = poses(quieto, 1);
  else {  // sin clip de reposo: pose original del esqueleto
    mixer.stopAllAction(); raiz.traverse((o) => { if (o.isSkinnedMesh) o.skeleton.pose(); });
    raiz.updateMatrixWorld(true); parado = [capturar(mallas)];
  }
  const caja = new THREE.Box3(); for (const p of paso[0]) { p.geo.computeBoundingBox(); caja.union(p.geo.boundingBox); }
  const { M, H } = normalizar(caja, { girar: cfg.girar ?? 0, altura: cfg.altura || 1.72 });
  for (const pose of [...paso, ...parado]) for (const p of pose) { p.geo.applyMatrix4(M); p.geo.computeBoundingSphere(); }
  if (cfg.sin_desplazamiento !== false) {  // anula el avance del clip (root motion): la persona camina en su sitio
    for (const pose of paso) { const c = new THREE.Box3(); for (const p of pose) { p.geo.computeBoundingBox(); c.union(p.geo.boundingBox); }
      const dx = -(c.min.x + c.max.x) / 2, dz = -(c.min.z + c.max.z) / 2; for (const p of pose) { p.geo.translate(dx, 0, dz); p.geo.computeBoundingSphere(); } }
  }
  const tris = paso[0].reduce((s, p) => s + p.geo.attributes.position.count / 3, 0);
  for (let k = 0; k < paso.length; k++) paso[k] = fusionarPose(paso[k]);
  parado[0] = fusionarPose(parado[0]);
  return { paso, parado: parado[0], H, tris, conAnimacion: !!caminar, periodo: caminar ? caminar.duration : 1 };
}

export const _prueba = { prepararVehiculo, prepararPersona, prepararJinete, cargador };  // para pruebas

// ------------------------------------------------------------------ arranque
// ctx: { scene, flota, egoMalla, colorEgo, maxPersonas, ocultarPersonasProcedurales }
// Devuelve un objeto `personas` (o null) con poner(...) y cerrar() para el bucle de dibujo.
export async function iniciarModelos3D(ctx) {
  let cfg;
  try { const r = await fetch(CARPETA + 'config.json', { cache: 'no-store' }); if (!r.ok) return null; cfg = await r.json(); }
  catch (e) { return null; }
  const L = cargador(); const cargar = (arch) => L.loadAsync(CARPETA + arch);
  const estado = { personas: null };
  const informe = [];

  // vehículos de fondo
  for (const [clave, c] of Object.entries(cfg.vehiculos || {})) {
    const fl = ctx.flota[clave]; if (!fl) { console.warn(`[modelos3d] tipo de vehículo desconocido: "${clave}"`); continue; }
    const opciones = typeof c === 'string' ? { archivo: c } : c; if (!opciones.archivo) continue;
    try {
      const v = prepararVehiculo(await cargar(opciones.archivo), opciones, fl.L);
      if (opciones.conductor) { const cj = typeof opciones.conductor === 'string' ? { archivo: opciones.conductor } : opciones.conductor;
        try { v.partes.push(...prepararJinete(await cargar(cj.archivo), cj)); } catch (e) { console.error(`[modelos3d] conductor de ${clave}:`, e); } }
      const max = fl.def.max; const nuevas = [];
      for (const p of v.partes) {
        const mat = p.tinte ? materialPintura(p.mat) : p.mat;
        const im = new THREE.InstancedMesh(p.geo, mat, max); im.count = 0; im.frustumCulled = false; im.castShadow = true; im.receiveShadow = true;
        if (p.tinte) im.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(max * 3).fill(1), 3);
        ctx.scene.add(im); nuevas.push({ im, tinte: p.tinte });
      }
      for (const m of fl.mallas) { ctx.scene.remove(m.im); m.im.count = 0; }
      fl.mallas = nuevas; fl.W = v.W;
      informe.push(`${clave}: ${opciones.archivo} · ${Math.round(v.tris).toLocaleString()} triángulos · ${v.L.toFixed(2)} m · pintura: ${v.partes.filter((p) => p.tinte).map((p) => p.nombre.trim() || '(sin nombre)').join(', ') || 'ninguna'}`);
      if (v.tris > 30000) console.warn(`[modelos3d] ${clave}: ${Math.round(v.tris)} triángulos es mucho para cientos de copias; puede ir lento.`);
    } catch (e) { console.error(`[modelos3d] no se pudo cargar ${clave} (${opciones.archivo}):`, e); }
  }

  // instructor
  if (cfg.instructor) {
    const opciones = typeof cfg.instructor === 'string' ? { archivo: cfg.instructor } : cfg.instructor;
    try {
      const v = prepararVehiculo(await cargar(opciones.archivo), opciones, ctx.egoMalla.userData.L || 4.5);
      const g = new THREE.Group();
      for (const p of v.partes) {
        const mat = p.tinte && opciones.pintura !== false ? (() => { const m = p.mat.clone(); if (m.color) m.color.copy(ctx.colorEgo); return m; })() : p.mat;
        const malla = new THREE.Mesh(p.geo, mat); malla.castShadow = true; g.add(malla);
      }
      ctx.egoMalla.geometry = new THREE.BufferGeometry(); ctx.egoMalla.add(g); ctx.egoMalla.userData.L = v.L;
      informe.push(`instructor: ${opciones.archivo} · ${Math.round(v.tris).toLocaleString()} triángulos`);
    } catch (e) { console.error(`[modelos3d] no se pudo cargar el instructor (${opciones.archivo}):`, e); }
  }

  // personas (una o varias, para que no sean todas iguales)
  const listaP = cfg.personas || (cfg.persona ? [cfg.persona] : []);
  const tipos = [];
  for (const c of listaP) {
    const opciones = typeof c === 'string' ? { archivo: c } : c;
    try {
      const p = prepararPersona(await cargar(opciones.archivo), opciones);
      // capacidad: las personas se reparten entre tipos y poses; se deja holgura
      const nt = listaP.length, porTipo = Math.ceil(ctx.maxPersonas / nt);
      const crear = (pose, max) => pose.map(({ geo, mat }) => { const im = new THREE.InstancedMesh(geo, mat, max); im.count = 0; im.frustumCulled = false; im.castShadow = true; ctx.scene.add(im); return im; });
      const capPaso = Math.min(porTipo * 2, Math.ceil((porTipo * 3) / p.paso.length) + 60), capParado = Math.min(ctx.maxPersonas, Math.ceil(porTipo * 2) + 60);
      tipos.push({ paso: p.paso.map((pose) => ({ ims: crear(pose, capPaso), n: 0, max: capPaso })), parado: { ims: crear(p.parado, capParado), n: 0, max: capParado }, periodo: p.periodo,
        velocidad: opciones.velocidad_animacion || 1 });
      informe.push(`persona: ${opciones.archivo} · ${Math.round(p.tris).toLocaleString()} triángulos · ${p.H.toFixed(2)} m · ${p.conAnimacion ? p.paso.length + ' poses de caminar' : 'sin animación de caminar (se deslizan)'}`);
    } catch (e) { console.error(`[modelos3d] no se pudo cargar la persona (${opciones.archivo}):`, e); }
  }
  if (tipos.length) {
    const PQ = new THREE.Quaternion(), PV = new THREE.Vector3(), PM = new THREE.Matrix4(), EJE = new THREE.Vector3(0, 1, 0), UNO = new THREE.Vector3(1, 1, 1);
    const cubetas = tipos.flatMap((t) => [...t.paso, t.parado]);
    estado.personas = {
      poner(x, y, angGrados, semilla, camina, t) {
        const r = Math.abs(Math.floor(semilla)); const tipo = tipos[r % tipos.length];
        let cub = tipo.parado;
        if (camina) { const fase = ((t * tipo.velocidad) / tipo.periodo + (r % 97) / 97) % 1; cub = tipo.paso[Math.floor(fase * tipo.paso.length) % tipo.paso.length]; }
        if (cub.n >= cub.max) return;
        PQ.setFromAxisAngle(EJE, -angGrados * Math.PI / 180); PV.set(x, 0.16, -y); PM.compose(PV, PQ, UNO);
        for (const im of cub.ims) im.setMatrixAt(cub.n, PM); cub.n++;
      },
      // geometría suelta (colores en vértices) para los imprevistos: peatón que cruza, vendedor
      geometriaFigura(semilla, caminando = true, extras = []) {
        const tipo = tipos[Math.abs(Math.floor(semilla)) % tipos.length];
        const cub = caminando ? tipo.paso[Math.floor(tipo.paso.length / 4)] : tipo.parado;
        if (cub.ims.length !== 1 || !cub.ims[0].material.vertexColors) return null;  // modelo con texturas: no aplica
        const g = cub.ims[0].geometry.clone(); g.deleteAttribute('uv');
        const out = extras.length ? mergeGeometries([g, ...extras], false) : g; out.computeBoundingSphere(); return out;
      },
      cerrar() { for (const c of cubetas) { for (const im of c.ims) { im.count = c.n; im.instanceMatrix.needsUpdate = true; } c.n = 0; } },
    };
    ctx.ocultarPersonasProcedurales();
  }
  if (informe.length) console.info('[modelos3d] cargados:\n  ' + informe.join('\n  '));
  return estado.personas;
}

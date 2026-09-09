/* Jarvis — hologramas na visão da câmera (formas 3D neon).
   Cena Three.js própria, canvas transparente por cima do vídeo.
   window.jarvisHolo: setActive / onControl / tick */
window.jarvisHolo = (() => {
  "use strict";

  const NEON = 0x7ce4ff, NEON2 = 0x46d6ff, TAU = Math.PI * 2;

  const cv = document.createElement("canvas");
  cv.id = "holo-canvas";
  cv.style.cssText = "position:fixed;inset:0;z-index:2;pointer-events:none;display:none";
  document.body.appendChild(cv);

  const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.set(0, 0, 6);
  const group = new THREE.Group();
  scene.add(group);

  function resize() {
    renderer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
  }
  resize();
  addEventListener("resize", resize);

  // ---------- fábrica de formas ----------
  function makeGeo(type) {
    switch (type) {
      case "cube": return new THREE.BoxGeometry(1.3, 1.3, 1.3);
      case "sphere": return new THREE.IcosahedronGeometry(0.95, 2);
      case "pyramid": return new THREE.ConeGeometry(1.0, 1.5, 4);
      case "cone": return new THREE.ConeGeometry(0.9, 1.7, 44);
      case "cylinder": return new THREE.CylinderGeometry(0.75, 0.75, 1.6, 36);
      case "torus": return new THREE.TorusGeometry(0.85, 0.30, 16, 44);
      case "octahedron": return new THREE.OctahedronGeometry(1.15);
      case "prism": return new THREE.CylinderGeometry(0.95, 0.95, 1.4, 6);
      default: return new THREE.BoxGeometry(1.2, 1.2, 1.2);
    }
  }

  function neonShape(type) {
    const geo = makeGeo(type);
    const g = new THREE.Group();
    g.add(new THREE.LineSegments(
      new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.92,
        blending: THREE.AdditiveBlending, depthWrite: false })
    ));
    g.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
      color: NEON2, transparent: true, opacity: 0.07,
      blending: THREE.AdditiveBlending, depthWrite: false })));
    g.userData.type = type;
    return g;
  }

  const shapes = [];   // { obj, spin:{x,y}, bob, grabbed, userScale, appear, grabOff }
  let count = 0, lastN = 0;

  function spawn(type) {
    const o = neonShape(type);
    const i = count++;
    o.position.set(((i % 3) - 1) * 2.3 + (Math.random() - 0.5) * 0.5,
                   ((Math.floor(i / 3) % 2) - 0.5) * -2.0 + (Math.random() - 0.5) * 0.4, 0);
    o.rotation.set(Math.random() * TAU, Math.random() * TAU, 0);
    o.scale.setScalar(0.01);
    group.add(o);
    shapes.push({
      obj: o, bob: Math.random() * TAU, grabbed: false, userScale: 1, appear: 0,
      grabOff: new THREE.Vector3(), twoRef: 0,
      spin: { x: (Math.random() - 0.5) * 0.006, y: (Math.random() - 0.5) * 0.008 + 0.006 },
    });
  }

  function clear() {
    shapes.forEach((s) => group.remove(s.obj));
    shapes.length = 0; count = 0;
  }

  function dbg(m) {
    const a = window.pywebview && window.pywebview.api;
    if (a && a.log) a.log("holo: " + m);
  }

  function onControl(holo) {
    if (!holo || !holo.n || holo.n <= lastN) return;
    lastN = holo.n;
    if (holo.action === "add" && holo.shape) { spawn(holo.shape); dbg("+ " + holo.shape + " (total " + shapes.length + ")"); }
    else if (holo.action === "clear") { clear(); dbg("limpou"); }
  }

  // ---------- tela -> mundo (plano z=0) ----------
  const _v = new THREE.Vector3();
  function screenToWorld(nx, ny) {
    let px, py;
    if (window.jarvisCam && window.jarvisCam.coverMap) [px, py] = window.jarvisCam.coverMap(nx, ny);
    else { px = nx * innerWidth; py = ny * innerHeight; }
    px = innerWidth - px;   // canvas/vídeo espelhados
    const ndcX = (px / innerWidth) * 2 - 1;
    const ndcY = -((py / innerHeight) * 2 - 1);
    _v.set(ndcX, ndcY, 0.5).unproject(camera);
    _v.sub(camera.position).normalize();
    return camera.position.clone().add(_v.multiplyScalar(-camera.position.z / _v.z));
  }

  // ---------- interação: pinça agarra a forma mais perto ----------
  function interact(handResults) {
    const hands = (handResults && handResults.hands) || [];
    const pinches = [];
    for (const h of hands) {
      const g = h.gesture;
      if (g && g.pinch >= 0.9 && g.pinchAt) pinches.push(screenToWorld(g.pinchAt.x, g.pinchAt.y));
    }

    // solta o que saiu do alcance de qualquer pinça
    for (const s of shapes) {
      if (s.grabbed && !pinches.some((p) => p.distanceTo(s.obj.position) < 1.8)) {
        s.grabbed = false; s.twoRef = 0;
      }
    }
    // agarra a mais perto de cada pinça e move
    for (const p of pinches) {
      let held = shapes.find((s) => s.grabbed && p.distanceTo(s.obj.position) < 2.2);
      if (!held) {
        let best = null, bd = 1.5;
        for (const s of shapes) {
          if (s.grabbed) continue;
          const d = p.distanceTo(s.obj.position);
          if (d < bd) { bd = d; best = s; }
        }
        if (best) { best.grabbed = true; best.grabOff.copy(best.obj.position).sub(p); held = best; }
      }
      if (held) held.obj.position.copy(p).add(held.grabOff);
    }

    // 2 pinças + 1 forma agarrada -> escala pela distância entre as pinças
    const held = shapes.find((s) => s.grabbed);
    if (pinches.length === 2 && held) {
      const d = pinches[0].distanceTo(pinches[1]);
      if (!held.twoRef) held.twoRef = d / Math.max(0.2, held.userScale);
      held.userScale = Math.max(0.3, Math.min(4.5, d / held.twoRef));
    } else if (held) {
      held.twoRef = 0;
    }
  }

  // ---------- loop ----------
  let active = false;
  function setActive(on) {
    active = on;
    cv.style.display = on ? "block" : "none";
    if (!on) renderer.clear();
  }

  function tick(t, handResults) {
    if (!active) return;
    interact(handResults);
    for (const s of shapes) {
      if (s.appear < 1) s.appear = Math.min(1, s.appear + 0.08);
      s.obj.scale.setScalar(s.appear * s.userScale);
      if (!s.grabbed) {
        s.obj.rotation.x += s.spin.x;
        s.obj.rotation.y += s.spin.y;
        s.obj.position.y += Math.sin(t * 1.1 + s.bob) * 0.0016;
      }
    }
    renderer.render(scene, camera);
  }

  setTimeout(() => {
    const a = window.pywebview && window.pywebview.api;
    if (a && a.log) a.log("holo: módulo carregado, renderer " + (renderer ? "ok" : "FALHOU"));
  }, 1500);

  return { setActive, onControl, tick, count: () => shapes.length, clear };
})();

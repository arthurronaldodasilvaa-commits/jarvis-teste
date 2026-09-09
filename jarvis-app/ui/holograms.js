/* Jarvis — hologramas na visão da câmera + interação por gestos (2 mãos).
   Cena Three.js própria, canvas transparente sobre o vídeo.

   Mão SELETORA  (a que pinça primeiro):
     👌 pinça perto de uma forma -> seleciona (fica ÂMBAR) e arrasta
     👌 no vazio                 -> desmarca
     ✊ punho  (nada selecionado) -> move TODAS as formas juntas
     🖐 varre a tela rápido      -> apaga TODAS
   Mão MODIFICADORA (a outra, só com algo selecionado):
     👌 pinça (junto da seletora) -> escala pela distância entre as 2 pinças
     ✊ punho                     -> a forma pula pra mão e segue ela
     ✌️ paz                       -> gira a forma seguindo a mão
     🖐 varre rápido              -> apaga a forma selecionada
   ☝️ apontar (qualquer mão)      -> raio ponteiro; destaca a forma mirada
*/
window.jarvisHolo = (() => {
  "use strict";

  const NEON = 0x7ce4ff, NEON2 = 0x46d6ff, AMBER = 0xffb24d, TAU = Math.PI * 2;

  const cv = document.createElement("canvas");
  cv.id = "holo-canvas";
  cv.style.cssText = "position:fixed;inset:0;z-index:2;pointer-events:none;display:none";
  document.body.appendChild(cv);

  const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
  camera.position.set(0, 0, 6.5);
  const group = new THREE.Group();
  scene.add(group);
  const fx2d = new THREE.Group();   // ponteiro etc — desenhado como linhas
  scene.add(fx2d);

  function resize() {
    renderer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
  }
  resize(); addEventListener("resize", resize);

  function dbg(m) { const a = window.pywebview && window.pywebview.api; if (a && a.log) a.log("holo: " + m); }

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
    const wire = new THREE.LineSegments(new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.92,
        blending: THREE.AdditiveBlending, depthWrite: false }));
    const fill = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: NEON2, transparent: true,
      opacity: 0.07, blending: THREE.AdditiveBlending, depthWrite: false }));
    g.add(wire); g.add(fill);
    g.userData = { type, wire, fill };
    return g;
  }

  const shapes = [];   // {obj, spin, bob, userScale, appear, sel, amber}
  let count = 0, lastN = 0;
  let selected = null;   // shape ou null

  const TRIG = new Set(["triangulo", "triangle", "triangulo_retangulo",
    "tabela_angulos", "angulos_notaveis", "tabela_relacoes", "relacoes"]);

  function place(o) {
    const i = count++;
    o.position.set(((i % 3) - 1) * 2.9 + (Math.random() - 0.5) * 0.4,
                   ((Math.floor(i / 3) % 2) - 0.5) * -2.6 + (Math.random() - 0.5) * 0.3, 0);
  }

  function spawn(type) {
    if (TRIG.has(type) && window.jarvisTrig) {
      const m = window.jarvisTrig.build(type);
      if (!m) return;
      place(m); group.add(m);
      shapes.push({ obj: m, bob: Math.random() * TAU, userScale: 1, appear: 0, amber: 0,
        math: true, spin: { x: 0, y: 0 } });
      return;
    }
    const o = neonShape(type);
    place(o);
    o.rotation.set(Math.random() * TAU, Math.random() * TAU, 0);
    group.add(o);
    shapes.push({ obj: o, bob: Math.random() * TAU, userScale: 1, appear: 0, amber: 0,
      spin: { x: (Math.random() - 0.5) * 0.005, y: (Math.random() - 0.5) * 0.007 + 0.005 } });
  }
  function removeShape(s) {
    group.remove(s.obj);
    const i = shapes.indexOf(s); if (i >= 0) shapes.splice(i, 1);
    if (selected === s) selected = null;
  }
  function clearAll() { [...shapes].forEach(removeShape); count = 0; }

  function onControl(holo) {
    if (!holo || !holo.n || holo.n <= lastN) return;
    lastN = holo.n;
    if (holo.action === "add" && holo.shape) { spawn(holo.shape); dbg("+ " + holo.shape + " (" + shapes.length + ")"); }
    else if (holo.action === "clear") { clearAll(); dbg("limpou"); }
  }

  // ---------- tela -> mundo (plano z=0) ----------
  const _v = new THREE.Vector3();
  function toWorld(nx, ny) {
    let px, py;
    if (window.jarvisCam && window.jarvisCam.coverMap) [px, py] = window.jarvisCam.coverMap(nx, ny);
    else { px = nx * innerWidth; py = ny * innerHeight; }
    px = innerWidth - px;   // vídeo/canvas espelhados
    _v.set((px / innerWidth) * 2 - 1, -((py / innerHeight) * 2 - 1), 0.5).unproject(camera);
    _v.sub(camera.position).normalize();
    return camera.position.clone().add(_v.multiplyScalar(-camera.position.z / _v.z));
  }
  const handCenter = (lm) => ({ x: (lm[0].x + lm[9].x) / 2, y: (lm[0].y + lm[9].y) / 2 });

  // ---------- histórico p/ detectar "varredura" (palma rápida) ----------
  const trail = new Map();   // hand idx -> [{x,t}]
  function pushTrail(key, x) {
    const now = performance.now();
    let a = trail.get(key) || [];
    a.push({ x, t: now });
    a = a.filter((p) => now - p.t < 450);
    trail.set(key, a);
    return a;
  }
  function swipe(key) {
    const a = trail.get(key) || [];
    if (a.length < 3) return 0;
    const dx = Math.abs(a[a.length - 1].x - a[0].x);
    const dt = a[a.length - 1].t - a[0].t;
    return (dt > 0 && dt < 400 && dx > 0.35) ? dx : 0;
  }

  // ---------- interação ----------
  const st = { resizeRef: 0, rotPrev: null, allPrev: null };

  function interact(res) {
    const hands = (res && res.hands) || [];
    hands.forEach((h) => { h.role = null; });
    if (!hands.length) return;

    // papéis: seletora = a que pinça (senão a 1ª); modificadora = a outra
    let selH = hands.find((h) => h.gesture && h.gesture.pinch >= 0.9) || hands[0];
    let modH = hands.find((h) => h !== selH) || null;
    selH.role = "selector"; if (modH) modH.role = "modifier";

    const sg = selH.gesture || {};
    const mg = (modH && modH.gesture) || {};
    const selPW = sg.pinchAt ? toWorld(sg.pinchAt.x, sg.pinchAt.y) : null;
    const modC = modH ? handCenter(modH.landmarks) : null;
    const modPW = mg.pinchAt ? toWorld(mg.pinchAt.x, mg.pinchAt.y) : null;

    pushTrail("sel", handCenter(selH.landmarks).x);
    if (modH) pushTrail("mod", modC.x);

    // ---- SELETORA ----
    if (sg.pinch >= 0.9 && selPW) {
      if (!selected || selPW.distanceTo(selected.obj.position) > 1.8) {
        let best = null, bd = 1.5;
        for (const s of shapes) {
          const d = selPW.distanceTo(s.obj.position);
          if (d < bd) { bd = d; best = s; }
        }
        if (best && best !== selected) { setSelected(best); best._grabOff = best.obj.position.clone().sub(selPW); }
        else if (!best) setSelected(null);
      }
      if (selected && !(mg.name === "punho")) {
        selected.obj.position.copy(selPW).add(selected._grabOff || new THREE.Vector3());
      }
    }

    // ✊ seletora, nada selecionado -> move TODAS
    if (!selected && sg.name === "punho") {
      const c = handCenter(selH.landmarks);
      if (st.allPrev) {
        const dw = toWorld(c.x, c.y).sub(toWorld(st.allPrev.x, st.allPrev.y));
        shapes.forEach((s) => s.obj.position.add(dw));
      }
      st.allPrev = c;
    } else st.allPrev = null;

    // 🖐 seletora varrendo -> apaga TODAS
    if (sg.name === "palma" && swipe("sel") > 0.5 && !selected) { clearAll(); trail.clear(); }

    // ---- MODIFICADORA (só com algo selecionado) ----
    if (selected && modH) {
      if (mg.name === "punho" && modC) {
        selected.obj.position.copy(toWorld(modC.x, modC.y));
      } else if (mg.pinch >= 0.9 && sg.pinch >= 0.9 && selPW && modPW) {
        const d = selPW.distanceTo(modPW);
        if (!st.resizeRef) st.resizeRef = d / Math.max(0.25, selected.userScale);
        selected.userScale = Math.max(0.3, Math.min(5, d / st.resizeRef));
      } else if (mg.name === "paz" && modC) {
        if (st.rotPrev) {
          selected.obj.rotation.y += (modC.x - st.rotPrev.x) * 6;
          selected.obj.rotation.x += (modC.y - st.rotPrev.y) * 6;
        }
        st.rotPrev = modC;
      } else if (mg.name === "palma" && swipe("mod") > 0.4) {
        removeShape(selected); trail.clear();
      }
      if (mg.pinch < 0.9) st.resizeRef = 0;
      if (mg.name !== "paz") st.rotPrev = null;
    } else { st.resizeRef = 0; st.rotPrev = null; }

    // ---- ☝️ ponteiro ----
    fx2d.clear();
    for (const h of hands) {
      if (h.gesture && h.gesture.name === "apontar") {
        const lm = h.landmarks;
        const a = toWorld(lm[8].x, lm[8].y);
        const dir = toWorld(lm[8].x, lm[8].y).sub(toWorld(lm[5].x, lm[5].y)).normalize();
        const b = a.clone().add(dir.multiplyScalar(8));
        const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]),
          new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.5,
            blending: THREE.AdditiveBlending }));
        fx2d.add(line);
        // destaca a forma mais perto do raio
        let hit = null, hd = 1.0;
        for (const s of shapes) {
          const d = s.obj.position.clone().sub(a).cross(dir).length();
          if (d < hd) { hd = d; hit = s; }
        }
        if (hit) hit._point = 1;
      }
    }
  }

  function setSelected(s) { selected = s; }

  // ---------- loop ----------
  let active = false;
  function setActive(on) {
    active = on;
    cv.style.display = on ? "block" : "none";
    if (!on) { renderer.clear(); trail.clear(); }
  }

  function tick(t, res) {
    if (!active) return;
    interact(res);

    for (const s of shapes) {
      if (s.appear < 1) s.appear = Math.min(1, s.appear + 0.09);
      s.obj.scale.setScalar(s.appear * s.userScale);

      const wantAmber = (s === selected) ? 1 : 0;
      s.amber += (wantAmber - s.amber) * 0.15;
      const ud = s.obj.userData;
      if (ud.wire) {
        ud.wire.material.color.copy(new THREE.Color(NEON).lerp(new THREE.Color(AMBER), s.amber));
        ud.wire.material.opacity = 0.92 + s.amber * 0.06;
        ud.fill.material.color.copy(new THREE.Color(NEON2).lerp(new THREE.Color(AMBER), s.amber));
        ud.fill.material.opacity = 0.07 + s.amber * 0.12 + (s._point || 0) * 0.1;
      } else if (s === selected) {
        s.obj.scale.multiplyScalar(1.0 + Math.sin(t * 6) * 0.006);   // pisca leve o modelo selecionado
      }
      s._point = (s._point || 0) * 0.85;

      if (s !== selected && !s.math) {
        s.obj.rotation.x += s.spin.x;
        s.obj.rotation.y += s.spin.y;
        s.obj.position.y += Math.sin(t * 1.05 + s.bob) * 0.0014;
      }
    }
    renderer.render(scene, camera);
  }

  setTimeout(() => dbg("módulo carregado, renderer " + (renderer ? "ok" : "FALHOU")), 1500);
  return { setActive, onControl, tick, count: () => shapes.length, clearAll, spawn };
})();

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

  const SLOTS = [[0, 0], [-2.4, 0.5], [2.4, 0.5], [-1.5, -1.9], [1.5, -1.9], [0, 2.0]];
  function place(o) {
    const [x, y] = SLOTS[count % SLOTS.length];
    count++;
    o.position.set(x + (Math.random() - 0.5) * 0.3, y + (Math.random() - 0.5) * 0.3, 0);
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

  // ---------- coordenadas ----------
  // ponto normalizado do FRAME (0..1) -> pixel na tela QUE O USUÁRIO VÊ (espelhada)
  function toScreenPx(nx, ny) {
    let px, py;
    if (window.jarvisCam && window.jarvisCam.coverMap) [px, py] = window.jarvisCam.coverMap(nx, ny);
    else { px = nx * innerWidth; py = ny * innerHeight; }
    return [innerWidth - px, py];   // espelhado p/ bater com o vídeo
  }
  // pixel da tela -> mundo, no plano z=depth
  const _v = new THREE.Vector3();
  function pxToWorld(px, py, depth = 0) {
    _v.set((px / innerWidth) * 2 - 1, -((py / innerHeight) * 2 - 1), 0.5).unproject(camera);
    _v.sub(camera.position).normalize();
    return camera.position.clone().add(_v.multiplyScalar((depth - camera.position.z) / _v.z));
  }
  function toWorld(nx, ny, depth = 0) {
    const [px, py] = toScreenPx(nx, ny);
    return pxToWorld(px, py, depth);
  }
  // mundo -> pixel na tela
  const _p = new THREE.Vector3();
  function worldToPx(w) {
    _p.copy(w).project(camera);
    return [(_p.x * 0.5 + 0.5) * innerWidth, (-_p.y * 0.5 + 0.5) * innerHeight];
  }
  const handCenter = (lm) => ({ x: (lm[0].x + lm[9].x) / 2, y: (lm[0].y + lm[9].y) / 2 });
  const finite = (n) => (Number.isFinite(n) ? n : 0);

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
  const st = { resizeRef: 0, rotPrev: null, allPrev: null, selPinchWas: false };
  let dbgDot = [0, 0], dbgOn = false;

  function nearestOnScreen(px, py, maxDistPx) {
    let best = null, bd = maxDistPx;
    for (const s of shapes) {
      const [sx, sy] = worldToPx(s.obj.position);
      const d = Math.hypot(sx - px, sy - py);
      if (d < bd) { bd = d; best = s; }
    }
    return best;
  }

  function interact(res) {
    const hands = (res && res.hands) || [];
    hands.forEach((h) => { h.role = null; });
    if (!hands.length) { st.allPrev = null; st.rotPrev = null; return; }

    let selH = hands.find((h) => h.gesture && h.gesture.pinch >= 0.9) || hands[0];
    let modH = hands.find((h) => h !== selH) || null;
    selH.role = "selector"; if (modH) modH.role = "modifier";

    const sg = selH.gesture || {};
    const mg = (modH && modH.gesture) || {};
    const selPx = sg.pinchAt ? toScreenPx(sg.pinchAt.x, sg.pinchAt.y) : null;
    const modC = modH ? handCenter(modH.landmarks) : null;
    const modPx = mg.pinchAt ? toScreenPx(mg.pinchAt.x, mg.pinchAt.y) : null;
    const R = Math.min(innerWidth, innerHeight) * 0.22;   // raio de "pega" em pixels

    pushTrail("sel", handCenter(selH.landmarks).x);
    if (modH) pushTrail("mod", modC.x);
    dbgOn = !!selPx;
    if (selPx) dbgDot = selPx;

    // ---- SELETORA: 👌 seleciona + arrasta ----
    const selPinch = sg.pinch >= 0.9 && !!selPx;
    if (selPinch) {
      const nearSel = selected && (() => {
        const [sx, sy] = worldToPx(selected.obj.position);
        return Math.hypot(sx - selPx[0], sy - selPx[1]) < R * 1.4;
      })();
      if (!st.selPinchWas) {
        // pinça ACABOU de fechar: escolhe / desmarca
        if (!nearSel) {
          const pick = nearestOnScreen(selPx[0], selPx[1], R);
          setSelected(pick || null);
        }
      }
      if (selected && mg.name !== "punho") {
        if (selected._grabOff == null) {
          selected._grabZ = selected.obj.position.z;
          selected._grabOff = selected.obj.position.clone().sub(pxToWorld(selPx[0], selPx[1], selected._grabZ));
        }
        const w = pxToWorld(selPx[0], selPx[1], selected._grabZ || 0).add(selected._grabOff);
        if (Number.isFinite(w.x)) selected.obj.position.copy(w);
      }
    } else if (selected) {
      selected._grabOff = null;   // soltou: para de arrastar (segue selecionado)
    }
    st.selPinchWas = selPinch;

    // ✊ seletora, nada selecionado -> move TODAS
    if (!selected && sg.name === "punho") {
      const c = handCenter(selH.landmarks);
      if (st.allPrev) {
        const [ax, ay] = toScreenPx(st.allPrev.x, st.allPrev.y);
        const [bx, by] = toScreenPx(c.x, c.y);
        const dw = pxToWorld(bx, by).sub(pxToWorld(ax, ay));
        shapes.forEach((s) => s.obj.position.add(dw));
      }
      st.allPrev = c;
    } else st.allPrev = null;

    // 🖐 seletora varrendo -> apaga TODAS
    if (sg.name === "palma" && swipe("sel") > 0.5 && !selected) { clearAll(); trail.clear(); }

    // ---- MODIFICADORA (só com algo selecionado) ----
    if (selected && modH) {
      if (mg.name === "punho" && modC) {
        const [mx, my] = toScreenPx(modC.x, modC.y);
        const w = pxToWorld(mx, my, selected._grabZ || 0);
        if (Number.isFinite(w.x)) selected.obj.position.copy(w);
      } else if (mg.pinch >= 0.9 && sg.pinch >= 0.9 && selPx && modPx) {
        const d = Math.hypot(selPx[0] - modPx[0], selPx[1] - modPx[1]);
        if (!st.resizeRef || !Number.isFinite(st.resizeRef)) st.resizeRef = Math.max(40, d) / Math.max(0.25, selected.userScale);
        const ns = d / st.resizeRef;
        selected.userScale = Math.max(0.25, Math.min(6, Number.isFinite(ns) ? ns : selected.userScale));
      } else if (mg.name === "paz" && modC) {
        if (st.rotPrev) {
          selected.obj.rotation.y += finite(modC.x - st.rotPrev.x) * 5;
          selected.obj.rotation.x += finite(modC.y - st.rotPrev.y) * 5;
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
        const [tx, ty] = toScreenPx(lm[8].x, lm[8].y);
        const [bx, by] = toScreenPx(lm[6].x, lm[6].y);
        const a = pxToWorld(tx, ty, 0);
        const dir = a.clone().sub(pxToWorld(bx, by, 0)).normalize();
        const b = a.clone().add(dir.clone().multiplyScalar(10));
        fx2d.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]),
          new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.45, blending: THREE.AdditiveBlending })));
        const hit = nearestOnScreen(tx, ty, R * 1.5);
        if (hit) hit._point = 1;
      }
    }
  }

  function setSelected(s) {
    if (selected === s) return;
    if (selected) selected._grabOff = null;
    selected = s;
    if (s) s._grabOff = null;
  }

  // marcador da pinça (mostra ONDE o sistema acha que sua pinça está)
  const marker = new THREE.Sprite(new THREE.SpriteMaterial({
    color: 0xffffff, transparent: true, opacity: 0, depthWrite: false,
    blending: THREE.AdditiveBlending }));
  marker.scale.set(0.35, 0.35, 1);
  scene.add(marker);

  // ---------- loop ----------
  let active = false;
  function setActive(on) {
    active = on;
    cv.style.display = on ? "block" : "none";
    if (!on) { renderer.clear(); trail.clear(); }
  }

  let _errLogged = false;
  function tick(t, res) {
    if (!active) return;
    try { interact(res); } catch (e) {
      if (!_errLogged) { _errLogged = true; dbg("ERRO interact: " + (e && e.message) + " | " + (e && e.stack || "")); }
    }

    // marcador da pinça
    if (dbgOn) {
      const w = pxToWorld(dbgDot[0], dbgDot[1], 0);
      if (Number.isFinite(w.x)) marker.position.copy(w);
      marker.material.opacity += (0.55 - marker.material.opacity) * 0.3;
    } else {
      marker.material.opacity += (0 - marker.material.opacity) * 0.3;
    }

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
      // trava contra NaN
      const p = s.obj.position;
      if (!Number.isFinite(p.x) || !Number.isFinite(p.y) || !Number.isFinite(p.z)) p.set(0, 0, 0);
      if (!Number.isFinite(s.userScale)) s.userScale = 1;
    }
    try { renderer.render(scene, camera); } catch (e) {
      if (!_errLogged) { _errLogged = true; dbg("ERRO render: " + (e && e.message)); }
    }
  }

  setTimeout(() => dbg("módulo carregado, renderer " + (renderer ? "ok" : "FALHOU")), 1500);
  return { setActive, onControl, tick, count: () => shapes.length, clearAll, spawn };
})();

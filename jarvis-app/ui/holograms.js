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
     ✋ palma sobre forma animada  -> CONGELA e navega no tempo pela posição da mão
     🖐 varre rápido              -> apaga a forma selecionada
   DUAS mãos ✊✊ (ou ✋✋) com algo selecionado -> gira como uma BOLA (trackball)
   ✋ PARADA ~0,5 s -> abre o menu de marcação. Com a MESMA mão aberta,
      EMPURRA numa direção e segura ~0,5 s:
        cima = limpar tudo   direita = trava/solta   baixo = duplicar   esquerda = explodir
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

  function spawn(type, opts, atPos) {
    let m = null;
    if (TRIG.has(type) && window.jarvisTrig) m = window.jarvisTrig.build(type);
    else if (window.jarvisModels && window.jarvisModels.has(type)) m = window.jarvisModels.build(type, opts);
    if (m) {
      if (atPos) { m.position.copy(atPos); count++; } else place(m);
      group.add(m);
      shapes.push({ obj: m, bob: Math.random() * TAU, userScale: 1, appear: 0, amber: 0,
        math: true, spin: { x: 0, y: 0 }, upd: m.userData && m.userData.update || null,
        spawnType: type, spawnOpts: opts || null });
      return shapes[shapes.length - 1];
    }
    const o = neonShape(type);
    if (atPos) { o.position.copy(atPos); count++; } else place(o);
    o.rotation.set(Math.random() * TAU, Math.random() * TAU, 0);
    group.add(o);
    shapes.push({ obj: o, bob: Math.random() * TAU, userScale: 1, appear: 0, amber: 0,
      spin: { x: (Math.random() - 0.5) * 0.005, y: (Math.random() - 0.5) * 0.007 + 0.005 },
      spawnType: type, spawnOpts: opts || null });
    return shapes[shapes.length - 1];
  }

  function dupSelected() {
    if (!selected) return;
    const off = new THREE.Vector3(0.8, 0.5, 0);
    const s = spawn(selected.spawnType, selected.spawnOpts, selected.obj.position.clone().add(off));
    if (s) { s.userScale = selected.userScale; s.obj.rotation.copy(selected.obj.rotation); setSelected(s); }
  }
  function explodeSelected() {
    if (!selected) return;
    selected.exploded = !selected.exploded;
    const kids = selected.obj.children.filter((c) => c.isMesh || c.isLine || c.isSprite);
    kids.forEach((c) => {
      if (!c.userData._home) c.userData._home = c.position.clone();
      c.userData._target = selected.exploded
        ? c.userData._home.clone().multiplyScalar(2.4).add(new THREE.Vector3(0, 0, (Math.random() - 0.5) * 1.5))
        : c.userData._home.clone();
    });
  }
  function lockSelected(on) {
    if (!selected) return;
    selected.locked = on == null ? !selected.locked : !!on;
  }
  function removeShape(s) {
    group.remove(s.obj);
    const i = shapes.indexOf(s); if (i >= 0) shapes.splice(i, 1);
    if (selected === s) selected = null;
  }
  function clearAll() { [...shapes].forEach(removeShape); count = 0; st.poked && st.poked.clear(); }

  const APP_START = Date.now();
  function onControl(holo) {
    if (!holo || !holo.n || holo.n <= lastN) return;
    lastN = holo.n;
    if (holo.n < APP_START - 3000) return;   // comando velho (de antes do app abrir) — ignora
    if (holo.action === "add" && holo.shape) { spawn(holo.shape, holo); st.poked.clear(); dbg("+ " + holo.shape + " (" + shapes.length + ")"); }
    else if (holo.action === "clear") { clearAll(); clearInk(); clearMeasure(); dbg("limpou"); }
    else if (holo.action === "dup") { dupSelected(); }
    else if (holo.action === "explode") { explodeSelected(); }
    else if (holo.action === "lock") { lockSelected(holo.on); }
    else if (holo.action === "mode") {
      st.drawMode = holo.mode === "draw";
      st.measureMode = holo.mode === "measure";
      if (holo.mode !== "measure") clearMeasure();   // sai da medida (ou vai pro normal/desenho)
      if (holo.mode !== "draw") clearInk();          // sai do desenho (ou vai pro normal/medida)
      st.measWas = false; st.twistPrev = null;
      dbg("modo " + (holo.mode || "normal"));
    }
    else if (holo.action === "clear_ink") { clearInk(); clearMeasure(); }
  }

  // ---------- desenhar no ar ----------
  const ink = new THREE.Group(); scene.add(ink);
  let stroke = null, strokePts = [], strokeT = 0;
  function clearInk() { [...ink.children].forEach((c) => ink.remove(c)); stroke = null; strokePts = []; }
  function inkPoint(w) {
    if (!Number.isFinite(w.x)) return;
    if (!stroke) {
      strokePts = [w.clone(), w.clone()];
      stroke = new THREE.Line(new THREE.BufferGeometry().setFromPoints(strokePts),
        new THREE.LineBasicMaterial({ color: NEON2, transparent: true, opacity: 0.95,
          blending: THREE.AdditiveBlending, depthWrite: false }));
      ink.add(stroke);
    }
    const last = strokePts[strokePts.length - 1];
    if (last.distanceTo(w) > 0.03) {
      strokePts.push(w.clone());
      stroke.geometry.setFromPoints(strokePts);
    }
    strokeT = performance.now();
  }
  function inkEndMaybe() { if (stroke && performance.now() - strokeT > 260) stroke = null; }

  // ---------- medir ----------
  const measure = new THREE.Group(); scene.add(measure);
  let mA = null, mLabel = null;
  function clearMeasure() { [...measure.children].forEach((c) => measure.remove(c)); mA = null; mLabel = null; }
  function measureTap(w) {
    if (!Number.isFinite(w.x)) return;
    if (!mA) {
      mA = w.clone();
      const d = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 10),
        new THREE.MeshBasicMaterial({ color: AMBER }));
      d.position.copy(mA); measure.add(d);
    } else {
      const dist = mA.distanceTo(w);
      measure.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([mA, w]),
        new THREE.LineBasicMaterial({ color: AMBER, transparent: true, opacity: 0.9,
          blending: THREE.AdditiveBlending })));
      const d2 = new THREE.Mesh(new THREE.SphereGeometry(0.06, 12, 10),
        new THREE.MeshBasicMaterial({ color: AMBER }));
      d2.position.copy(w); measure.add(d2);
      const lbl = makeTextSprite(dist.toFixed(2) + " u");
      lbl.position.copy(mA).add(w).multiplyScalar(0.5).add(new THREE.Vector3(0, 0.2, 0));
      measure.add(lbl);
      mA = null;
    }
  }
  function makeTextSprite(txt) {
    const c = document.createElement("canvas"); c.width = 256; c.height = 64;
    const x = c.getContext("2d");
    x.font = '600 34px "Segoe UI", monospace'; x.fillStyle = "#ffb24d";
    x.shadowColor = "#ffb24d"; x.shadowBlur = 10; x.textBaseline = "middle";
    x.fillText(txt, 8, 34);
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c),
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    s.scale.set(256 / 190, 64 / 190, 1);
    return s;
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

  // sprite de texto do menu — leve, sem caixa, no estilo do HUD
  function mkText(txt, color = "#bfe9ff") {
    const FS = 30, dpr = Math.min(devicePixelRatio || 1, 2);
    const c = document.createElement("canvas");
    let x = c.getContext("2d");
    x.font = `600 ${FS}px "Segoe UI", Consolas, sans-serif`;
    const label = String(txt).toUpperCase();
    const tw = x.measureText(label).width;
    c.width = Math.ceil((tw + 16) * dpr); c.height = Math.ceil((FS + 14) * dpr);
    x = c.getContext("2d"); x.scale(dpr, dpr);
    x.font = `600 ${FS}px "Segoe UI", Consolas, sans-serif`;
    x.textBaseline = "middle"; x.textAlign = "center";
    x.fillStyle = color; x.shadowColor = color; x.shadowBlur = 8;
    x.fillText(label, c.width / dpr / 2, c.height / dpr / 2);
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter; tex.anisotropy = 4;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true,
      depthWrite: false, blending: THREE.AdditiveBlending }));
    s.scale.set(c.width / dpr / 260, c.height / dpr / 260, 1);
    return s;
  }

  // ---------- interação ----------
  const C_NEON = new THREE.Color(NEON), C_NEON2 = new THREE.Color(NEON2), C_AMBER = new THREE.Color(AMBER);
  const C_LOCK = new THREE.Color(0x7affc0);
  const st = { resizeRef: 0, rotPrev: null, allPrev: null, selPinchWas: false,
    poked: new Set(), pokeT: 0, trackPrev: null, palmT: 0, palmC: null,
    menuOn: false, menuAnchor: null, menuHover: -1, menuFrac: 0, menuCursor: null,
    menuDwellStart: 0, palmStart: 0, palmGrace: 0, scrubT: null };
  let dbgDot = [0, 0], dbgOn = false;
  let selectorId = null;   // id da mão que é a "seletora" (fica grudado)

  function nearestOnScreen(px, py, maxDistPx) {
    let best = null, bd = maxDistPx;
    for (const s of shapes) {
      if (s.locked) continue;
      const [sx, sy] = worldToPx(s.obj.position);
      const d = Math.hypot(sx - px, sy - py);
      if (d < bd) { bd = d; best = s; }
    }
    return best;
  }

  function interact(res) {
    const now = performance.now();
    const hands = (res && res.hands) || [];
    hands.forEach((h) => { h.role = null; });
    if (!hands.length) { st.allPrev = null; st.rotPrev = null; return; }

    // SELETORA = grudada por identidade; muda só se a OUTRA mão pinçar
    let selH = hands.find((h) => h.id === selectorId);
    const pinchers = hands.filter((h) => h.gesture && h.gesture.pinch >= 0.9);
    if (pinchers.length && (!selH || pinchers.indexOf(selH) < 0)) {
      selH = pinchers[0];
    }
    if (!selH) selH = hands[0];
    selectorId = selH.id;
    let modH = hands.find((h) => h !== selH) || null;
    selH.role = "selector"; if (modH) modH.role = "modifier";

    const sg = selH.gesture || {};
    const mg = (modH && modH.gesture) || {};
    const selPx = sg.pinchAt ? toScreenPx(sg.pinchAt.x, sg.pinchAt.y) : null;
    const modC = modH ? handCenter(modH.landmarks) : null;
    const modPx = mg.pinchAt ? toScreenPx(mg.pinchAt.x, mg.pinchAt.y) : null;
    const R = Math.min(innerWidth, innerHeight) * 0.22;   // raio de "pega" em pixels

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
      if (selected && !selected.locked && mg.name !== "punho" && sg.name !== "paz") {
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

    // ---- ✌️ SELETORA: gira a forma com UMA mão só (roll + movimento) ----
    if (selected && !selected.locked && !selected.math && sg.name === "paz") {
      const lm = selH.landmarks;
      const roll = Math.atan2(lm[5].y - lm[17].y, lm[5].x - lm[17].x);   // inclinação da palma
      const c = handCenter(lm);
      if (st.twistPrev != null) {
        let dr = roll - st.twistPrev.roll;
        if (dr > Math.PI) dr -= TAU; if (dr < -Math.PI) dr += TAU;
        selected.obj.rotation.z -= finite(dr);
        selected.obj.rotation.y += finite(c.x - st.twistPrev.x) * 4;
      }
      st.twistPrev = { roll, x: c.x, y: c.y };
    } else st.twistPrev = null;

    // ---- 🖐+🖐 / ✊+✊ TRACKBALL: gira a forma com as DUAS mãos, como uma bola ----
    const twoBall = selected && !selected.locked && !selected.math && modH
      && ((sg.name === "punho" && mg.name === "punho")
        || (sg.name === "palma" && mg.name === "palma"));
    if (twoBall) {
      const cA = handCenter(selH.landmarks), cB = handCenter(modH.landmarks);
      const cur = { ang: Math.atan2(cB.y - cA.y, cB.x - cA.x),
        mx: (cA.x + cB.x) / 2, my: (cA.y + cB.y) / 2 };
      if (st.trackPrev) {
        let da = cur.ang - st.trackPrev.ang;
        if (da > Math.PI) da -= TAU; if (da < -Math.PI) da += TAU;
        selected.obj.rotation.z -= finite(da);
        selected.obj.rotation.y += finite(cur.mx - st.trackPrev.mx) * 6;
        selected.obj.rotation.x += finite(cur.my - st.trackPrev.my) * 6;
      }
      st.trackPrev = cur;
    } else st.trackPrev = null;

    // ---- MODIFICADORA (só com algo selecionado) ----
    if (selected && !selected.locked && modH && !twoBall) {
      if (mg.name === "punho" && modC) {
        const [mx, my] = toScreenPx(modC.x, modC.y);
        const w = pxToWorld(mx, my, selected._grabZ || 0);
        if (Number.isFinite(w.x)) selected.obj.position.copy(w);
      } else if (mg.pinch >= 0.9 && sg.pinch >= 0.9 && selPx && modPx) {
        const d = Math.hypot(selPx[0] - modPx[0], selPx[1] - modPx[1]);
        if (!st.resizeRef || !Number.isFinite(st.resizeRef)) st.resizeRef = Math.max(40, d) / Math.max(0.25, selected.userScale);
        const ns = d / st.resizeRef;
        selected.userScale = Math.max(0.25, Math.min(6, Number.isFinite(ns) ? ns : selected.userScale));
      } else if (mg.name === "paz" && modC && !selected.math) {
        // gira — proibido em modelos 2D/texto (triângulo, tabelas)
        if (st.rotPrev) {
          selected.obj.rotation.y += finite(modC.x - st.rotPrev.x) * 5;
          selected.obj.rotation.x += finite(modC.y - st.rotPrev.y) * 5;
        }
        st.rotPrev = modC;
      }
      if (mg.pinch < 0.9) st.resizeRef = 0;
      if (mg.name !== "paz") st.rotPrev = null;
    } else { st.resizeRef = 0; st.rotPrev = null; }

    // ---- ✋ MODIFICADORA sobre forma animada: CONGELA e navega no tempo ----
    st.scrubT = null;
    if (!twoBall && selected && selected.upd && modH && mg.name === "palma" && modC) {
      const u = Math.min(1, Math.max(0, modC.x));       // 0..1 pela posição da mão
      st.scrubT = u * 12;                               // 12 s de linha do tempo
      try { selected.upd(st.scrubT); } catch (_) { /* nada */ }
    }

    // ---- ✋ MENU DE MARCAÇÃO: 1 mão só. Mostra a palma ~0,5 s -> abre.
    //      Depois EMPURRA a mesma palma numa direção e SEGURA ~0,5 s pra escolher.
    //      cima = Limpar tudo · direita = Trava/Solta · baixo = Duplicar · esquerda = Explodir ----
    const selPalm = !twoBall && !st.scrubT && sg.name === "palma";
    const REACH = Math.max(45, innerHeight * 0.06);      // empurrão mínimo, relativo à tela
    const palmC0 = selPalm ? toScreenPx(handCenter(selH.landmarks).x, handCenter(selH.landmarks).y) : null;
    if (selPalm && !st.menuOn) {
      if (!st.palmStart) { st.palmStart = now; st.palmOpenAt = palmC0; }
      if (Math.hypot(palmC0[0] - st.palmOpenAt[0], palmC0[1] - st.palmOpenAt[1]) > REACH * 1.5) st.palmOpenAt = palmC0;
      if (now - st.palmStart > 500) {
        st.menuOn = true;
        st.menuOrigin = st.palmOpenAt.slice();          // onde a mão estava (mede o empurrão)
        st.menuAnchor = [Math.max(260, Math.min(innerWidth - 260, st.palmOpenAt[0])),
          Math.max(170, Math.min(innerHeight - 170, st.palmOpenAt[1]))];   // clampado (desenho)
      }
      st.palmGrace = 0; st.menuHover = -1; st.menuFrac = 0;
    } else if (st.menuOn && selPalm) {
      const dx = palmC0[0] - st.menuOrigin[0], dy = palmC0[1] - st.menuOrigin[1];
      const reach = Math.hypot(dx, dy);
      const DIRS = [[0, -1], [1, 0], [0, 1], [-1, 0]];
      let hover = -1, best = 0.5;
      if (reach > REACH) DIRS.forEach((d, i) => {
        const dot = (dx * d[0] + dy * d[1]) / reach;
        if (dot > best) { best = dot; hover = i; }
      });
      let frac = 0;
      if (hover >= 0) {
        if (hover !== st.menuHover) st.menuDwellStart = now;
        frac = Math.min(1, (now - st.menuDwellStart) / 1100);   // segura ~1,1 s pra confirmar
        if (frac >= 1) { try { MENU[hover].fn(); } catch (_) { /* nada */ } _closeMenu(); }
      } else { st.menuDwellStart = 0; }
      st.menuHover = hover; st.menuFrac = frac;
      st.menuCursor = [Math.max(-230, Math.min(230, dx)), Math.max(-230, Math.min(230, dy))];
      st.palmGrace = 0;
    } else if (st.menuOn) {
      // sem palma: dá uma graça de ~6 frames antes de fechar (jitter do tracker)
      st.palmGrace = (st.palmGrace || 0) + 1;
      if (st.palmGrace > 6) _closeMenu();
    } else {
      st.palmStart = 0; st.palmOpenAt = null;
    }
    _layoutMenu();

    // ---- modo MEDIR: pinça marca pontos ----
    if (st.measureMode) {
      const p = selPx || modPx;
      const anyPinch = sg.pinch >= 0.9 || mg.pinch >= 0.9;
      if (anyPinch && !st.measWas && p) measureTap(pxToWorld(p[0], p[1], 0));
      st.measWas = anyPinch;
    }

    // ---- ☝️ APONTAR: desenha (modo caneta) ou encosta pra apagar ----
    fx2d.clear();
    const touchR = R * 0.5;
    let anyPoint = false;
    for (const h of hands) {
      const g = h.gesture;
      if (!g || g.name !== "apontar") continue;
      anyPoint = true;
      const lm = h.landmarks;
      const [tx, ty] = toScreenPx(lm[8].x, lm[8].y);
      const a = pxToWorld(tx, ty, 0);
      if (st.drawMode) {
        inkPoint(a);
        pokeDot.position.copy(a); pokeDot.material.opacity = 0.9;
        continue;
      }
      const dir = a.clone().sub(pxToWorld(...toScreenPx(lm[6].x, lm[6].y), 0)).normalize();
      fx2d.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([a, a.clone().add(dir.multiplyScalar(9))]),
        new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending })));
      pokeDot.position.copy(a); pokeDot.material.opacity = 0.8;

      const hadSel = selected;   // congela a seleção deste frame
      for (const s of [...shapes]) {
        const [sx, sy] = worldToPx(s.obj.position);
        const on = Math.hypot(sx - tx, sy - ty) < touchR;
        s._pokeN = on ? (s._pokeN || 0) + 1 : 0;
        if (!on || s._pokeN < 3) continue;
        s._point = 1;
        if (hadSel) {
          // com seleção: SÓ o selecionado some, e só se for ele que eu encostei
          if (s === hadSel) removeShape(s);
        } else {
          st.poked.add(s.id); st.pokeT = now;
        }
      }
    }
    if (!anyPoint) {
      pokeDot.material.opacity += (0 - pokeDot.material.opacity) * 0.3;
      shapes.forEach((s) => { s._pokeN = 0; });
    }
    inkEndMaybe();

    // apaga TODOS: sem seleção, encostou em todos -> some tudo
    if (!selected && shapes.length && [...shapes].every((s) => st.poked.has(s.id))) {
      clearAll();
    }
    if (now - st.pokeT > 1600) st.poked.clear();
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
  // ponta do dedo quando aponta
  const pokeDot = new THREE.Sprite(new THREE.SpriteMaterial({
    color: 0x9becff, transparent: true, opacity: 0, depthWrite: false,
    blending: THREE.AdditiveBlending }));
  pokeDot.scale.set(0.3, 0.3, 1);
  scene.add(pokeDot);

  // ---------- menu de marcação (1 mão: palma parada abre, empurra pra escolher) ----------
  //  ordem = cima, direita, baixo, esquerda
  const MENU = [
    { t: "Limpar", fn: () => clearAll() },
    { t: "Travar", fn: () => lockSelected(null) },
    { t: "Duplicar", fn: () => dupSelected() },
    { t: "Explodir", fn: () => explodeSelected() },
  ];
  const MENU_OFF = [[0, -132], [214, 0], [0, 132], [-214, 0]];   // px a partir do centro
  const menuGrp = new THREE.Group(); scene.add(menuGrp);
  MENU.forEach((m) => { m.spr = mkText(m.t); m.baseScale = m.spr.scale.clone(); menuGrp.add(m.spr); });
  // aro fino no centro + 4 tiquinhos indicando as direções
  const menuBase = new THREE.Group(); menuGrp.add(menuBase);
  const ringMat = new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0,
    blending: THREE.AdditiveBlending, depthWrite: false });
  const ringPts = [];
  for (let i = 0; i <= 48; i++) ringPts.push(new THREE.Vector3(Math.cos(i / 48 * TAU) * 0.34, Math.sin(i / 48 * TAU) * 0.34, 0));
  menuBase.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ringPts), ringMat));
  // cursor: um pequeno "+" que segue a mão
  const curMat = new THREE.LineBasicMaterial({ color: AMBER, transparent: true, opacity: 0,
    blending: THREE.AdditiveBlending, depthWrite: false });
  const menuCur = new THREE.Group();
  menuCur.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
    [new THREE.Vector3(-0.1, 0, 0), new THREE.Vector3(0.1, 0, 0)]), curMat));
  menuCur.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
    [new THREE.Vector3(0, -0.1, 0), new THREE.Vector3(0, 0.1, 0)]), curMat));
  menuGrp.add(menuCur);
  // anel de progresso do dwell no item escolhido
  const menuRing = new THREE.Mesh(new THREE.RingGeometry(0.16, 0.19, 32),
    new THREE.MeshBasicMaterial({ color: AMBER, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false }));
  menuGrp.add(menuRing);

  function _closeMenu() {
    st.menuOn = false; st.palmStart = 0; st.menuAnchor = null; st.menuOrigin = null;
    st.palmOpenAt = null; st.menuDwellStart = 0; st.menuHover = -1;
    st.menuFrac = 0; st.menuCursor = null;
  }
  function _layoutMenu() {
    const show = st.menuOn ? 1 : 0;
    const anchor = st.menuAnchor;
    if (!(anchor && Number.isFinite(anchor[0]))) {
      MENU.forEach((m) => { m.spr.material.opacity += (0 - m.spr.material.opacity) * 0.3; });
      ringMat.opacity += (0 - ringMat.opacity) * 0.3;
      curMat.opacity += (0 - curMat.opacity) * 0.3;
      menuRing.material.opacity += (0 - menuRing.material.opacity) * 0.3;
      return;
    }
    const wc = pxToWorld(anchor[0], anchor[1], 0);
    // escala em mundo por px, pra manter tudo do mesmo tamanho na tela
    const wc2 = pxToWorld(anchor[0] + 100, anchor[1], 0);
    const uPerPx = Number.isFinite(wc.x) && Number.isFinite(wc2.x) ? Math.abs(wc2.x - wc.x) / 100 : 0.01;
    menuBase.position.set(wc.x, wc.y, 0);
    MENU.forEach((m, i) => {
      m.spr.position.set(wc.x + MENU_OFF[i][0] * uPerPx, wc.y - MENU_OFF[i][1] * uPerPx, 0.02);
      const hot = i === st.menuHover;
      m.spr.material.opacity += ((show ? (hot ? 1 : 0.5) : 0) - m.spr.material.opacity) * 0.3;
      m.spr.scale.copy(m.baseScale).multiplyScalar(hot ? 1.15 : 1);
    });
    const cur = st.menuCursor || [0, 0];
    menuCur.position.set(wc.x + cur[0] * uPerPx, wc.y - cur[1] * uPerPx, 0.03);
    ringMat.opacity += ((show ? 0.4 : 0) - ringMat.opacity) * 0.3;
    curMat.opacity += ((show ? 0.85 : 0) - curMat.opacity) * 0.3;
    const f = st.menuFrac || 0;
    if (st.menuHover >= 0) {
      menuRing.position.set(wc.x + MENU_OFF[st.menuHover][0] * uPerPx,
        wc.y - MENU_OFF[st.menuHover][1] * uPerPx, 0.01);
      menuRing.scale.setScalar(2.4 - f * 1.4);
      menuRing.material.opacity = 0.25 + f * 0.7;
    } else { menuRing.material.opacity += (0 - menuRing.material.opacity) * 0.3; }
  }

  // ---------- loop ----------
  let active = false;
  function setActive(on) {
    active = on;
    cv.style.display = on ? "block" : "none";
    if (!on) { renderer.clear(); st.poked.clear(); }
  }

  let _errLogged = false;
  function tick(t, res) {
    if (!active) return;
    try { _tick(t, res); } catch (e) {
      if (!_errLogged) { _errLogged = true; dbg("ERRO tick: " + (e && e.message) + " | " + (e && (e.stack || "")).slice(0, 300)); }
      try { renderer.render(scene, camera); } catch (_) { /* nada */ }
    }
  }

  function _tick(t, res) {
    try { interact(res); } catch (e) {
      if (!_errLogged) { _errLogged = true; dbg("ERRO interact: " + (e && e.message) + " | " + (e && (e.stack || "")).slice(0, 300)); }
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
      s.lockL = (s.lockL || 0) + ((s.locked ? 1 : 0) - (s.lockL || 0)) * 0.15;
      const ud = s.obj.userData;
      if (ud.wire) {
        ud.wire.material.color.copy(C_NEON).lerp(C_AMBER, s.amber).lerp(C_LOCK, s.lockL * 0.8);
        ud.wire.material.opacity = 0.92 + s.amber * 0.06;
        ud.fill.material.color.copy(C_NEON2).lerp(C_AMBER, s.amber);
        ud.fill.material.opacity = 0.07 + s.amber * 0.12 + (s._point || 0) * 0.1;
      } else {
        // modelo composto (triângulo, tabelas): tinge TUDO em direção ao âmbar
        if (!s._mats) {
          s._mats = [];
          s.obj.traverse((o) => {
            if (o.material && o.material.color) s._mats.push({ m: o.material, c: o.material.color.clone() });
          });
        }
        for (const x of s._mats) x.m.color.copy(x.c).lerp(C_AMBER, s.amber * 0.9);
      }
      s._point = (s._point || 0) * 0.85;

      if (s !== selected && !s.math && !s.locked) {
        s.obj.rotation.x += s.spin.x;
        s.obj.rotation.y += s.spin.y;
        s.obj.position.y += Math.sin(t * 1.05 + s.bob) * 0.0014;
      }
      if (s.upd && s !== selected && !s.locked) { try { s.upd(t); } catch (_) { s.upd = null; } }
      // explodir: interpola filhos até o alvo
      if (s.exploded != null) {
        for (const c of s.obj.children) {
          if (c.userData && c.userData._target) c.position.lerp(c.userData._target, 0.15);
        }
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
  return { setActive, onControl, tick, count: () => shapes.length, clearAll, spawn, _geo: makeGeo,
    hasSelection: () => !!selected };
})();

/* Jarvis — biblioteca de modelos de estudo (holograma).
   window.jarvisModels.build(name, opts) -> THREE.Group | null
   Modelos que animam expõem  group.userData.update(t).                       */
window.jarvisModels = (() => {
  "use strict";
  const NEON = 0x7ce4ff, SOFT = 0x9becff, AMBER = 0xffb24d, GREEN = 0x7affc0, RED = 0xff8a8a;
  const TAU = Math.PI * 2;

  // ---------- helpers ----------
  function label(text, o = {}) {
    o = Object.assign({ font: 40, pad: 14, color: NEON, bg: null, weight: 600, scale: 230 }, o);
    const c = document.createElement("canvas");
    let x = c.getContext("2d");
    x.font = `${o.weight} ${o.font}px "Segoe UI", Consolas, monospace`;
    const lines = String(text).split("\n");
    const w = Math.max(...lines.map((l) => x.measureText(l).width)) + o.pad * 2;
    const lh = o.font * 1.38;
    c.width = Math.ceil(w); c.height = Math.ceil(lh * lines.length + o.pad * 2);
    x = c.getContext("2d");
    x.font = `${o.weight} ${o.font}px "Segoe UI", Consolas, monospace`;
    if (o.bg) {
      x.fillStyle = o.bg; x.fillRect(0, 0, c.width, c.height);
      x.strokeStyle = "rgba(124,228,255,0.45)"; x.lineWidth = 2; x.strokeRect(1, 1, c.width - 2, c.height - 2);
    }
    x.fillStyle = colStr(o.color); x.textBaseline = "top";
    x.shadowColor = colStr(o.color); x.shadowBlur = 12;
    lines.forEach((l, i) => x.fillText(l, o.pad, o.pad + i * lh));
    const tex = new THREE.CanvasTexture(c); tex.minFilter = THREE.LinearFilter; tex.anisotropy = 4;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false,
      blending: o.bg ? THREE.NormalBlending : THREE.AdditiveBlending }));
    s.scale.set(c.width / o.scale, c.height / o.scale, 1);
    return s;
  }
  const colStr = (c) => (typeof c === "number" ? "#" + c.toString(16).padStart(6, "0") : c);

  // sprite de texto que dá pra reescrever a cada frame
  function dynLabel(w = 420, h = 110, o = {}) {
    o = Object.assign({ font: 30, color: SOFT, scale: 230 }, o);
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    const tex = new THREE.CanvasTexture(c); tex.minFilter = THREE.LinearFilter;
    const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true,
      depthWrite: false, blending: THREE.AdditiveBlending }));
    spr.scale.set(w / o.scale, h / o.scale, 1);
    spr.setText = (txt) => {
      const x = c.getContext("2d");
      x.clearRect(0, 0, w, h);
      x.font = `600 ${o.font}px "Segoe UI", Consolas, monospace`;
      x.fillStyle = colStr(o.color); x.textBaseline = "top";
      x.shadowColor = colStr(o.color); x.shadowBlur = 10;
      String(txt).split("\n").forEach((l, i) => x.fillText(l, 6, 6 + i * o.font * 1.35));
      tex.needsUpdate = true;
    };
    return spr;
  }
  function line(pts, color = NEON, opacity = 0.95) {
    return new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity,
        blending: THREE.AdditiveBlending, depthWrite: false }));
  }
  const V = (x, y, z = 0) => new THREE.Vector3(x, y, z);
  function put(g, spr, x, y, s = 1) { spr.position.set(x, y, 0.02); spr.scale.multiplyScalar(s); g.add(spr); return spr; }
  function ball(r, color) {
    return new THREE.Mesh(new THREE.SphereGeometry(r, 20, 16),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85 }));
  }
  function stick(a, b, color = SOFT, rad = 0.05) {
    const d = b.clone().sub(a), len = d.length();
    const m = new THREE.Mesh(new THREE.CylinderGeometry(rad, rad, len, 10),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6 }));
    m.position.copy(a).add(b).multiplyScalar(0.5);
    m.quaternion.setFromUnitVectors(V(0, 1, 0), d.normalize());
    return m;
  }
  function arrow(from, to, color = AMBER, label3d) {
    const g = new THREE.Group();
    g.add(line([from, to], color, 0.95));
    const dir = to.clone().sub(from).normalize();
    const head = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.24, 12),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 }));
    head.position.copy(to);
    head.quaternion.setFromUnitVectors(V(0, 1, 0), dir);
    g.add(head);
    if (label3d) put(g, label(label3d, { color, font: 30 }), to.x + dir.x * 0.3, to.y + dir.y * 0.3 + 0.15, 0.6);
    return g;
  }
  function axes(sz = 2.4, lab = true) {
    const g = new THREE.Group();
    g.add(line([V(-sz, 0), V(sz, 0)], 0x4bb6d6, 0.6));
    g.add(line([V(0, -sz), V(0, sz)], 0x4bb6d6, 0.6));
    for (let i = -Math.floor(sz); i <= sz; i++) {
      if (!i) continue;
      g.add(line([V(i, -0.06), V(i, 0.06)], 0x4bb6d6, 0.4));
      g.add(line([V(-0.06, i), V(0.06, i)], 0x4bb6d6, 0.4));
    }
    if (lab) { put(g, label("x", { color: 0x8fd8ee, font: 28 }), sz + 0.2, -0.25, 0.55);
               put(g, label("y", { color: 0x8fd8ee, font: 28 }), 0.22, sz + 0.2, 0.55); }
    return g;
  }

  // ================= A1 — círculo trigonométrico =================
  function circulo() {
    const g = new THREE.Group();
    const R = 1.8;
    g.add(axes(2.5));
    // circunferência
    const cpts = [];
    for (let i = 0; i <= 96; i++) cpts.push(V(R * Math.cos(i / 96 * TAU), R * Math.sin(i / 96 * TAU)));
    g.add(line(cpts, NEON, 0.7));

    const radius = line([V(0, 0), V(R, 0)], AMBER, 1);
    const sinSeg = line([V(R, 0), V(R, 0)], GREEN, 1);
    const cosSeg = line([V(0, 0), V(R, 0)], 0xff9de0, 1);
    const dot = ball(0.06, AMBER);
    g.add(radius); g.add(sinSeg); g.add(cosSeg); g.add(dot);
    const readout = dynLabel(480, 90);
    put(g, readout, 0, -3.0, 0.6);
    readout.setText("θ = 0°\nsen 0.00   cos 1.00");
    put(g, label("sen θ", { color: colStr(GREEN), font: 24 }), R + 0.55, 0.9, 0.5);
    put(g, label("cos θ", { color: "#ff9de0", font: 24 }), 0.9, -0.35, 0.5);

    g.userData.type = "circulo_trig";
    g.userData.update = (t) => {
      const a = (t * 0.55) % TAU;
      const x = R * Math.cos(a), y = R * Math.sin(a);
      radius.geometry.setFromPoints([V(0, 0), V(x, y)]);
      sinSeg.geometry.setFromPoints([V(x, 0), V(x, y)]);
      cosSeg.geometry.setFromPoints([V(0, 0), V(x, 0)]);
      dot.position.set(x, y, 0);
      const deg = Math.round(a / TAU * 360);
      readout.setText(`θ = ${deg}°\nsen ${Math.sin(a).toFixed(2)}   cos ${Math.cos(a).toFixed(2)}`);
    };
    return g;
  }

  // ================= A6 — plotter de função =================
  function plot(opts) {
    const expr = (opts && opts.expr) || "x^2";
    const f = compile(expr);
    if (!f) return null;
    const g = new THREE.Group();
    g.add(axes(3));
    let pts = [];
    const flush = () => { if (pts.length > 1) g.add(line(pts, NEON, 0.95)); pts = []; };
    for (let px = -3; px <= 3.001; px += 0.04) {
      const y = f(px);
      if (Number.isFinite(y) && Math.abs(y) <= 3.3) pts.push(V(px, y));
      else flush();
    }
    flush();
    put(g, label("y = " + expr.replace(/\*/g, "·").replace(/\^/g, "^"), { font: 32, color: AMBER }), 0, 3.4, 0.6);
    g.userData.type = "plot";
    return g;
  }
  function compile(expr) {
    let e = String(expr).toLowerCase().replace(/\s+/g, "")
      .replace(/^y=/, "").replace(/^f\(x\)=/, "")
      .replace(/\^/g, "**")
      .replace(/(\d)(x|\()/g, "$1*$2")          // 2x -> 2*x
      .replace(/(x|\))(x|\()/g, "$1*$2")
      .replace(/\b(sin|sen)\b/g, "Math.sin").replace(/\bcos\b/g, "Math.cos")
      .replace(/\btan\b/g, "Math.tan").replace(/\bsqrt|raiz\b/g, "Math.sqrt")
      .replace(/\blog\b/g, "Math.log").replace(/\babs\b/g, "Math.abs")
      .replace(/\bpi\b/g, "Math.PI").replace(/\be\b/g, "Math.E");
    if (!/^[-+*/(). 0-9xMathsincoqrtaeglbP]+$/.test(e.replace(/\*\*/g, ""))) return null;
    try { const fn = new Function("x", "return (" + e + ");"); fn(1); return fn; }
    catch (_) { return null; }
  }

  // ================= A2 — sólido + fórmula =================
  const SOLID_FORMULA = {
    esfera: ["sphere", "V = 4/3 · π · r³\nA = 4 · π · r²"],
    cubo: ["cube", "V = a³\nA = 6 · a²"],
    cilindro: ["cylinder", "V = π · r² · h\nA = 2πr(r + h)"],
    cone: ["cone", "V = (π · r² · h) / 3\nA = πr(r + g)"],
    piramide: ["pyramid", "V = (Ab · h) / 3"],
  };
  function solidFormula(opts) {
    const key = (opts && opts.solid) || "esfera";
    const def = SOLID_FORMULA[key] || SOLID_FORMULA.esfera;
    const g = new THREE.Group();
    const geo = window.jarvisHolo && window.jarvisHolo._geo ? window.jarvisHolo._geo(def[0]) : new THREE.SphereGeometry(0.9, 20, 14);
    const wire = new THREE.LineSegments(new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.9,
        blending: THREE.AdditiveBlending, depthWrite: false }));
    wire.position.x = -1.3;
    g.add(wire);
    put(g, label(key.toUpperCase() + "\n\n" + def[1], { font: 34, color: SOFT, bg: "rgba(4,16,24,0.82)", scale: 170 }), 1.4, 0, 0.6);
    g.userData.type = "solido_formula";
    g.userData.update = (t) => { wire.rotation.y = t * 0.5; wire.rotation.x = Math.sin(t * 0.3) * 0.2; };
    return g;
  }

  // ================= A3 — física =================
  function corpoLivre() {
    const g = new THREE.Group();
    const box = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.9, 0.9),
      new THREE.MeshBasicMaterial({ color: NEON, transparent: true, opacity: 0.12 }));
    g.add(box);
    g.add(new THREE.LineSegments(new THREE.WireframeGeometry(new THREE.BoxGeometry(0.9, 0.9, 0.9)),
      new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.8 })));
    g.add(arrow(V(0, 0), V(0, -1.6), AMBER, "P = m·g"));
    g.add(arrow(V(0, 0.45), V(0, 2), GREEN, "N"));
    g.add(arrow(V(0.45, 0), V(2, 0), 0xff9de0, "F"));
    g.add(arrow(V(-0.45, 0), V(-1.5, 0), RED, "at"));
    put(g, label("DIAGRAMA DE CORPO LIVRE", { font: 28, color: SOFT }), 0, 2.6, 0.6);
    g.userData.type = "corpo_livre";
    return g;
  }
  function lancamento() {
    const g = new THREE.Group();
    g.add(line([V(-3, -1.6), V(3, -1.6)], 0x4bb6d6, 0.6));
    const v0 = 3.2, ang = Math.PI / 4, gAcc = 4.5;
    const pts = [];
    for (let t = 0; t <= 2; t += 0.04) {
      const x = -2.6 + v0 * Math.cos(ang) * t;
      const y = -1.6 + v0 * Math.sin(ang) * t - 0.5 * gAcc * t * t;
      if (y < -1.7) break;
      pts.push(V(x, y));
    }
    g.add(line(pts, NEON, 0.95));
    g.add(arrow(V(-2.6, -1.6), V(-2.6 + Math.cos(ang) * 1.2, -1.6 + Math.sin(ang) * 1.2), AMBER, "v₀"));
    const ball0 = ball(0.09, AMBER); g.add(ball0);
    put(g, label("LANÇAMENTO OBLÍQUO\nx = v₀cosθ·t     y = v₀senθ·t − ½g·t²", { font: 26, color: SOFT }), 0, 2, 0.6);
    g.userData.type = "lancamento";
    g.userData.update = (t) => {
      const i = Math.floor((t * 18) % pts.length);
      if (pts[i]) ball0.position.copy(pts[i]);
    };
    return g;
  }
  function planoInclinado() {
    const g = new THREE.Group();
    const A = V(-2.4, -1.4), B = V(2.4, -1.4), C = V(2.4, 1.2);
    g.add(line([A, B, C, A], NEON, 0.9));
    // bloco no meio da rampa
    const mid = A.clone().add(C).multiplyScalar(0.5);
    const along = C.clone().sub(A).normalize();
    const normal = V(-along.y, along.x);
    const blk = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.4, 0.4),
      new THREE.MeshBasicMaterial({ color: NEON, transparent: true, opacity: 0.15 }));
    blk.position.copy(mid).add(normal.clone().multiplyScalar(0.22));
    blk.rotation.z = Math.atan2(along.y, along.x);
    g.add(blk);
    g.add(arrow(blk.position, blk.position.clone().add(V(0, -1.3)), AMBER, "P"));
    g.add(arrow(blk.position, blk.position.clone().add(normal.clone().multiplyScalar(1.1)), GREEN, "N"));
    g.add(arrow(blk.position, blk.position.clone().add(along.clone().multiplyScalar(-1.1)), 0xff9de0, "Px = P·senθ"));
    put(g, label("PLANO INCLINADO", { font: 28, color: SOFT }), 0, 1.9, 0.6);
    put(g, label("θ", { color: AMBER, font: 30 }), A.x + 0.7, A.y + 0.12, 0.55);
    g.userData.type = "plano_inclinado";
    return g;
  }

  // ================= A4 — química =================
  function molecula(kind) {
    const g = new THREE.Group();
    const O = 0xff8a8a, H = 0xdfefff, Cc = 0x9bb0c0, N = 0x8ab6ff;
    if (kind === "agua") {
      const o = ball(0.34, O); g.add(o);
      const a = 104.5 * Math.PI / 180;
      const h1 = V(Math.cos(Math.PI / 2 + a / 2), Math.sin(Math.PI / 2 + a / 2)).multiplyScalar(0.95);
      const h2 = V(Math.cos(Math.PI / 2 - a / 2), Math.sin(Math.PI / 2 - a / 2)).multiplyScalar(0.95);
      [h1, h2].forEach((p) => { g.add(stick(V(0, 0), p)); const b = ball(0.2, H); b.position.copy(p); g.add(b); });
      put(g, label("H₂O — água", { font: 30, color: SOFT }), 0, -1.4, 0.6);
    } else if (kind === "metano") {
      const c = ball(0.34, Cc); g.add(c);
      const d = [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]].map((v) => V(...v).normalize().multiplyScalar(1.0));
      d.forEach((p) => { g.add(stick(V(0, 0, 0), p)); const b = ball(0.2, H); b.position.copy(p); g.add(b); });
      put(g, label("CH₄ — metano", { font: 30, color: SOFT }), 0, -1.6, 0.6);
      g.userData.update = (t) => { g.rotation.y = t * 0.5; };
    } else if (kind === "gas_carbonico" || kind === "co2") {
      const c = ball(0.3, Cc); g.add(c);
      [V(-1.15, 0), V(1.15, 0)].forEach((p) => {
        g.add(stick(V(0, 0), p.clone().multiplyScalar(0.55), AMBER));
        g.add(stick(V(0, 0.12), p.clone().multiplyScalar(0.55).add(V(0, 0.12)), AMBER));
        const b = ball(0.28, O); b.position.copy(p); g.add(b);
      });
      put(g, label("CO₂ — gás carbônico   (linear, 180°)", { font: 27, color: SOFT }), 0, -1.4, 0.6);
    } else if (kind === "amonia" || kind === "nh3") {
      const nn = ball(0.34, N); g.add(nn);
      [[0, 1, 0.35], [0.87, -0.5, 0.35], [-0.87, -0.5, 0.35]].forEach((d) => {
        const p = V(...d).normalize().multiplyScalar(1.0);
        g.add(stick(V(0, 0, 0), p)); const b = ball(0.2, H); b.position.copy(p); g.add(b);
      });
      put(g, label("NH₃ — amônia   (piramidal, ~107°)", { font: 27, color: SOFT }), 0, -1.7, 0.6);
      g.userData.update = (t) => { g.rotation.y = t * 0.45; };
    } else { // benzeno
      for (let i = 0; i < 6; i++) {
        const A = V(Math.cos(i / 6 * TAU), Math.sin(i / 6 * TAU)).multiplyScalar(1.0);
        const Bn = V(Math.cos((i + 1) / 6 * TAU), Math.sin((i + 1) / 6 * TAU)).multiplyScalar(1.0);
        g.add(stick(A, Bn, i % 2 ? AMBER : SOFT));
        const c = ball(0.22, Cc); c.position.copy(A); g.add(c);
        const hp = A.clone().multiplyScalar(1.6);
        g.add(stick(A, hp, H)); const hb = ball(0.14, H); hb.position.copy(hp); g.add(hb);
      }
      put(g, label("C₆H₆ — benzeno", { font: 30, color: SOFT }), 0, -1.9, 0.6);
      g.userData.update = (t) => { g.rotation.z = t * 0.3; };
    }
    g.userData.type = "molecula_" + kind;
    return g;
  }
  function tabelaPeriodica() {
    const g = new THREE.Group();
    put(g, label(
      "TABELA PERIÓDICA — grupos principais\n" +
      "  1  H                                          He\n" +
      "  Li Be              B  C  N  O  F  Ne\n" +
      "  Na Mg              Al Si P  S  Cl Ar\n" +
      "  K  Ca ... Zn       Ga Ge As Se Br Kr\n" +
      "  metais · ametais · gases nobres",
      { font: 30, color: SOFT, bg: "rgba(4,16,24,0.85)", scale: 150 }), 0, 0, 0.6);
    g.userData.type = "tabela_periodica";
    return g;
  }

  // ================= A5 — biologia (célula) =================
  function celula() {
    const g = new THREE.Group();
    const outer = [];
    for (let i = 0; i <= 80; i++) outer.push(V(1.9 * Math.cos(i / 80 * TAU), 1.5 * Math.sin(i / 80 * TAU)));
    g.add(line(outer, NEON, 0.85));
    const nuc = []; for (let i = 0; i <= 48; i++) nuc.push(V(0.6 * Math.cos(i / 48 * TAU) - 0.2, 0.6 * Math.sin(i / 48 * TAU)));
    g.add(line(nuc, AMBER, 0.9));
    for (let k = 0; k < 5; k++) {
      const a = k / 5 * TAU + 0.6;
      const m = ball(0.13, GREEN); m.position.set(1.0 * Math.cos(a), 0.85 * Math.sin(a), 0); g.add(m);
    }
    put(g, label("membrana", { font: 24, color: SOFT }), 1.7, 1.4, 0.55);
    put(g, label("núcleo", { font: 24, color: AMBER }), -0.2, 0.0, 0.55);
    put(g, label("mitocôndrias", { font: 22, color: GREEN }), 1.2, -1.3, 0.55);
    put(g, label("CÉLULA ANIMAL", { font: 28, color: SOFT }), 0, 1.95, 0.6);
    g.userData.type = "celula";
    return g;
  }

  // ================= B1 — onda (física) =================
  function onda(opts) {
    const g = new THREE.Group();
    g.add(axes(3.2, false));
    const A = 1.15, k = 2.1, w = 2.0;
    const wave = line([V(0, 0)], NEON, 0.95); g.add(wave);
    const dot = ball(0.09, AMBER); g.add(dot);
    // marcadores de amplitude e comprimento de onda
    g.add(line([V(-3, A), V(3, A)], 0x2a5a6e, 0.4));
    g.add(line([V(-3, -A), V(3, -A)], 0x2a5a6e, 0.4));
    put(g, label("A", { color: GREEN, font: 24 }), 3.15, A, 0.5);
    const lam = TAU / k;
    g.add(arrow(V(-2.6, -A - 0.5), V(-2.6 + lam, -A - 0.5), 0xff9de0));
    g.add(arrow(V(-2.6 + lam, -A - 0.5), V(-2.6, -A - 0.5), 0xff9de0));
    put(g, label("λ", { color: "#ff9de0", font: 24 }), -2.6 + lam / 2, -A - 0.9, 0.5);
    put(g, label("ONDA   y = A · sen(k·x − ω·t)", { font: 26, color: SOFT }), 0, 2.7, 0.6);
    g.userData.type = "onda";
    g.userData.update = (t) => {
      const pts = [];
      for (let x = -3; x <= 3.001; x += 0.05) pts.push(V(x, A * Math.sin(k * x - w * t)));
      wave.geometry.setFromPoints(pts);
      dot.position.set(2.4, A * Math.sin(k * 2.4 - w * t), 0);
    };
    return g;
  }

  // ================= B2 — pêndulo simples (física) =================
  function pendulo() {
    const g = new THREE.Group();
    const piv = V(0, 2.4);
    const pb = ball(0.08, SOFT); pb.position.copy(piv); g.add(pb);
    g.add(line([V(-1.3, 2.4), V(1.3, 2.4)], 0x4bb6d6, 0.5));
    const rod = line([piv, piv], SOFT, 0.85); g.add(rod);
    const bob = ball(0.3, AMBER); g.add(bob);
    const L = 3.4, th0 = 0.5;
    // arco tracejado do movimento
    const arc = [];
    for (let i = -1; i <= 1; i += 0.05) arc.push(V(piv.x + L * Math.sin(th0 * i), piv.y - L * Math.cos(th0 * i)));
    g.add(line(arc, 0x2a5a6e, 0.4));
    put(g, label("PÊNDULO SIMPLES\nT = 2π · √(L / g)", { font: 26, color: SOFT }), 0, 3.0, 0.6);
    g.userData.type = "pendulo";
    g.userData.update = (t) => {
      const th = th0 * Math.cos(t * 1.7);
      const end = V(piv.x + L * Math.sin(th), piv.y - L * Math.cos(th));
      rod.geometry.setFromPoints([piv, end]);
      bob.position.copy(end);
    };
    return g;
  }

  // ================= B3 — circuito em série (física) =================
  function circuito() {
    const g = new THREE.Group();
    const P = [V(-2.3, -1.5), V(2.3, -1.5), V(2.3, 1.5), V(-2.3, 1.5)];
    const seg = [[P[0], P[1]], [P[1], P[2]], [P[2], P[3]], [P[3], P[0]]];
    const segLen = seg.map(([a, b]) => b.distanceTo(a));
    const per = segLen.reduce((s, l) => s + l, 0);
    const at = (u) => {                       // u em 0..1 -> ponto no perímetro
      let d = u * per;
      for (let i = 0; i < 4; i++) {
        if (d <= segLen[i]) return seg[i][0].clone().lerp(seg[i][1], d / segLen[i]);
        d -= segLen[i];
      }
      return P[0].clone();
    };
    g.add(line([...P, P[0]], NEON, 0.55));
    // pilha (lado de baixo): duas barras
    g.add(line([V(-0.35, -1.5), V(-0.35, -1.15)], SOFT, 1));
    g.add(line([V(0.15, -1.5), V(0.15, -1.9)], SOFT, 1));
    put(g, label("+", { color: AMBER, font: 26 }), 0.15, -2.05, 0.5);
    put(g, label("V", { color: SOFT, font: 24 }), -0.9, -1.5, 0.5);
    // resistor (lado de cima): zigue-zague
    const zz = [V(-1.1, 1.5)];
    for (let i = 0; i < 6; i++) zz.push(V(-1.1 + i * 0.37 + 0.18, 1.5 + (i % 2 ? 0.28 : -0.28)));
    zz.push(V(1.1, 1.5));
    g.add(line(zz, GREEN, 1));
    put(g, label("R", { color: GREEN, font: 24 }), 0, 2.0, 0.5);
    put(g, label("CIRCUITO EM SÉRIE     V = R · I", { font: 25, color: SOFT }), 0, -2.5, 0.6);
    const dots = [];
    for (let i = 0; i < 10; i++) { const d = ball(0.07, AMBER); g.add(d); dots.push(d); }
    g.userData.type = "circuito";
    g.userData.update = (t) => {
      dots.forEach((d, i) => d.position.copy(at(((t * 0.18 + i / dots.length) % 1))));
    };
    return g;
  }

  // ================= B4 — campo elétrico (física) =================
  function campoEletrico() {
    const g = new THREE.Group();
    const qA = V(-1.6, 0), qB = V(1.6, 0);
    const a = ball(0.32, RED); a.position.copy(qA); g.add(a);
    const b = ball(0.32, 0x8ab6ff); b.position.copy(qB); g.add(b);
    put(g, label("+", { color: "#fff", font: 40 }), qA.x, qA.y, 0.5);
    put(g, label("−", { color: "#fff", font: 40 }), qB.x, qB.y, 0.5);
    // linhas de campo curvas de + para −
    for (let j = -3; j <= 3; j++) {
      if (!j && false) continue;
      const off = j * 0.42;
      const pts = [];
      for (let s = 0; s <= 1.0001; s += 0.04) {
        const x = qA.x + (qB.x - qA.x) * s;
        const bend = Math.sin(s * Math.PI) * off;
        pts.push(V(x, bend));
      }
      g.add(line(pts, j === 0 ? SOFT : 0x4bb6d6, 0.55));
      // seta no meio
      const mid = Math.floor(pts.length / 2);
      g.add(arrow(pts[mid - 1], pts[mid + 1], 0x6fcbe0));
    }
    put(g, label("CAMPO ELÉTRICO     E = k · q / d²", { font: 25, color: SOFT }), 0, 2.3, 0.6);
    g.userData.type = "campo_eletrico";
    return g;
  }

  // ================= B5 — soma de vetores (mat/física) =================
  function vetores() {
    const g = new THREE.Group();
    g.add(axes(2.6));
    const a = V(1.8, 0.6), b = V(0.7, 1.7);
    const c = a.clone().add(b);
    g.add(arrow(V(0, 0), a, AMBER, "a"));
    g.add(arrow(V(0, 0), b, GREEN, "b"));
    g.add(arrow(V(0, 0), c, NEON, "a + b"));
    // paralelogramo tracejado
    g.add(line([a, c], 0x3a6a7e, 0.5));
    g.add(line([b, c], 0x3a6a7e, 0.5));
    put(g, label("SOMA DE VETORES", { font: 26, color: SOFT }), 0, 2.9, 0.6);
    g.userData.type = "vetores";
    return g;
  }

  // ================= B6 — derivada: reta tangente (cálculo) =================
  function derivada(opts) {
    const g = new THREE.Group();
    const expr = (opts && opts.expr) || "0.35*x^2";
    const f = compile(expr) || ((x) => 0.35 * x * x);
    const h = 1e-4, df = (x) => (f(x + h) - f(x - h)) / (2 * h);
    g.add(axes(3));
    const cur = [];
    for (let x = -3; x <= 3.001; x += 0.05) { const y = f(x); if (Math.abs(y) < 3.2) cur.push(V(x, y)); }
    g.add(line(cur, NEON, 0.9));
    const tan = line([V(0, 0), V(0, 0)], AMBER, 1); g.add(tan);
    const dot = ball(0.09, AMBER); g.add(dot);
    const readout = dynLabel(460, 70); put(g, readout, 0, -3.1, 0.6);
    put(g, label("y = " + expr + "      f′(x) = inclinação da tangente", { font: 24, color: SOFT }), 0, 3.4, 0.6);
    g.userData.type = "derivada";
    g.userData.update = (t) => {
      const x = 2.4 * Math.sin(t * 0.6);
      const y = f(x), m = df(x);
      tan.geometry.setFromPoints([V(x - 1.3, y - m * 1.3), V(x + 1.3, y + m * 1.3)]);
      dot.position.set(x, y, 0);
      readout.setText(`x = ${x.toFixed(2)}     f′(x) = ${m.toFixed(2)}`);
    };
    return g;
  }

  // ================= B7 — integral: soma de Riemann (cálculo) =================
  function integral(opts) {
    const g = new THREE.Group();
    const expr = (opts && opts.expr) || "0.5*x+1.6";
    const f = compile(expr) || ((x) => 0.5 * x + 1.6);
    g.add(axes(3));
    const cur = [];
    for (let x = -2.6; x <= 2.601; x += 0.05) cur.push(V(x, f(x)));
    g.add(line(cur, NEON, 0.9));
    const bars = new THREE.Group(); g.add(bars);
    const readout = dynLabel(460, 70); put(g, readout, 0, -3.1, 0.6);
    put(g, label("∫ f(x) dx  ≈  Σ f(xᵢ)·Δx      (área sob a curva)", { font: 23, color: SOFT }), 0, 3.4, 0.6);
    const x0 = -2.4, dx = 0.3;
    g.userData.type = "integral";
    g.userData.update = (t) => {
      const xEnd = -2.4 + ((t * 0.9) % 5.2);
      while (bars.children.length) bars.remove(bars.children[0]);
      let area = 0;
      for (let x = x0; x < xEnd; x += dx) {
        const y = Math.max(0, f(x + dx / 2));
        area += y * dx;
        const r = new THREE.Mesh(new THREE.PlaneGeometry(dx * 0.92, y),
          new THREE.MeshBasicMaterial({ color: AMBER, transparent: true, opacity: 0.18,
            blending: THREE.AdditiveBlending, depthWrite: false }));
        r.position.set(x + dx / 2, y / 2, -0.01);
        bars.add(r);
      }
      readout.setText(`x = ${xEnd.toFixed(1)}     área ≈ ${area.toFixed(2)}`);
    };
    return g;
  }

  // ================= B8 — superfície z = f(x,y) (multivariável) =================
  function superficie3d(opts) {
    const g = new THREE.Group();
    const kind = (opts && opts.kind) || "sela";
    const S = 2.2, seg = 22;
    const geo = new THREE.PlaneGeometry(S * 2, S * 2, seg, seg);
    const pos = geo.attributes.position;
    const zf = kind === "paraboloide" ? (x, y) => (x * x + y * y) * 0.5
      : kind === "ondas" ? (x, y) => Math.sin(x * 2.4) * Math.cos(y * 2.4) * 0.55
        : (x, y) => (x * x - y * y) * 0.6;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i) / S, y = pos.getY(i) / S;
      pos.setZ(i, zf(x, y));
    }
    const wire = new THREE.LineSegments(new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({ color: NEON, transparent: true, opacity: 0.6,
        blending: THREE.AdditiveBlending, depthWrite: false }));
    wire.rotation.x = -1.05;
    g.add(wire);
    const names = { sela: "z = x² − y²   (sela)", paraboloide: "z = x² + y²   (paraboloide)", ondas: "z = sen x · cos y" };
    put(g, label(names[kind] || names.sela, { font: 28, color: AMBER }), 0, 2.7, 0.6);
    g.userData.type = "superficie_3d";
    g.userData.update = (t) => { wire.rotation.z = t * 0.3; };
    return g;
  }

  // ================= B9 — geometria molecular (VSEPR, química) =================
  const VSEPR = {
    linear: { dirs: [[1, 0, 0], [-1, 0, 0]], nome: "Linear — 180°" },
    angular: { dirs: [[Math.cos(0.9), Math.sin(0.9), 0], [Math.cos(2.24), Math.sin(2.24), 0]], nome: "Angular — ~104°" },
    trigonal: { dirs: [[0, 1, 0], [0.87, -0.5, 0], [-0.87, -0.5, 0]], nome: "Trigonal plana — 120°" },
    tetraedrica: { dirs: [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], nome: "Tetraédrica — 109,5°" },
    piramidal: { dirs: [[0, 1, 0.3], [0.87, -0.5, 0.3], [-0.87, -0.5, 0.3]], nome: "Piramidal — ~107°" },
    octaedrica: { dirs: [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], nome: "Octaédrica — 90°" },
  };
  function geometriaMolecular(opts) {
    const key = (opts && opts.shape) || "tetraedrica";
    const def = VSEPR[key] || VSEPR.tetraedrica;
    const g = new THREE.Group();
    const c = ball(0.36, 0x9bb0c0); g.add(c);
    def.dirs.forEach((d) => {
      const p = V(...d).normalize().multiplyScalar(1.25);
      g.add(stick(V(0, 0, 0), p));
      const b = ball(0.22, 0xdfefff); b.position.copy(p); g.add(b);
    });
    put(g, label("GEOMETRIA MOLECULAR\n" + def.nome, { font: 26, color: SOFT }), 0, -1.9, 0.6);
    g.userData.type = "geometria_" + key;
    g.userData.update = (t) => { g.rotation.y = t * 0.5; };
    return g;
  }

  // ================= C1 — DNA (dupla hélice, biologia) =================
  function dna() {
    const g = new THREE.Group();
    const rungs = new THREE.Group(); g.add(rungs);
    const s1 = [], s2 = [];
    const N = 34, H = 4.2, R = 0.8;
    for (let i = 0; i <= N; i++) {
      const y = -H / 2 + i / N * H;
      const a = i / N * TAU * 2.4;
      const p1 = V(Math.cos(a) * R, y, Math.sin(a) * R);
      const p2 = V(Math.cos(a + Math.PI) * R, y, Math.sin(a + Math.PI) * R);
      s1.push(p1); s2.push(p2);
      if (i % 2 === 0) rungs.add(stick(p1, p2, i % 4 ? 0x8ab6ff : 0xff9de0, 0.035));
    }
    g.add(line(s1, NEON, 0.95)); g.add(line(s2, GREEN, 0.95));
    put(g, label("DNA — dupla hélice\nA–T   C–G", { font: 26, color: SOFT }), 0, -2.7, 0.6);
    g.userData.type = "dna";
    g.userData.update = (t) => { g.rotation.y = t * 0.6; };
    return g;
  }

  // ================= C2 — sistema solar (física / astronomia) =================
  function sistemaSolar() {
    const g = new THREE.Group();
    const sun = ball(0.42, AMBER); g.add(sun);
    const defs = [["Merc", 0.9, 0.10, 2.4], ["Vênus", 1.3, 0.14, 1.7],
      ["Terra", 1.8, 0.16, 1.3], ["Marte", 2.3, 0.13, 1.0],
      ["Júpiter", 3.1, 0.30, 0.55]];
    const planets = defs.map(([nm, r, sz]) => {
      const orbit = [];
      for (let i = 0; i <= 72; i++) orbit.push(V(Math.cos(i / 72 * TAU) * r, Math.sin(i / 72 * TAU) * r * 0.4));
      g.add(line(orbit, 0x3a6a7e, 0.4));
      const b = ball(sz, NEON); g.add(b);
      put(g, label(nm, { font: 18, color: SOFT }), r, 0.25, 0.45);
      return { b, r };
    });
    put(g, label("SISTEMA SOLAR", { font: 26, color: SOFT }), 0, 2.5, 0.6);
    g.userData.type = "sistema_solar";
    g.userData.update = (t) => {
      defs.forEach((d, i) => {
        const a = t * d[3] + i;
        planets[i].b.position.set(Math.cos(a) * d[1], Math.sin(a) * d[1] * 0.4, 0);
      });
      sun.scale.setScalar(1 + Math.sin(t * 2) * 0.04);
    };
    return g;
  }

  // ================= C3 — transformações geométricas (matemática) =================
  function transformacoes(opts) {
    const kind = (opts && opts.kind) || "rotacao";
    const g = new THREE.Group();
    g.add(axes(3));
    const base = [V(0.4, 0.3), V(2.0, 0.5), V(0.9, 1.9), V(0.4, 0.3)];
    g.add(line(base, 0x6a7f8f, 0.7));
    const moved = line(base.map((p) => p.clone()), NEON, 1);
    g.add(moved);
    const names = { translacao: "TRANSLAÇÃO", rotacao: "ROTAÇÃO 90°",
      reflexao: "REFLEXÃO (eixo y)", homotetia: "HOMOTETIA (×1.6)" };
    put(g, label(names[kind] || names.rotacao, { font: 26, color: AMBER }), 0, 3.4, 0.6);
    g.userData.type = "transformacao_" + kind;
    g.userData.update = (t) => {
      const k = (Math.sin(t * 0.8) + 1) / 2;   // 0..1 ida e volta
      const pts = base.map((p) => {
        if (kind === "translacao") return p.clone().add(V(-1.4 * k, 1.1 * k));
        if (kind === "reflexao") return V(p.x * (1 - 2 * k), p.y);
        if (kind === "homotetia") return p.clone().multiplyScalar(1 + 0.6 * k);
        const ang = k * Math.PI / 2;   // rotação
        return V(p.x * Math.cos(ang) - p.y * Math.sin(ang), p.x * Math.sin(ang) + p.y * Math.cos(ang));
      });
      moved.geometry.setFromPoints(pts);
    };
    return g;
  }

  // ================= C4 — gráfico estatístico (barras / setores) =================
  function grafico(opts) {
    const raw = (opts && opts.data) || [4, 7, 3, 9, 5];
    const vals = raw.map(Number).filter((n) => Number.isFinite(n) && n >= 0).slice(0, 8);
    const pie = opts && /setor|pizza|circul/.test(String(opts.kind || ""));
    const g = new THREE.Group();
    if (!pie) {
      g.add(line([V(-2.6, -1.6), V(2.6, -1.6)], 0x4bb6d6, 0.6));
      g.add(line([V(-2.6, -1.6), V(-2.6, 1.8)], 0x4bb6d6, 0.6));
      const mx = Math.max(...vals, 1), bw = 4.6 / (vals.length * 1.5);
      vals.forEach((v, i) => {
        const h = v / mx * 3.0, x = -2.2 + i * bw * 1.5;
        const bar = new THREE.Mesh(new THREE.PlaneGeometry(bw, h),
          new THREE.MeshBasicMaterial({ color: NEON, transparent: true, opacity: 0.22,
            blending: THREE.AdditiveBlending, depthWrite: false }));
        bar.position.set(x, -1.6 + h / 2, 0);
        g.add(bar);
        g.add(line([V(x - bw / 2, -1.6 + h), V(x + bw / 2, -1.6 + h)], NEON, 1));
        put(g, label(String(v), { font: 22, color: SOFT }), x, -1.6 + h + 0.22, 0.5);
      });
      put(g, label("GRÁFICO DE BARRAS", { font: 24, color: SOFT }), 0, 2.2, 0.6);
    } else {
      const tot = vals.reduce((s, v) => s + v, 0) || 1;
      let a0 = Math.PI / 2;
      const cols = [NEON, GREEN, AMBER, 0xff9de0, 0x8ab6ff, RED, SOFT, 0xbff0ff];
      vals.forEach((v, i) => {
        const a1 = a0 - v / tot * TAU;
        const seg = [V(0, 0)];
        for (let a = a0; a >= a1 - 0.001; a -= 0.06) seg.push(V(Math.cos(a) * 1.7, Math.sin(a) * 1.7));
        seg.push(V(0, 0));
        g.add(line(seg, cols[i % cols.length], 0.9));
        const am = (a0 + a1) / 2;
        put(g, label(Math.round(v / tot * 100) + "%", { font: 20, color: cols[i % cols.length] }),
          Math.cos(am) * 2.0, Math.sin(am) * 2.0, 0.5);
        a0 = a1;
      });
      put(g, label("GRÁFICO DE SETORES", { font: 24, color: SOFT }), 0, 2.3, 0.6);
    }
    g.userData.type = "grafico_estatistico";
    return g;
  }

  // ================= C5 — coração (biologia) =================
  function coracao() {
    const g = new THREE.Group();
    // silhueta de coração (paramétrica)
    const heart = [];
    for (let i = 0; i <= 80; i++) {
      const tt = i / 80 * TAU;
      const x = 16 * Math.sin(tt) ** 3;
      const y = 13 * Math.cos(tt) - 5 * Math.cos(2 * tt) - 2 * Math.cos(3 * tt) - Math.cos(4 * tt);
      heart.push(V(x * 0.11, y * 0.11 + 0.2));
    }
    const outline = line(heart, RED, 0.9); g.add(outline);
    // câmaras
    const chambers = new THREE.Group(); g.add(chambers);
    [[-0.55, 0.55, "AD"], [0.55, 0.55, "AE"], [-0.5, -0.35, "VD"], [0.5, -0.35, "VE"]].forEach(([x, y, nm]) => {
      const c = ball(0.26, 0xff8a8a); c.position.set(x, y, 0); chambers.add(c);
      put(g, label(nm, { font: 20, color: SOFT }), x, y, 0.5);
    });
    // vasos
    g.add(stick(V(-0.2, 1.0), V(-0.2, 2.0), 0x8ab6ff, 0.08));   // veia cava
    g.add(stick(V(0.25, 1.0), V(0.6, 2.0), RED, 0.08));         // aorta
    put(g, label("aorta", { font: 18, color: RED }), 0.75, 1.9, 0.45);
    put(g, label("CORAÇÃO — 4 câmaras", { font: 24, color: SOFT }), 0, -2.1, 0.6);
    g.userData.type = "coracao";
    g.userData.update = (t) => {
      const b = 1 + Math.max(0, Math.sin(t * 4.5)) * 0.09;      // batida
      chambers.scale.setScalar(b);
      outline.material.opacity = 0.75 + Math.max(0, Math.sin(t * 4.5)) * 0.22;
    };
    return g;
  }

  // ================= D — holograma gerado por spec (o Jarvis "inventa") =================
  //  spec = { title, parts:[ {t, ...} ], spin }
  //  t: ball|stick|arrow|line|curve|ring|box|plane|label|cone|torus
  const COLS = { neon: NEON, soft: SOFT, amber: AMBER, green: GREEN, red: RED,
    azul: 0x8ab6ff, blue: 0x8ab6ff, cyan: NEON, rosa: 0xff9de0, pink: 0xff9de0,
    cinza: 0x9bb0c0, grey: 0x9bb0c0, gray: 0x9bb0c0, branco: 0xdfefff, white: 0xdfefff,
    dim: 0x4bb6d6, "": SOFT };
  const col = (c) => COLS[String(c || "").toLowerCase()] ?? (typeof c === "number" ? c : SOFT);
  const vec = (a) => (Array.isArray(a) ? V(+a[0] || 0, +a[1] || 0, +a[2] || 0) : V(0, 0, 0));

  function fromSpec(opts) {
    const spec = (opts && (opts.spec || opts)) || {};
    let parts = spec.parts || spec.elementos || [];
    if (typeof parts === "string") { try { parts = JSON.parse(parts); } catch (_) { parts = []; } }
    if (!Array.isArray(parts) || !parts.length) return null;
    const g = new THREE.Group();
    let hasAxes = false;
    for (const p of parts.slice(0, 60)) {
      try {
        const t = String(p.t || p.tipo || p.type || "").toLowerCase();
        const c = col(p.c || p.cor || p.color);
        if (t === "ball" || t === "esfera" || t === "atomo" || t === "ponto") {
          const b = ball(Math.min(1.2, +p.r || +p.raio || 0.2), c);
          b.position.copy(vec(p.at || p.pos)); g.add(b);
          if (p.label) put(g, label(String(p.label), { color: c, font: 24 }),
            (p.at ? +p.at[0] : 0), (p.at ? +p.at[1] : 0) + (+p.r || 0.2) + 0.25, 0.55);
        } else if (t === "stick" || t === "ligacao" || t === "bastao") {
          g.add(stick(vec(p.from || p.de), vec(p.to || p.para), c, 0.05));
        } else if (t === "arrow" || t === "seta" || t === "vetor") {
          g.add(arrow(vec(p.from || p.de), vec(p.to || p.para), c, p.label));
        } else if (t === "line" || t === "linha") {
          const pts = (p.pts || p.pontos || []).map(vec);
          if (pts.length > 1) g.add(line(pts, c, 0.9));
        } else if (t === "curve" || t === "curva" || t === "grafico") {
          const f = compile(p.expr || p.funcao || "x");
          if (f) {
            const pts = [];
            for (let x = -3; x <= 3.001; x += 0.05) { const y = f(x); if (Number.isFinite(y) && Math.abs(y) < 3.4) pts.push(V(x, y)); }
            if (pts.length > 1) g.add(line(pts, c, 0.95));
          }
        } else if (t === "ring" || t === "anel" || t === "orbita" || t === "circulo") {
          const r = Math.min(3, +p.r || +p.raio || 1);
          const pts = [];
          for (let i = 0; i <= 72; i++) pts.push(V(Math.cos(i / 72 * TAU) * r, Math.sin(i / 72 * TAU) * r).add(vec(p.at)));
          g.add(line(pts, c, 0.7));
        } else if (t === "box" || t === "caixa" || t === "cubo") {
          const s = Array.isArray(p.size || p.tamanho) ? (p.size || p.tamanho) : [1, 1, 1];
          const geo = new THREE.BoxGeometry(+s[0] || 1, +s[1] || 1, +s[2] || 1);
          const m = new THREE.LineSegments(new THREE.WireframeGeometry(geo),
            new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending }));
          m.position.copy(vec(p.at)); g.add(m);
        } else if (t === "plane" || t === "plano" || t === "retangulo") {
          const m = new THREE.Mesh(new THREE.PlaneGeometry(+p.w || 1.5, +p.h || 1),
            new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false }));
          m.position.copy(vec(p.at)); g.add(m);
        } else if (t === "cone") {
          const m = new THREE.Mesh(new THREE.ConeGeometry(+p.r || 0.5, +p.h || 1, 20),
            new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.2 }));
          m.position.copy(vec(p.at)); g.add(m);
        } else if (t === "torus" || t === "anel3d") {
          const m = new THREE.Mesh(new THREE.TorusGeometry(+p.r || 0.9, +p.tube || 0.2, 12, 40),
            new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.25 }));
          m.position.copy(vec(p.at)); g.add(m);
        } else if (t === "axes" || t === "eixos") {
          g.add(axes(+p.size || 3)); hasAxes = true;
        } else if (t === "label" || t === "texto" || t === "rotulo") {
          put(g, label(String(p.text || p.texto || ""), { color: c, font: +p.size || 26 }),
            (p.at ? +p.at[0] : 0), (p.at ? +p.at[1] : 0), 0.6);
        }
      } catch (_) { /* pula a parte com erro */ }
    }
    if (!g.children.length) return null;
    if (spec.title || spec.titulo) {
      put(g, label(String(spec.title || spec.titulo).toUpperCase(),
        { font: 28, color: SOFT }), 0, hasAxes ? 3.5 : 2.6, 0.6);
    }
    g.userData.type = "spec";
    if (spec.spin || spec.girar) g.userData.update = (t) => { g.rotation.y = t * 0.45; };
    return g;
  }

  // ---------- registro ----------
  const B = {
    circulo_trigonometrico: circulo, circulo_trig: circulo, circunferencia_trig: circulo,
    plot: plot, plota: plot, grafico: plot, funcao: plot,
    solido_formula: solidFormula, formula_solido: solidFormula,
    corpo_livre: corpoLivre, diagrama_corpo_livre: corpoLivre, vetores_forca: corpoLivre,
    lancamento_obliquo: lancamento, lancamento: lancamento, projetil: lancamento,
    plano_inclinado: planoInclinado, rampa: planoInclinado,
    molecula_agua: () => molecula("agua"), agua: () => molecula("agua"),
    molecula_metano: () => molecula("metano"), metano: () => molecula("metano"),
    molecula_benzeno: () => molecula("benzeno"), benzeno: () => molecula("benzeno"),
    molecula_co2: () => molecula("co2"), co2: () => molecula("co2"), gas_carbonico: () => molecula("co2"),
    molecula_amonia: () => molecula("amonia"), amonia: () => molecula("amonia"), nh3: () => molecula("amonia"),
    tabela_periodica: tabelaPeriodica, periodica: tabelaPeriodica,
    celula: celula, celula_animal: celula,

    // --- lote B: física / cálculo / química ---
    onda: onda, onda_senoidal: onda, ondas: onda,
    pendulo: pendulo, pendulo_simples: pendulo,
    circuito: circuito, circuito_serie: circuito, circuito_eletrico: circuito,
    campo_eletrico: campoEletrico, campo_cargas: campoEletrico, linhas_de_campo: campoEletrico,
    vetores: vetores, soma_de_vetores: vetores, soma_vetores: vetores,
    derivada: derivada, reta_tangente: derivada, tangente: derivada,
    integral: integral, soma_de_riemann: integral, area_sob_curva: integral,
    superficie_3d: superficie3d, superficie: superficie3d,
    paraboloide: () => superficie3d({ kind: "paraboloide" }),
    sela: () => superficie3d({ kind: "sela" }),
    geometria_molecular: geometriaMolecular,
    vsepr: geometriaMolecular,
    geometria_linear: () => geometriaMolecular({ shape: "linear" }),
    geometria_angular: () => geometriaMolecular({ shape: "angular" }),
    geometria_trigonal: () => geometriaMolecular({ shape: "trigonal" }),
    geometria_tetraedrica: () => geometriaMolecular({ shape: "tetraedrica" }),
    geometria_piramidal: () => geometriaMolecular({ shape: "piramidal" }),
    geometria_octaedrica: () => geometriaMolecular({ shape: "octaedrica" }),

    // --- lote C: biologia / astronomia / estatística / transformações ---
    dna: dna, dupla_helice: dna, acido_desoxirribonucleico: dna,
    sistema_solar: sistemaSolar, planetas: sistemaSolar, orbitas: sistemaSolar,
    coracao: coracao, coração: coracao,
    grafico_barras: grafico, grafico_de_barras: grafico, estatistica: grafico,
    grafico_setores: (o) => grafico(Object.assign({ kind: "setores" }, o)),
    grafico_pizza: (o) => grafico(Object.assign({ kind: "setores" }, o)),
    transformacao: transformacoes, transformacoes: transformacoes,
    translacao: () => transformacoes({ kind: "translacao" }),
    rotacao_geometrica: () => transformacoes({ kind: "rotacao" }),
    reflexao: () => transformacoes({ kind: "reflexao" }),
    homotetia: () => transformacoes({ kind: "homotetia" }),

    // --- lote D: holograma que o Jarvis inventa (a partir de um spec JSON) ---
    spec: fromSpec, holograma_gerado: fromSpec, inventado: fromSpec,
  };
  return {
    has: (name) => !!B[name],
    build: (name, opts) => (B[name] ? B[name](opts) : null),
  };
})();

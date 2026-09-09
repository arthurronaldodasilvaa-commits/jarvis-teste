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
    tabela_periodica: tabelaPeriodica, periodica: tabelaPeriodica,
    celula: celula, celula_animal: celula,
  };
  return {
    has: (name) => !!B[name],
    build: (name, opts) => (B[name] ? B[name](opts) : null),
  };
})();

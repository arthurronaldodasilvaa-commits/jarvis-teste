/* Jarvis — modelos de estudo: trigonometria.
   window.jarvisTrig.build(name) -> THREE.Group  (nomes: triangulo, tabela_angulos, tabela_relacoes) */
window.jarvisTrig = (() => {
  "use strict";
  const NEON = "#7ce4ff", DIM = "#4bb6d6";

  function label3d(text, o = {}) {
    o = Object.assign({ font: 46, pad: 18, color: NEON, bg: null, weight: 600, scale: 220 }, o);
    const c = document.createElement("canvas");
    let ctx = c.getContext("2d");
    ctx.font = `${o.weight} ${o.font}px "Segoe UI", Consolas, monospace`;
    const lines = String(text).split("\n");
    const w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + o.pad * 2;
    const lh = o.font * 1.4;
    c.width = Math.ceil(w); c.height = Math.ceil(lh * lines.length + o.pad * 2);
    ctx = c.getContext("2d");
    ctx.font = `${o.weight} ${o.font}px "Segoe UI", Consolas, monospace`;
    if (o.bg) {
      ctx.fillStyle = o.bg; ctx.fillRect(0, 0, c.width, c.height);
      ctx.strokeStyle = "rgba(124,228,255,0.5)"; ctx.lineWidth = 2;
      ctx.strokeRect(1, 1, c.width - 2, c.height - 2);
    }
    ctx.fillStyle = o.color; ctx.textBaseline = "top";
    ctx.shadowColor = o.color; ctx.shadowBlur = 12;
    lines.forEach((l, i) => ctx.fillText(l, o.pad, o.pad + i * lh));
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter; tex.anisotropy = 4;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true,
      depthWrite: false, blending: o.bg ? THREE.NormalBlending : THREE.AdditiveBlending }));
    s.scale.set(c.width / o.scale, c.height / o.scale, 1);
    return s;
  }

  function lineSeg(pts, color = 0x7ce4ff, opacity = 0.95) {
    return new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color, transparent: true, opacity,
        blending: THREE.AdditiveBlending, depthWrite: false }));
  }

  // ---------- triângulo retângulo 3-4-5 ----------
  function triangle() {
    const g = new THREE.Group();
    const sc = 0.62;
    const C = new THREE.Vector3(-2 * sc, -1.5 * sc, 0);   // ângulo reto
    const B = new THREE.Vector3(2 * sc, -1.5 * sc, 0);    // ângulo β  (cateto b = CB = 4)
    const A = new THREE.Vector3(-2 * sc, 1.5 * sc, 0);    // ângulo α  (cateto a = CA = 3)
    g.add(lineSeg([C, B, A, C]));

    // marca do ângulo reto
    const m = 0.28;
    g.add(lineSeg([
      new THREE.Vector3(C.x + m, C.y, 0), new THREE.Vector3(C.x + m, C.y + m, 0),
      new THREE.Vector3(C.x, C.y + m, 0),
    ], 0x7ce4ff, 0.8));

    // arcos dos ângulos α e β
    function arc(center, from, to, r, steps = 24) {
      const pts = [];
      for (let i = 0; i <= steps; i++) {
        const ang = from + (to - from) * (i / steps);
        pts.push(new THREE.Vector3(center.x + r * Math.cos(ang), center.y + r * Math.sin(ang), 0));
      }
      return lineSeg(pts, 0xffb24d, 0.85);
    }
    // α em A: entre AC (pra baixo, -90°) e AB
    const aToB = Math.atan2(B.y - A.y, B.x - A.x);
    g.add(arc(A, -Math.PI / 2, aToB, 0.6));
    // β em B: entre BC (pra esquerda, 180°) e BA
    const bToA = Math.atan2(A.y - B.y, A.x - B.x);
    g.add(arc(B, Math.PI, bToA, 0.6));

    // rótulos
    const put = (spr, x, y, s = 1) => { spr.position.set(x, y, 0.02); spr.scale.multiplyScalar(s); g.add(spr); };
    put(label3d("a", { color: "#9becff" }), C.x - 0.42, (C.y + A.y) / 2, 0.62);
    put(label3d("b", { color: "#9becff" }), (C.x + B.x) / 2, C.y - 0.42, 0.62);
    put(label3d("hipotenusa", { color: "#9becff", font: 34 }), (A.x + B.x) / 2 + 0.35, (A.y + B.y) / 2 + 0.35, 0.6);
    put(label3d("90°", { font: 34 }), C.x + 0.55, C.y + 0.42, 0.55);
    put(label3d("α", { color: "#ffb24d" }), A.x + 0.55, A.y - 0.7, 0.6);
    put(label3d("β", { color: "#ffb24d" }), B.x - 0.75, B.y + 0.55, 0.6);
    put(label3d("α ≈ 37°   β ≈ 53°   ( 3 · 4 · 5 )", { font: 30, color: "#8fd8ee" }), 0, A.y + 0.9, 0.6);

    g.userData.type = "triangulo";
    return g;
  }

  function panel(title, body) {
    const g = new THREE.Group();
    const s = label3d(title + "\n\n" + body, {
      font: 40, weight: 500, color: NEON, bg: "rgba(4,16,24,0.82)", scale: 150,
    });
    g.add(s);
    g.userData.type = "painel";
    return g;
  }

  function tabelaAngulos() {
    return panel("ÂNGULOS NOTÁVEIS",
      "            30°        45°        60°\n" +
      "  sen      1/2       √2/2      √3/2\n" +
      "  cos     √3/2      √2/2       1/2\n" +
      "  tan     √3/3        1         √3");
  }

  function tabelaRelacoes() {
    return panel("RELAÇÕES TRIGONOMÉTRICAS",
      "  sen α = cateto oposto ÷ hipotenusa\n" +
      "  cos α = cateto adjacente ÷ hipotenusa\n" +
      "  tan α = cateto oposto ÷ cateto adjacente\n" +
      "  tan α = sen α ÷ cos α\n" +
      "  sen²α + cos²α = 1");
  }

  const BUILDERS = {
    triangulo: triangle, triangle: triangle, "triangulo_retangulo": triangle,
    tabela_angulos: tabelaAngulos, angulos_notaveis: tabelaAngulos,
    tabela_relacoes: tabelaRelacoes, relacoes: tabelaRelacoes,
  };

  return { build: (name) => (BUILDERS[name] || (() => null))() };
})();

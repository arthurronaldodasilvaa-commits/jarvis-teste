/* Jarvis — "Teia" do Segundo Cérebro: grafo das notas + [[links]] (estilo Obsidian).
   Canvas 2D próprio dentro de #atlas. hologram.js chama tick()/setActive()/onEvent()/refresh(). */
window.jarvisAtlas = (() => {
  "use strict";

  const host = document.getElementById("atlas");
  const cv = document.createElement("canvas");
  cv.style.cssText = "position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab";
  host.appendChild(cv);
  const ctx = cv.getContext("2d");
  const panel = document.getElementById("note-panel");
  const search = document.getElementById("brain2-search");

  const TYPE = {
    materia:  { c: "#46d6ff", r: 13, lbl: "MATÉRIA" },
    topico:   { c: "#8fdcff", r: 9,  lbl: "TÓPICO" },
    questao:  { c: "#ffb64a", r: 8,  lbl: "QUESTÃO" },
    ideia:    { c: "#b98bff", r: 8,  lbl: "IDEIA" },
    quadro:   { c: "#49f5b0", r: 9,  lbl: "QUADRO" },
    nota:     { c: "#9ecad8", r: 7,  lbl: "NOTA" },
  };
  const ty = (t) => TYPE[t] || TYPE.nota;

  const S = {
    active: false, nodes: [], byId: new Map(), edges: [],
    cam: { x: 0, y: 0, z: 1 }, hover: null, sel: null,
    filter: "", highlight: null, ready: false,
  };

  // ---------------- dados ----------------
  async function refresh() {
    const api = window.pywebview && window.pywebview.api;
    if (!api || !api.brain_graph) return;
    let g;
    try { g = await api.brain_graph(); } catch (e) { return; }
    const notes = (g && g.notes) || [];
    const keep = S.byId;
    const nodes = [], byId = new Map();
    const spread = 70 + 34 * Math.sqrt(notes.length);
    notes.forEach((n, i) => {
      const old = keep.get(n.id);
      const a = (i / Math.max(1, notes.length)) * Math.PI * 2;
      const nd = old || { x: Math.cos(a) * spread + (Math.random() - 0.5) * 40,
                          y: Math.sin(a) * spread + (Math.random() - 0.5) * 40, vx: 0, vy: 0 };
      Object.assign(nd, { id: n.id, title: n.title, type: n.type, rel: n.rel,
                          tags: n.tags || [], excerpt: n.excerpt || "", links: n.links || [] });
      nodes.push(nd); byId.set(n.id, nd);
    });
    const edges = [];
    nodes.forEach((n) => n.links.forEach((l) => {
      if (byId.has(l)) edges.push({ a: n, b: byId.get(l) });
    }));
    S.nodes = nodes; S.byId = byId; S.edges = edges; S.ready = true;
    if (!S._everCentered) {
      for (let i = 0; i < 260; i++) layout();   // pré-assenta a simulação
      S._centerFrames = 30;
    }
  }

  function fitView() {
    if (!S.nodes.length) return;
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    S.nodes.forEach((n) => { x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y);
                             x1 = Math.max(x1, n.x); y1 = Math.max(y1, n.y); });
    const w = cv.width / (devicePixelRatio || 1), h = cv.height / (devicePixelRatio || 1);
    const z = Math.min(1.6, Math.max(0.45, 0.8 * Math.min(w / (x1 - x0 + 240), h / (y1 - y0 + 240))));
    S.cam.z = z; S.cam.x = (x0 + x1) / 2; S.cam.y = (y0 + y1) / 2;
  }

  // ---------------- layout força-dirigida (O(n²), vault é pequeno) ----------------
  // Fruchterman-Reingold: repulsão k²/d entre todos, atração d²/k nas arestas.
  const K = 190;         // distância ideal entre nós ligados
  function layout() {
    const N = S.nodes;
    N.forEach((n) => { n.fx = 0; n.fy = 0; });
    for (let i = 0; i < N.length; i++) {
      const a = N[i];
      for (let j = i + 1; j < N.length; j++) {
        const b = N[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        let d = Math.hypot(dx, dy) || 0.01;
        const f = (K * K) / d;
        dx /= d; dy /= d;
        a.fx += dx * f; a.fy += dy * f; b.fx -= dx * f; b.fy -= dy * f;
      }
      a.fx -= a.x * 0.28; a.fy -= a.y * 0.28;   // gravidade pro centro (fraca)
    }
    S.edges.forEach((e) => {
      let dx = e.b.x - e.a.x, dy = e.b.y - e.a.y;
      const d = Math.hypot(dx, dy) || 0.01;
      const f = (d * d) / K;
      dx /= d; dy /= d;
      e.a.fx += dx * f; e.a.fy += dy * f; e.b.fx -= dx * f; e.b.fy -= dy * f;
    });
    N.forEach((n) => {
      if (n === S.drag) return;
      const d = Math.hypot(n.fx, n.fy) || 0.01;
      const step = Math.min(d, 60) * 0.16;      // limite de deslocamento (cooling fixo)
      n.x += (n.fx / d) * step;
      n.y += (n.fy / d) * step;
    });
  }

  // ---------------- render ----------------
  function resize() {
    const r = devicePixelRatio || 1;
    cv.width = host.clientWidth * r; cv.height = host.clientHeight * r;
  }
  function toScreen(x, y) {
    const w = cv.width / (devicePixelRatio || 1), h = cv.height / (devicePixelRatio || 1);
    return [(x - S.cam.x) * S.cam.z + w / 2, (y - S.cam.y) * S.cam.z + h / 2];
  }
  function toWorld(px, py) {
    const w = cv.width / (devicePixelRatio || 1), h = cv.height / (devicePixelRatio || 1);
    return [(px - w / 2) / S.cam.z + S.cam.x, (py - h / 2) / S.cam.z + S.cam.y];
  }

  function draw() {
    const r = devicePixelRatio || 1;
    ctx.setTransform(r, 0, 0, r, 0, 0);
    ctx.clearRect(0, 0, cv.width, cv.height);
    const q = S.filter;
    const hl = S.highlight;   // Set de ids realçados (ou null)
    const dim = (n) => (q && !n.title.toLowerCase().includes(q)) || (hl && !hl.has(n.id));

    ctx.lineWidth = 1;
    S.edges.forEach((e) => {
      const [ax, ay] = toScreen(e.a.x, e.a.y), [bx, by] = toScreen(e.b.x, e.b.y);
      const on = S.hover && (e.a === S.hover || e.b === S.hover);
      ctx.strokeStyle = on ? "rgba(150,230,255,0.65)"
        : (dim(e.a) && dim(e.b)) ? "rgba(120,170,190,0.05)" : "rgba(120,170,190,0.16)";
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
    });

    S.nodes.forEach((n) => {
      const [x, y] = toScreen(n.x, n.y);
      const info = ty(n.type);
      const rad = info.r * Math.max(0.6, Math.min(1.6, S.cam.z));
      const faded = dim(n);
      ctx.globalAlpha = faded ? 0.18 : 1;
      ctx.beginPath(); ctx.arc(x, y, rad, 0, Math.PI * 2);
      ctx.fillStyle = info.c;
      ctx.shadowColor = info.c; ctx.shadowBlur = (n === S.hover || n === S.sel) ? 18 : 8;
      ctx.fill(); ctx.shadowBlur = 0;
      if (n === S.sel) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke(); }
      if (!faded && (S.cam.z > 0.7 || n === S.hover)) {
        ctx.globalAlpha = 0.92;
        ctx.fillStyle = "#dcedf4";
        ctx.font = `${Math.round(11 * Math.min(1.4, Math.max(0.9, S.cam.z)))}px "Segoe UI", monospace`;
        ctx.textAlign = "center";
        ctx.fillText(n.title, x, y + rad + 13);
      }
      ctx.globalAlpha = 1;
    });
  }

  // ---------------- markdown mínimo (compartilhado) ----------------
  function mdRender(src) {
    const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    src = src.replace(/^---\s*\n[\s\S]*?\n---\s*\n/, "");   // tira frontmatter
    const lines = esc(src).split("\n");
    let html = "", inList = false, inTbl = false;
    const inline = (t) => t
      .replace(/\[\[([^\]|]+)(\|[^\]]+)?\]\]/g, "<i>$1</i>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
    for (let ln of lines) {
      const tbl = ln.match(/^\s*\|(.+)\|\s*$/);
      if (tbl) {
        if (/^[\s|:-]+$/.test(ln)) continue;
        if (!inTbl) { html += "<table>"; inTbl = true; }
        html += "<tr>" + tbl[1].split("|").map((c) => `<td>${inline(c.trim())}</td>`).join("") + "</tr>";
        continue;
      }
      if (inTbl) { html += "</table>"; inTbl = false; }
      const h = ln.match(/^(#{1,4})\s+(.*)/);
      if (h) { if (inList) { html += "</ul>"; inList = false; }
               html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; continue; }
      const li = ln.match(/^\s*[-*]\s+(.*)/);
      if (li) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(li[1])}</li>`; continue; }
      if (inList) { html += "</ul>"; inList = false; }
      if (ln.trim()) html += `<p>${inline(ln)}</p>`;
    }
    if (inList) html += "</ul>";
    if (inTbl) html += "</table>";
    return html;
  }
  window.jarvisMD = { render: mdRender };

  // ---------------- painel da nota ----------------
  function renderPanel(n) {
    let bodyHtml = mdRender(n._full || n.excerpt || "_(sem prévia)_");
    bodyHtml = bodyHtml.replace(/^<h1>[^<]*<\/h1>/, "");   // a nota já traz "# Título"
    panel.innerHTML =
      `<div class="np-head"><span class="np-tag">${ty(n.type).lbl}</span>` +
      `<button class="np-btn" id="np-obs">abrir no obsidian</button></div>` +
      `<h1>${n.title}</h1>` + bodyHtml +
      (n.links.length ? "<h2>Ligações</h2><ul>" +
        n.links.map((l) => `<li>${(S.byId.get(l) || {}).title || l}</li>`).join("") + "</ul>" : "");
    const api = window.pywebview && window.pywebview.api;
    const ob = document.getElementById("np-obs");
    if (ob) ob.onclick = () => api && api.board_open_obsidian && api.board_open_obsidian(n.rel);
  }
  async function openNote(n) {
    if (!n) return;
    S.sel = n;
    renderPanel(n);
    panel.classList.add("on");
    const api = window.pywebview && window.pywebview.api;
    if (api && api.note_text && !n._full) {
      try { n._full = await api.note_text(n.rel); if (S.sel === n) renderPanel(n); } catch (e) {}
    }
  }
  function closeNote() { panel.classList.remove("on"); S.sel = null; }

  // ---------------- interação (mouse) ----------------
  let panning = false, last = null;
  cv.addEventListener("pointerdown", (e) => {
    cv.setPointerCapture(e.pointerId);
    const [wx, wy] = toWorld(e.offsetX, e.offsetY);
    const hit = pick(wx, wy);
    if (hit) { S.drag = hit; hit.pinned = true; }
    else { panning = true; cv.style.cursor = "grabbing"; }
    last = [e.offsetX, e.offsetY];
  });
  cv.addEventListener("pointermove", (e) => {
    const [wx, wy] = toWorld(e.offsetX, e.offsetY);
    if (S.drag) { S.drag.x = wx; S.drag.y = wy; S.drag.vx = S.drag.vy = 0; }
    else if (panning && last) {
      S.cam.x -= (e.offsetX - last[0]) / S.cam.z;
      S.cam.y -= (e.offsetY - last[1]) / S.cam.z;
      last = [e.offsetX, e.offsetY];
    } else { S.hover = pick(wx, wy); cv.style.cursor = S.hover ? "pointer" : "grab"; }
  });
  cv.addEventListener("pointerup", (e) => {
    if (S.drag && last && Math.hypot(e.offsetX - last[0], e.offsetY - last[1]) < 4) openNote(S.drag);
    S.drag = null; panning = false; last = null; cv.style.cursor = "grab";
  });
  cv.addEventListener("wheel", (e) => {
    e.preventDefault();
    const [wx, wy] = toWorld(e.offsetX, e.offsetY);
    S.cam.z = Math.max(0.15, Math.min(4, S.cam.z * (e.deltaY < 0 ? 1.12 : 0.89)));
    const [nx, ny] = toWorld(e.offsetX, e.offsetY);
    S.cam.x += wx - nx; S.cam.y += wy - ny;
  }, { passive: false });

  function pick(wx, wy) {
    let best = null, bd = 22 / S.cam.z;
    S.nodes.forEach((n) => {
      const d = Math.hypot(n.x - wx, n.y - wy);
      if (d < bd + ty(n.type).r) { bd = d; best = n; }
    });
    return best;
  }

  // busca
  if (search) search.addEventListener("input", () => { S.filter = search.value.trim().toLowerCase(); });
  addEventListener("keydown", (e) => {
    if (!S.active) return;
    if (e.key === "/" && document.activeElement !== search) { e.preventDefault(); search.focus(); }
    else if (e.key === "Escape" && panel.classList.contains("on")) { e.stopImmediatePropagation(); closeNote(); }
  }, true);

  // ---------------- eventos de voz ----------------
  function onEvent(ev) {
    if (!ev) return;
    if (ev.action === "focus" && ev.id) {
      const n = S.byId.get(ev.id);
      if (n) {
        S.cam.z = Math.max(S.cam.z, 1.1);
        openNote(n);
        S.cam.x = n.x + 210 / S.cam.z;   // painel cobre a direita
        S.cam.y = n.y; S.highlight = null;
      }
    } else if (ev.action === "neighbors" && ev.id) {
      const n = S.byId.get(ev.id);
      if (n) { S.highlight = new Set([n.id, ...n.links]); S.cam.x = n.x; S.cam.y = n.y; }
    } else if (ev.action === "filter") {
      S.highlight = new Set(S.nodes.filter((n) => n.type === ev.type
        && (!ev.of || n.links.includes(ev.of) || n.id === ev.of)).map((n) => n.id));
    } else if (ev.action === "clear") {
      S.highlight = null; S.filter = ""; if (search) search.value = "";
    }
  }

  // ---------------- API p/ o hologram.js ----------------
  function setActive(on) {
    S.active = on;
    if (on) {
      resize();
      if (!S.ready) refresh();
      else S._centerFrames = 12;
    } else { closeNote(); }
  }
  addEventListener("resize", () => { if (S.active) resize(); });

  function tick() {
    if (!S.active) return;
    if (cv.width !== Math.round(host.clientWidth * (devicePixelRatio || 1))) resize();
    if (S._centerFrames > 0 && S.nodes.length && host.clientWidth > 50) {
      layout(); fitView(); S._centerFrames--; S._everCentered = true;
    }
    layout();
    draw();
  }

  return { setActive, tick, refresh, onEvent };
})();

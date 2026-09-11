/* Jarvis — "Quadro" do Segundo Cérebro: lousa infinita de células (.canvas do Obsidian).
   DOM puro dentro de #board. hologram.js chama tick()/setActive()/onEvent(). */
window.jarvisBoard = (() => {
  "use strict";

  const host = document.getElementById("board");
  const world = document.createElement("div");
  world.style.cssText = "position:absolute;top:0;left:0;transform-origin:0 0;will-change:transform";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.style.cssText = "position:absolute;overflow:visible;pointer-events:none;left:0;top:0";
  svg.setAttribute("width", "1"); svg.setAttribute("height", "1");
  world.appendChild(svg);
  host.appendChild(world);

  const S = {
    active: false, rel: "", nodes: [], edges: [], jarvis: {},
    cam: { x: 60, y: 60, z: 1 }, sel: null, els: new Map(), dirty: false, saveT: 0,
    connectFrom: null,
  };
  // estado do controle por gesto (usado pela barra e pelo tick)
  const cursor = document.getElementById("b2-cursor");
  const G = { on: true, sx: 0, sy: 0, has: false, grab: null, pinchWas: false, panPrev: null };
  try { G.on = localStorage.getItem("jarvis-b2-gesture") !== "0"; } catch (e) {}
  const uid = () => "n" + Math.random().toString(36).slice(2, 10);
  const md = () => window.jarvisMD || { render: (s) => s.replace(/[<>]/g, "") };

  // ---------------- carregar / salvar ----------------
  async function listBoards() {
    const api = window.pywebview && window.pywebview.api;
    try { return (await api.board_list()) || []; } catch (e) { return []; }
  }
  async function load(rel, keepView) {
    const api = window.pywebview && window.pywebview.api;
    if (!api || !api.board_read) return;
    let data;
    try { data = await api.board_read(rel); } catch (e) { return; }
    S.rel = rel;
    S.nodes = (data.nodes || []).map((n) => ({ ...n }));
    S.edges = (data.edges || []).map((e) => ({ ...e }));
    S.jarvis = data._jarvis || {};
    if (!keepView) S._fitFrames = 24;   // re-enquadra (absorve timing de layout)
    render();
    pushCtx();
  }
  function pushCtx() {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.brain_ctx) {
      try { api.brain_ctx({ board: S.rel, selected: S.sel || "",
        sub: window.jarvisBrainUI ? window.jarvisBrainUI.sub() : "board" }); } catch (e) {}
    }
  }
  function scheduleSave() {
    S.dirty = true; S.saveT = performance.now() + 700;
  }
  async function flush() {
    if (!S.dirty || !S.rel || performance.now() < S.saveT) return;
    S.dirty = false;
    const api = window.pywebview && window.pywebview.api;
    try {
      await api.board_write(S.rel, { nodes: S.nodes, edges: S.edges, _jarvis: S.jarvis });
    } catch (e) { S.dirty = true; }
  }

  // ---------------- render ----------------
  function applyCam() {
    world.style.transform = `translate(${-S.cam.x * S.cam.z}px, ${-S.cam.y * S.cam.z}px) scale(${S.cam.z})`;
  }
  function fitView() {
    if (!S.nodes.length) { S.cam = { x: -host.clientWidth / 2 + 120, y: -host.clientHeight / 2 + 120, z: 1 }; applyCam(); return; }
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    S.nodes.forEach((n) => { x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y);
      x1 = Math.max(x1, n.x + (n.width || 250)); y1 = Math.max(y1, n.y + (n.height || 120)); });
    const z = Math.min(1.4, Math.max(0.3,
      0.85 * Math.min(host.clientWidth / (x1 - x0 + 120), host.clientHeight / (y1 - y0 + 120))));
    S.cam.z = z;
    S.cam.x = (x0 + x1) / 2 - host.clientWidth / (2 * z);
    S.cam.y = (y0 + y1) / 2 - host.clientHeight / (2 * z);
    applyCam();
  }

  const PRESET = { "1": "#ff6b6b", "2": "#ffa94d", "3": "#ffd43b", "4": "#46d6ff", "5": "#49f5b0", "6": "#b98bff" };
  function cellColor(n) { return PRESET[n.color] || n.color || "var(--neon-dim)"; }

  function render() {
    [...S.els.values()].forEach((el) => el.remove());
    S.els.clear();
    S.nodes.forEach(mkCell);
    drawEdges();
    applyCam();
    let hint = document.getElementById("b2-empty");
    if (!S.nodes.length) {
      if (!hint) {
        hint = document.createElement("div"); hint.id = "b2-empty";
        hint.style.cssText = "position:absolute;left:50%;top:44%;transform:translate(-50%,-50%);" +
          "color:rgba(158,202,216,0.55);font:13px 'Segoe UI',monospace;text-align:center;pointer-events:none";
        host.appendChild(hint);
      }
      hint.textContent = S.rel ? "quadro vazio — ＋ Texto, ou diga \"cria uma célula sobre…\""
                               : "nenhum quadro ainda — diga \"novo quadro <nome>\"";
    } else if (hint) { hint.remove(); }
  }

  function mkCell(n) {
    const el = document.createElement("div");
    el.className = "b2-cell";
    el.dataset.id = n.id;
    const jk = (S.jarvis[n.id] || {}).kind;
    el.style.cssText =
      `position:absolute;left:${n.x}px;top:${n.y}px;width:${n.width || 250}px;` +
      `min-height:${n.height || 120}px;box-sizing:border-box;` +
      `background:rgba(6,12,18,0.92);border:1px solid ${jk ? "var(--neon)" : cellColor(n)};` +
      `border-radius:8px;padding:12px 14px;color:#cfe6ef;font:12px/1.5 "Segoe UI",monospace;` +
      `box-shadow:0 4px 24px rgba(0,0,0,0.45);cursor:grab;overflow:hidden`;
    if (n.type === "file") {
      el.innerHTML = `<div class="b2-k">📄 ${(n.file || "").split("/").pop().replace(/\.md$/, "")}</div>` +
        `<div style="opacity:.6;font-size:11px;margin-top:6px">nota do vault — dois cliques abre no Obsidian</div>`;
    } else if (jk) {
      el.innerHTML = `<div class="b2-k" style="color:var(--neon)">✦ ${jk === "ai-live" ? "IA" : jk}</div>` +
        `<div class="b2-body">${md().render(n.text || "")}</div>`;
    } else {
      el.innerHTML = `<div class="b2-body">${md().render(n.text || "_(vazio)_")}</div>`;
    }
    // portas de conexão
    ["t", "r", "b", "l"].forEach((side) => {
      const p = document.createElement("div");
      p.className = "b2-port b2-port-" + side;
      p.dataset.side = side;
      el.appendChild(p);
    });
    wireCell(el, n);
    world.appendChild(el);
    S.els.set(n.id, el);
  }

  function drawEdges() {
    [...svg.querySelectorAll("path,text")].forEach((p) => p.remove());
    const SIDE = { top: [0.5, 0], right: [1, 0.5], bottom: [0.5, 1], left: [0, 0.5],
                   t: [0.5, 0], r: [1, 0.5], b: [0.5, 1], l: [0, 0.5] };
    S.edges.forEach((e) => {
      const a = S.nodes.find((n) => n.id === e.fromNode), b = S.nodes.find((n) => n.id === e.toNode);
      if (!a || !b) return;
      const [fx, fy] = SIDE[e.fromSide] || [0.5, 0.5], [tx, ty] = SIDE[e.toSide] || [0.5, 0.5];
      const x1 = a.x + (a.width || 250) * fx, y1 = a.y + (a.height || 120) * fy;
      const x2 = b.x + (b.width || 250) * tx, y2 = b.y + (b.height || 120) * ty;
      const dx = Math.abs(x2 - x1) * 0.5 + 20;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "rgba(120,200,230,0.4)");
      path.setAttribute("stroke-width", "1.5");
      svg.appendChild(path);
      if (e.label) {
        const tnode = document.createElementNS("http://www.w3.org/2000/svg", "text");
        tnode.setAttribute("x", (x1 + x2) / 2); tnode.setAttribute("y", (y1 + y2) / 2 - 4);
        tnode.setAttribute("fill", "#9ecad8"); tnode.setAttribute("font-size", "10");
        tnode.setAttribute("text-anchor", "middle"); tnode.textContent = e.label;
        svg.appendChild(tnode);
      }
    });
  }

  // ---------------- interação de célula ----------------
  function wireCell(el, n) {
    let drag = null;
    el.addEventListener("pointerdown", (e) => {
      if (e.target.classList.contains("b2-port")) {
        S.connectFrom = { id: n.id, side: e.target.dataset.side };
        e.stopPropagation(); return;
      }
      if (el.isContentEditable) return;
      el.setPointerCapture(e.pointerId);
      S.sel = n.id;
      [...S.els.values()].forEach((x) => x.classList.remove("sel"));
      el.classList.add("sel");
      drag = { px: e.clientX, py: e.clientY, x: n.x, y: n.y };
      el.style.cursor = "grabbing";
      e.stopPropagation();
    });
    el.addEventListener("pointermove", (e) => {
      if (!drag) return;
      n.x = drag.x + (e.clientX - drag.px) / S.cam.z;
      n.y = drag.y + (e.clientY - drag.py) / S.cam.z;
      el.style.left = n.x + "px"; el.style.top = n.y + "px";
      drawEdges();
    });
    el.addEventListener("pointerup", (e) => {
      if (S.connectFrom && S.connectFrom.id !== n.id) {
        finishConnect(n.id, e.target.dataset && e.target.dataset.side);
      }
      S.connectFrom = null;
      if (drag) { drag = null; el.style.cursor = "grab"; scheduleSave(); }
    });
    el.addEventListener("dblclick", (e) => {
      e.stopPropagation();
      if (n.type === "file") {
        const api = window.pywebview && window.pywebview.api;
        api && api.board_open_obsidian && api.board_open_obsidian(
          (S.rel.split("/").slice(0, -1).concat(n.file).join("/")).replace(/^\//, ""));
        return;
      }
      editCell(el, n);
    });
  }

  function editCell(el, n) {
    const body = el.querySelector(".b2-body") || el;
    body.textContent = n.text || "";
    el.contentEditable = "true";
    el.classList.add("editing");
    el.focus();
    const done = () => {
      el.contentEditable = "false";
      el.classList.remove("editing");
      n.text = (el.textContent || "").trim();
      body.innerHTML = md().render(n.text || "_(vazio)_");
      el.removeEventListener("blur", done);
      scheduleSave();
    };
    el.addEventListener("blur", done);
  }

  function finishConnect(toId, toSide) {
    const from = S.connectFrom;
    if (!from || from.id === toId) return;
    S.edges.push({ id: "e" + Math.random().toString(36).slice(2, 8),
      fromNode: from.id, fromSide: { t: "top", r: "right", b: "bottom", l: "left" }[from.side] || "right",
      toNode: toId, toSide: { t: "top", r: "right", b: "bottom", l: "left" }[toSide] || "left" });
    drawEdges(); scheduleSave();
  }

  // ---------------- pan / zoom no fundo ----------------
  let pan = null;
  host.addEventListener("pointerdown", (e) => {
    if (e.target !== host && e.target !== world && e.target !== svg) return;
    pan = { px: e.clientX, py: e.clientY, x: S.cam.x, y: S.cam.y };
    S.sel = null;
    [...S.els.values()].forEach((x) => x.classList.remove("sel"));
  });
  addEventListener("pointermove", (e) => {
    if (!pan) return;
    S.cam.x = pan.x - (e.clientX - pan.px) / S.cam.z;
    S.cam.y = pan.y - (e.clientY - pan.py) / S.cam.z;
    applyCam();
  });
  addEventListener("pointerup", () => { pan = null; });
  host.addEventListener("wheel", (e) => {
    e.preventDefault();
    const wx = S.cam.x + e.offsetX / S.cam.z, wy = S.cam.y + e.offsetY / S.cam.z;
    S.cam.z = Math.max(0.2, Math.min(3, S.cam.z * (e.deltaY < 0 ? 1.12 : 0.89)));
    S.cam.x = wx - e.offsetX / S.cam.z; S.cam.y = wy - e.offsetY / S.cam.z;
    applyCam();
  }, { passive: false });

  addEventListener("keydown", (e) => {
    if (!S.active || S.brainSub === "teia") return;
    if ((e.key === "Delete" || e.key === "Backspace") && S.sel &&
        !document.querySelector(".b2-cell.editing")) {
      const n = S.nodes.find((x) => x.id === S.sel);
      if (n && confirm(`Apagar a célula "${(n.text || n.file || "").slice(0, 30)}"?`)) {
        S.nodes = S.nodes.filter((x) => x.id !== S.sel);
        S.edges = S.edges.filter((x) => x.fromNode !== S.sel && x.toNode !== S.sel);
        delete S.jarvis[S.sel]; S.sel = null;
        render(); scheduleSave();
      }
    }
  }, true);

  // ---------------- criar célula ----------------
  function addCell(kind, text) {
    const cx = S.cam.x + host.clientWidth / (2 * S.cam.z) - 125;
    const cy = S.cam.y + host.clientHeight / (2 * S.cam.z) - 60;
    const n = { id: uid(), type: "text", text: text || "", x: Math.round(cx), y: Math.round(cy),
      width: 260, height: 120 };
    S.nodes.push(n);
    if (kind === "ai") S.jarvis[n.id] = { kind: "ai-live", prompt: text || "" };
    if (kind === "img") { n.text = "🖼️ (imagem — em breve)"; }
    mkCell(n); scheduleSave();
    if (kind === "text") editCell(S.els.get(n.id), n);
    return n;
  }

  // barra inferior
  const B = (id, fn) => { const b = document.getElementById(id); if (b) b.onclick = fn; };
  B("b2-teia", () => window.jarvisBrainUI && window.jarvisBrainUI.setSub("teia"));
  B("b2-board", () => window.jarvisBrainUI && window.jarvisBrainUI.setSub("board"));
  B("b2-add-text", () => addCell("text"));
  B("b2-add-ai", () => addCell("ai"));
  B("b2-add-img", () => addCell("img"));
  B("b2-gesture", () => setGesture(!G.on));
  setGesture(G.on);   // aplica o estado salvo no botão
  function syncBar() {
    const sub = window.jarvisBrainUI ? window.jarvisBrainUI.sub() : "board";
    const t = document.getElementById("b2-teia"), b = document.getElementById("b2-board");
    if (t) t.classList.toggle("on", sub === "teia");
    if (b) b.classList.toggle("on", sub === "board");
  }

  // ---------------- eventos de voz ----------------
  function onEvent(ev) {
    if (!ev) return;
    if (ev.op === "add_cell") addCell(ev.own ? "ai" : "text", ev.text || "");
    else if (ev.op === "open_board" && ev.rel) load(ev.rel);
    else if (ev.op === "reload") { if (S.rel) load(S.rel, true); }
    else if (ev.op === "obsidian") {
      const api = window.pywebview && window.pywebview.api;
      const rel = S.sel && S.nodes.find((n) => n.id === S.sel);
      if (api && api.board_open_obsidian) {
        api.board_open_obsidian(rel && rel.type === "file"
          ? S.rel.split("/").slice(0, -1).concat(rel.file).join("/").replace(/^\//, "")
          : S.rel);
      }
    }
  }

  // ---------------- gesto (mão na janelinha da webcam) ----------------
  //   pinça (👌) = pega e move a célula mais perto
  //   palma (🖐) = arrasta o quadro
  // Cursor visível o tempo todo que houver mão. Toggle 🖐 na barra liga/desliga.
  function setGesture(on) {
    G.on = on;
    try { localStorage.setItem("jarvis-b2-gesture", on ? "1" : "0"); } catch (e) {}
    const b = document.getElementById("b2-gesture");
    if (b) b.classList.toggle("on", on);
    if (!on && cursor) { cursor.classList.remove("on", "grab"); }
    if (!on) { G.grab = null; G.panPrev = null; }
  }

  function gesture(g) {
    if (!cursor) return;
    const hand = G.on && g && g.hands && g.hands[0];
    if (!hand) {
      cursor.classList.remove("on", "grab");
      if (G.grab) { scheduleSave(); pushCtx(); }
      G.grab = null; G.panPrev = null; G.has = false; return;
    }
    const gg = hand.gesture || {};
    const lm = hand.landmarks;
    const px = lm[9] ? lm[9].x : 0.5, py = lm[9] ? lm[9].y : 0.5;
    // ponta = pinça se pinçando, senão centro da palma; espelhado
    const tipx = gg.pinch >= 0.6 && gg.pinchAt ? gg.pinchAt.x : px;
    const tipy = gg.pinch >= 0.6 && gg.pinchAt ? gg.pinchAt.y : py;
    const tx = (1 - tipx) * innerWidth, ty = tipy * innerHeight;
    // suaviza
    if (!G.has) { G.sx = tx; G.sy = ty; G.has = true; }
    G.sx += (tx - G.sx) * 0.35; G.sy += (ty - G.sy) * 0.35;
    cursor.style.left = G.sx + "px"; cursor.style.top = G.sy + "px";
    cursor.classList.add("on");

    const wx = S.cam.x + G.sx / S.cam.z, wy = S.cam.y + G.sy / S.cam.z;
    const pinching = gg.pinch >= 0.8;
    cursor.classList.toggle("grab", pinching && !!G.grab);

    if (pinching) {
      G.panPrev = null;
      if (!G.grab && !G.pinchWas) {            // pinça ACABOU de fechar → pega
        let best = null, bd = 200;
        S.nodes.forEach((n) => {
          const cx = n.x + (n.width || 250) / 2, cy = n.y + (n.height || 120) / 2;
          const d = Math.hypot(cx - wx, cy - wy);
          if (d < bd) { bd = d; best = n; }
        });
        if (best) {
          G.grab = { n: best, ox: best.x - wx, oy: best.y - wy };
          S.sel = best.id;
          [...S.els.values()].forEach((x) => x.classList.remove("sel"));
          const el = S.els.get(best.id); if (el) el.classList.add("sel");
        }
      } else if (G.grab) {
        G.grab.n.x = wx + G.grab.ox; G.grab.n.y = wy + G.grab.oy;
        const el = S.els.get(G.grab.n.id);
        if (el) { el.style.left = G.grab.n.x + "px"; el.style.top = G.grab.n.y + "px"; }
        drawEdges();
      }
    } else {
      if (G.grab) { scheduleSave(); pushCtx(); G.grab = null; }
      if (gg.name === "palma") {               // mão aberta = arrasta o quadro
        if (G.panPrev) {
          S.cam.x -= (G.sx - G.panPrev.x) / S.cam.z;
          S.cam.y -= (G.sy - G.panPrev.y) / S.cam.z;
          applyCam();
        }
        G.panPrev = { x: G.sx, y: G.sy };
      } else {
        G.panPrev = null;
      }
    }
    G.pinchWas = pinching;
  }

  // ---------------- API ----------------
  async function setActive(on) {
    S.active = on;
    syncBar();
    if (!on) {
      flush();
      if (cursor) cursor.classList.remove("on", "grab");
      G.grab = null; G.panPrev = null; G.has = false;
      return;
    }
    if (!S.rel) {
      const boards = await listBoards();
      if (boards.length) load(boards[0]);
      else render();
    } else {
      applyCam();
    }
  }
  function tick(t, g) {
    if (!S.active) return;
    S.brainSub = window.jarvisBrainUI ? window.jarvisBrainUI.sub() : "board";
    syncBar();
    if (S._fitFrames > 0 && S.nodes.length && host.clientWidth > 50) {
      fitView(); S._fitFrames--;
    }
    if (S.brainSub === "board") {
      gesture(g);
    } else if (cursor) {
      cursor.classList.remove("on", "grab"); G.grab = null; G.panPrev = null; G.has = false;
    }
    flush();
  }

  return { setActive, tick, onEvent };
})();

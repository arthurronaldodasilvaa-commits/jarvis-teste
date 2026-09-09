/* Jarvis — cérebro holográfico (Three.js r128) */
(() => {
  "use strict";

  const NEON = 0x46d6ff;
  const NEON_SOFT = 0x9becff;
  const TAU = Math.PI * 2;

  const host = document.getElementById("scene");
  const statusEl = document.getElementById("status");

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x000000, 0.14);

  const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 100);
  camera.position.set(0, 0, 4.2);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.setClearColor(0x000000, 1);
  host.appendChild(renderer.domElement);

  // ---------- glow de fundo ----------
  function radialSprite(size) {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0.0, "rgba(120,230,255,0.55)");
    g.addColorStop(0.35, "rgba(70,214,255,0.18)");
    g.addColorStop(1.0, "rgba(0,0,0,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    const mat = new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(c), blending: THREE.AdditiveBlending,
      depthWrite: false, transparent: true,
    });
    return new THREE.Sprite(mat);
  }
  const glow = radialSprite(512);
  glow.scale.set(9, 9, 1);
  glow.position.z = -1.5;
  scene.add(glow);

  // ---------- núcleo ----------
  const core = new THREE.Group();
  scene.add(core);

  const shellDefs = [
    { r: 1.15, detail: 1, opacity: 0.90, scale: 1.00, phase: 0.0, freq: 0.9 },
    { r: 1.15, detail: 1, opacity: 0.30, scale: 1.22, phase: 1.4, freq: 0.62 },
    { r: 1.15, detail: 1, opacity: 0.13, scale: 1.52, phase: 2.9, freq: 0.44 },
    { r: 0.72, detail: 0, opacity: 0.85, scale: 1.00, phase: 0.7, freq: 1.1 },
  ];
  const shells = shellDefs.map((d) => {
    const wire = new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(d.r, d.detail));
    const mat = new THREE.LineBasicMaterial({
      color: NEON, transparent: true, opacity: d.opacity,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const seg = new THREE.LineSegments(wire, mat);
    seg.scale.setScalar(d.scale);
    seg.userData = d;
    core.add(seg);
    return seg;
  });

  const blobMat = new THREE.MeshBasicMaterial({
    color: NEON, transparent: true, opacity: 0.06,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const blob = new THREE.Mesh(new THREE.IcosahedronGeometry(1.02, 2), blobMat);
  core.add(blob);

  const points = new THREE.Points(
    new THREE.IcosahedronGeometry(1.15, 4),
    new THREE.PointsMaterial({
      color: NEON_SOFT, size: 0.035, transparent: true, opacity: 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
  );
  core.add(points);

  const rings = [];
  [[1.9, 0.012, 0], [2.25, 0.010, Math.PI / 2.6], [2.6, 0.008, -Math.PI / 3.5]].forEach(([R, tube, tilt], i) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(R, tube, 8, 140),
      new THREE.MeshBasicMaterial({
        color: NEON, transparent: true, opacity: 0.5 - i * 0.12,
        blending: THREE.AdditiveBlending, depthWrite: false,
      })
    );
    ring.rotation.x = Math.PI / 2 + tilt;
    ring.userData.speed = 0.15 + i * 0.12;
    ring.userData.baseOpacity = 0.5 - i * 0.12;
    rings.push(ring);
    core.add(ring);
  });

  // ---------- starfield ----------
  const starGeo = new THREE.BufferGeometry();
  const N = 420, sp = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    sp[i * 3] = (Math.random() - 0.5) * 40;
    sp[i * 3 + 1] = (Math.random() - 0.5) * 26;
    sp[i * 3 + 2] = -Math.random() * 30 - 2;
  }
  starGeo.setAttribute("position", new THREE.BufferAttribute(sp, 3));
  const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0x2a6f88, size: 0.05, transparent: true, opacity: 0.6 }));
  scene.add(stars);

  // ---------- estado ----------
  const state = {
    speaking: false,
    speakLevel: 0,       // suavizado 0..1
    amplitude: 0.5,      // profundidade do pulso quando falando
    status: "SISTEMA ONLINE",
    paused: false,
    pausedLevel: 0,      // suavizado 0..1
    view: "brain",       // "brain" | "camera"
    cameraMatch: "Brio",
  };

  function applyView(v) {
    if (v === state.view) return;
    state.view = v;
    const cam = v === "camera";
    document.body.classList.toggle("camera", cam);
    renderer.domElement.style.display = cam ? "none" : "block";
    const lbl = document.getElementById("cam-btn-label");
    if (lbl) lbl.textContent = cam ? "Cérebro" : "Câmera";
    if (window.jarvisHolo) window.jarvisHolo.setActive(cam);
    if (cam) window.jarvisCam.start(state.cameraMatch);
    else window.jarvisCam.stop();
  }

  window.jarvis = {
    setSpeaking: (b) => { state.speaking = !!b; },
    setAmplitude: (a) => { state.amplitude = Math.max(0, Math.min(1, +a || 0)); },
    setStatus: (s) => { state.status = String(s || ""); },
  };

  // ---------- botão liga/pausa ----------
  const powerBtn = document.getElementById("power");
  const powerLbl = document.getElementById("power-label");
  const fxEl = document.getElementById("fx");
  powerBtn.addEventListener("click", () => {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.toggle_pause) api.toggle_pause().then((c) => applyPaused(!!(c && c.paused)));
    else applyPaused(!state.paused);   // fallback offline
  });
  function applyPaused(p) {
    state.paused = p;
    document.body.classList.toggle("paused", p);
    fxEl.classList.toggle("paused", p);
    powerLbl.textContent = p ? "Pausado — clique p/ ativar" : "Ouvindo";
  }

  // botão câmera <-> cérebro
  const camBtn = document.getElementById("cam-btn");
  if (camBtn) camBtn.addEventListener("click", () => {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.toggle_view) api.toggle_view().then((c) => applyView((c && c.view) || "brain"));
    else applyView(state.view === "camera" ? "brain" : "camera");
  });

  // ---------- ponte com o Python (1 round-trip: state.json + control.json) ----------
  function pollState() {
    const api = window.pywebview && window.pywebview.api;
    if (!api || !api.get_status) return;
    api.get_status().then((s) => {
      if (!s) return;
      state.speaking = !!s.speaking;
      if (typeof s.amplitude === "number") state.amplitude = s.amplitude;
      if (s.status) state.status = s.status;
      if (s.camera_match) state.cameraMatch = s.camera_match;
      window.jarvisCam.configure(s);
      if (window.jarvisHolo && s.holo) window.jarvisHolo.onControl(s.holo);
      const p = !!s.paused;
      if (p !== state.paused) applyPaused(p);
      if (s.view === "camera" || s.view === "brain") applyView(s.view);
    }).catch(() => {});
  }
  setInterval(pollState, 250);

  // ---------- fechar ----------
  addEventListener("keydown", (e) => { if (e.key === "Escape") closeApp(); });
  document.getElementById("close").addEventListener("click", closeApp);
  function closeApp() {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.close) api.close();
    else window.close();
  }

  // ---------- loop (60fps quando ativo, ~30fps parado — economiza bateria/GPU) ----------
  const clock = new THREE.Clock();
  let _skip = false;
  function tick() {
    requestAnimationFrame(tick);
    const t = clock.getElapsedTime();
    if (state.view === "camera") {
      const g = window.jarvisHands && window.jarvisHands.results();
      let extra = "";
      if (g && g.hands && g.hands.length) {
        const names = g.hands.map((h) => h.gesture && h.gesture.name).filter(Boolean);
        if (names.length) extra = " · " + names.map((n) => window.jarvisGestures.label(n)).join(" / ");
      }
      const n = window.jarvisHolo ? window.jarvisHolo.count() : 0;
      statusEl.textContent = "CÂMERA ATIVA" + (n ? " · " + n + " forma" + (n > 1 ? "s" : "") : "") + extra;
      if (window.jarvisHolo) window.jarvisHolo.tick(t, g);
      return;
    }

    const idle = state.speakLevel < 0.01 && !state.speaking
              && Math.abs(state.pausedLevel - (state.paused ? 1 : 0)) < 0.01;
    if (idle) { _skip = !_skip; if (_skip) return; }   // pula 1 frame sim, 1 não

    state.pausedLevel += ((state.paused ? 1 : 0) - state.pausedLevel) * 0.06;
    const pz = state.pausedLevel;               // 0 ativo -> 1 pausado

    // rampa suave (~1s) pra entrar/sair do "falando" (zerado quando pausado)
    state.speakLevel += (((state.speaking && !state.paused) ? 1 : 0) - state.speakLevel) * 0.045;
    const spk = state.speakLevel;
    const depth = 0.5 + state.amplitude;               // 0.5 .. 1.5

    // pulso LENTO (~0.55 Hz) — a "respiração" enquanto fala
    const slow = 0.5 + 0.5 * Math.sin(t * TAU * 0.55);

    // escala do núcleo: idle respira de leve; falando pulsa devagar e mais forte
    const idleBreath = 1 + Math.sin(t * 1.4) * 0.015;
    const scale = idleBreath + spk * depth * (0.05 + 0.06 * slow);
    core.scale.setScalar(scale);

    // rotação — quase para quando pausado
    const rot = (0.0022 + spk * 0.0035) * (1 - pz * 0.92);
    core.rotation.y += rot;
    core.rotation.x = Math.sin(t * 0.22) * 0.14;
    blob.rotation.y -= rot * 1.5;
    points.rotation.y += rot * 0.4;
    rings.forEach((r) => { r.rotation.z += r.userData.speed * (0.008 + spk * 0.012) * (1 - pz * 0.9); });

    // brilhos "piscando" devagar; escurece bastante quando pausado
    const dim = 1 - pz * 0.62;
    shells.forEach((s) => {
      const d = s.userData;
      const wave = 0.5 + 0.5 * Math.sin(t * TAU * d.freq + d.phase);
      s.material.opacity = d.opacity * dim * (1 + spk * depth * (0.7 + 1.4 * wave));
    });
    points.material.opacity = 0.9 * dim;
    rings.forEach((r) => { r.material.opacity = r.userData.baseOpacity * dim; });
    blobMat.opacity = (0.06 + spk * depth * (0.10 + 0.14 * slow)) * dim;

    glow.scale.setScalar((9 + spk * depth * (2.2 + 2.0 * slow)) * (1 - pz * 0.25));
    glow.material.opacity = (0.85 + spk * 0.15 * slow) * (1 - pz * 0.5);

    camera.position.z = 4.2 - spk * depth * (0.30 + 0.22 * slow) + pz * 0.35;
    camera.lookAt(0, 0, 0);

    stars.rotation.z += 0.0003;

    statusEl.textContent = state.paused ? "PAUSADO" : (state.speaking ? "FALANDO" : state.status);

    renderer.render(scene, camera);
  }
  tick();

  addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });
})();

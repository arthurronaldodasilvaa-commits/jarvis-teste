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
  };

  window.jarvis = {
    setSpeaking: (b) => { state.speaking = !!b; },
    setAmplitude: (a) => { state.amplitude = Math.max(0, Math.min(1, +a || 0)); },
    setStatus: (s) => { state.status = String(s || ""); },
  };

  // ---------- ponte com o Python (state.json) ----------
  let _dbgReady = false, _lastSpeaking = null;
  function dbg(m) {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.debug) api.debug("[" + new Date().toISOString() + "] " + m);
  }
  function pollState() {
    const api = window.pywebview && window.pywebview.api;
    if (!api || !api.get_state) return;
    if (!_dbgReady) { _dbgReady = true; dbg("ponte pywebview OK"); }
    api.get_state().then((s) => {
      if (!s) return;
      const sp = !!s.speaking;
      if (sp !== _lastSpeaking) { _lastSpeaking = sp; dbg("speaking=" + sp + " status=" + s.status); }
      state.speaking = sp;
      if (typeof s.amplitude === "number") state.amplitude = s.amplitude;
      if (s.status) state.status = s.status;
    }).catch((e) => dbg("erro get_state: " + e));
  }
  setInterval(pollState, 200);

  // ---------- fechar ----------
  addEventListener("keydown", (e) => { if (e.key === "Escape") closeApp(); });
  document.getElementById("close").addEventListener("click", closeApp);
  function closeApp() {
    const api = window.pywebview && window.pywebview.api;
    if (api && api.close) api.close();
    else window.close();
  }

  // ---------- loop ----------
  const clock = new THREE.Clock();
  function tick() {
    const t = clock.getElapsedTime();

    // rampa suave (~1s) pra entrar/sair do "falando"
    state.speakLevel += ((state.speaking ? 1 : 0) - state.speakLevel) * 0.045;
    const spk = state.speakLevel;
    const depth = 0.5 + state.amplitude;               // 0.5 .. 1.5

    // pulso LENTO (~0.55 Hz) — a "respiração" enquanto fala
    const slow = 0.5 + 0.5 * Math.sin(t * TAU * 0.55);

    // escala do núcleo: idle respira de leve; falando pulsa devagar e mais forte
    const idleBreath = 1 + Math.sin(t * 1.4) * 0.015;
    const scale = idleBreath + spk * depth * (0.05 + 0.06 * slow);
    core.scale.setScalar(scale);

    // rotação — quase igual; um tiquinho mais viva falando
    const rot = 0.0022 + spk * 0.0035;
    core.rotation.y += rot;
    core.rotation.x = Math.sin(t * 0.22) * 0.14;
    blob.rotation.y -= rot * 1.5;
    points.rotation.y += rot * 0.4;
    rings.forEach((r) => { r.rotation.z += r.userData.speed * (0.008 + spk * 0.012); });

    // brilhos "piscando" devagar, cada casca em sua própria fase
    shells.forEach((s) => {
      const d = s.userData;
      const wave = 0.5 + 0.5 * Math.sin(t * TAU * d.freq + d.phase);   // 0..1 lento
      s.material.opacity = d.opacity * (1 + spk * depth * (0.7 + 1.4 * wave));
    });
    blobMat.opacity = 0.06 + spk * depth * (0.10 + 0.14 * slow);

    // glow de fundo — infla e clareia junto com o pulso lento
    glow.scale.setScalar(9 + spk * depth * (2.2 + 2.0 * slow));
    glow.material.opacity = 0.85 + spk * 0.15 * slow;

    // câmera: zoom in/out LENTO, sem tremida
    camera.position.z = 4.2 - spk * depth * (0.30 + 0.22 * slow);
    camera.lookAt(0, 0, 0);

    stars.rotation.z += 0.0003;

    statusEl.textContent = state.speaking ? "FALANDO" : state.status;

    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  tick();

  addEventListener("resize", () => {
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight);
  });
})();

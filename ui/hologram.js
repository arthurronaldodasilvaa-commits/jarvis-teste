/* Jarvis — cérebro holográfico (Three.js r128) */
(() => {
  "use strict";

  const NEON = 0x46d6ff;
  const NEON_SOFT = 0x8fe8ff;

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
  function radialSprite(size, color) {
    const c = document.createElement("canvas");
    c.width = c.height = size;
    const g = c.getContext("2d").createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0, color);
    g.addColorStop(0.4, "rgba(70,214,255,0.20)");
    g.addColorStop(1, "rgba(0,0,0,0)");
    const ctx = c.getContext("2d");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    const tex = new THREE.CanvasTexture(c);
    const mat = new THREE.SpriteMaterial({ map: tex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true });
    const s = new THREE.Sprite(mat);
    return s;
  }
  const glow = radialSprite(512, "rgba(70,214,255,0.55)");
  glow.scale.set(9, 9, 1);
  glow.position.z = -1.5;
  scene.add(glow);

  // ---------- núcleo ----------
  const core = new THREE.Group();
  scene.add(core);

  const shellDefs = [
    { r: 1.15, detail: 1, opacity: 0.9, color: NEON },
    { r: 1.15, detail: 1, opacity: 0.28, color: NEON, scale: 1.22 },
    { r: 1.15, detail: 1, opacity: 0.12, color: NEON, scale: 1.5 },
    { r: 0.72, detail: 0, opacity: 0.85, color: NEON_SOFT },
  ];
  const shells = shellDefs.map((d) => {
    const geo = new THREE.IcosahedronGeometry(d.r, d.detail);
    const wire = new THREE.WireframeGeometry(geo);
    const mat = new THREE.LineBasicMaterial({
      color: d.color, transparent: true, opacity: d.opacity,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const seg = new THREE.LineSegments(wire, mat);
    if (d.scale) seg.scale.setScalar(d.scale);
    seg.userData.baseOpacity = d.opacity;
    core.add(seg);
    return seg;
  });

  // volume interno translúcido
  const blobMat = new THREE.MeshBasicMaterial({
    color: NEON, transparent: true, opacity: 0.06,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const blob = new THREE.Mesh(new THREE.IcosahedronGeometry(1.02, 2), blobMat);
  core.add(blob);

  // pontos nos vértices (sinapses)
  const ptsGeo = new THREE.IcosahedronGeometry(1.15, 4);
  const points = new THREE.Points(
    ptsGeo,
    new THREE.PointsMaterial({
      color: NEON_SOFT, size: 0.035, transparent: true, opacity: 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
  );
  core.add(points);

  // anéis tipo reator
  const rings = [];
  [[1.9, 0.012, 0], [2.25, 0.010, Math.PI / 2.6], [2.6, 0.008, -Math.PI / 3.5]].forEach(([R, tube, tilt], i) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(R, tube, 8, 140),
      new THREE.MeshBasicMaterial({ color: NEON, transparent: true, opacity: 0.5 - i * 0.12, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    ring.rotation.x = Math.PI / 2 + tilt;
    ring.userData.speed = 0.15 + i * 0.12;
    rings.push(ring);
    core.add(ring);
  });

  // ---------- starfield ----------
  const starGeo = new THREE.BufferGeometry();
  const N = 420, pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    pos[i * 3] = (Math.random() - 0.5) * 40;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 26;
    pos[i * 3 + 2] = -Math.random() * 30 - 2;
  }
  starGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0x2a6f88, size: 0.05, transparent: true, opacity: 0.6 }));
  scene.add(stars);

  // ---------- estado ----------
  const state = {
    speaking: false,      // alvo
    speakLevel: 0,        // suavizado 0..1
    amplitude: 0.4,       // intensidade do pulso quando falando
    pulse: 0,             // "one-shot" decaindo
    status: "SISTEMA ONLINE",
  };

  window.jarvis = {
    setSpeaking: (b) => { state.speaking = !!b; },
    setAmplitude: (a) => { state.amplitude = Math.max(0, Math.min(1, +a || 0)); },
    pulseOnce: () => { state.pulse = 1; },
    setStatus: (s) => { state.status = String(s || ""); },
  };

  // ---------- ponte com o Python (state.json) ----------
  function pollState() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_state) {
      window.pywebview.api.get_state().then((s) => {
        if (!s) return;
        state.speaking = !!s.speaking;
        if (typeof s.amplitude === "number") state.amplitude = s.amplitude;
        if (s.status) state.status = s.status;
      }).catch(() => {});
    }
  }
  setInterval(pollState, 200);

  // ---------- teclado / botão ----------
  addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeApp();
    else if (e.key.toLowerCase() === "s") state.speaking = !state.speaking;
    else if (e.code === "Space") { state.pulse = 1; e.preventDefault(); }
  });
  document.getElementById("close").addEventListener("click", closeApp);
  function closeApp() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.close) window.pywebview.api.close();
    else window.close();
  }

  // ---------- loop ----------
  const clock = new THREE.Clock();
  function tick() {
    const t = clock.getElapsedTime();
    const dt = Math.min(clock.getDelta ? 0 : 0, 0); // (getElapsedTime já avança)

    // suavização do "falando"
    const target = state.speaking ? 1 : 0;
    state.speakLevel += (target - state.speakLevel) * 0.08;
    state.pulse *= 0.92;
    const energy = Math.max(state.speakLevel * (0.5 + state.amplitude), state.pulse);

    // respiração / dilatação
    const breathe = 1
      + Math.sin(t * 1.6) * 0.02
      + energy * (0.10 + Math.sin(t * 14) * 0.06);
    core.scale.setScalar(breathe);

    // rotação (mais rápida quando fala)
    const rot = 0.0025 + energy * 0.012;
    core.rotation.y += rot;
    core.rotation.x = Math.sin(t * 0.25) * 0.15;
    blob.rotation.y -= rot * 1.6;
    points.rotation.y += rot * 0.5;

    rings.forEach((r, i) => { r.rotation.z += r.userData.speed * (0.01 + energy * 0.03); });

    // brilho das cascas
    shells.forEach((s, i) => {
      s.material.opacity = s.userData.baseOpacity * (1 + energy * 1.3);
    });
    blobMat.opacity = 0.06 + energy * 0.20;
    glow.scale.setScalar(9 + energy * 4);
    glow.material.opacity = 0.9 + energy * 0.1;

    // câmera dolly (zoom in/out enquanto fala)
    camera.position.z = 4.2 - energy * 0.55 + Math.sin(t * 9) * energy * 0.18;
    camera.lookAt(0, 0, 0);

    stars.rotation.z += 0.0004;

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

  setTimeout(() => (statusEl.textContent = state.status), 600);
})();

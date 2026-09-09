/* Jarvis — painel de configurações (edita o config.toml pelo app). */
(() => {
  "use strict";
  const api = () => (window.pywebview && window.pywebview.api) || null;
  const panel = document.getElementById("settings");
  const form = document.getElementById("settings-form");

  // campo: [chave pontilhada, rótulo, tipo, opções]
  const FIELDS = [
    ["profile.active", "Perfil ativo", "select:_profiles"],
    ["assistant.address", "Como te chamar", "text"],
    ["assistant.user_name", "Seu nome", "text"],
    ["assistant.wake_word", "Palavra de ativação", "text"],
    ["assistant.attention_reply", "Resposta ao chamar", "text"],
    ["tts.engine", "Motor de voz", "choice:piper,sapi"],
    ["tts.sapi_voice", "Voz do Windows (se SAPI)", "select:_voices"],
    ["audio.input_device_match", "Microfone (trecho do nome)", "text"],
    ["app.camera_match", "Câmera (trecho do nome)", "text"],
    ["location.city", "Cidade do clima", "text"],
    ["arrival.enabled", "Frase de chegada ligada", "bool"],
    ["arrival.phrase", "Frase de chegada", "text"],
    ["arrival.briefing", "Briefing na chegada", "bool"],
    ["camera.media_gestures", "Gestos de mídia na câmera", "bool"],
    ["camera.auto_return_seconds", "Voltar pro cérebro após (s, 0=nunca)", "number"],
    ["danger.allow_shutdown", "Permitir desligar o PC", "bool"],
    ["danger.allow_typing", "Permitir digitar/escrever", "bool"],
  ];

  let cur = {};

  function open() {
    const a = api();
    if (!a || !a.get_config) return;
    a.get_config().then((cfg) => {
      cur = cfg || {};
      render();
      panel.classList.add("on");
    });
  }
  function close() { panel.classList.remove("on"); }

  function render() {
    form.innerHTML = "";
    for (const [key, label, type] of FIELDS) {
      const row = document.createElement("div"); row.className = "row";
      const l = document.createElement("label"); l.textContent = label; row.appendChild(l);
      let el;
      if (type === "bool") {
        el = document.createElement("input"); el.type = "checkbox";
        el.checked = cur[key] === true;
      } else if (type === "number") {
        el = document.createElement("input"); el.type = "number";
        el.value = cur[key] == null ? 0 : cur[key];
      } else if (type.startsWith("choice:")) {
        el = document.createElement("select");
        for (const o of type.slice(7).split(",")) {
          const op = document.createElement("option");
          op.value = o; op.textContent = o;
          if (o === (cur[key] || "")) op.selected = true;
          el.appendChild(op);
        }
      } else if (type.startsWith("select:")) {
        el = document.createElement("select");
        const opts = cur[type.slice(7)] || [];
        if (key === "profile.active") opts.unshift("");
        for (const o of opts) {
          const op = document.createElement("option");
          op.value = o; op.textContent = o || "(padrão)";
          if (o === (cur[key] || "")) op.selected = true;
          el.appendChild(op);
        }
      } else {
        el = document.createElement("input"); el.type = "text";
        el.value = cur[key] == null ? "" : cur[key];
      }
      el.dataset.key = key; el.dataset.type = type;
      row.appendChild(el); form.appendChild(row);
    }
  }

  function save() {
    const patch = {};
    form.querySelectorAll("[data-key]").forEach((el) => {
      const k = el.dataset.key, t = el.dataset.type;
      let v;
      if (t === "bool") v = el.checked;
      else if (t === "number") v = parseFloat(el.value) || 0;
      else v = el.value;
      if (v !== cur[k]) patch[k] = v;
    });
    if (!Object.keys(patch).length) { close(); return; }
    const a = api();
    if (a && a.set_config) {
      a.set_config(patch).then((r) => {
        close();
        if (r && r.ok === false) alert("Não salvou: " + (r.msg || "erro"));
      });
    }
  }

  document.getElementById("gear").addEventListener("click", open);
  document.getElementById("set-cancel").addEventListener("click", close);
  document.getElementById("set-save").addEventListener("click", save);
  panel.addEventListener("click", (e) => { if (e.target === panel) close(); });
  addEventListener("keydown", (e) => { if (e.key === "Escape" && panel.classList.contains("on")) { e.stopImmediatePropagation(); close(); } }, true);

  window.jarvisSettings = { open, close };
})();

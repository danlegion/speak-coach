// Speak Coach — thin client (Pocket mode, M1).
// Captures a drill rep (MediaRecorder), collects the Predict taps,
// uploads the raw blob to the mailbox, then polls for Felix's scorecard.
"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  plan: null,
  stream: null,
  recorder: null,
  chunks: [],
  blob: null,
  mime: "",
  timerId: null,
  startedAt: 0,
  predict: { pace: "", fillers: "" },
  session: null,
  pollId: null,
};

// Access token (set once per device; the mailbox checks it when configured).
function getToken() { return localStorage.getItem("sc_token") || ""; }
async function apiFetch(url, opts = {}, retry = true) {
  opts.headers = { ...(opts.headers || {}), "X-App-Token": getToken() };
  const res = await fetch(url, opts);
  if (res.status === 401 && retry) {
    const t = prompt("Access token for your Speak Coach mailbox:");
    if (t) {
      localStorage.setItem("sc_token", t.trim());
      return apiFetch(url, opts, false);
    }
  }
  return res;
}

function show(id) {
  for (const s of document.querySelectorAll(".screen")) s.classList.add("hidden");
  $(id).classList.remove("hidden");
}

function fmt(sec) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Station vs Pocket: wide landscape screens (Portal) get the Station label.
if (Math.min(screen.width, screen.height) >= 600 && screen.width > screen.height) {
  $("modeLabel").textContent = "Station mode";
}

async function loadPlan() {
  const res = await apiFetch("/api/plan");
  const plan = await res.json();
  state.plan = plan;
  const d = plan.drill;
  $("dTrack").textContent = `${d.track} · ${d.level}`;
  $("dName").textContent = `${d.name} (${d.code})`;
  $("dPrompt").textContent = d.prompt;
  $("dTime").textContent = `${d.time_seconds}s`;
  $("dAudience").textContent = d.audience;
  $("dBar").textContent = d.bar;
  $("dFix").textContent = plan.fix_carried_forward;
  $("dConstraints").innerHTML = d.constraints.map((c) => `<li>${c}</li>`).join("");
  $("dPrinciples").innerHTML = d.principles.map((c) => `<li>${c}</li>`).join("");
  $("targetLabel").textContent = `Target ${fmt(d.time_seconds)} · no restarts`;
}

async function startRecording() {
  const wantVideo = $("videoToggle").checked;
  const constraints = wantVideo
    ? { audio: true, video: { facingMode: "user" } }
    : { audio: true };
  state.stream = await navigator.mediaDevices.getUserMedia(constraints);
  if (wantVideo) {
    $("preview").srcObject = state.stream;
    $("preview").classList.remove("hidden");
  }
  const mime = ["video/webm", "audio/webm", "audio/mp4", "video/mp4"]
    .find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || "";
  state.recorder = new MediaRecorder(state.stream, mime ? { mimeType: mime } : undefined);
  state.mime = state.recorder.mimeType || mime;
  state.chunks = [];
  state.recorder.ondataavailable = (e) => { if (e.data.size) state.chunks.push(e.data); };
  state.recorder.onstop = onStopped;
  // 3-2-1 countdown, then record.
  show("screen-record");
  const cd = $("countdown");
  cd.classList.remove("hidden");
  for (const n of [3, 2, 1]) {
    cd.textContent = n;
    await new Promise((r) => setTimeout(r, 700));
  }
  cd.classList.add("hidden");
  state.recorder.start(250);
  state.startedAt = Date.now();
  $("btnRec").classList.add("hidden");
  $("btnStop").classList.remove("hidden");
  $("timer").textContent = "0:00";
  state.timerId = setInterval(() => {
    $("timer").textContent = fmt((Date.now() - state.startedAt) / 1000);
  }, 250);
}

function stopRecording() {
  if (state.recorder && state.recorder.state !== "inactive") state.recorder.stop();
}

function onStopped() {
  clearInterval(state.timerId);
  if (state.stream) state.stream.getTracks().forEach((t) => t.stop());
  state.blob = new Blob(state.chunks, { type: state.mime || "application/octet-stream" });
  show("screen-predict");
}

function wireChips(elId, key) {
  $(elId).addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    for (const b of $(elId).querySelectorAll("button")) b.classList.remove("sel");
    btn.classList.add("sel");
    state.predict[key] = btn.dataset.v;
    $("btnUpload").disabled = !(state.predict.pace && state.predict.fillers);
  });
}

async function upload() {
  const d = state.plan.drill;
  const mode = state.mime.startsWith("video") || $("videoToggle").checked ? "video" : "audio";
  $("btnUpload").disabled = true;
  $("upHint").textContent = "Sending…";
  try {
    const res = await apiFetch(`/api/upload?drill=${encodeURIComponent(d.code)}&mode=${mode}`, {
      method: "POST",
      headers: {
        "Content-Type": state.mime || "application/octet-stream",
        "X-Predict-Pace": state.predict.pace,
        "X-Predict-Fillers": state.predict.fillers,
      },
      body: state.blob,
    });
    if (!res.ok) throw new Error(`upload failed (${res.status})`);
    const out = await res.json();
    state.session = out.session;
    const pb = $("playback");
    pb.src = URL.createObjectURL(state.blob);
    pb.classList.remove("hidden");
    show("screen-done");
    poll();
    state.pollId = setInterval(poll, 8000);
  } catch (err) {
    $("upHint").textContent = `Upload failed — ${err.message}. Your take is still on this screen; tap again to retry.`;
    $("btnUpload").disabled = false;
  }
}

async function poll() {
  if (!state.session) return;
  try {
    const res = await apiFetch(`/api/status?session=${encodeURIComponent(state.session)}`);
    if (!res.ok) return;
    const out = await res.json();
    if (out.status === "scored") {
      clearInterval(state.pollId);
      renderScorecard(out.scorecard);
    } else if (out.status === "processed") {
      $("pollStatus").textContent = "Measured ✓ — Felix is writing the scorecard…";
    }
  } catch (_) { /* keep polling */ }
}

function renderScorecard(sc) {
  $("waitCard").classList.add("hidden");
  $("scoreCard").classList.remove("hidden");
  const v = $("scVerdict");
  v.textContent = sc.verdict === "Clear" ? "✓ Clear" : "↻ Re-drill";
  v.className = `verdict ${sc.verdict === "Clear" ? "clear" : "redrill"}`;
  const m = sc.metrics || {};
  const cell = (val, label) => `<div><span class="mv">${val}</span><span class="mk">${label}</span></div>`;
  $("scMetrics").innerHTML = [
    cell(m.duration_s != null ? `${m.duration_s}s` : "—", "Duration"),
    cell(m.wpm ?? "—", "Words / min"),
    cell(m.fillers_per_min ?? "—", "Fillers / min"),
    cell(m.repetitions_per_min ?? "—", "Phrase repeats / min"),
    cell(m.pauses_1s ?? "—", "Pauses ≥ 1s"),
    cell(m.speech_ratio != null ? `${Math.round(m.speech_ratio * 100)}%` : "—", "Speech ratio"),
  ].join("");
  $("scStrengths").innerHTML = (sc.strengths || []).map((s) => `<li>${s}</li>`).join("");
  $("scFix").textContent = sc.one_fix || "";
  $("scNext").textContent = sc.next ? `Next: ${sc.next}` : "";
}

$("btnStart").addEventListener("click", () => {
  show("screen-record");
  $("btnRec").classList.remove("hidden");
  $("btnStop").classList.add("hidden");
});
$("btnRec").addEventListener("click", () => {
  startRecording().catch((err) => {
    $("recHint").textContent = `Camera/mic unavailable: ${err.message}. Allow permission and try again.`;
  });
});
$("btnStop").addEventListener("click", stopRecording);
$("btnUpload").addEventListener("click", upload);
$("btnAgain").addEventListener("click", () => location.reload());
wireChips("paceChips", "pace");
wireChips("fillerChips", "fillers");
loadPlan().catch(() => { $("dPrompt").textContent = "Could not load today's plan — check connection and reload."; });

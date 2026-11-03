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

let planReady = false;

async function loadPlan() {
  // Validates before touching state.plan: a 401 body ({"error": ...}) must
  // never be stored as the plan, or upload() later crashes on drill.code.
  const res = await apiFetch("/api/plan");
  if (!res.ok) {
    const err = new Error(`plan request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  const plan = await res.json();
  const d = plan && plan.drill;
  if (!d || !d.code) throw new Error("plan response has no drill");
  state.plan = plan;
  $("dTrack").textContent = `${d.track} · ${d.level}`;
  $("dName").textContent = `${d.name} (${d.code})`;
  $("dPrompt").textContent = d.prompt;
  $("dTime").textContent = `${d.time_seconds}s`;
  $("dAudience").textContent = d.audience;
  $("dBar").textContent = d.bar;
  $("dFix").textContent = plan.fix_carried_forward;
  $("dConstraints").innerHTML = (d.constraints || []).map((c) => `<li>${c}</li>`).join("");
  $("dPrinciples").innerHTML = (d.principles || []).map((c) => `<li>${c}</li>`).join("");
  $("targetLabel").textContent = `Target ${fmt(d.time_seconds)} · no restarts`;
}

// Retries through the free tier's wake-up (first hit after idle can take
// ~a minute). A 401 is not retried: it means the token is missing/wrong,
// so clear it and let the next attempt prompt for it again.
async function ensurePlan() {
  const delays = [0, 3000, 10000, 20000];
  $("btnStart").disabled = true;
  for (let i = 0; i < delays.length; i++) {
    if (delays[i]) await new Promise((r) => setTimeout(r, delays[i]));
    $("dPrompt").textContent = i === 0
      ? "Loading today's plan…"
      : "Waking the mailbox — this can take a minute on the free tier…";
    try {
      await loadPlan();
      planReady = true;
      $("btnStart").disabled = false;
      $("btnStart").textContent = "Start drill";
      return true;
    } catch (err) {
      if (err.status === 401) {
        localStorage.removeItem("sc_token");
        $("dPrompt").textContent = "The mailbox didn't accept the saved token — tap “Retry loading plan” and re-enter it when asked.";
        break;
      }
    }
  }
  $("btnStart").disabled = false;
  $("btnStart").textContent = "Retry loading plan";
  if ($("dPrompt").textContent.startsWith("Waking")) {
    $("dPrompt").textContent = "Couldn't reach the mailbox — check connection and tap “Retry loading plan”.";
  }
  return false;
}

// Lets a recorded take be saved out of the page if upload keeps failing,
// so a take is never trapped in the tab.
function offerTakeDownload() {
  if (!state.blob) return "";
  const url = URL.createObjectURL(state.blob);
  const ext = state.mime.includes("mp4") ? "mp4" : "webm";
  return ` <a href="${url}" download="speak-coach-take.${ext}">Download this take as a backup</a>`;
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
  if (!state.plan || !state.plan.drill) {
    $("upHint").textContent = "Today's plan never loaded, so there's no drill to attach this take to — reconnecting…";
    if (!(await ensurePlan())) {
      $("upHint").innerHTML = `Still no plan loaded. ${offerTakeDownload()} Or reload the page and try again.`;
      return;
    }
  }
  const d = state.plan.drill;
  // Mode is what the user asked for, not the container: browsers report
  // audio-only MediaRecorder output as video/webm, which previously sent
  // audio takes down the video-analysis path and stalled the pass.
  const mode = $("videoToggle").checked ? "video" : "audio";
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
    $("upHint").innerHTML = `Upload failed — ${err.message}. Your take is still on this screen; tap again to retry.${offerTakeDownload()}`;
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

$("btnStart").addEventListener("click", async () => {
  if (!planReady) {
    if (!(await ensurePlan())) return;
  }
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
ensurePlan();

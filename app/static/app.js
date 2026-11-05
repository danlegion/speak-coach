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
    localStorage.setItem("sc_last_session", out.session);
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
    if (res.status === 404) {
      // The mailbox lost this session (a deploy wipes Render's free disk).
      // Say so instead of waiting forever; the scorecard survives on
      // Felix's side and reappears under Past scorecards after a restore.
      clearInterval(state.pollId);
      $("pollStatus").textContent = "This session is gone from the mailbox (a deploy cleared it) — your take and scorecard are safe with Felix. Reload the page and open it under Past scorecards.";
      return;
    }
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

// Stats card (main page): metrics tracked, current score, overall score,
// and per-metric trend vs the previous scored rep. "Up/down/flat" is
// judged by what is good for this speaker, not by the raw number:
// fillers, repeats and speech ratio improve going down; pauses improve
// going up; pace is good when it stays inside the conversational band.
const TRACKED = [
  { key: "duration_s", label: "Duration", fmt: (v) => `${v}s`, good: "bar", tol: 0 },
  { key: "wpm", label: "Words / min (band 120–150)", fmt: (v) => `${v}`, good: "band", tol: 0 },
  { key: "fillers_per_min", label: "Fillers / min", fmt: (v) => `${v}`, good: "down", tol: 0.5 },
  { key: "repetitions_per_min", label: "Phrase repeats / min", fmt: (v) => `${v}`, good: "down", tol: 0.5 },
  { key: "pauses_1s", label: "Pauses ≥ 1s", fmt: (v) => `${v}`, good: "up", tol: 0 },
  { key: "speech_ratio", label: "Speech ratio", fmt: (v) => `${Math.round(v * 100)}%`, good: "down", tol: 0.05 },
];

function trendFor(def, cur, prev) {
  if (cur == null || prev == null) return { arrow: "→", word: "flat", cls: "t-flat" };
  if (def.good === "band") {
    const inBand = (v) => v >= 120 && v <= 150;
    if (inBand(cur) && inBand(prev)) return { arrow: "→", word: "flat, in band", cls: "t-flat" };
    if (inBand(cur) && !inBand(prev)) return { arrow: "↑", word: "improving", cls: "t-good" };
    if (!inBand(cur) && inBand(prev)) return { arrow: "↓", word: "slipping", cls: "t-bad" };
    return { arrow: "→", word: "flat", cls: "t-flat" };
  }
  const diff = cur - prev;
  if (Math.abs(diff) <= def.tol) return { arrow: "→", word: "flat", cls: "t-flat" };
  if (def.good === "down") {
    return diff < 0 ? { arrow: "↓", word: "improving", cls: "t-good" } : { arrow: "↑", word: "slipping", cls: "t-bad" };
  }
  if (def.good === "up") {
    return diff > 0 ? { arrow: "↑", word: "improving", cls: "t-good" } : { arrow: "↓", word: "slipping", cls: "t-bad" };
  }
  return { arrow: diff > 0 ? "↑" : "↓", word: diff > 0 ? "up" : "down", cls: "t-flat" };
}

async function loadStats() {
  const curEl = $("statsCurrent"), trendEl = $("statsTrend"), ovEl = $("statsOverall");
  try {
    const res = await apiFetch("/api/sessions");
    if (!res.ok) { curEl.textContent = "Couldn't load stats yet."; return; }
    const sessions = (await res.json()).sessions || [];
    const scored = [];
    for (const s of sessions.filter((x) => x.has_scorecard)) {
      try {
        const st = await apiFetch(`/api/status?session=${encodeURIComponent(s.session)}`);
        if (!st.ok) continue;
        const out = await st.json();
        if (out.scorecard) scored.push({ session: s.session, drill: s.drill, scorecard: out.scorecard });
      } catch (_) { /* skip */ }
    }
    // Drop pipeline-test takes (their notes say synthetic) and collapse
    // mailbox-restored duplicates: same drill + same measured numbers.
    // The signature is seeded even for skipped synthetics, so a
    // synthetic's restored copy can't leak through as a "real" rep.
    const seen = new Set();
    const real = [];
    for (const s of scored.sort((a, b) => a.session.localeCompare(b.session))) {
      const sc = s.scorecard;
      const m = sc.metrics || {};
      const sig = [s.drill, m.duration_s, m.wpm, m.word_count, m.fillers_per_min].join("|");
      if (seen.has(sig)) continue;
      seen.add(sig);
      if ((sc.note || "").toLowerCase().includes("synthetic")) continue;
      real.push(s);
    }
    if (!real.length) {
      curEl.textContent = "No scored reps yet.";
      ovEl.textContent = "—";
      return;
    }
    const latest = real[real.length - 1];
    const prev = real.length > 1 ? real[real.length - 2] : null;
    const lm = latest.scorecard.metrics || {};
    const verdictCls = latest.scorecard.verdict === "Clear" ? "v-clear" : "v-bad";
    const verdictMark = latest.scorecard.verdict === "Clear" ? "✓ Clear" : "↻ Re-drill";
    curEl.innerHTML = `${latest.drill || "Drill"} · ${latest.session.slice(0, 10)} · <span class="${verdictCls}">${verdictMark}</span>`;
    let improving = 0, slipping = 0;
    // Duration has no trend: its only goal is the drill's own time bar.
    const DRILL_SECONDS = { "V-L1-1": 60, "V-L1-2": 60, "V-L2-1": 90, "V-L2-2": 90, "V-L3-1": 90, "V-L3-2": 60, "V-L4-1": 120 };
    trendEl.innerHTML = TRACKED.map((def) => {
      const cur = lm[def.key], prv = prev ? (prev.scorecard.metrics || {})[def.key] : null;
      const was = prv != null ? `was ${def.fmt(prv)} · ` : "";
      if (def.good === "bar") {
        const target = DRILL_SECONDS[latest.drill];
        const bar = target == null ? "no time bar"
          : cur >= target ? `✓ ${target}s bar met` : `✗ ${target}s bar missed`;
        const cls = target == null ? "t-flat" : cur >= target ? "t-good" : "t-bad";
        const cell = target == null ? "" : cur >= target ? "cell-good" : "cell-bad";
        return `<div class="scorerow ${cell}"><div class="sr-top"><span class="sr-label">${def.label}</span><span class="sr-value">${cur != null ? def.fmt(cur) : "—"}</span></div><div class="sr-trend ${cls}">${was}${bar}</div></div>`;
      }
      const t = trendFor(def, cur, prv);
      if (["wpm", "fillers_per_min", "repetitions_per_min", "pauses_1s"].includes(def.key)) {
        if (t.word === "improving") improving++;
        if (t.word === "slipping") slipping++;
      }
      const cell = def.good === "band"
        ? (cur != null && cur >= 120 && cur <= 150 ? "cell-good" : "cell-bad")
        : t.word === "improving" ? "cell-good" : t.word === "slipping" ? "cell-bad" : "";
      return `<div class="scorerow ${cell}"><div class="sr-top"><span class="sr-label">${def.label}</span><span class="sr-value">${cur != null ? def.fmt(cur) : "—"}</span></div><div class="sr-trend ${t.cls}">${was}${t.arrow} ${t.word}</div></div>`;
    }).join("");
    const clears = real.filter((s) => s.scorecard.verdict === "Clear").length;
    // Overall 0–100: half the current level's gate progress, half the
    // latest rep's bar attainment. Bars use the nearest defined goals:
    // duration = the drill's time bar, WPM = the 120–150 band, fillers =
    // under 8/min (L2 bar), pauses = 3+ (L3 count bar). Phrase repeats
    // have no numeric bar yet, so they count as trend only, never in
    // the number. The number measures your current level, not your
    // career total — it resets when a new level starts.
    const levelMatch = (latest.drill || "").match(/V-L(\d)-/);
    const level = levelMatch ? levelMatch[1] : "1";
    const levelClears = real.filter((s) => s.scorecard.verdict === "Clear" && (s.drill || "").startsWith(`V-L${level}-`)).length;
    const gatePct = Math.round((levelClears / 3) * 100);
    const bars = [];
    const target = DRILL_SECONDS[latest.drill];
    if (target != null && lm.duration_s != null) bars.push(lm.duration_s >= target ? 100 : 0);
    if (lm.wpm != null) bars.push(lm.wpm >= 120 && lm.wpm <= 150 ? 100 : 0);
    if (lm.fillers_per_min != null) bars.push(lm.fillers_per_min < 8 ? 100 : 0);
    if (lm.pauses_1s != null) bars.push(lm.pauses_1s >= 3 ? 100 : 0);
    const barsMet = bars.filter((b) => b === 100).length;
    const repPct = bars.length ? Math.round(bars.reduce((a, b) => a + b, 0) / bars.length) : gatePct;
    const overall = Math.round((gatePct + repPct) / 2);
    const overallTrend = real.length < 2 ? "need more reps for a trend"
      : improving > slipping ? "improving" : slipping > improving ? "slipping" : "flat";
    const band = overall >= 80 ? "good" : overall >= 50 ? "mid" : "bad";
    ovEl.innerHTML = `<div class="overall-num ${band}">${overall}<span class="overall-max">/100</span></div>`
      + `<div class="overall-bar"><div class="overall-fill ${band}" style="width:${overall}%"></div></div>`
      + `<div class="sub">Voice L${level} · ${clears}/${real.length} reps Clear · ½ gate (${gatePct}: ${levelClears}/3 Clears) + ½ latest rep bars (${repPct}: ${barsMet}/${bars.length} met) · Trend: ${overallTrend}</div>`;
    $("statsNote").textContent = "Test takes excluded. Duration shows the drill's time bar, not a trend; pace is judged against the 120–150 band.";
  } catch (_) {
    curEl.textContent = "Couldn't load stats yet.";
  }
}

// Past scorecards: survives reloads, unlike the in-memory session id.
async function loadPast() {
  const list = $("pastList");
  try {
    const res = await apiFetch("/api/sessions");
    if (!res.ok) { list.textContent = "Couldn't load past scorecards yet."; return; }
    const sessions = (await res.json()).sessions || [];
    const scored = sessions.filter((s) => s.has_scorecard);
    if (!scored.length) { list.textContent = "No scorecards yet — your first one lands here."; return; }
    list.innerHTML = "";
    for (const s of scored.reverse()) {
      const btn = document.createElement("button");
      btn.textContent = `${s.drill || "Drill"} · ${s.session.slice(0, 10)} · loading…`;
      btn.addEventListener("click", async () => {
        state.session = s.session;
        localStorage.setItem("sc_last_session", s.session);
        show("screen-done");
        $("waitCard").classList.remove("hidden");
        $("scoreCard").classList.add("hidden");
        $("pollStatus").textContent = "Loading scorecard…";
        await poll();
      });
      list.appendChild(btn);
      try {
        const st = await apiFetch(`/api/status?session=${encodeURIComponent(s.session)}`);
        if (st.ok) {
          const out = await st.json();
          if (out.scorecard) {
            const cls = out.scorecard.verdict === "Clear" ? "v-clear" : "v-bad";
            const mark = out.scorecard.verdict === "Clear" ? "✓ Clear" : "↻ Re-drill";
            btn.innerHTML = `${s.drill || "Drill"} · ${s.session.slice(0, 10)} · <span class="${cls}">${mark}</span>`;
          }
        }
      } catch (_) { /* leave the loading label */ }
    }
  } catch (_) {
    list.textContent = "Couldn't load past scorecards yet.";
  }
}

function renderScorecard(sc) {
  $("waitCard").classList.add("hidden");
  $("scoreCard").classList.remove("hidden");
  const v = $("scVerdict");
  v.textContent = sc.verdict === "Clear" ? "✓ Clear" : "↻ Re-drill";
  v.className = `verdict ${sc.verdict === "Clear" ? "clear" : "redrill"}`;
  $("scoreCard").classList.toggle("card-clear", sc.verdict === "Clear");
  $("scoreCard").classList.toggle("card-redrill", sc.verdict !== "Clear");
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
ensurePlan().then((ok) => { if (ok) { loadPast(); loadStats(); } });

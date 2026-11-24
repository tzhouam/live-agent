const $ = (id) => document.getElementById(id);
const canvas = $("screen"), g = canvas.getContext("2d");
let ws = null, audioCtx = null, playhead = 0, queue = [], pending = null, recorder = null, epoch = 0, decoding = [];
let lastUtterT = null, verified = 0, repairs = 0, pingTimer = null;
let connectionAttempt = 0, sessionState = "disconnected", sessionStatus = null, pingTimeouts = [], startupTimer = null;
let latestAttention = null;
let latestInputRequestId = null;
let errorLanguage = null;
// The custom browser avatar is an opt-in preview. Video remains decoded for immediate fallback.
const TEACHER_AVATAR_MODEL = "teacher-mesh-v1", TEACHER_AVATAR_URL = "/assets/teacher-mesh/rig-v7.json";
let teacherAvatar = null, avatarNegotiated = false, avatarEpoch = null, avatarDisabled = false;
let avatarLastTime = null, avatarMouthOpen = 0, avatarMouthRound = 0;
let avatarMotionBase = 0, avatarMotionStart = 0;
let avatarCaptureAt = -Infinity, avatarCaptureCounts = new Map();
let avatarLastState = null;
function avatarRequested() {
  try { return new URL(window.location.href, "http://localhost/").searchParams.get("avatar") === "mesh"; }
  catch (_) { return false; }
}
async function loadTeacherAvatar() { return (await import("/assets/avatar-renderer.js")).createTeacherAvatar; }
function avatarActive() { return avatarNegotiated && !avatarDisabled && teacherAvatar?.active === true; }
function avatarPresentation(q) {
  if (!avatarNegotiated && !q?.meta.avatar) return {};
  return {renderer: avatarActive() ? "mesh" : "video", ...(avatarActive() ? {model: TEACHER_AVATAR_MODEL} : {}),
    epoch: q?.meta.avatar?.epoch ?? avatarEpoch};
}
function resetTeacherAvatar() {
  avatarLastTime = null; avatarMouthOpen = avatarMouthRound = 0;
  avatarMotionBase = 0; avatarMotionStart = audioCtx?.currentTime || 0;
  avatarCaptureAt = -Infinity; avatarCaptureCounts.clear();
  avatarLastState = null;
  try { teacherAvatar?.reset(); } catch (error) { fallbackTeacherAvatar(error); }
}
function destroyTeacherAvatar() {
  teacherAvatar?.destroy(); teacherAvatar = null; avatarNegotiated = false; avatarEpoch = null;
  avatarDisabled = false; canvas.style.visibility = "visible";
  $("screenWrap").dataset.renderer = "video";
}
function fallbackTeacherAvatar(reason) {
  if (avatarDisabled && !teacherAvatar) return;
  const wasNegotiated = avatarNegotiated;
  const previous = teacherAvatar; teacherAvatar = null; avatarDisabled = true; previous?.destroy();
  avatarLastTime = null; avatarMouthOpen = avatarMouthRound = 0; avatarLastState = null;
  canvas.style.visibility = "visible"; $("screenWrap").dataset.renderer = "video";
  if (wasNegotiated) send({type: "avatar_renderer", renderer: "video", epoch: avatarEpoch});
  if (sessionStatus) renderBadges(sessionStatus);
  if (reason) console.warn("Teacher avatar unavailable; using video", reason);
}
async function prepareTeacherAvatar(attempt) {
  if (!avatarRequested()) return;
  try {
    const create = await loadTeacherAvatar();
    if (attempt !== connectionAttempt || sessionState !== "connecting") return;
    const avatar = await create({container: $("screenWrap"), fallbackCanvas: canvas, modelUrl: TEACHER_AVATAR_URL,
      onFallback: reason => { if (attempt === connectionAttempt) fallbackTeacherAvatar(reason); }});
    if (attempt !== connectionAttempt || sessionState !== "connecting") { avatar.destroy(); return; }
    if (avatarDisabled || !avatar.active || avatar.model !== TEACHER_AVATAR_MODEL) { avatar.destroy(); return; }
    teacherAvatar = avatar;
    teacherAvatar.render({gesture: "idle", requestTime: 0, duration: 1, motionTime: 0, mouthOpen: 0, mouthRound: 0});
  } catch (error) { if (attempt === connectionAttempt) fallbackTeacherAvatar(error); }
}
const submissionNamespace = window.crypto?.randomUUID?.() || Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
let submissionSequence = 0;
const EXAMPLES = ["请给我讲一道例题", "这一步我还没明白", "给我一道练习题", "请讲慢一点"];
const ENGLISH = {
  "board.figureEnlarge": "Enlarge diagram", "board.figureTitle": "Lesson diagram", "board.figureClose": "Close diagram",
  "board.figurePrevious": "Previous", "board.figureNext": "Next", "board.figureBrowse": "View diagrams",
  "board.figureCount": "Diagram {current} of {total}",
  "session.connecting": "Connecting…", "session.starting": "Preparing your tutor…",
  "session.ready": "Tutor ready", "session.ended": "Session ended. You can start again.",
  "session.closed": "Disconnected", "session.connectFailed": "We could not connect to your tutor. Please try again.",
  "session.failed": "Your session stopped. Please reconnect to continue.",
  "session.audioUnavailable": "Audio is unavailable in this browser. Please use a browser with audio support.",
  "session.protocolError": "The tutor connection could not be read. Please reconnect.",
  "session.started": "Your tutoring session has started.", "session.notReady": "Please wait until your tutor is ready.",
  "session.startTimeout": "Your tutor is taking longer than expected. Please try connecting again.",
  "session.sendFailed": "Your message was not sent. Please reconnect and try again.",
  "input.voiceEmpty": "No speech was recognized. Try speaking again or type your question.",
  "input.voiceFailed": "Your voice could not be recognized. Try again or type your question.",
  "input.responseFailed": "Your tutor could not prepare a response. Please send your question again.",
  "voice.hold": "Hold to speak", "voice.release": "Release to send", "voice.permission": "Waiting for microphone permission…",
  "voice.unavailable": "Voice input is unavailable here. You can type your question instead.",
  "voice.disabled": "Voice recognition is unavailable in this session. Please type your question.",
  "voice.denied": "Microphone permission was declined. Allow it in your browser, or type your question.",
  "voice.missing": "No microphone was found. Connect a microphone or type your question.",
  "voice.busy": "The microphone is being used elsewhere. You can type your question instead.",
  "voice.failed": "We could not record your voice. You can type your question instead.",
  "camera.on": "Enable focus check", "camera.off": "Stop focus check", "camera.permission": "Waiting for camera permission…",
  "camera.disabled": "Focus check is off", "camera.enabled": "Focus check is on. Images are analyzed without being saved.",
  "camera.denied": "Camera permission was declined. You can continue without a camera.",
  "camera.missing": "No camera was found. You can continue without a camera.",
  "camera.busy": "The camera is being used elsewhere. You can continue without it.",
  "camera.failed": "We could not use the camera. You can continue without it.",
  "board.title": "Lesson board", "board.ask": "Ask a question: your tutor explains it on the board.",
  "board.sentence": "Sentence ", "board.sentenceSuffix": "", "idle": "Ready when you are",
  "board.lesson": "Choose a topic to start a lesson.", "profile.none": "This session does not use a learner profile.",
  "profile.learner": "Learner", "profile.gradeMissing": "Grade not set", "profile.noExams": "No exam results yet",
  "profile.mastery": "Concept mastery (uncalibrated estimates; evidence shown below)",
  "profile.examWeak": "Areas to revisit: ", "profile.estimated": "Uncalibrated estimate",
  "profile.source.exercise": "Based on recorded practice", "profile.source.exam": "Inferred from exam errors",
  "profile.source.none": "No recorded evidence", "profile.attempts": "Recorded practice: ", "profile.correct": " correct",
  "profile.level.mastered": "Mastered", "profile.level.partial": "Partly understood", "profile.level.weak": "Needs work", "profile.level.unknown": "Not assessed",
  "badge.generator": "Video", "badge.mock": "Mock video (CPU preview)", "badge.puppet": "Puppet video (skeleton rig, CPU)",
  "badge.director": "Director", "badge.mesh": "Custom VTuber (browser mesh)",
  "badge.openLoop": "A1 open loop", "badge.online": "A2 online director", "badge.responder": "Responder",
  "badge.rules": "Rules (preview)", "badge.judge": "Judging", "badge.mockJudge": "Simulated judging (preview)",
  "badge.none": "None", "badge.speech": "Input", "badge.voice": "Voice enabled", "badge.text": "Text only",
  "state.listening": "Listening", "state.deciding": "Preparing a response", "state.erasure": "Deletion in progress (generation paused)",
  "status.open": "In progress", "status.complied": "Verified complete", "status.failed": "Failed", "status.refused": "Declined / fallback",
  "status.withdrawn": "Withdrawn", "status.capacity_skipped": "Capacity skip", "status.presented": "Presented (not assessed)",
  "kind.action": "Action", "kind.multistep": "Multiple steps", "kind.content": "Content", "kind.memory": "Memory", "kind.chat": "Conversation",
  "state.steps": "Steps ", "state.revisions": "Corrections ", "state.requests": "Requests ",
  "memory.recalled": "Recalled: ", "memory.erased": "This page’s conversation and memory records have been cleared as requested.",
  "attention.label": "Focus check: ", "attention.focused": "Focused", "attention.distracted": "Distracted",
  "attention.absent": "Outside the camera view", "attention.unknown": "Unclear", "attention.off": "Off",
  "attention.confirming": " · confirming", "attention.checking": "Focus check: analysing…",
  "av.reportOutput": "Reported audio output delay ≈ ", "av.reportRefresh": " ms; display refresh ≈ ", "av.reportCompensated": " ms (automatically compensated)",
  "profile.noConcepts": "Concept records appear after practice.", "exercise.unsure": "I’m not sure",
  "profile.edit": "Edit ↗", "profile.viewAll": "See all records ↗",
  "exercise.choose": "Choose ", "caption.label": "Tutor", "device.changed": "Your audio device changed. Use audio/video sync if the picture and sound no longer match.",
  "event.forget": " · Delete “{term}”", "event.retry": " · Retry #{request}", "event.withCorrections": " · With corrections",
  "event.repeat": "(repeat the original instruction)", "event.done": "Done.", "event.afterVerification": "(after verification)",
  "event.superseded": "Replaced by a newer instruction", "event.narrationRemoved": "Removed unverified completion wording: “{text}”",
  "event.erasureComplete": "Deleted {count} records (including derived content, logs and generator state)",
  "event.erasurePending": "Deletion incomplete: generation paused while processing", "event.complete": "Complete",
  "event.incomplete": "Incomplete (safely paused)", "event.playbackStopped": "Playback stopped; unpresented content discarded",
  "event.outline": "Lesson outline: {title} ({count} sections)",
  "event.section": "Section {index} prepared: {title} ({lines} sentences, {points} board points)",
  "event.sectionFailed": "Section {index} generation failed{next}", "event.skipped": "; skipped", "event.retrying": "; retrying",
  "event.outlineFailed": "Lesson outline generation failed", "event.planned": "Whole lesson prepared: {title}",
  "event.figureJudgement": "Figure assessment “{title}”: ",
  "event.figurePoint": "Point {index}, complexity {complexity} {decision}{reason}",
  "event.figureNeeded": "→ figure", "event.figureNotNeeded": "→ no figure",
  "event.figure": "Figure for point {index} prepared ({kind})", "event.plot": "Plotted figure", "event.illustration": "Illustration", "event.diagram": "Teaching diagram",
  "event.figureFailed": "Figure generation failed: {error}", "event.exercise": "Practice ({concept}): {text}",
  "event.exerciseFailed": "Practice generation failed: {error}",
  "event.exerciseTimeout": "No answer for practice “{concept}”; the tutor will explain and continue",
  "event.gradingFailed": "Grading failed: {error}", "event.profileUpdated": "Learner profile updated ({changed})",
  "event.depth.review": "Review", "event.depth.core": "Core", "event.depth.new": "New material", "event.withPractice": "+practice",
  "event.sectionPractice": "Practice after this section: {text}", "event.unsure": "Not sure",
  "event.correct": "Correct", "event.incorrect": "Incorrect", "event.mastery": " · Estimated mastery {before} → {after}",
  "event.anchorsRemoved": "Absent from the first shot: {anchors} (removed from the prompt)", "event.correctedTarget": " · Correction → #{target}",
};
function tr(key, fallback) {
  const product = window.LiveAgentProduct;
  const value = product?.edition === "university" ? (ENGLISH[key] ?? fallback) : fallback;
  return product?.t?.(key, value) ?? value;
}
function diagnostic(key, fallback, values = {}) {
  return tr(`event.${key}`, fallback).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? ""));
}
function productEvent(name, detail) {
  if (name === "submitted") latestInputRequestId = detail.request_id ?? null;
  window.dispatchEvent(new CustomEvent(`live-agent:${name}`, {detail}));
}
function nextSubmissionId() { return `client:${submissionNamespace}:${(++submissionSequence).toString(36)}`; }
function acceptsActivity(requestId) { return window.LiveAgentProduct?.acceptsActivity?.(requestId) !== false; }
function activeSocket(socket, attempt) { return socket === ws && attempt === connectionAttempt; }
function ready() { return sessionState === "ready" && ws?.readyState === 1; }
function idleExamples() { return window.LiveAgentProduct?.examples?.() || personaChips || EXAMPLES; }
const STATUS = {open: "进行中", complied: "已验证完成", failed: "失败", refused: "拒绝/降级", withdrawn: "已撤回",
                capacity_skipped: "容量跳过", presented: "已呈现（未判定）"};
const KIND = {action: "动作", multistep: "多步动作", content: "内容", memory: "记忆", chat: "闲聊"};

function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function send(o, socket = ws) {
  if (!socket || socket !== ws || socket.readyState !== 1) return false;
  try { socket.send(JSON.stringify(o)); return true; }
  catch (e) { console.warn("WebSocket send failed", e); return false; }
}
function setConn(s, live) { const el = $("conn"); el.textContent = s; el.className = "badge" + (live ? " live" : ""); }
function sessionChanged(state, detail = {}) {
  sessionState = state;
  errorLanguage = state === "error" ? (window.LiveAgentProduct?.edition === "university" ? "en" : "zh") : null;
  const live = state === "ready", busy = state === "connecting" || live;
  $("connect").disabled = busy; $("disconnect").disabled = !busy;
  ["text", "send"].forEach(id => $(id).disabled = !live);
  $("talk").disabled = !live || !sessionStatus?.asr || micUploading;
  $("cam").disabled = !live || !sessionStatus?.attention || camPending;
  ["mode", "uid", "sid"].forEach(id => { if ($(id)) $(id).disabled = busy; });
  document.querySelectorAll("#chips .chip").forEach(button => button.disabled = !live);
  const failure = $("connectionError");
  if (failure) {
    failure.hidden = state !== "error";
    const message = failure.querySelector("#connectionErrorText") || failure;
    message.textContent = state === "error" ? detail.message || "" : "";
  }
  window.LiveAgentProduct?.sessionChanged?.(state, {...detail, status: sessionStatus});
}
function notice(key, fallback, error) {
  if (error) feed(null, "bad", "Browser", error.message || String(error));
  chat("sys", tr(key, fallback));
}
function clearEmpty(el) { const e = el.querySelector(".empty"); if (e) e.remove(); }

function chat(kind, text) {
  const el = $("chat"); clearEmpty(el);
  const d = document.createElement("div"); d.className = "msg " + kind; d.textContent = text;
  el.appendChild(d); el.scrollTop = el.scrollHeight;
}
function feed(t, cls, what, detail) {
  const el = $("feed"); clearEmpty(el);
  const d = document.createElement("div"); d.className = "ev " + (cls || "");
  const labels = {"理解": "Interpretation", "锁定": "Locked", "动作质检": "Action check", "语音质检": "Speech check",
    "前向修正": "Forward correction", "完成声明": "Completion claim", "拒绝/降级": "Declined / fallback", "容量跳过": "Capacity skip",
    "叙述守卫": "Narration guard", "删除": "Deletion", "打断": "Interrupted", "审核": "Audit", "错误": "Error",
    "备课": "Lesson preparation", "因材施教": "Adapted lesson", "教案": "Lesson plan", "练习": "Practice", "批改": "Grading",
    "提醒学生": "Focus reminder", "场景锚定": "Scene anchors", "场景连续性": "Scene continuity", "未通过": "Not passed", "无法判定": "Unclear", "通过": "Passed"};
  if (window.LiveAgentProduct?.edition === "university") {
    for (const label of Object.keys(labels).sort((a, b) => b.length - a.length)) what = String(what).replaceAll(label, labels[label]);
  }
  d.innerHTML = `<span class="t">${t != null ? t.toFixed(1) : ""}</span><span><span class="what">${esc(what)}</span>${esc(detail || "")}</span>`;
  el.appendChild(d); while (el.children.length > 200) el.firstChild.remove(); el.scrollTop = el.scrollHeight;
}
function memo(text, cls) {
  const el = $("memory"); clearEmpty(el);
  const d = document.createElement("div"); d.className = "ev " + (cls || "");
  d.innerHTML = `<span class="t"></span><span>${esc(text)}</span>`;
  el.appendChild(d); el.scrollTop = el.scrollHeight;
}

function setChips(list, enabled) {  // one-click examples; the server sends the persona's own in "status"
  const container = $("chips"), active = document.activeElement;
  const focused = active && container.contains(active) && active.classList.contains("chip") ? active.dataset.prompt : null;
  container.innerHTML = "";
  let replacement = null;
  list.forEach(x => {
    const b = document.createElement("button"); b.className = "chip";
    b.textContent = typeof x === "object" ? x.label : x; b.disabled = !enabled;
    b.dataset.prompt = typeof x === "object" ? x.text : x;
    if (typeof x === "object" && x.description) b.setAttribute("aria-label", x.description);
    b.onclick = () => sendText(typeof x === "object" ? x.text : x); $("chips").appendChild(b);
    if (focused != null && b.dataset.prompt === focused) replacement = b;
  });
  if (focused != null && enabled) (replacement || $("text")).focus({preventScroll: true});
}
setChips(window.LiveAgentProduct?.examples?.() || EXAMPLES, false);

// ---------------------------------------------------------------- connection
function clearStartupTimer() { clearTimeout(startupTimer); startupTimer = null; }
function finishSession(socket, attempt, state, message) {
  if (!activeSocket(socket, attempt)) return;
  ws = null; connectionAttempt++;
  clearStartupTimer();
  clearInterval(pingTimer); pingTimer = null;
  pingTimeouts.forEach(clearTimeout); pingTimeouts = [];
  cancelSpeech(); camOff(false); stopAll(); destroyTeacherAvatar(); clearBoardFigures();
  currentExercise = null; exerciseKey = ""; setChips(idleExamples(), false);
  sessionStatus = null;
  setConn(tr("session.closed", "连接已关闭"));
  $("overlay").style.display = "flex"; $("overlay").textContent = message;
  sessionChanged(state, {message});
}
function resetSessionView() {
  latestInputRequestId = null;
  stopAll(); destroyTeacherAvatar(); clearBoardFigures();
  g.clearRect(0, 0, canvas.width, canvas.height);
  ["chat", "feed", "memory", "chains"].forEach(id => $(id).innerHTML = "");
  $("flags").textContent = "";
  ["sLambda", "sReq", "sRtt", "sLatency"].forEach(id => $(id).textContent = "–");
  verified = repairs = 0; lastUtterT = null; lastGraded = null; exerciseKey = ""; currentExercise = null;
  $("sVerified").textContent = "0"; $("sRepairs").textContent = "0";
  personaChips = EXAMPLES; setChips(idleExamples(), false); showProfile(null);
  shownBoard = null; lastBoard = null; onScreen = null;
  $("board").classList.remove("on"); $("boardTitle").textContent = ""; $("boardItems").innerHTML = "";
  $("boardImg").removeAttribute("src"); $("boardCap").textContent = "";
  delete $("board").dataset.key;
  delete $("board").dataset.content;
}
$("connect").onclick = async () => {
  if (sessionState === "connecting" || sessionState === "ready") return;
  const attempt = ++connectionAttempt;
  const student = $("student") || $("sid");
  const mode = $("mode").value === "public" ? "public" : "private";
  const hello = {type: "hello", mode, user_id: mode === "public" ? "public-preview" : $("uid").value};
  if (mode === "private") hello.student = student.value.trim();
  sessionStatus = null;
  resetSessionView();
  sessionChanged("connecting");
  setConn(tr("session.connecting", "连接中…"));
  $("overlay").style.display = "flex"; $("overlay").textContent = tr("session.starting", "正在准备老师…");
  startupTimer = setTimeout(() => {
    if (attempt !== connectionAttempt || sessionState !== "connecting") return;
    const message = tr("session.startTimeout", "老师准备的时间有点长，请重新连接试试。");
    const socket = ws;
    if (socket) { finishSession(socket, attempt, "error", message); socket.close(); }
    else {
      connectionAttempt++; clearStartupTimer(); destroyTeacherAvatar();
      setConn(tr("session.closed", "连接已关闭")); $("overlay").textContent = message;
      sessionChanged("error", {message});
    }
  }, 30000);
  try {
    if (!audioCtx || audioCtx.state === "closed") {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) throw new Error("AudioContext unavailable");
      audioCtx = new Audio(); master = null;
    }
    await audioCtx.resume();
  } catch (error) {
    if (attempt !== connectionAttempt) return;
    clearStartupTimer();
    const message = tr("session.audioUnavailable", "浏览器暂时无法播放声音，请使用支持音频的浏览器后重试。");
    feed(null, "bad", "AudioContext", error.message);
    setConn(tr("session.closed", "连接已关闭"));
    $("overlay").textContent = message; sessionChanged("error", {message});
    return;
  }
  if (attempt !== connectionAttempt || sessionState !== "connecting") return;
  await prepareTeacherAvatar(attempt);
  if (attempt !== connectionAttempt || sessionState !== "connecting") return;
  let socket;
  try { socket = new WebSocket(window.LiveAgentAPI.websocketUrl()); }
  catch (error) {
    clearStartupTimer();
    const message = tr("session.connectFailed", "暂时连接不上老师，请重试。");
    feed(null, "bad", "WebSocket", error.message); $("overlay").textContent = message; destroyTeacherAvatar();
    setConn(tr("session.closed", "连接已关闭")); sessionChanged("error", {message}); return;
  }
  ws = socket; socket.binaryType = "arraybuffer";
  socket.onopen = async () => {
    // H.264 segments need ~1/6 of the bandwidth of per-frame JPEG (a remote bridge cannot carry JPEG in real time)
    const video_codecs = (await h264Supported()) ? ["h264"] : [];
    if (!activeSocket(socket, attempt) || socket.readyState !== 1) return;
    const avatarHello = teacherAvatar?.active && !avatarDisabled
      ? {renderer: "mesh", avatar_model: TEACHER_AVATAR_MODEL, avatar_video_frames: true} : {};
    if (!send({...hello, video_codecs, ...avatarHello}, socket)) {
      finishSession(socket, attempt, "error", tr("session.connectFailed", "暂时连接不上老师，请重试。"));
      socket.close(); return;
    }
    const ping = () => activeSocket(socket, attempt) && send({type: "ping", t: performance.now()}, socket);
    ping(); pingTimeouts = [setTimeout(ping, 300), setTimeout(ping, 600)]; pingTimer = setInterval(ping, 3000);
  };
  socket.onclose = event => {
    if (!activeSocket(socket, attempt)) return;
    const starting = sessionState === "connecting";
    const state = starting || event?.wasClean === false || (event?.code && event.code !== 1000) ? "error" : "disconnected";
    finishSession(socket, attempt, state, state === "error"
      ? (starting ? tr("session.connectFailed", "暂时连接不上老师，请重试。") : tr("session.failed", "会话暂时中断了，请重新连接后继续。"))
      : tr("session.ended", "会话已结束，可以重新开始。"));
  };
  socket.onerror = () => {
    finishSession(socket, attempt, "error", tr("session.connectFailed", "暂时连接不上老师，请重试。"));
    socket.close();
  };
  socket.onmessage = ev => onMessage(ev, socket, attempt);
  startRender();
};
$("disconnect").onclick = () => {
  const socket = ws;
  if (socket) {
    finishSession(socket, connectionAttempt, "disconnected", tr("session.ended", "会话已结束，可以重新开始。"));
    socket.close();
  } else if (sessionState === "connecting") {
    connectionAttempt++; clearStartupTimer(); stopAll(); destroyTeacherAvatar(); sessionChanged("disconnected");
    setConn(tr("session.closed", "连接已关闭")); $("overlay").textContent = tr("session.ended", "会话已结束，可以重新开始。");
  }
};

async function onMessage(ev, socket = ws, attempt = connectionAttempt) {
  if (!activeSocket(socket, attempt)) return;
  if (typeof ev.data === "string") {
    let m;
    try {
      m = JSON.parse(ev.data);
      if (!m || typeof m !== "object" || Array.isArray(m) || typeof m.type !== "string") throw new Error("Invalid message envelope");
    }
    catch (error) {
      feed(null, "bad", "Protocol", error.message);
      finishSession(socket, attempt, "error", tr("session.protocolError", "暂时无法读取老师的回应，请重新连接。")); socket.close(); return;
    }
    if (m.type === "chunk") { pending = {meta: m, frames: [], pcm: null, epoch}; }
    else if (m.type === "stop") {
      if (Number.isInteger(m.epoch)) avatarEpoch = m.epoch;
      stopAll();
    }
    else if (m.type === "event") { onEvent(m); }
    else if (m.type === "state") { onState(m); }
    else if (m.type === "transcript") {
      if (m.text && (m.request_id == null || m.request_id === latestInputRequestId)) chat("user", "🎙 " + m.text);
    }
    else if (m.type === "input_error") {
      if (m.superseded || (m.request_id ?? null) !== latestInputRequestId) return;
      const messages = {
        voice_empty: ["input.voiceEmpty", "没有识别到语音，请再说一次，或输入问题。"],
        voice_failed: ["input.voiceFailed", "这次语音暂时识别失败，请重试或输入问题。"],
        response_failed: ["input.responseFailed", "老师这次暂时没能准备好回答，请重新发送问题。"],
      };
      const [key, fallback] = messages[m.code] || messages.response_failed;
      notice(key, fallback);
      productEvent("input-error", m);
    }
    else if (m.type === "status") { onStatus(m); }
    else if (m.type === "profile") { showProfile(m.profile, lastGraded); }
    else if (m.type === "error") {
      feed(null, "bad", "错误", m.error);
      finishSession(socket, attempt, "error", tr("session.failed", "会话暂时中断了，请重新连接后继续。")); socket.close();
    }
    else if (m.type === "pong") {
      const rtt = performance.now() - m.t;
      send({type: "clock", t_client: m.t, t_server: m.ts, rtt});
      $("sRtt").textContent = rtt.toFixed(0);
    }
    return;
  }
  if (!pending) return;
  const h264 = pending.meta.codec === "h264";
  if (h264 && !pending.video) {
    pending.video = decodeH264(ev.data, pending.meta);  // one Annex-B segment: all of the chunk's frames
    pending.video.catch(() => {});  // handled when the chunk completes (below)
  } else if (!h264 && pending.frames.length < (pending.meta.video_frames ?? pending.meta.n_frames)) {
    pending.frames.push(createImageBitmap(new Blob([ev.data], {type: "image/jpeg"})));
  } else {
    pending.pcm = new Int16Array(ev.data);
    const c = pending; pending = null;
    const video = h264 ? c.video : decodeJpegFrames(c.frames);
    c.frames = [];
    if (currentChunk(c, socket, attempt)) decoding.push(c);  // preserve PCM arrival order
    const completed = finishChunkDecode(c, video, socket, attempt);
    if (avatarActive() && currentChunk(c, socket, attempt)) {
      // Browser speech and mesh motion need PCM, not the hidden fallback video.
      makeChunkReady(c);
    } else await completed;  // video clients still start with a fully decoded picture
  }
}

function currentChunk(c, socket, attempt) {
  return activeSocket(socket, attempt) && c.epoch === epoch &&
    !(avatarNegotiated && c.meta.avatar && c.meta.avatar.epoch !== avatarEpoch);
}
async function decodeJpegFrames(promises) {
  const frames = await Promise.allSettled(promises);
  const failed = frames.find(frame => frame.status === "rejected");
  if (failed) {
    frames.forEach(frame => { if (frame.status === "fulfilled") frame.value.close?.(); });
    throw failed.reason;
  }
  return frames.map(frame => frame.value);
}
function makeChunkReady(c) {
  if (c.decoded) return;
  c.decoded = true;
  // For mesh, receipt means PCM is available; video clients include decode time.
  send({type: "chunk_received", request: c.meta.request, chunk: c.meta.chunk, tp: performance.now(), ...avatarPresentation(c)});
  while (decoding.length && decoding[0].decoded) {
    const head = decoding.shift();
    if (head.epoch === epoch) head.queued = schedule(head);
  }
}
async function finishChunkDecode(c, video, socket, attempt) {
  let frames;
  try { frames = await video; }
  catch (error) {
    console.warn("Video decode failed, falling back to JPEG", error);
    if (currentChunk(c, socket, attempt)) send({type: "video_codec", codec: "jpeg"}, socket);
    frames = [];
  }
  if (!currentChunk(c, socket, attempt) || c.queued?.retired) {
    frames.forEach(frame => frame.close?.()); return;
  }
  c.frames = frames;
  if (c.queued) c.queued.frames = frames;  // schedule() returns a separate playback object
  else makeChunkReady(c);
}

function renderBadges(m) {
  const b = $("badges"); b.querySelectorAll(".badge:not(#conn)").forEach(x => x.remove());
  const items = [
    [tr("badge.generator", "生成"), avatarActive() ? tr("badge.mesh", "定制 VTuber（浏览器网格动画）") : m.generator === "mock" ? tr("badge.mock", "占位视频（CPU 演示）")
      : m.generator === "puppet" ? tr("badge.puppet", "木偶视频（骨架动画，CPU）") : m.generator],
    [tr("badge.director", "导演"), m.director === "open_loop" ? tr("badge.openLoop", "A1 开环") : tr("badge.online", "A2 在线导演")],
    [tr("badge.responder", "应答"), m.responder === "rules" ? tr("badge.rules", "规则（演示）") : m.responder],
    [tr("badge.judge", "质检"), {mock: tr("badge.mockJudge", "模拟判定（演示）"), vlm: "VLM", none: tr("badge.none", "无")}[m.judge] || m.judge],
    [tr("badge.speech", "输入"), m.asr ? tr("badge.voice", "语音已启用") : tr("badge.text", "仅文字")],
  ];
  for (const [k, v] of items) {
    const s = document.createElement("span"); s.className = "badge"; s.textContent = `${k}: ${v}`; b.appendChild(s);
  }
}
function boardSentenceLabel(k, n) {
  return tr("board.sentence", "第 ") + k + "/" + n + tr("board.sentenceSuffix", " 句");
}
function renderFocusLabel() {
  const d = latestAttention;
  if (d && d.state !== "off") {
    const st = d.stable || d.state;
    const names = {focused: "专注", distracted: "走神", absent: "不在画面", unknown: "无法判断"};
    $("focus").className = "focusline " + (st || "");
    const confirming = d.state !== "unknown" && d.state !== st;
    const observed = confirming ? d.state : st;
    $("focus").textContent = tr("attention.label", "专注检测：") + tr(`attention.${observed}`, names[observed] || observed)
      + (confirming || !d.stable && d.state !== "unknown" ? tr("attention.confirming", " · 确认中") : "")
      + (d.reason ? ` (${d.reason})` : "");
  } else {
    $("focus").className = "focusline";
    $("focus").textContent = camStream && !d ? tr("attention.checking", "专注检测：正在分析…") : tr("camera.disabled", "专注检测未开启");
  }
  $("focusLive").className = $("focus").className + " focus-live";
  $("focusLive").textContent = $("focus").textContent;
  $("focusLive").hidden = d ? d.state === "off" : !camStream;
}
function refreshLanguage() {
  refreshBoardFigureLabels();
  setConn(sessionState === "ready" ? tr("session.ready", "老师已就绪") : sessionState === "connecting"
    ? tr("session.connecting", "连接中…") : connectionAttempt ? tr("session.closed", "连接已关闭") : tr("idle", "待开始"), sessionState === "ready");
  const language = window.LiveAgentProduct?.edition === "university" ? "en" : "zh";
  if (sessionState === "error" && errorLanguage !== language) {
    const message = tr("session.failed", "会话暂时中断了，请重新连接后继续。");
    $("overlay").style.display = "flex"; $("overlay").textContent = message;
    const failure = $("connectionError");
    if (failure) {
      failure.hidden = false;
      (failure.querySelector("#connectionErrorText") || failure).textContent = message;
    }
    errorLanguage = language;
  }
  if (sessionStatus) renderBadges(sessionStatus);
  $("cam").textContent = camPending ? tr("camera.permission", "等待摄像头授权…") : camStream
    ? tr("camera.off", "关闭专注检测") : tr("camera.on", "开启专注检测");
  $("talk").textContent = recorder?.state === "recording" ? tr("voice.release", "松开发送") : micPressed
    ? tr("voice.permission", "等待麦克风授权…") : tr("voice.hold", "按住说话");
  $("talk").title = sessionStatus?.asr ? "" : tr("voice.disabled", "这次会话暂时不能识别语音，请用文字提问。");
  renderFocusLabel();
  if (currentExercise) {
    if (acceptsActivity(currentExercise.request_id ?? null)) renderExerciseChips(currentExercise);
    else { currentExercise = null; exerciseKey = ""; renderExerciseChips(null); }
  }
  if (shownBoard?.key === "idle") {
    $("boardTitle").innerHTML = esc(tr("board.title", "学习黑板"));
    $("boardItems").innerHTML = [tr("board.ask", "可以提问题，老师会边讲边写。"), tr("board.lesson", "选一个学习主题，就可以开始上课。")]
      .map(text => `<li>${esc(text)}</li>`).join("");
  } else if (shownBoard) {
    $("boardTitle").innerHTML = shownBoard.title;
    const [k, n] = shownBoard.progress || [];
    if (k != null && n != null) for (const li of $("boardItems").children) li.querySelector(".dots")?.setAttribute("aria-label", boardSentenceLabel(k, n));
  }
  if (!$("avPanel").hidden) avInfo();
}
function onStatus(m) {
  clearStartupTimer();
  const firstReady = sessionState !== "ready";
  if (firstReady && teacherAvatar) {
    const avatar = m.avatar;
    if (avatar?.renderer === "mesh" && avatar.model === TEACHER_AVATAR_MODEL && Number.isInteger(avatar.epoch)) {
      avatarNegotiated = true; avatarEpoch = avatar.epoch;
      $("screenWrap").dataset.renderer = "mesh";
      $("overlay").style.display = "none";
    } else fallbackTeacherAvatar("The server did not negotiate this avatar model");
  }
  sessionStatus = m;
  setConn(tr("session.ready", "老师已就绪"), true);
  if (Array.isArray(m.examples) && m.examples.length) personaChips = m.examples;
  if (!exerciseKey) setChips(m.board ? idleExamples() : personaChips, true);
  showProfile(m.student);
  if (m.board && (!shownBoard || shownBoard.key === "idle"))
    showBoard({key: "idle", title: esc(tr("board.title", "学习黑板")), reveal: null,
               items: [esc(tr("board.ask", "可以提问题，老师会边讲边写。")), esc(tr("board.lesson", "选一个学习主题，就可以开始上课。"))]});
  $("cam").hidden = !m.attention;
  renderBadges(m);
  if (m.persona) $("title").textContent = m.persona;
  $("talk").title = m.asr ? "" : tr("voice.disabled", "这次会话暂时不能识别语音，请用文字提问。");
  sessionChanged("ready", {status: m});
  if (firstReady) chat("sys", tr("session.started", "老师已准备好，可以开始提问了。"));
  productEvent("status", m);
}

// ---------------------------------------------------------------- panel
// ---------------------------------------------------------------- student profile and exercises
let personaChips = EXAMPLES, profile = null, exerciseKey = "", currentExercise = null, lastGraded = null;
const LEVEL = {mastered: "已掌握", partial: "基本理解", weak: "薄弱", unknown: "未评估"};
function showProfile(p, flash) {
  profile = p || null;
  productEvent("profile", profile);
  $("profEdit").hidden = !p;
  const el = $("prof");
  if (!p) { el.innerHTML = `<div class="empty">${esc(tr("profile.none", "这次会话未使用学生档案。"))}</div>`; return; }
  $("profEdit").textContent = (p.exams || []).length > 2 || (p.concepts || []).length > 4
    ? tr("profile.viewAll", "完整记录见档案 ↗") : tr("profile.edit", "编辑 ↗");
  const exams = (p.exams || []).slice(-2).map(e => `<li>${esc(e.date || "")} ${esc(e.subject)}${esc(e.name)} <b>${e.score}</b>/${e.full}` +
    (e.weak && e.weak.length ? ` · ${esc(tr("profile.examWeak", "失分："))}${esc(e.weak.join("、"))}` : "") + "</li>").join("");
  const SRC = {exercise: tr("profile.source.exercise", "据记录的练习"), exam: tr("profile.source.exam", "据考试失分推断")};
  const cps = (p.concepts || []).slice(0, 4).map((c, index) => {
    const evidence = tr(`profile.level.${c.level}`, LEVEL[c.level] || c.level) + " · " + tr("profile.estimated", "未校准的估计") +
      " · " + (SRC[c.source] || tr("profile.source.none", "无记录依据")) +
      (typeof c.attempts === "number" ? " · " + tr("profile.attempts", "记录练习：") + (c.correct ?? 0) + "/" + c.attempts + tr("profile.correct", " 次正确") : "");
    return `<div class="concept-record"><div class="cp ${esc(c.level)}${flash === c.name ? " flash" : ""}" tabindex="0" aria-describedby="concept-evidence-${index}" title="${esc(evidence)}">
      <span>${esc(c.name)}</span><span class="bar" aria-hidden="true"><i style="width:${Math.round((c.mastery ?? 0) * 100)}%"></i></span>
      <span class="v">${c.mastery == null ? "–" : (c.source === "exam" ? "≈" : "") + Math.round(c.mastery * 100) + "%"}</span></div>
      <p class="meta concept-evidence" id="concept-evidence-${index}">${esc(evidence)}</p></div>`;
  }).join("");
  el.innerHTML = `<div class="who">${esc(p.name || tr("profile.learner", "同学"))} · ${esc(p.grade || tr("profile.gradeMissing", "年级未填"))}</div>` +
    (exams ? `<ul class="exams">${exams}</ul>` : `<div class="meta">${esc(tr("profile.noExams", "还没有考试成绩"))}</div>`) +
    (cps ? `<div class="meta">${esc(tr("profile.mastery", "知识点掌握度（未校准的估计；每条记录下方列出依据）"))}</div>` + cps : `<div class="meta">${esc(tr("profile.noConcepts", "做练习后，这里会出现知识点记录。"))}</div>`);
}
$("profEdit").onclick = () => {
  const id = profile ? profile.id : $("sid").value;
  window.location.href = `/profile?student=${encodeURIComponent(id)}&edition=${encodeURIComponent(window.LiveAgentProduct?.edition || "primary")}`;
};
function renderExerciseQuestion(node, ex) {
  const question = ex.question || ex.concept || "", options = ex.option_texts || [];
  // These optional fields are escaped text/MathML from the same server renderer as the board.
  // Legacy packets and missing rendered options retain safely escaped plain text.
  node.innerHTML = [typeof ex.question_html === "string" && ex.question_html ? ex.question_html : esc(question),
    ...options.map((option, index) => typeof ex.option_html?.[index] === "string" && ex.option_html[index]
      ? ex.option_html[index] : esc(option))].join("\n");
}
function showExercise(ex, requestId = ex?.request_id ?? null) {  // answer buttons while an exercise waits; the persona's examples otherwise
  if (!acceptsActivity(requestId)) {
    if (currentExercise && !acceptsActivity(currentExercise.request_id ?? null)) {
      currentExercise = null; exerciseKey = ""; renderExerciseChips(null);
    }
    return;
  }
  currentExercise = ex || null;
  const key = ex ? JSON.stringify([requestId, ex.concept, ex.question, ex.options || [], ex.option_texts || []]) : "";
  if (key === exerciseKey) return;
  exerciseKey = key;
  renderExerciseChips(currentExercise);
}
function renderExerciseChips(ex) {
  const live = ready();
  if (!ex) { setChips(sessionStatus?.board ? idleExamples() : personaChips, live); return; }
  setChips([...(ex.options || []).map((o, index) => ({label: tr("exercise.choose", "选 ") + o, text: "选 " + o,
              description: ex.option_texts?.[index] ? tr("exercise.choose", "选 ") + o + ": " + ex.option_texts[index] : undefined})),
            {label: tr("exercise.unsure", "我不会"), text: "我不会"}], live);
  document.querySelectorAll("#chips .chip").forEach(b => b.classList.add("answer"));
}

function onState(s) {
  productEvent("state", s);
  showExercise(s.exercise, s.exercise ? s.exercise.request_id ?? null : currentExercise?.request_id ?? null);
  $("sLambda").textContent = typeof s.lambda_s === "number" ? s.lambda_s.toFixed(1) : "–";
  $("sReq").textContent = s.next_lock ?? "–";
  const flags = [];
  if (s.listening) flags.push(tr("state.listening", "聆听中"));
  if (s.awaiting_decision) flags.push(tr("state.deciding", "等待应答决策"));
  if (!s.erasure_gate_open) flags.push(tr("state.erasure", "删除进行中（已暂停生成）"));
  $("flags").textContent = flags.join(" · ");
  const el = $("chains");
  if (!s.chains || !s.chains.length) return;
  el.innerHTML = "";
  for (const c of s.chains.slice().reverse()) {
    const steps = c.steps && c.steps.length > 1 ? ` · ${tr("state.steps", "步骤 ")}${Math.min(c.step_index, c.steps.length)}/${c.steps.length}` : "";
    const d = document.createElement("div"); d.className = "chain";
    d.innerHTML = `<div class="top"><span class="intent">${esc(c.intent)}</span><span class="pill ${esc(c.status)}">${esc(tr(`status.${c.status}`, STATUS[c.status] || c.status))}</span></div>
      <div class="meta">${esc(tr(`kind.${c.kind}`, KIND[c.kind] || c.kind))}${steps}${c.revisions ? ` · ${tr("state.revisions", "改口 ")}${c.revisions}` : ""}${c.requests.length ? ` · ${tr("state.requests", "请求 ")}${c.requests.join(", ")}` : ""}</div>`;
    el.appendChild(d);
  }
}

function onEvent(m) {
  productEvent("event", m);
  const d = m.data || {}, t = m.t, k = m.request;
  switch (m.event) {
    case "utterance_end":
      if (d.text) { lastUtterT = t; }
      if (d.decision) {
        const dec = d.decision;
        feed(t, "", "理解", `${dec.relation || ""}/${dec.kind || ""}` + (dec.forget_term ? diagnostic("forget", " · 删除「{term}」", {term: dec.forget_term}) : ""));
        (d.recalled || []).forEach(x => memo(tr("memory.recalled", "召回：") + x));
      }
      break;
    case "lock":
      if (d.transcript) chat("persona", d.transcript);
      feed(t, "", `锁定 #${k}`, (d.action ? d.action.slice(0, 70) : "") + (d.transcript ? ` · 「${d.transcript}」` : "") +
           (d.retry_of != null ? diagnostic("retry", " · 重试 #{request}", {request: d.retry_of}) : "") +
           ((d.corrections || []).length ? diagnostic("withCorrections", " · 附修正") : ""));
      break;
    case "verdict":
      if (d.kind === "action") {
        if (d.label === "complied") verified++;
        $("sVerified").textContent = verified;
        feed(t, d.label === "complied" ? "ok" : d.label === "not_complied" ? "bad" : "warn",
             `动作质检 #${k}: ${{complied: "通过", not_complied: "未通过", unknown: "无法判定"}[d.label] || d.label}`,
             d.rationale ? " · " + d.rationale : "");
      } else {
        feed(t, d.label === "complied" ? "ok" : "warn", `语音质检 #${k}: ${d.label === "complied" ? "通过" : "未通过"}`,
             d.rationale ? " · " + d.rationale : "");
      }
      break;
    case "repair":
      repairs++; $("sRepairs").textContent = repairs;
      feed(t, "warn", `前向修正 #${k}→#${d.earliest_correctable}`, d.correction ? " · " + d.correction.slice(0, 80) : diagnostic("repeat", "（重复原指令）"));
      break;
    case "completion_claim": feed(t, "ok", "完成声明", `「${d.text || diagnostic("done", "好了。")}」` + diagnostic("afterVerification", "（在验证之后）")); break;
    case "refusal": feed(t, "bad", "拒绝/降级", d.reason || ""); break;
    case "capacity_skip": feed(t, "warn", "容量跳过", d.reason || diagnostic("superseded", "被更新的指令取代")); break;
    case "narration_guard": feed(t, "warn", "叙述守卫", diagnostic("narrationRemoved", "去掉未验证的完成说法：「{text}」", {text: d.original})); break;
    case "speech_onset":
      if (lastUtterT != null && (d.chain_ids || []).length) {
        $("sLatency").textContent = (t - lastUtterT).toFixed(1); lastUtterT = null;
      }
      break;
    case "playback_stop":
      if (d.erasure) {
        clearBoardFigures();
        if (d.erasure_complete) {
          // this page kept its own copy of what was typed and recalled: clear it too
          $("chat").innerHTML = ""; $("memory").innerHTML = ""; $("caption").textContent = "";
          document.querySelectorAll("#feed .ev").forEach(e => e.remove());
          chat("sys", tr("memory.erased", "已按删除请求清除本页的对话与记忆记录"));
        }
        memo(d.erasure_complete ? diagnostic("erasureComplete", "已删除 {count} 条记录（含派生内容、日志与生成器状态）", {count: d.deleted}) : diagnostic("erasurePending", "删除未完成：已暂停生成，等待处理"),
             d.erasure_complete ? "ok" : "bad");
        feed(t, d.erasure_complete ? "ok" : "bad", "删除", d.erasure_complete ? diagnostic("complete", "完成") : diagnostic("incomplete", "未完成（安全暂停）"));
      } else { feed(t, "", "打断", diagnostic("playbackStopped", "停止播放，丢弃未呈现内容")); }
      break;
    case "audit":
      if ((d.issues || []).length) feed(t, "warn", "审核", d.issues.join(", "));
      break;
    case "error": feed(t, "bad", "错误", `${d.where || ""} ${d.error || ""}`); break;
    case "lesson": {
      if (d.stage === "figure" && d.figure) boardFigureReady(d);
      const s = {outline: diagnostic("outline", "课程大纲：{title}（{count} 节）", {title: d.title, count: (d.sections || []).length}),
                 section: diagnostic("section", "第 {index} 节已备好：{title}（{lines} 句，{points} 条板书）", {index: (d.section ?? 0) + 1, title: d.title, lines: d.lines, points: d.points}),
                 section_failed: diagnostic("sectionFailed", "第 {index} 节生成失败{next}", {index: (d.section ?? 0) + 1, next: d.attempt ? diagnostic("skipped", "，已跳过") : diagnostic("retrying", "，重试中")}),
                 outline_failed: diagnostic("outlineFailed", "课程大纲生成失败"), planned: diagnostic("planned", "整节课已备好：{title}", {title: d.title}),
                 figure_judgement: diagnostic("figureJudgement", "配图判断「{title}」：", {title: d.title}) + (d.judgements || []).map(j =>
                   diagnostic("figurePoint", "第 {index} 条 复杂度 {complexity} {decision}{reason}", {index: j.point + 1, complexity: j.complexity ?? "?",
                     decision: j.need ? diagnostic("figureNeeded", "→ 配图") : diagnostic("figureNotNeeded", "→ 不配"), reason: j.why ? ` (${j.why})` : ""})).join("; "),
                 figure: diagnostic("figure", "第 {index} 条的配图已画好（{kind}）", {index: (d.point ?? 0) + 1, kind: d.kind === "plot" ? diagnostic("plot", "精确作图") : d.kind === "diagram" ? diagnostic("diagram", "示意图") : diagnostic("illustration", "插图")}),
                 figure_failed: diagnostic("figureFailed", "配图失败：{error}", {error: d.error}),
                 exercise: diagnostic("exercise", "出题（{concept}）：{text}", {concept: d.concept, text: d.exercise}),
                 exercise_failed: diagnostic("exerciseFailed", "出题失败：{error}", {error: d.error}),
                 exercise_timeout: diagnostic("exerciseTimeout", "练习「{concept}」无人作答，老师讲解后继续", {concept: d.concept}),
                 grading_failed: diagnostic("gradingFailed", "批改失败：{error}", {error: d.error}),
                 profile_updated: diagnostic("profileUpdated", "学生档案已更新（{changed}）", {changed: (d.changed || []).join(", ")})}[d.stage];
      if (s) feed(t, d.stage.endsWith("failed") ? "bad" : "", "备课", s);
      if (d.stage === "outline" && d.plan) {
        const dep = {review: diagnostic("depth.review", "复习"), core: diagnostic("depth.core", "重点"), new: diagnostic("depth.new", "新课")};
        feed(t, "", d.adaptive ? "因材施教" : "教案", (d.note ? d.note + "；" : "") + d.plan.map((x, i) =>
          `${i + 1}.${x.title}[${dep[x.depth] || x.depth}${x.exercise ? diagnostic("withPractice", "+练习") : ""}]`).join(" "));
      }
      if (d.stage === "section" && d.exercise) feed(t, "", "练习", diagnostic("sectionPractice", "本节后出题：{text}", {text: d.exercise}));
      if (d.stage === "exercise_graded") {
        const m = d.mastery;
        feed(t, d.correct ? "ok" : "bad", "批改", `${d.concept}：${d.skipped ? diagnostic("unsure", "不会") : d.correct ? diagnostic("correct", "答对") : diagnostic("incorrect", "答错")}` +
             (d.misconception ? `（${d.misconception}）` : "") +
             (m && m.after != null ? diagnostic("mastery", " · 掌握度 {before} → {after}", {before: m.before == null ? "–" : Math.round(m.before * 100) + "%", after: Math.round(m.after * 100) + "%"}) : ""));
      }
      if (d.stage === "exercise_graded") lastGraded = d.concept;
      if (d.stage === "exercise_open") showExercise(d);
      if (d.stage === "exercise_closed") showExercise(null, d.request_id ?? null);
      break;
    }
    case "attention": {
      if (d.state !== "off" && !camStream) break;  // no stale verdict after opt-out
      latestAttention = d;
      renderFocusLabel();
      if (d.nudge) feed(t, "warn", "提醒学生", `「${d.nudge}」`);
      break;
    }
    case "continuity":
      if ((d.anchor_removed || []).length) feed(t, "", `场景锚定 #${k}`, diagnostic("anchorsRemoved", "首个镜头未出现：{anchors}（不再在提示中描述）", {anchors: d.anchor_removed.join(", ")}));
      if (d.wrong && Object.keys(d.wrong).length) {
        feed(t, (d.corrections || []).length ? "warn" : "", `场景连续性 #${k}`,
             Object.entries(d.wrong).map(([n, c]) => `${n}×${c.join("/")}`).join("，") +
             ((d.corrections || []).length ? diagnostic("correctedTarget", " · 修正→#{target}", {target: d.target}) : ""));
      }
      break;
  }
}

// ---------------------------------------------------------------- board (server-rendered, escaped HTML + MathML)
function layoutStage() {  // video + 3:4 board side by side at one height (stacked on narrow screens)
  const row = document.querySelector(".stagerow"), board = $("board"), cv = $("screen");
  const on = board.classList.contains("on"), W = row.clientWidth, gap = 12, va = cv.width / cv.height;
  const cap = innerWidth <= 620 ? 300 : innerWidth <= 860 ? 390 : Infinity;
  let H;
  if (!on) { H = Math.min(0.68 * innerHeight, W / va, cap); }
  else if (innerWidth <= 860) { H = Math.min(0.6 * innerHeight, W / va, cap); board.style.width = W + "px"; board.style.height = (W * 3 / 4) + "px"; }
  else { H = Math.min(0.55 * innerHeight, (W - gap) / (va + 4 / 3)); board.style.width = (H * 4 / 3) + "px"; board.style.height = H + "px"; }
  cv.style.height = H + "px"; cv.style.width = (H * va) + "px"; cv.style.maxHeight = "none";
  if (on) { board.dataset.base = Math.max(12, parseFloat(board.style.height) / 22); fitBoard(); }
}

function fitBoard() {  // shrink the text until every shown point fits: the point being spoken is never clipped
  const el = $("board"), ol = $("boardItems");
  let fs = parseFloat(el.dataset.base || "19");
  el.style.fontSize = fs + "px";
  while (fs > 11 && (ol.scrollHeight > ol.clientHeight + 1 || el.scrollHeight > el.clientHeight + 1)) {
    fs -= 1; el.style.fontSize = fs + "px";
  }
}
addEventListener("resize", layoutStage);
addEventListener("load", layoutStage);

let shownBoard = null;  // the board view on display (the chunk on screen switches it only when it differs)
const boardFigures = new Map();  // unique lesson/answer board key -> point -> completed figure
let failedBoardFigure = null;
let enlargedBoardFigure = null;
let displayedBoardFigure = null;
let boardGallerySelection = null;  // a learner's selection lasts until the board or spoken point changes
let boardGalleryContext = null;
function refreshBoardFigureLabels() {
  $("boardEnlarge").textContent = tr("board.figureEnlarge", "放大配图");
  $("boardFigureTitle").textContent = tr("board.figureTitle", "课程配图");
  $("boardFigureClose").setAttribute("aria-label", tr("board.figureClose", "关闭配图"));
  $("boardImg").setAttribute("aria-label", tr("board.figureEnlarge", "放大配图"));
  $("boardImg").alt = tr("board.figureTitle", "课程配图");
  $("boardFigureLarge").alt = $("boardFigureCaption").textContent || tr("board.figureTitle", "课程配图");
  $("boardPrevious").textContent = tr("board.figurePrevious", "上一张");
  $("boardNext").textContent = tr("board.figureNext", "下一张");
  renderBoardGallery();
}
function clearEnlargedBoardFigure() {
  $("boardFigureLarge").removeAttribute("src"); $("boardFigureCaption").textContent = "";
  $("boardFigureLarge").alt = tr("board.figureTitle", "课程配图");
  enlargedBoardFigure = null;
}
function closeBoardFigure() {
  if ($("boardFigureDialog").open) $("boardFigureDialog").close();
  clearEnlargedBoardFigure();
}
function openBoardFigure() {
  const fig = displayedBoardFigure;
  if (!validBoardFigure(fig) || !$("board").classList.contains("hasfig")) return;
  enlargedBoardFigure = {key: shownBoard.key, url: fig.url};
  $("boardFigureLarge").src = fig.url;
  $("boardFigureCaption").innerHTML = fig.caption || "";
  $("boardFigureLarge").alt = $("boardFigureCaption").textContent || tr("board.figureTitle", "课程配图");
  if (!$("boardFigureDialog").open) $("boardFigureDialog").showModal();
}
$("boardEnlarge").onclick = openBoardFigure;
$("boardImg").onclick = openBoardFigure;
$("boardImg").setAttribute("role", "button"); $("boardImg").tabIndex = 0;
$("boardImg").setAttribute("aria-haspopup", "dialog"); $("boardImg").setAttribute("aria-controls", "boardFigureDialog");
$("boardImg").onkeydown = event => {
  if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openBoardFigure(); }
};
$("boardFigureClose").onclick = closeBoardFigure;
$("boardFigureDialog").oncancel = event => { event.preventDefault(); closeBoardFigure(); };
$("boardFigureDialog").onclose = () => {
  // Native close events are queued: an old event must not clear a reopened viewer.
  if (!$("boardFigureDialog").open) clearEnlargedBoardFigure();
};
$("boardFigureLarge").onerror = closeBoardFigure;
refreshBoardFigureLabels();
function validBoardFigure(figure) {
  return figure && typeof figure.url === "string" && /^\/board\/img\/(?:[0-9a-f]{16}|[pd][0-9a-f]{15})\.png$/.test(figure.url);
}
function applyBoardFigure(b) {
  if (!b) return b;
  if (Array.isArray(b.figures)) {
    if (!boardFigures.has(b.key)) boardFigures.set(b.key, new Map());
    const cache = boardFigures.get(b.key);
    b.figures.forEach(fig => {
      if (!validBoardFigure(fig) || (fig.point != null && (!Number.isInteger(fig.point) || fig.point < 0))) return;
      const point = fig.point ?? null;
      // A completed event can arrive after this playback snapshot was made.
      // Keep that newer event's image/caption when an older snapshot returns.
      if (!cache.get(point)?._readyEvent) cache.set(point, {url: fig.url,
        caption: typeof fig.caption === "string" ? fig.caption : ""});
    });
    if (boardFigures.size > 32) boardFigures.delete(boardFigures.keys().next().value);
  }
  const figures = boardFigures.get(b.key);
  const currentMembers = (b.figures || []).filter(fig => validBoardFigure(fig) && fig.url === b.figure?.url
    && (fig.point == null || (Number.isInteger(fig.point) && fig.point >= 0)));
  const currentMember = currentMembers.find(fig => (fig.point ?? null) === (b.reveal ?? null)) || currentMembers[0];
  const snapshotPoint = b._figurePoint !== undefined ? b._figurePoint
    : currentMember ? currentMember.point ?? null : b.reveal ?? null;
  if (validBoardFigure(b.figure) && figures && !figures.get(snapshotPoint)?._readyEvent) {
    figures.set(snapshotPoint, {url: b.figure.url, caption: typeof b.figure.caption === "string" ? b.figure.caption : ""});
  }
  const exact = figures?.get(b.reveal), whole = figures?.get(null);
  if (!exact && b._figurePoint != null && b._figurePoint !== b.reveal) {
    delete b.figure; delete b._figurePoint;
  }
  if (exact) { b.figure = exact; b._figurePoint = b.reveal; }
  else if (whole && (!b.figure || b._figurePoint === null || b.figure.url === whole.url)) {
    b.figure = whole; b._figurePoint = null;
  }
  const ready = new Map();
  figures?.forEach((fig, point) => ready.set(point, {url: fig.url, caption: fig.caption, point}));
  if (validBoardFigure(b.figure)) {
    const point = b._figurePoint !== undefined ? b._figurePoint : snapshotPoint;
    // An explicit current snapshot also supports servers sending a single figure.
    if (!ready.has(point)) ready.set(point, {url: b.figure.url,
      caption: typeof b.figure.caption === "string" ? b.figure.caption : "", point});
  }
  b.figures = [...ready.values()].sort((a, z) => (a.point ?? -1) - (z.point ?? -1));
  return b;
}
function boardGalleryFigures() {
  const unique = new Map();
  (shownBoard?.figures || []).forEach(fig => { if (validBoardFigure(fig) && !unique.has(fig.url)) unique.set(fig.url, fig); });
  return [...unique.values()];
}
function renderBoardGallery() {
  const figures = boardGalleryFigures(), index = figures.findIndex(fig => fig.url === displayedBoardFigure?.url);
  $("boardGallery").hidden = !figures.length;
  $("boardBrowse").hidden = index >= 0 && $("board").classList.contains("hasfig");
  $("boardBrowse").textContent = `${tr("board.figureBrowse", "查看配图")} ${figures.length}`;
  $("boardPrevious").hidden = $("boardNext").hidden = index < 0 || figures.length < 2;
  $("boardPrevious").disabled = index <= 0;
  $("boardNext").disabled = index < 0 || index >= figures.length - 1;
  $("boardFigureCount").hidden = index < 0;
  $("boardFigureCount").textContent = index < 0 ? "" : `${index + 1} / ${figures.length}`;
  $("boardFigureCount").setAttribute("aria-label", index < 0 ? "" :
    tr("board.figureCount", "配图 {current} / {total}").replace("{current}", index + 1).replace("{total}", figures.length));
}
function selectBoardFigure(index) {
  const figures = boardGalleryFigures();
  if (!shownBoard || !Number.isInteger(index) || index < 0 || index >= figures.length) return;
  boardGallerySelection = {key: shownBoard.key, url: figures[index].url};
  showBoard(shownBoard);
}
function stepBoardFigure(direction) {
  const figures = boardGalleryFigures(), index = figures.findIndex(fig => fig.url === displayedBoardFigure?.url);
  selectBoardFigure(index < 0 ? 0 : index + direction);
}
$("boardBrowse").onclick = () => selectBoardFigure(0);
$("boardPrevious").onclick = () => stepBoardFigure(-1);
$("boardNext").onclick = () => stepBoardFigure(1);
function boardFigureReady(d) {
  if (typeof d.board !== "string" || !d.board || !validBoardFigure(d.figure)
      || (d.point != null && (!Number.isInteger(d.point) || d.point < 0))) return;
  if (!boardFigures.has(d.board)) boardFigures.set(d.board, new Map());
  boardFigures.get(d.board).set(d.point ?? null, {url: d.figure.url,
    caption: typeof d.figure.caption === "string" ? d.figure.caption : "", _readyEvent: true});
  if (boardFigures.size > 32) boardFigures.delete(boardFigures.keys().next().value);
  [shownBoard, lastBoard, onScreen?.board, pending?.meta.board, ...queue.map(q => q.board),
    ...decoding.map(c => c.meta.board)].forEach(b => { if (b?.key === d.board) applyBoardFigure(b); });
  if (shownBoard?.key === d.board) showBoard(shownBoard);
}
function clearBoardFigures() {
  closeBoardFigure();
  boardFigures.clear(); failedBoardFigure = null;
  displayedBoardFigure = boardGallerySelection = boardGalleryContext = null;
  delete $("board").dataset.content;
  [shownBoard, lastBoard, onScreen?.board, pending?.meta.board, ...queue.map(q => q.board),
    ...decoding.map(c => c.meta.board)].forEach(b => {
    if (b) { delete b.figure; delete b.figures; delete b._figurePoint; }
  });
  $("boardImg").removeAttribute("src"); $("boardCap").textContent = "";
  $("board").classList.remove("hasfig");
  renderBoardGallery();
}
$("boardImg").onload = () => { if (displayedBoardFigure?.url === $("boardImg").getAttribute("src")) fitBoard(); };
$("boardImg").onerror = () => {
  failedBoardFigure = $("boardImg").getAttribute("src");
  closeBoardFigure();
  $("board").classList.remove("hasfig"); $("boardCap").textContent = "";
  renderBoardGallery(); fitBoard();
};
function showBoard(b) {
  const context = JSON.stringify([b.key, b.reveal ?? null]);
  if (boardGalleryContext !== context) boardGallerySelection = null;
  boardGalleryContext = context;
  applyBoardFigure(b);
  shownBoard = b;
  const el = $("board");
  if (!el.classList.contains("on")) { el.classList.add("on"); layoutStage(); }
  const content = JSON.stringify([b.title, b.items]);
  if (el.dataset.key !== b.key || el.dataset.content !== content) {
    el.dataset.key = b.key;
    el.dataset.content = content;
    $("boardTitle").innerHTML = b.title;
    $("boardItems").innerHTML = b.items.map(x => `<li>${x}</li>`).join("");
  }
  const manual = boardGallerySelection?.key === b.key
    ? boardGalleryFigures().find(fig => fig.url === boardGallerySelection.url) : null;
  if (boardGallerySelection && !manual) boardGallerySelection = null;
  const fig = manual || (validBoardFigure(b.figure) ? b.figure : null);
  displayedBoardFigure = fig;
  if (enlargedBoardFigure && (enlargedBoardFigure.key !== b.key || enlargedBoardFigure.url !== fig?.url)) closeBoardFigure();
  else if (enlargedBoardFigure && fig) {
    $("boardFigureCaption").innerHTML = fig.caption || "";
    $("boardFigureLarge").alt = $("boardFigureCaption").textContent || tr("board.figureTitle", "课程配图");
  }
  el.classList.toggle("hasfig", !!fig);
  if (fig) {
    if ($("boardImg").getAttribute("src") !== fig.url || failedBoardFigure === fig.url) {
      failedBoardFigure = null; $("boardImg").src = fig.url;
    }
    $("boardCap").innerHTML = fig.caption || "";
  } else {
    $("boardImg").removeAttribute("src"); $("boardCap").textContent = "";
  }
  renderBoardGallery();
  const lis = [...$("boardItems").children];
  lis.forEach((li, i) => {
    li.classList.toggle("hidden", b.reveal !== null && b.reveal !== undefined && i > b.reveal);
    li.classList.toggle("now", i === b.reveal);
    li.querySelector(".dots")?.remove();
  });
  const cur = (b.reveal !== null && b.reveal !== undefined) ? lis[b.reveal] : null;
  if (cur && b.progress) {  // how far into this point the teacher is: one dot per sentence about it
    const [k, n] = b.progress, d = document.createElement("span");
    d.className = "dots"; d.textContent = "●".repeat(k) + "○".repeat(Math.max(0, n - k));
    d.setAttribute("aria-label", boardSentenceLabel(k, n)); cur.appendChild(d);
  }
  fitBoard();
  if (cur) cur.scrollIntoView({block: "nearest"});
}

// ---------------------------------------------------------------- H.264 (WebCodecs)
const H264 = "avc1.42E01F";  // baseline, level 3.1 (480x864 @ 24 fps)
async function h264Supported() {
  try {
    if (typeof VideoDecoder === "undefined") return false;
    const r = await VideoDecoder.isConfigSupported({codec: H264, codedWidth: 480, codedHeight: 864});
    return !!r.supported;
  } catch (e) { return false; }
}
function decodeH264(buf, meta) {
  return new Promise((resolve, reject) => {
    const out = []; let dec = null, finished = false;
    const close = () => { try { dec?.close(); } catch (_) {} };
    const fail = error => {
      if (finished) return;
      finished = true; close();
      out.forEach(frame => frame.then(image => image.close?.()).catch(() => {}));
      reject(error);
    };
    try {
      dec = new VideoDecoder({
        output: f => {
          if (finished) { f.close(); return; }
          try {
            const image = createImageBitmap(f).finally(() => f.close());
            image.catch(() => {}); out.push(image);
          } catch (error) { f.close(); fail(error); }
        },
        error: fail,
      });
      dec.configure({codec: H264, codedWidth: meta.width, codedHeight: meta.height, optimizeForLatency: true});
      let off = 0;
      meta.sizes.forEach((n, i) => {
        const sourceFrame = meta.video_frame_indices?.[i] ?? i;
        dec.decode(new EncodedVideoChunk({type: i === 0 ? "key" : "delta", timestamp: Math.round(sourceFrame * 1e6 / meta.fps),
                                          data: new Uint8Array(buf, off, n)}));
        off += n;
      });
      dec.flush().then(() => Promise.all(out)).then(frames => {
        if (finished) return;  // fail() owns the output bitmap cleanup
        finished = true; close(); resolve(frames);
      }, fail);
    } catch (error) { fail(error); }
  });
}

// ---------------------------------------------------------------- playback (master clock = AudioContext)
function avatarMouthAt(q, elapsed) {
  const pcm = q?.pcm, sr = q?.meta.sample_rate;
  if (!pcm?.length || !sr || elapsed < 0 || elapsed >= pcm.length / sr) return {open: 0, round: 0};
  const center = Math.floor(elapsed * sr), radius = Math.max(1, Math.floor(sr * 0.02));
  const begin = Math.max(0, center - radius), end = Math.min(pcm.length, center + radius);
  let energy = 0, crossings = 0;
  for (let i = begin; i < end; i++) {
    const sample = pcm[i] / 32768; energy += sample * sample;
    if (i > begin && (pcm[i] >= 0) !== (pcm[i - 1] >= 0)) crossings++;
  }
  const rms = Math.sqrt(energy / Math.max(1, end - begin));
  const open = Math.min(1, Math.max(0, (rms - 0.009) / 0.13));
  // A restrained acoustic approximation, rather than a claim of phoneme recognition.
  const voiced = Math.max(0, 1 - crossings / Math.max(1, end - begin) / 0.18);
  return {open: Math.sqrt(open) * 0.88, round: open > 0.06 ? voiced * 0.35 : 0};
}
function captureTeacherAvatar(q, t) {
  const now = performance.now(), count = avatarCaptureCounts.get(q.meta.request) || 0;
  if (document.hidden || !ready() || now - avatarCaptureAt < 500 || (q.avatarCaptures || 0) >= 12 || count >= 24) return;
  avatarCaptureAt = now;  // failed captures are bounded too; never substitute a video frame
  let image;
  try { image = teacherAvatar.capture(); } catch (_) { return; }
  if (typeof image !== "string" || !image.startsWith("data:image/jpeg;base64,") || image.length > 160000) return;
  const elapsed = Math.max(0, t - q.start), meta = q.meta.avatar;
  const frame = Math.max(0, Math.min(q.meta.n_frames - 1, Math.floor(elapsed / (q.end - q.start) * q.meta.n_frames)));
  if (send({type: "avatar_frame", renderer: "mesh", model: TEACHER_AVATAR_MODEL, epoch: meta.epoch,
    request: q.meta.request, chunk: q.meta.chunk, frame, tp: now,
    request_time_s: meta.request_time_s + elapsed, mime: "image/jpeg", image})) {
    q.avatarCaptures = (q.avatarCaptures || 0) + 1; avatarCaptureCounts.set(q.meta.request, count + 1);
    while (avatarCaptureCounts.size > 32) avatarCaptureCounts.delete(avatarCaptureCounts.keys().next().value);
  }
}
function renderTeacherAvatar(q, t) {
  if (!avatarActive()) return;
  let state = {gesture: "idle", requestTime: 0, duration: 1,
    motionTime: Math.max(0, avatarMotionBase + t - avatarMotionStart), mouthOpen: 0, mouthRound: 0};
  if (q) {
    const meta = q.meta.avatar;
    if (!meta || meta.renderer !== "mesh" || meta.model !== TEACHER_AVATAR_MODEL || meta.epoch !== avatarEpoch ||
        ![meta.request_time_s, meta.request_duration_s, meta.motion_time_s].every(Number.isFinite) || meta.request_duration_s <= 0) {
      fallbackTeacherAvatar("Avatar timing metadata was unavailable"); return;
    }
    const elapsed = Math.max(0, t - q.start), mouth = avatarMouthAt(q, elapsed);
    const dt = avatarLastTime == null ? refreshS : Math.max(0, Math.min(0.1, t - avatarLastTime));
    const smooth = 1 - Math.exp(-dt / (mouth.open > avatarMouthOpen ? 0.035 : 0.055));
    avatarMouthOpen += smooth * (mouth.open - avatarMouthOpen);
    avatarMouthRound += smooth * (mouth.round - avatarMouthRound);
    state = {gesture: typeof meta.gesture === "string" ? meta.gesture : "idle",
      requestTime: meta.request_time_s + elapsed, duration: meta.request_duration_s,
      motionTime: meta.motion_time_s + elapsed, mouthOpen: avatarMouthOpen, mouthRound: avatarMouthRound};
    avatarMotionBase = meta.motion_time_s; avatarMotionStart = q.start;
  } else {
    avatarMouthOpen = avatarMouthRound = 0;
  }
  avatarLastTime = t;
  try {
    teacherAvatar.render(state);
    if (!teacherAvatar?.active) { fallbackTeacherAvatar("The avatar renderer stopped"); return; }
    avatarLastState = {...state, request: q?.meta.request ?? null, chunk: q?.meta.chunk ?? null};
    if (q && !q.endedSent) captureTeacherAvatar(q, t);
  } catch (error) { fallbackTeacherAvatar(error); }
}
function schedule(c) {
  const m = c.meta, sr = m.sample_rate;
  if (canvas.width !== m.width || canvas.height !== m.height) { canvas.width = m.width; canvas.height = m.height; layoutStage(); }
  const buf = audioCtx.createBuffer(1, Math.max(1, c.pcm.length), sr);
  const ch = buf.getChannelData(0);
  for (let i = 0; i < c.pcm.length; i++) ch[i] = c.pcm[i] / 32768;
  const start = Math.max(audioCtx.currentTime + 0.05, playhead);
  const dur = m.duration || m.n_frames / m.fps;
  const src = audioCtx.createBufferSource(); src.buffer = buf; src.connect(outGain()); src.start(start);
  playhead = start + dur;
  if (c.meta.board) lastBoard = c.meta.board;  // chunk 0 of a request carries its board; later chunks show the same
  const q = {...c, start, end: start + dur, src, startedSent: false, endedSent: false, board: lastBoard};
  // Playback acks also come from the audio clock: in a background tab requestAnimationFrame stops (no frames are
  // painted, so render() sends nothing) while the audio plays on, and the server would stop locking new clips.
  // In a visible tab the picture can still be on this chunk when its audio ends (output delay, "画面延后"), and
  // render() sends chunk_end with the complete list of painted frames when the picture ends; this is the fallback.
  const ep = epoch;
  src.onended = () => {
    const check = () => {
      if (ep !== epoch || q.endedSent) return;
      // no frame rendered (without an error) for 0.5 s: the render loop is stalled or failing, ack from the audio clock
      if (document.hidden || performance.now() - lastGoodRender > 500) ackChunk(q);
      else setTimeout(check, 250);  // render() sends chunk_end itself when the picture reaches the end
    };
    check();
  };
  queue.push(q);
  return q;
}

function ackChunk(q) {  // start/end acks with their scheduled times; painted frames only as actually painted
  if (!q.startedSent) {
    q.startedSent = true;
    send({type: "chunk_start", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.start), ...avatarPresentation(q)});
  }
  if (!q.endedSent) {
    q.endedSent = true;
    send({type: "chunk_end", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.end),
          painted: Array.from(q.painted || []), tp_last_paint: q.lastPaint, ...avatarPresentation(q)});
  }
}

function retireChunk(q) {
  q.retired = true;
  q.frames.forEach(frame => frame.close?.()); q.frames = [];
}

function stopAll() {
  if (window.__avTrace) window.__avTrace.push({stop: true, p: performance.now()});  // test hook
  epoch += 1;
  if (pending) {
    pending.frames.forEach(frame => Promise.resolve(frame).then(image => image.close?.()).catch(() => {}));
    pending.video?.then(frames => frames.forEach(image => image.close?.())).catch(() => {});
  }
  pending = null;
  decoding.forEach(retireChunk); decoding = [];
  $("caption").textContent = "";  // the scripted caption must not outlive a barge-in or erasure
  for (const q of queue) {
    try { q.src.stop(); } catch (e) {}
    retireChunk(q);
  }
  queue = []; playhead = audioCtx ? audioCtx.currentTime : 0;
  onScreen = null; resetTeacherAvatar();
}

// AudioContext time -> performance clock (ms) at the audio *output* (includes output latency).
function ctxToPerf(t) {
  const o = audioCtx.getOutputTimestamp ? audioCtx.getOutputTimestamp() : null;
  if (!o || !o.performanceTime) return performance.now() + (t - audioCtx.currentTime) * 1000;
  return o.performanceTime + (t - o.contextTime) * 1000;
}

// The context time of the sample the listener hears right now. audioCtx.currentTime runs ahead of the speaker by the
// output latency (tens of ms wired, 150-300 ms on Bluetooth), so frames picked by it show the mouth before the voice.
function heardTime() {
  const o = audioCtx.getOutputTimestamp ? audioCtx.getOutputTimestamp() : null;
  if (o && o.performanceTime > 0 && o.contextTime > 0) return o.contextTime + (performance.now() - o.performanceTime) / 1000;
  return audioCtx.currentTime - ((audioCtx.baseLatency || 0) + (audioCtx.outputLatency || 0));  // both stages
}

// ---------------------------------------------------------------- lip sync
// A frame is drawn for the sound the listener hears when that frame reaches the screen: the heard time (above), plus
// one display refresh (a canvas drawn now appears at the next vsync at the earliest; the real display delay is not
// observable from a page, so this is an estimate), minus the viewer's own offset ("画面延后": Bluetooth headsets often
// add more delay than the device reports; the beep-and-flash test measures the whole chain by eye and ear).
// Caption and board switch on the same clock.
// chunks stay drawable this long after their end: the slider can move the picture back by its whole range (-300 -> +300)
const AV_KEY = "liveagent.avOffsetMs", AV_MAX_S = 0.3, RETAIN_S = 2 * AV_MAX_S + 0.05;
let avOffsetMs = 0, refreshS = 1 / 60, lastRaf = 0, rendering = false, calib = null, onScreen = null, lastBoard = null;
let lastGoodRender = 0;  // performance time of the last frame rendered without an error
try { avOffsetMs = Math.max(-300, Math.min(300, Number(localStorage.getItem(AV_KEY)) || 0)); } catch (e) {}
function mediaTime() { return heardTime() + refreshS - avOffsetMs / 1000; }
function startRender() { if (!rendering) { rendering = true; requestAnimationFrame(render); } }
function setAvOffset(ms) {
  avOffsetMs = Math.max(-AV_MAX_S * 1000, Math.min(AV_MAX_S * 1000, Math.round(ms / 10) * 10));
  $("avOffset").value = avOffsetMs; $("avOffsetV").textContent = `${avOffsetMs > 0 ? "+" : ""}${avOffsetMs} ms`;
  try { localStorage.setItem(AV_KEY, String(avOffsetMs)); } catch (e) {}
}
function avInfo() {
  if (!audioCtx) { $("avInfo").textContent = ""; return; }
  const out = Math.max(0, audioCtx.currentTime - heardTime());
  $("avInfo").textContent = tr("av.reportOutput", "声卡报告的输出延迟 ≈ ") + Math.round(out * 1000) +
    tr("av.reportRefresh", " ms，屏幕刷新 ≈ ") + Math.round(refreshS * 1000) + tr("av.reportCompensated", " ms（均已自动补偿）");
}
$("avBtn").onclick = () => {
  const p = $("avPanel"), open = p.hidden;
  p.hidden = !open; $("avBtn").setAttribute("aria-expanded", String(open));
  if (open) avInfo();
};
$("avOffset").oninput = (e) => setAvOffset(+e.target.value);
$("avReset").onclick = () => setAvOffset(0);
$("avTest").onclick = () => {  // six beeps on the audio clock, each with a white flash drawn on the media clock
  audioCtx = audioCtx || new AudioContext();
  audioCtx.resume();
  if (calib) calib.oscs.forEach(o => { try { o.stop(); } catch (e) {} });  // a second click restarts the test
  const t0 = audioCtx.currentTime + 0.3, times = [], oscs = [];
  for (let i = 0; i < 6; i++) {
    const t = t0 + i * 0.8, osc = audioCtx.createOscillator(), env = audioCtx.createGain();
    osc.frequency.value = 1000; env.gain.setValueAtTime(0, t);
    env.gain.linearRampToValueAtTime(0.5, t + 0.005); env.gain.setValueAtTime(0.5, t + 0.07);
    env.gain.linearRampToValueAtTime(0, t + 0.08);
    osc.connect(env).connect(audioCtx.destination);  // not through outGain: push-to-talk ducking must not mute it
    osc.start(t); osc.stop(t + 0.09);
    times.push(t); oscs.push(osc);
  }
  calib = {times, oscs, until: t0 + 6 * 0.8};
  startRender(); setTimeout(avInfo, 500);
};
setAvOffset(avOffsetMs);
if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {  // a new headset has its own delay
  navigator.mediaDevices.addEventListener("devicechange", () => {
    if (avOffsetMs) chat("sys", tr("device.changed", "音频设备变了；如果口型和声音对不上，可以打开音画同步重新测试。"));
  });
}

function render(ts) {
  try { renderFrame(ts); lastGoodRender = performance.now(); }
  catch (e) { console.error("render", e); }  // one bad frame must not stop the picture for the rest of the session
  if (rendering) requestAnimationFrame(render);
}

function renderFrame(ts) {
  if (window.__avTrace) window.__avRenders = (window.__avRenders || 0) + 1;  // test hook: one loop, not two
  if (lastRaf && ts > lastRaf) {  // the display's refresh interval, smoothed (60 Hz: 16.7 ms)
    const dt = (ts - lastRaf) / 1000;
    if (dt > 0.004 && dt < 0.05) refreshS += 0.1 * (dt - refreshS);
  }
  lastRaf = ts || lastRaf;
  if (calib && audioCtx) {
    const mt = mediaTime(), on = calib.times.some(b => mt >= b && mt < b + 0.08);
    if (on && !calib.on && window.__avFlashLog) window.__avFlashLog.push(heardTime());  // test hook
    calib.on = on; $("avFlash").style.opacity = on ? "0.9" : "0";
    if (mt > calib.until) { calib = null; $("avFlash").style.opacity = "0"; }
  }
  if (audioCtx) {
    const t = mediaTime();  // frames, caption and board follow the sound as heard (lip sync)
    if (avatarNegotiated && !avatarDisabled && teacherAvatar?.active !== true) fallbackTeacherAvatar("WebGL became unavailable");
    let speakingChunk = null;
    for (const q of queue) {
      if (!q.startedSent && t >= q.start) {
        q.startedSent = true; $("overlay").style.display = "none";
        send({type: "chunk_start", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.start), ...avatarPresentation(q)});
      }
      if (t >= q.start && t < q.end) speakingChunk = q;
      if (t >= q.start && t < q.end && onScreen !== q) {  // caption and board of the chunk on screen, in either
        onScreen = q;                                      // direction (the slider can move the picture back)
        if (q.meta.transcript) $("caption").innerHTML = `<small>${esc(tr("caption.label", "老师"))}</small>${esc(q.meta.transcript)}`;
        if (q.board && q.board !== shownBoard) showBoard(q.board);  // the board point being spoken
      }
      if (!avatarActive() && q.startedSent && t >= q.start && t < q.end && q.frames.length) {  // t can move back (offset change)
        const logical = Math.max(0, Math.min(q.meta.n_frames - 1, Math.floor((t - q.start) / (q.end - q.start) * q.meta.n_frames)));
        const sources = q.meta.video_frame_indices;
        let idx = Math.max(0, Math.min(q.frames.length - 1, Math.floor((t - q.start) / (q.end - q.start) * q.frames.length)));
        if (Array.isArray(sources) && sources.length === q.frames.length) {
          idx = 0;
          while (idx + 1 < sources.length && sources[idx + 1] <= logical) idx++;
        }
        const sourceIndex = Array.isArray(sources) ? sources[idx] : idx;
        g.drawImage(q.frames[idx], 0, 0, canvas.width, canvas.height);
        (q.painted = q.painted || new Set()).add(sourceIndex);  // native source indices actually shown (QC evidence)
        q.lastPaint = performance.now();
        if (window.__avTrace) window.__avTrace.push({t, heard: heardTime(), ctx: audioCtx.currentTime, p: performance.now(),
                                                     start: q.start, end: q.end, idx: sourceIndex, n: q.meta.n_frames,
                                                     key: `${q.meta.request}/${q.meta.chunk}`, line: q.meta.transcript || "",
                                                     cap: $("caption").textContent, ended: q.endedSent,
                                                     board: q.board ? q.board.key : null,
                                                     shown: shownBoard ? shownBoard.key : null});
      }
      if (!q.endedSent && t >= q.end) {  // a snapshot: if the slider later takes the picture back into this chunk,
        q.endedSent = true;              // those paints are not reported (painted stays conservative, E a lower bound)
        send({type: "chunk_end", request: q.meta.request, chunk: q.meta.chunk, tp: ctxToPerf(q.end),
              painted: Array.from(q.painted || []), tp_last_paint: q.lastPaint, ...avatarPresentation(q)});
      }
    }
    renderTeacherAvatar(speakingChunk, t);
    // a chunk leaves only when its picture is done plus the slider's whole range: moving the slider can take the
    // picture back into a chunk that ended, and its frames must still be there
    queue = queue.filter(q => {
      if (!(q.endedSent && t >= q.end + RETAIN_S)) return true;
      retireChunk(q); return false;
    });
  }
}

// ---------------------------------------------------------------- camera focus check (opt-in)
// Aspect-preserving frames up to 640x480 every 1.5 s (configured targets), while explicitly enabled; analysed
// in memory (focused / distracted / absent) and never stores or records it.
let camStream = null, camTimer = null, camPending = false, camRequest = 0;
const camCanvas = document.createElement("canvas");
const CAMERA_INTERVAL_MS = 1500;
async function camOn() {
  if (!ready() || !sessionStatus?.attention || camStream || camPending) return;
  const request = ++camRequest, socket = ws, attempt = connectionAttempt;
  camPending = true; $("cam").disabled = true; $("cam").textContent = tr("camera.permission", "等待摄像头授权…");
  let stream;
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera unavailable");
    stream = await navigator.mediaDevices.getUserMedia({video: {width: {ideal: 640}, height: {ideal: 480}, facingMode: "user"}, audio: false});
  } catch (e) {
    if (request === camRequest && activeSocket(socket, attempt)) {
      camPending = false; $("cam").disabled = false; $("cam").textContent = tr("camera.on", "开启专注检测");
      permissionNotice("camera", e);
    }
    return;
  }
  if (request !== camRequest || !activeSocket(socket, attempt) || !ready()) {
    stream.getTracks().forEach(track => track.stop()); return;
  }
  camPending = false; camStream = stream; latestAttention = null; $("cam").disabled = false;
  const v = $("camView"); v.srcObject = camStream; v.hidden = false;
  const capture = () => {
    if (request !== camRequest || !camStream || !activeSocket(socket, attempt) || !ready() || !v.videoWidth || !v.videoHeight) return;
    const scale = Math.min(1, 640 / v.videoWidth, 480 / v.videoHeight);
    camCanvas.width = Math.max(1, Math.round(v.videoWidth * scale));
    camCanvas.height = Math.max(1, Math.round(v.videoHeight * scale));
    camCanvas.getContext("2d").drawImage(v, 0, 0, camCanvas.width, camCanvas.height);
    send({type: "camera", jpeg: camCanvas.toDataURL("image/jpeg", 0.75).split(",")[1]});
  };
  camTimer = setInterval(capture, CAMERA_INTERVAL_MS);
  v.play().then(capture).catch(() => {});
  $("cam").textContent = tr("camera.off", "关闭专注检测");
  renderFocusLabel();
}
function camOff(tell = true) {
  camRequest++; camPending = false; latestAttention = null;
  if (camTimer) clearInterval(camTimer);
  camTimer = null;
  if (camStream) camStream.getTracks().forEach(t => t.stop());
  const was = !!camStream; camStream = null;
  $("camView").srcObject = null; $("camView").hidden = true; $("cam").textContent = tr("camera.on", "开启专注检测");
  if (was && tell) send({type: "camera_off"});
  $("cam").disabled = !ready() || !sessionStatus?.attention;
  renderFocusLabel();
}
$("cam").onclick = () => camStream ? camOff() : camOn();

// ---------------------------------------------------------------- input
// A comment does not cut the video here: the server keeps it playing and sends "stop" when the reply is ready.
// While the user holds push-to-talk the persona's audio is muted (not the video) so the mic hears only the user.
let master = null;  // output gain: every chunk's audio goes through it
function outGain() {
  if (!master) { master = audioCtx.createGain(); master.connect(audioCtx.destination); }
  return master;
}
function duck(on) { if (audioCtx) outGain().gain.setTargetAtTime(on ? 0 : 1, audioCtx.currentTime, 0.03); }
let micPressed = false, micRequest = 0, micStream = null, micUploading = false;
function permissionNotice(device, error) {
  const kind = {NotAllowedError: "denied", SecurityError: "denied", NotFoundError: "missing", NotReadableError: "busy"}[error.name] || "failed";
  const messages = {
    voice: {denied: "麦克风未获授权，可以在浏览器里允许，或者用文字提问。", missing: "没有找到麦克风，可以接上麦克风，或者用文字提问。", busy: "麦克风正在被别的程序使用，可以先用文字提问。", failed: "暂时无法录音，可以用文字提问。"},
    camera: {denied: "摄像头未获授权，不开摄像头也可以继续学习。", missing: "没有找到摄像头，不开摄像头也可以继续学习。", busy: "摄像头正在被别的程序使用，不开摄像头也可以继续学习。", failed: "暂时无法使用摄像头，不开摄像头也可以继续学习。"},
  };
  notice(`${device}.${kind}`, messages[device][kind], error);
}
function resetTalkButton() {
  $("talk").classList.remove("recording"); $("talk").textContent = tr("voice.hold", "按住说话");
}
function cancelSpeech() {
  micPressed = false; micUploading = false; micRequest++;
  if (recorder) {
    recorder.onstop = null; recorder.ondataavailable = null;
    if (recorder.state !== "inactive") { try { recorder.stop(); } catch (e) {} }
  }
  micStream?.getTracks().forEach(track => track.stop()); micStream = null; recorder = null;
  duck(false); resetTalkButton();
}
$("talk").onpointerdown = async event => {
  if (!ready() || !sessionStatus?.asr || micPressed || micUploading || recorder?.state === "recording") return;
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    notice("voice.unavailable", "这个浏览器暂时不能录音，可以用文字提问。"); return;
  }
  micPressed = true;
  const request = ++micRequest, socket = ws, attempt = connectionAttempt;
  $("talk").textContent = tr("voice.permission", "等待麦克风授权…");
  try { if (event?.pointerId != null) $("talk").setPointerCapture(event.pointerId); } catch (e) {}
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
    if (!micPressed || request !== micRequest || !activeSocket(socket, attempt) || !ready()) {
      stream.getTracks().forEach(track => track.stop()); return;
    }
    const parts = [];
    const recording = new MediaRecorder(stream); recorder = recording; micStream = stream;
    recording.ondataavailable = e => { if (e.data.size) parts.push(e.data); };
    recording.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      if (recorder === recording) { recorder = null; micStream = null; }
      if (!parts.length || !activeSocket(socket, attempt) || request !== micRequest) return;
      micUploading = true; $("talk").disabled = true;
      try {
        const bytes = await new Blob(parts).arrayBuffer();
        if (!activeSocket(socket, attempt) || request !== micRequest || !ready()) return;
        if (send({type: "audio_end", tp: recording.endedAt ?? performance.now()}, socket)) socket.send(bytes);
      } catch (error) { if (activeSocket(socket, attempt)) permissionNotice("voice", error); }
      finally {
        if (request === micRequest && activeSocket(socket, attempt)) {
          micUploading = false; $("talk").disabled = !ready() || !sessionStatus?.asr;
        }
      }
    };
    recording.onerror = error => {
      if (request === micRequest && activeSocket(socket, attempt)) {
        cancelSpeech(); permissionNotice("voice", error.error || error);
      }
    };
    recording.start();
    const requestId = nextSubmissionId();
    if (!send({type: "speech_start", request_id: requestId}, socket)) throw new Error("Unable to start voice input");
    productEvent("submitted", {request_id: requestId, activity: false});
    duck(true); $("talk").classList.add("recording"); $("talk").textContent = tr("voice.release", "松开发送");
  } catch (error) {
    stream?.getTracks().forEach(track => track.stop());
    if (request === micRequest && activeSocket(socket, attempt)) {
      cancelSpeech(); permissionNotice("voice", error);
    }
  }
};
function endSpeech(cancel = false) {
  if (cancel) { cancelSpeech(); return; }
  if (!micPressed) return;
  micPressed = false;
  duck(false);
  if (recorder?.state === "recording") { recorder.endedAt = performance.now(); recorder.stop(); }
  else micRequest++;  // releasing while permission is pending cancels that request
  resetTalkButton();
}
$("talk").onpointerup = () => endSpeech();
$("talk").onpointerleave = event => { if (!$("talk").hasPointerCapture?.(event?.pointerId)) endSpeech(); };
$("talk").onpointercancel = () => endSpeech();
$("talk").onkeydown = event => {
  if ([" ", "Enter"].includes(event.key) && !event.repeat) { event.preventDefault(); $("talk").onpointerdown(); }
};
$("talk").onkeyup = event => {
  if ([" ", "Enter"].includes(event.key)) { event.preventDefault(); endSpeech(); }
};
$("talk").onblur = () => { if (micPressed) endSpeech(); };
addEventListener("blur", () => { if (micPressed || recorder) endSpeech(); });
function sendText(v, lessonContext, requestId) {
  v = (v ?? $("text").value).trim(); if (!v || !ready()) return false;
  const activity = requestId != null;
  if (activity && (typeof requestId !== "string" || !requestId.trim() || requestId.length > 64)) return false;
  const packet = {type: "text", text: v, tp: performance.now(), request_id: activity ? requestId : nextSubmissionId()};
  if (lessonContext && typeof lessonContext.subject === "string" && lessonContext.subject.trim() &&
      Number.isInteger(lessonContext.grade) && lessonContext.grade >= 1 && lessonContext.grade <= 12 &&
      typeof lessonContext.topic === "string" && lessonContext.topic.trim()) {
    packet.lesson_context = {subject: lessonContext.subject.trim(), grade: lessonContext.grade, topic: lessonContext.topic.trim()};
  }
  if (!send(packet)) {
    notice("session.sendFailed", "消息还没有发出去，请重新连接后再试。"); return false;
  }
  productEvent("submitted", {request_id: packet.request_id, activity});
  chat("user", v); $("text").value = ""; return true;
}
$("send").onclick = () => sendText();
$("text").onkeydown = e => { if (e.key === "Enter" && !e.isComposing && !e.shiftKey) { e.preventDefault(); sendText(); } };
addEventListener("pagehide", () => { $("disconnect").onclick(); cancelSpeech(); camOff(false); });
window.LiveAgentMedia = {...window.LiveAgentMedia, refreshLanguage, restoreExercise: showExercise, renderExerciseQuestion,
  avatarState: () => ({renderer: avatarActive() ? "mesh" : "video", model: avatarActive() ? TEACHER_AVATAR_MODEL : null,
    epoch: avatarEpoch, ...(avatarLastState || {})}),
  captureAvatar: () => { try { return avatarActive() ? teacherAvatar.capture() : null; } catch (_) { return null; } }};
refreshLanguage();

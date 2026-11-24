const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const editions = ["primary", "secondary", "university", "live"];
let preferredEdition = "secondary";
try { preferredEdition = localStorage.getItem("liveAgent.edition") || preferredEdition; } catch (_) {}
const requestedEdition = new URLSearchParams(location.search).get("edition");
const edition = editions.includes(requestedEdition) ? requestedEdition : editions.includes(preferredEdition) ? preferredEdition : "secondary";
try { localStorage.setItem("liveAgent.edition", edition); } catch (_) {}
const english = edition === "university";
const zh = {
  skip:"跳到主要内容", brand:"芽学", courses:"探索课程", brandSub:"陪你把知识学明白", space:"我的学习空间", classroom:"私人课堂", profile:"学习档案", recordings:"课堂记录",
  sideTitle:"每个人，都有自己的节奏。", sideText:"告诉老师你学到了哪里，从这里继续向前。", editionLabel:"学习阶段", privateSpace:"一对一学习 · 本地演示", back:"返回课堂 ↗", eyebrow:"A LITTLE ABOUT YOU", title:"让学习更适合你。", intro:"补充你的年级和学习情况，老师会用更合适的例子、节奏和练习陪你学习。", demo:"演示档案", studentLabel:"当前学生", privacy:"档案只用于一对一学习。掌握度是未经校准的估计，可以手动修正。",
  basicKicker:"先认识一下", basic:"基本信息", nameLabel:"怎么称呼你", gradeLabel:"年级 / 学习阶段", namePlaceholder:"如 小明", gradePlaceholder:"如 初二", basicHelp:"只填写你愿意分享的信息。不确定的内容可以留空。", examKicker:"找到下一步", exams:"考试与测验", addExam:"＋ 添加成绩", examHelp:"写下最近的测验成绩。需要再练习的知识点，用逗号或顿号分开。", conceptKicker:"看看学习进展", concepts:"知识点掌握度", estimate:"估计值", conceptHelp:"这些估计来自测验、练习或手动调整，不是正式评定。滑块可以用方向键调整。",
  weak:"值得再练习", partial:"正在理解", mastered:"比较熟悉", unknown:"还未评估", newConcept:"添加知识点", subject:"学科", masteryInput:"估计掌握度 %", conceptPlaceholder:"如 因式分解", subjectPlaceholder:"如 数学", masteryPlaceholder:"可留空", addConcept:"＋ 添加", newConceptHelp:"留空表示还未评估；填写后作为手动估计保存。", historyKicker:"一步一步的积累", history:"最近练习", time:"时间", concept:"知识点", result:"结果", question:"题目", answer:"你的回答", dataOptions:"管理练习记录", clearHistory:"保存时清空练习记录、练习次数、错因和练习得出的掌握度",
  guideTitle:"从你现在的位置出发。", guideText:"成绩是线索，不是标签。告诉老师哪里有点难，让下一次练习更有帮助。", guideTipTitle:"小提示", guideTip:"课堂中的练习结果会自动更新这里。手动改动后，记得点击「保存档案」。", guideLink:"去课堂试一试 ↗", retry:"重新载入", reset:"恢复初始档案", discard:"放弃修改", save:"保存档案", loading:"载入中…", dirty:"有未保存的修改", noStudents:"暂时没有可用的学习档案。请联系这台服务的管理者。", loaded:"已载入 · 版本 {version}", initial:" · 初始演示内容，尚未保存", meta:"档案 {id} · 版本 {version}", gradeEmpty:"还没有填写学习阶段", noExams:"还没有测验成绩。需要时再添加就好。", examName:"测验名称", examPlaceholder:"如 期中考试", date:"日期", score:"分数（必填）", full:"满分（必填）", subjectRequired:"学科（必填）", weakConcepts:"需要再练习的知识点", weakPlaceholder:"如 因式分解、浮力", removeExam:"删除这次测验", remove:"删除", manual:"手动设定", exerciseSource:"练习 {correct}/{attempts} 对", examSource:"据测验失分推断", clearing:"保存时清除估计", manualUnsaved:"手动估计（未保存）", noConcepts:"还没有知识点记录。做一次练习，或者添加你想学的内容。", masteryLabel:"{name}的估计掌握度", sliderTitle:"方向键可调整估计掌握度", latestError:"最近的错因：", clear:"清除", clearTitle:"清除手动估计；若有相关测验，将使用测验推断的估计", undo:"撤销", correct:"正确", tryAgain:"需要再练习", noHistory:"还没有练习记录。你的课堂练习会出现在这里。", badExam:"请为每次测验填写学科、分数和满分。", saving:"正在保存…", saved:"已保存 · 版本 {version} · 课堂会同步更新", conflict:"档案在你编辑时更新了。请点击「放弃修改」载入最新内容，再重新编辑。", saveFailed:"保存失败：{message}", loadFailed:"暂时无法载入档案：{message}", resetConfirm:"恢复「{name}」的初始档案？保存的成绩、估计掌握度和练习记录都会删除。", resetDone:"已恢复初始档案", resetFailed:"恢复失败：{message}", switchConfirm:"有未保存的修改。继续会放弃这些修改。", refreshed:"已自动更新课堂练习 · 版本 {version}", navLabel:"主导航"
};
const en = {
  skip:"Skip to content", brand:"YāLearn", courses:"Explore topics", brandSub:"A little clearer, every day", space:"My learning space", classroom:"Live classroom", profile:"Learning profile", recordings:"Session recordings", sideTitle:"Your pace. Your next step.", sideText:"Help your tutor understand where you are, and where you want to go.", editionLabel:"Learning edition", privateSpace:"One-to-one learning · Local demo", back:"Back to study room ↗", eyebrow:"A LITTLE ABOUT YOU", title:"Make this space yours.", intro:"Share your study stage and recent work so your tutor can adapt the examples, pace and practice.", demo:"Demo profile", studentLabel:"Active learner", privacy:"Profiles are used only in private sessions. Mastery values are uncalibrated estimates that you can adjust.",
  basicKicker:"Start with the essentials", basic:"About you", nameLabel:"Preferred name", gradeLabel:"School grade (optional)", namePlaceholder:"Your name", gradePlaceholder:"Choose a school grade, or leave blank", basicHelp:"Only Chinese school grades are supported in profiles. Leave the grade blank if none applies. This edition changes the interface language; teaching and the current catalogue remain Chinese school subjects.", examKicker:"Find your next step", exams:"Assessments & results", addExam:"＋ Add result", examHelp:"Add a recent assessment. Separate topics that need practice with commas.", conceptKicker:"A view of your progress", concepts:"Topic understanding", estimate:"Estimated", conceptHelp:"These estimates come from assessments, practice or manual adjustments. They are not formal evaluations. Use arrow keys to adjust sliders.",
  weak:"Needs practice", partial:"Developing", mastered:"More comfortable", unknown:"Not assessed", newConcept:"New topic", subject:"Subject", masteryInput:"Estimated mastery %", conceptPlaceholder:"e.g. Derivatives", subjectPlaceholder:"e.g. Maths", masteryPlaceholder:"Optional", addConcept:"＋ Add", newConceptHelp:"Leave blank for not assessed. A value is saved as a manual estimate.", historyKicker:"Build on your practice", history:"Recent practice", time:"When", concept:"Topic", result:"Result", question:"Question", answer:"Your answer", dataOptions:"Manage practice data", clearHistory:"Clear practice history, attempt counts, error notes and practice-derived mastery when saving",
  guideTitle:"Start where you are.", guideText:"A result is a clue, not a label. Let your tutor know what feels difficult so the next practice can help.", guideTipTitle:"Good to know", guideTip:"Classroom practice updates this profile automatically. Save your profile after making manual changes.", guideLink:"Return to your study room ↗", retry:"Try again", reset:"Restore initial profile", discard:"Discard changes", save:"Save profile", loading:"Loading profile…", dirty:"You have unsaved changes", noStudents:"No learning profiles are available. Ask the operator of this service to enable one.", loaded:"Profile loaded · Version {version}", initial:" · Initial demo content, not saved yet", meta:"Profile {id} · Version {version}", gradeEmpty:"Study stage not set", noExams:"No assessments yet. Add a result whenever it helps.", examName:"Assessment name", examPlaceholder:"e.g. Midterm", date:"Date", score:"Score (required)", full:"Maximum (required)", subjectRequired:"Subject (required)", weakConcepts:"Topics to revisit", weakPlaceholder:"e.g. Derivatives, vectors", removeExam:"Remove this assessment", remove:"Remove", manual:"Manual estimate", exerciseSource:"Practice: {correct}/{attempts} correct", examSource:"Inferred from assessment gaps", clearing:"Estimate clears when saved", manualUnsaved:"Manual estimate (unsaved)", noConcepts:"No topics yet. Try a practice question or add something you want to study.", masteryLabel:"Estimated mastery of {name}", sliderTitle:"Use arrow keys to adjust estimated mastery", latestError:"Recent error: ", clear:"Clear", clearTitle:"Clear the manual estimate; a relevant assessment estimate may still apply", undo:"Undo", correct:"Correct", tryAgain:"Try again", noHistory:"No practice yet. Your classroom answers will appear here.", badExam:"Enter a subject, score and maximum for every assessment.", saving:"Saving your profile…", saved:"Saved · Version {version} · Your session will update", conflict:"Your profile changed while you were editing. Select “Discard changes” to load the latest version, then edit again.", saveFailed:"Could not save: {message}", loadFailed:"Could not load your profile: {message}", resetConfirm:"Restore the initial profile for “{name}”? Saved results, mastery estimates and practice history will be deleted.", resetDone:"Initial profile restored", resetFailed:"Could not restore: {message}", switchConfirm:"You have unsaved changes. Continuing will discard them.", refreshed:"Classroom practice updated · Version {version}", navLabel:"Main navigation"
};
const copy = english ? en : {...zh, ...(edition === "primary" ? {
  classroom:"我的小课堂", profile:"我的学习卡", recordings:"看看课堂记录", courses:"找点新知识", title:"学习小档案，从这里开始。", eyebrow:"我的学习小档案", intro:"让老师知道你读几年级、哪些地方还想练一练。遇到不会填的，可以请爸爸妈妈帮忙。", sideTitle:"一点点，也会变成大进步。", sideText:"不着急，我们从你会的地方一起出发。", nameLabel:"老师怎么称呼你", gradePlaceholder:"如 小学四年级", basicKicker:"让老师认识你", conceptPlaceholder:"如 分数加减法", weakPlaceholder:"如 分数加减法、面积", guideTitle:"不会也没关系。", guideText:"告诉老师你哪里卡住了，一起换个办法，再试一次。", guideTip:"可以和家长一起填写。课堂练习后，老师会自动更新档案；自己改动后记得保存。"
} : {})};
function t(key, values = {}) { return String(copy[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? "")); }
const LEVEL = {mastered:t("mastered"), partial:t("partial"), weak:t("weak"), unknown:t("unknown")};
const SCHOOL_GRADES = ["小学一年级","小学二年级","小学三年级","小学四年级","小学五年级","小学六年级","初一","初二","初三","高一","高二","高三"];
const GRADES = english ? SCHOOL_GRADES : edition === "primary" ? SCHOOL_GRADES.slice(0,6) : SCHOOL_GRADES.slice(6);
document.documentElement.lang = english ? "en" : "zh-CN";
document.documentElement.dataset.edition = edition;
document.title = t("profile") + " · " + t("brand");
document.querySelectorAll("[data-copy]").forEach(el => { el.textContent = t(el.dataset.copy); });
document.querySelectorAll("[data-placeholder]").forEach(el => { el.placeholder = t(el.dataset.placeholder); });
$("mainNav").setAttribute("aria-label", t("navLabel"));
$("editionSelect").setAttribute("aria-label", t("editionLabel"));
$("student").setAttribute("aria-label", t("studentLabel"));
$("identityCard").setAttribute("aria-label", t("profile"));
$("editionSelect").value = edition;
$("editionBadge").textContent = english ? "University & adult" : edition === "primary" ? "小学版" : "中学版";
$("status").textContent = t("loading");
$("grades").innerHTML = GRADES.map(g => `<option value="${g}"${english ? ` label="Grade ${SCHOOL_GRADES.indexOf(g) + 1} · ${g}"` : ""}>`).join("");
let sid = new URLSearchParams(location.search).get("student") || "";
let server = null;          // the profile as last loaded
let exams = [];             // editable copy
let edits = new Map();      // concept name -> {mastery?, delete?, subject?}
let dirty = false;
let state = "loading";
let generation = 0;        // invalidates responses from an earlier load or write

function canEdit() { return state === "ready" && server?.id === sid; }
function isCurrent(requestGeneration, requestSid) { return generation === requestGeneration && sid === requestSid; }

function setStatus(text, cls) { const el = $("status"); el.textContent = text; el.className = "status " + (cls || ""); }
function markDirty() {
  if (!canEdit()) return;
  dirty = true; $("save").disabled = false; $("discard").disabled = false;
  setStatus(t("dirty"), "dirty");
}
function clean() { dirty = false; $("save").disabled = true; $("discard").disabled = true; }

const api = window.LiveAgentAPI.fetchJson;

function pageLink(path, selectedEdition = edition) {
  const query = new URLSearchParams({edition:selectedEdition});
  if (sid) query.set("student", sid);
  const [route, hash] = path.split("#");
  return route + "?" + query.toString() + (hash ? "#" + hash : "");
}
function updateLinks() {
  const paths = {classroom:"/", courses:"/#courses", profile:"/profile", recordings:"/traces"};
  document.querySelectorAll("[data-link]").forEach(el => { el.href = pageLink(paths[el.dataset.link]); });
  $("back").href = pageLink("/");
}
function setReady(ready) {
  document.querySelectorAll("[data-profile-control], #exams input, #exams button, #concepts input, #concepts button").forEach(el => { el.disabled = !ready; });
  $("save").disabled = !ready || !dirty;
  $("discard").disabled = !ready || !dirty;
}
function clearProfileView(message = t("loading")) {
  server = null; exams = []; edits = new Map(); clean();
  ["name", "grade", "newName", "newSubject", "newMastery"].forEach(id => { $(id).value = ""; });
  $("clearHist").checked = false; $("meta").textContent = "";
  $("profileName").textContent = message; $("profileGrade").textContent = "";
  $("avatar").textContent = "…"; $("demoBadge").hidden = true;
  $("exams").innerHTML = $("concepts").innerHTML = `<p class="empty">${esc(message)}</p>`;
  $("hist").innerHTML = `<tr><td colspan="5" class="empty">${esc(message)}</td></tr>`;
}
$("editionSelect").onchange = () => {
  if (dirty && !confirm(t("switchConfirm"))) { $("editionSelect").value = edition; return; }
  const next = $("editionSelect").value;
  if (!editions.includes(next)) return;
  try { localStorage.setItem("liveAgent.edition", next); } catch (_) {}
  location.href = pageLink("/profile", next);
};
updateLinks();


async function loadList() {
  const requestGeneration = ++generation;
  state = "loading"; setReady(false); clearProfileView(); setStatus(t("loading"));
  try {
    const {students} = await api("/api/students");
    if (generation !== requestGeneration) return false;
    if (!students.length) { state = "failed"; clearProfileView(t("profile")); setStatus(t("noStudents"), "err"); return false; }
    if (!students.some(s => s.id === sid)) sid = students[0].id;
    $("student").innerHTML = students.map(s =>
      `<option value="${esc(s.id)}"${s.id === sid ? " selected" : ""}>${esc(s.name || s.id)}${s.grade ? " · " + esc(s.grade) : ""} (${esc(s.id)})</option>`).join("");
    return await load();
  } catch (err) {
    if (generation === requestGeneration) loadError(err);
    return false;
  }
}

async function load() {
  const requestSid = sid, requestGeneration = ++generation;
  state = "loading"; setReady(false); clearProfileView(); setStatus(t("loading"));
  history.replaceState(null, "", pageLink("/profile"));
  updateLinks();
  try {
    const loaded = await api(`/api/students/${encodeURIComponent(requestSid)}`);
    if (!isCurrent(requestGeneration, requestSid)) return false;
    if (loaded.id !== requestSid) throw new Error("Profile identity mismatch");
    server = loaded;
    exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
    edits = new Map(); $("clearHist").checked = false;
    state = "ready"; render(); clean(); setReady(true);
    $("retryLoad").hidden = true;
    setStatus(t("loaded", {version:server.version}) + (server.saved ? "" : t("initial")), "ok");
    return true;
  } catch (err) {
    if (isCurrent(requestGeneration, requestSid)) loadError(err);
    return false;
  }
}

function render() {
  $("name").value = server.name || ""; $("grade").value = server.grade || "";
  $("meta").textContent = t("meta", {id:server.id, version:server.version});
  $("profileName").textContent = server.name || t("profile");
  $("profileGrade").textContent = server.grade || t("gradeEmpty");
  $("avatar").textContent = Array.from(server.name || (english ? "L" : "同"))[0];
  $("demoBadge").hidden = server.id !== "demo" && !!server.saved;
  renderExams(); renderConcepts(); renderHistory(); updateLinks();
}

function renderExams() {
  const el = $("exams");
  if (!exams.length) { el.innerHTML = `<div class="empty">${t("noExams")}</div>`; return; }
  el.innerHTML = exams.map((e, i) => {
    const pct = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
    return `<div class="exam" data-i="${i}">
      <label>${t("subjectRequired")} <input aria-describedby="examHelp" data-k="subject" value="${esc(e.subject)}" maxlength="12"></label>
      <label>${t("examName")} <input data-k="name" value="${esc(e.name)}" maxlength="20" placeholder="${t("examPlaceholder")}"></label>
      <label>${t("date")} <input data-k="date" type="date" value="${esc(e.date)}"></label>
      <label>${t("score")} <input data-k="score" type="number" min="0" step="0.5" value="${esc(e.score)}"></label>
      <label>${t("full")} <input data-k="full" type="number" min="1" step="1" value="${esc(e.full)}"></label>
      <label>${t("weakConcepts")} <input aria-describedby="examHelp" data-k="weak" value="${esc(e.weak)}" placeholder="${t("weakPlaceholder")}"></label>
      <span class="pct">${pct}</span>
      <button class="ghost" data-del="${i}" aria-label="${t("removeExam")}">${t("remove")}</button></div>`;
  }).join("");
}
$("exams").addEventListener("input", (ev) => {
  if (!canEdit()) return;
  const row = ev.target.closest(".exam"), k = ev.target.dataset.k;
  if (!row || !k) return;
  const e = exams[+row.dataset.i];
  e[k] = (k === "score" || k === "full") ? (ev.target.value === "" ? "" : +ev.target.value) : ev.target.value;
  if (k === "score" || k === "full") row.querySelector(".pct").textContent = e.full > 0 && e.score !== "" ? Math.round(100 * e.score / e.full) + "%" : "";
  markDirty();
});
$("exams").addEventListener("click", (ev) => {
  if (!canEdit()) return;
  const i = ev.target.dataset.del;
  if (i === undefined) return;
  exams.splice(+i, 1); renderExams(); markDirty();
});
$("addExam").onclick = () => {
  if (!canEdit()) return;
  exams.push({subject: "", name: "", date: new Date().toISOString().slice(0, 10), score: "", full: 100, weak: ""});
  renderExams(); markDirty();
  $("exams").lastElementChild.querySelector("input").focus();
};

function srcText(c) {
  if (c.source === "manual") return `<span class="src manual">${t("manual")}</span>`;
  if (c.source === "exercise") return `<span class="src">${t("exerciseSource", {correct:c.correct, attempts:c.attempts})}</span>`;
  if (c.source === "exam") return `<span class="src">${t("examSource")}</span>`;
  return `<span class="src">${t("unknown")}</span>`;
}
function levelOf(m, c) {
  if (m == null) return "unknown";
  if (m >= 0.8) return (c.attempts >= 3 || c.source === "manual" || edits.get(c.name)?.mastery != null) ? "mastered" : "partial";
  return m >= 0.5 ? "partial" : "weak";
}
function renderConcepts() {
  const el = $("concepts");
  const list = server.concepts.slice();
  for (const [name, e] of edits) if (e.added && !list.some(c => c.name === name))
    list.push({name, subject: e.subject || "", mastery: null, source: null, attempts: 0, correct: 0, notes: []});
  if (!list.length) { el.innerHTML = `<div class="empty">${t("noConcepts")}</div>`; return; }
  el.innerHTML = list.map(c => {
    const e = edits.get(c.name) || {};
    const m = "mastery" in e ? e.mastery : c.mastery;
    const lvl = levelOf(m, c);
    const pct = m == null ? "–" : (c.source === "exam" && !("mastery" in e) ? "≈" : "") + Math.round(m * 100) + "%";
    const src = "mastery" in e ? (e.mastery == null ? `<span class="src">${t("clearing")}</span>` : `<span class="src manual">${t("manualUnsaved")}</span>`) : srcText(c);
    return `<div class="concept ${lvl}${e.delete ? " removed" : ""}${Object.keys(e).length ? " changed" : ""}" data-name="${esc(c.name)}">
      <span class="name">${esc(c.name)}</span>
      <span class="muted">${esc(c.subject || "")}</span>
      <span class="grow"><input type="range" min="0" max="100" value="${m == null ? 50 : Math.round(m * 100)}" aria-label="${esc(t("masteryLabel", {name:c.name}))}" aria-describedby="conceptHelp"
               title="${t("sliderTitle")}" aria-valuetext="${m == null ? t("unknown") : Math.round(m * 100) + '% · ' + t("estimate")}"></span>
      <span class="v">${pct}</span>
      <span class="grow">${src}${c.notes && c.notes.length ? `<div class="muted">${t("latestError")}${esc(c.notes[c.notes.length - 1])}</div>` : ""}
        <div class="muted">${LEVEL[lvl]}</div></span>
      <span class="row" style="gap:4px">
        <button class="ghost" data-act="clear" title="${t("clearTitle")}">${t("clear")}</button>
        <button class="ghost" data-act="${e.delete ? "undo" : "delete"}">${t(e.delete ? "undo" : "remove")}</button></span></div>`;
  }).join("");
}
$("concepts").addEventListener("input", (ev) => {
  if (!canEdit()) return;
  if (ev.target.type !== "range") return;
  const name = ev.target.closest(".concept").dataset.name;
  edits.set(name, {...(edits.get(name) || {}), mastery: +ev.target.value / 100, delete: false});
  const row = ev.target.closest(".concept");
  row.querySelector(".v").textContent = ev.target.value + "%";
  markDirty();
});
$("concepts").addEventListener("change", (ev) => { if (canEdit() && ev.target.type === "range") renderConcepts(); });
$("concepts").addEventListener("click", (ev) => {
  if (!canEdit()) return;
  const act = ev.target.dataset.act; if (!act) return;
  const name = ev.target.closest(".concept").dataset.name, e = edits.get(name) || {};
  if (act === "clear") edits.set(name, {...e, mastery: null, delete: false});
  if (act === "delete") edits.set(name, {...e, delete: true});
  if (act === "undo") { const {delete: _, ...rest} = e; Object.keys(rest).length ? edits.set(name, rest) : edits.delete(name); }
  renderConcepts(); markDirty();
});
$("addConcept").onclick = () => {
  if (!canEdit()) return;
  const name = $("newName").value.trim(); if (!name) { $("newName").focus(); return; }
  const raw = $("newMastery").value.trim();
  const e = {added: true, subject: $("newSubject").value.trim()};
  if (raw !== "") e.mastery = Math.max(0, Math.min(100, +raw)) / 100;
  edits.set(name, e);
  $("newName").value = ""; $("newMastery").value = "";
  renderConcepts(); markDirty();
};

function renderHistory() {
  const h = server.history || [];
  $("hist").innerHTML = h.length ? h.map(x => `<tr><td>${esc(x.t)}</td><td>${esc(x.concept)}</td>
      <td class="${x.correct ? "ok" : "bad"}">${t(x.correct ? "correct" : "tryAgain")}</td><td>${esc(x.question)}</td><td>${esc(x.answer)}</td></tr>`).join("")
    : `<tr><td colspan="5" class="empty">${t("noHistory")}</td></tr>`;
}

["name", "grade"].forEach(id => $(id).addEventListener("input", markDirty));
$("clearHist").addEventListener("change", markDirty);

$("save").onclick = async () => {
  if (!canEdit() || !dirty) return;
  const requestSid = server.id;
  const bad = exams.find(e => !String(e.subject).trim() || e.score === "" || !(e.full > 0));
  if (bad) { setStatus(t("badExam"), "err"); return; }
  const body = {
    version: server.version, name: $("name").value.trim(), grade: $("grade").value.trim(),
    exams: exams.map(e => ({subject: e.subject.trim(), name: e.name.trim(), date: e.date, score: +e.score, full: +e.full,
                            weak: String(e.weak).split(/[、,，;；\s]+/).filter(Boolean)})),
    concepts: [...edits].map(([name, e]) => ({name, ...(e.delete ? {delete: true} : {}),
      ...("mastery" in e && !e.delete ? {mastery: e.mastery} : {}), ...(e.added ? {subject: e.subject} : {})})),
    clear_history: $("clearHist").checked,
  };
  const requestGeneration = ++generation;
  state = "saving"; setReady(false); setStatus(t("saving"));
  try {
    const saved = await api(`/api/students/${encodeURIComponent(requestSid)}`, {method: "PUT", body: JSON.stringify(body)});
    if (!isCurrent(requestGeneration, requestSid)) return;
    if (saved.id !== requestSid) throw new Error("Profile identity mismatch");
    server = saved;
    exams = server.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
    edits = new Map(); $("clearHist").checked = false; state = "ready"; render(); clean(); setReady(true);
    setStatus(t("saved", {version:server.version}), "ok");
  } catch (err) {
    if (!isCurrent(requestGeneration, requestSid)) return;
    state = "ready"; setReady(true);
    if (err.status === 409) setStatus(t("conflict"), "err");
    else setStatus(t("saveFailed", {message:err.message}), "err");
  }
};
$("discard").onclick = () => { if (canEdit()) return load(); };
$("reset").onclick = async () => {
  if (!canEdit()) return;
  if (!confirm(t("resetConfirm", {name:server.name || sid}))) return;
  const requestSid = server.id, requestGeneration = ++generation, version = server.version;
  state = "resetting"; setReady(false); setStatus(t("loading"));
  try {
    await api(`/api/students/${encodeURIComponent(requestSid)}/reset`, {method: "POST", body: JSON.stringify({version})});
    if (!isCurrent(requestGeneration, requestSid)) return;
    const reloading = load(), reloadGeneration = generation;
    if (await reloading && isCurrent(reloadGeneration, requestSid)) setStatus(t("resetDone"), "ok");
  } catch (err) {
    if (!isCurrent(requestGeneration, requestSid)) return;
    state = "ready"; setReady(true); setStatus(t("resetFailed", {message:err.message}), "err");
  }
};
$("student").onchange = async () => {
  if (dirty && !confirm(t("switchConfirm"))) { $("student").value = sid; return; }
  sid = $("student").value; await load();
};
window.addEventListener("beforeunload", (ev) => { if (dirty) { ev.preventDefault(); ev.returnValue = ""; } });

// while nothing is being edited, follow changes made by a running lesson (graded exercises)
setInterval(async () => {
  if (dirty || !canEdit() || document.hidden) return;
  const refreshSid = server.id, refreshProfile = server, refreshGeneration = generation;
  try {
    const now = await api(`/api/students/${encodeURIComponent(refreshSid)}`);
    // Fetching can overlap edits, saves, student changes or another refresh.
    if (dirty || !canEdit() || !isCurrent(refreshGeneration, refreshSid) || server !== refreshProfile || document.hidden || now.id !== refreshSid) return;
    if (now.version !== server.version) { server = now; exams = now.exams.map(e => ({...e, weak: (e.weak || []).join("、")}));
      render(); setStatus(t("refreshed", {version:now.version}), "ok"); }
  } catch (_) { /* offline for a moment: try again next time */ }
}, 5000);

function loadError(e) { state = "failed"; setReady(false); clearProfileView(t("profile")); setStatus(t("loadFailed", {message:e.message}), "err"); $("retryLoad").hidden = false; }
$("retryLoad").onclick = loadList;
loadList();

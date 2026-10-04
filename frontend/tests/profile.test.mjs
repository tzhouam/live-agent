import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/assets/profile.js", import.meta.url), "utf8");

function profile(version, name = "Saved name", id = "demo") {
  return {id, version, name, grade: "初二", saved: true,
    exams: [{subject: "数学", name: "期中", date: "2026-10-01", score: 60, full: 100, weak: []}],
    concepts: [], history: []};
}

function editor({edition, storedEdition, confirm = () => true} = {}) {
  const elements = new Map(), requests = [], historyUrls = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: "", textContent: "", innerHTML: "", checked: false,
      listeners: new Map(),
      addEventListener(event, listener) { this.listeners.set(event, listener); },
      setAttribute(name, value) { this[name] = value; },
    });
    return elements.get(id);
  }
  let poll;
  for (const link of ["classroom", "courses", "profile", "recordings"])
    element(link + "Link").dataset = {link};
  const controls = ["name", "grade", "addExam", "newName", "newSubject", "newMastery", "addConcept", "clearHist", "reset", "examScore", "examDelete", "conceptSlider", "conceptDelete"];
  const document = {hidden: false, getElementById: element,
    documentElement: {dataset: {}}, querySelectorAll: selector =>
      selector.includes("[data-profile-control]") ? controls.map(element) :
      selector === "[data-link]" ? ["classroom", "courses", "profile", "recordings"].map(link => element(link + "Link")) : []};
  const context = vm.createContext({document,
    window: {addEventListener() {}, LiveAgentAPI: {fetchJson(path, opts) {
      // Leave the initial student-list request pending; tests supply a loaded editor.
      if (path === "/api/students") return new Promise(() => {});
      return new Promise((resolve, reject) => { requests.push({path, opts, resolve, reject}); });
    }}},
    location: {search: "?student=demo" + (edition ? "&edition=" + edition : "")}, URLSearchParams,
    localStorage: {getItem: () => storedEdition, setItem() {}},
    history: {replaceState(_state, _unused, url) { historyUrls.push(url); }}, confirm,
    setInterval(callback) { poll = callback; },
  });
  function run(code) { return vm.runInContext(code, context); }
  vm.runInContext(source, context);
  run(`server = ${JSON.stringify(profile(1))}; exams = server.exams.map(e => ({...e, weak: ""})); render(); clean();`);
  // Bootstrap the controlled fixture as a completed load, including its controls.
  run(`if (typeof state !== "undefined") state = "ready"; setReady(true);`);
  return {document, element, requests, historyUrls, run, poll: () => poll(),
    editName(value) {
      element("name").value = value;
      element("name").listeners.get("input")();
    },
    editExam(score) {
      const row = {dataset: {i: "0"}, querySelector: () => ({textContent: ""})};
      element("exams").listeners.get("input")({target: {
        dataset: {k: "score"}, value: String(score), closest: () => row,
      }});
    },
  };
}

test("a pending refresh preserves unsaved name and exam drafts", async () => {
  const page = editor(), pending = page.poll();
  page.editName("Unsaved name");
  page.editExam(95);
  page.requests[0].resolve(profile(2, "External name"));
  await pending;
  assert.equal(page.element("name").value, "Unsaved name");
  assert.equal(page.run("exams[0].score"), 95);
  assert.equal(page.run("dirty"), true);
  assert.equal(page.run("server.version"), 1);
  assert.match(page.element("status").textContent, /有未保存的修改/);
});

test("a refresh started before a successful save cannot replace the saved profile", async () => {
  const page = editor(), pending = page.poll();
  page.editName("Just saved name");
  const saving = page.element("save").onclick();
  assert.equal(page.requests[1].opts.method, "PUT");
  assert.equal(JSON.parse(page.requests[1].opts.body).name, "Just saved name");
  page.requests[1].resolve(profile(3, "Just saved name"));
  await saving;
  page.requests[0].resolve(profile(2, "Earlier external name"));
  await pending;
  assert.equal(page.element("name").value, "Just saved name");
  assert.equal(page.run("server.version"), 3);
  assert.equal(page.run("dirty"), false);
});

test("a refresh started before a manual reload cannot replace the loaded profile", async () => {
  const page = editor(), pending = page.poll();
  const reloading = page.element("discard").onclick();
  page.requests[1].resolve(profile(3, "Reloaded name"));
  await reloading;
  page.requests[0].resolve(profile(2, "Earlier external name"));
  await pending;
  assert.equal(page.element("name").value, "Reloaded name");
  assert.equal(page.run("server.version"), 3);
});

test("a pending refresh for the previous student is discarded during student switching", async () => {
  const page = editor(), pending = page.poll();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  assert.equal(page.requests[0].path, "/api/students/demo");
  assert.equal(page.requests[1].path, "/api/students/other");
  // The old refresh returns before the selected student's load finishes.
  page.requests[0].resolve(profile(2, "Previous student"));
  await pending;
  assert.equal(page.element("name").value, "");
  assert.equal(page.run("server"), null);
  page.requests[1].resolve(profile(1, "Other student", "other"));
  await switching;
  assert.equal(page.element("name").value, "Other student");
  assert.equal(page.run("server.id"), "other");
});

test("an older overlapping refresh cannot replace a newer refresh result", async () => {
  const page = editor(), first = page.poll(), second = page.poll();
  page.requests[1].resolve(profile(3, "Newer name"));
  await second;
  page.requests[0].resolve(profile(2, "Earlier name"));
  await first;
  assert.equal(page.element("name").value, "Newer name");
  assert.equal(page.run("server.version"), 3);
});

test("an unchanged, clean editor accepts a refresh with a newer version", async () => {
  const page = editor(), pending = page.poll();
  const updated = profile(2, "External name");
  updated.exams[0].score = 80;
  page.requests[0].resolve(updated);
  await pending;
  assert.equal(page.element("name").value, "External name");
  assert.equal(page.run("exams[0].score"), 80);
  assert.equal(page.run("server.version"), 2);
  assert.equal(page.run("dirty"), false);
  assert.match(page.element("status").textContent, /已自动更新/);
});

test("a pending refresh does not update an editor hidden before the response", async () => {
  const page = editor(), pending = page.poll();
  page.document.hidden = true;
  page.requests[0].resolve(profile(2, "External name"));
  await pending;
  assert.equal(page.element("name").value, "Saved name");
  assert.equal(page.run("server.version"), 1);
});

test("edition query overrides stored preference and localizes profile controls", () => {
  const page = editor({edition: "university", storedEdition: "primary"});
  assert.equal(page.document.documentElement.lang, "en");
  assert.equal(page.element("editionSelect").value, "university");
  assert.match(page.element("exams").innerHTML, /Assessment name/);
  assert.match(page.element("back").href, /edition=university/);
  assert.match(page.element("back").href, /student=demo/);
  assert.equal(page.element("demoBadge").hidden, false);
  assert.equal(page.element("profileName").textContent, "Saved name");
});

test("stored primary edition offers age-appropriate copy and grade suggestions", () => {
  const page = editor({storedEdition: "primary"});
  assert.equal(page.document.documentElement.lang, "zh-CN");
  assert.equal(page.run('t("title")'), "学习小档案，从这里开始。");
  assert.match(page.element("grades").innerHTML, /小学四年级/);
  assert.doesNotMatch(page.element("grades").innerHTML, /初二/);
  assert.equal(page.element("grade").value, "初二"); // Existing data survives an edition switch.
});

test("English grade suggestions submit canonical school values rather than unsupported adult stages", () => {
  const page = editor({edition: "university"});
  const values = [...page.element("grades").innerHTML.matchAll(/value="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(values, ["小学一年级","小学二年级","小学三年级","小学四年级","小学五年级","小学六年级","初一","初二","初三","高一","高二","高三"]);
  assert.match(page.element("grades").innerHTML, /label="Grade 8 · 初二"/);
  assert.doesNotMatch(page.element("grades").innerHTML, /University|Postgrad|Adult|Professional/);
  assert.match(page.run('t("basicHelp")'), /Leave the grade blank/);
});

test("invalid editions fall back to the Chinese secondary edition", () => {
  const page = editor({edition: "unknown", storedEdition: "unknown"});
  assert.equal(page.element("editionSelect").value, "secondary");
  assert.match(page.element("grades").innerHTML, /初二/);
  assert.equal(page.document.documentElement.lang, "zh-CN");
});

test("profile reload retains edition and student in the URL", async () => {
  const page = editor({edition: "university"});
  const reloading = page.element("discard").onclick();
  page.requests[0].resolve(profile(2));
  await reloading;
  assert.equal(page.historyUrls[0], "/profile?edition=university&student=demo");
});

test("version conflicts keep the English draft and explain recovery", async () => {
  const page = editor({edition: "university"});
  page.editName("Keep my draft");
  const saving = page.element("save").onclick();
  page.requests[0].reject(Object.assign(new Error("profile changed"), {status: 409}));
  await saving;
  assert.equal(page.element("name").value, "Keep my draft");
  assert.equal(page.run("dirty"), true);
  assert.equal(page.element("save").disabled, false);
  assert.match(page.element("status").textContent, /Discard changes/);
});

test("a slow learner switch cannot save the previous learner's fields to the new learner", async () => {
  const page = editor();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.editName("Previous learner draft");
  const saving = page.element("save").onclick();
  const writes = page.requests.filter(request => request.opts?.method === "PUT");
  // Settle an unsafe request so the failure records the actual target and body.
  for (const request of writes) request.resolve(profile(2, "Previous learner draft", "other"));
  await saving;
  assert.equal(writes.length, 0, JSON.stringify(writes.map(({path, opts}) => ({path, body:JSON.parse(opts.body)}))));
  page.requests[0].resolve(profile(1, "Other learner", "other"));
  await switching;
  assert.equal(page.element("name").value, "Other learner");
});

test("loading a learner disables static and generated edits, reset and save", async () => {
  const page = editor();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  for (const id of ["name", "grade", "addExam", "newName", "clearHist", "examScore", "examDelete", "conceptSlider", "conceptDelete", "reset", "save", "discard"])
    assert.equal(page.element(id).disabled, true, id);
  page.editExam(95);
  assert.equal(page.run("exams.length"), 0);
  await page.element("reset").onclick();
  assert.equal(page.requests.length, 1);
  page.requests[0].resolve(profile(1, "Other learner", "other"));
  await switching;
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.element("reset").disabled, false);
  assert.equal(page.element("save").disabled, true);
});

test("a stale learner load cannot replace the latest selection", async () => {
  const page = editor();
  page.element("student").value = "other";
  const first = page.element("student").onchange();
  page.element("student").value = "third";
  const second = page.element("student").onchange();
  page.requests[1].resolve(profile(3, "Third learner", "third"));
  await second;
  page.requests[0].resolve(profile(1, "Other learner", "other"));
  await first;
  assert.equal(page.run("server.id"), "third");
  assert.equal(page.element("name").value, "Third learner");
  assert.equal(page.historyUrls.at(-1), "/profile?edition=secondary&student=third");
});

test("a stale failed load cannot disable the latest learner or replace its status", async () => {
  const page = editor();
  page.element("student").value = "other";
  const first = page.element("student").onchange();
  page.element("student").value = "third";
  const second = page.element("student").onchange();
  page.requests[1].resolve(profile(3, "Third learner", "third"));
  await second;
  const status = page.element("status").textContent;
  page.requests[0].reject(new Error("old learner unavailable"));
  await first;
  assert.equal(page.element("name").value, "Third learner");
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.element("retryLoad").hidden, true);
  assert.equal(page.element("status").textContent, status);
});

test("a save completing after a switch cannot replace the new learner or its controls", async () => {
  const page = editor();
  page.editName("Saved previous learner");
  const saving = page.element("save").onclick();
  assert.equal(page.requests[0].path, "/api/students/demo");
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[1].resolve(profile(1, "Other learner", "other"));
  await switching;
  const status = page.element("status").textContent;
  page.requests[0].resolve(profile(2, "Saved previous learner"));
  await saving;
  assert.equal(page.run("server.id"), "other");
  assert.equal(page.element("name").value, "Other learner");
  assert.equal(page.element("status").textContent, status);
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.element("save").disabled, true);
});

test("an old save conflict cannot enable saving or show recovery for a different learner", async () => {
  const page = editor();
  page.editName("Previous draft");
  const saving = page.element("save").onclick();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[1].resolve(profile(1, "Other learner", "other"));
  await switching;
  const status = page.element("status").textContent;
  page.requests[0].reject(Object.assign(new Error("previous profile changed"), {status:409}));
  await saving;
  assert.equal(page.element("status").textContent, status);
  assert.equal(page.element("save").disabled, true);
});

test("a reset completing after a switch cannot reload or replace the new learner", async () => {
  const page = editor();
  const resetting = page.element("reset").onclick();
  assert.equal(page.requests[0].path, "/api/students/demo/reset");
  assert.equal(JSON.parse(page.requests[0].opts.body).version, 1);
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[1].resolve(profile(1, "Other learner", "other"));
  await switching;
  const status = page.element("status").textContent;
  page.requests[0].resolve(profile(2, "Reset previous learner"));
  await new Promise(resolve => setImmediate(resolve));
  // The old implementation wrongly starts a GET for the current selection.
  if (page.requests[2]) page.requests[2].resolve(profile(2, "Unwanted reload", "other"));
  await resetting;
  assert.equal(page.requests.length, 2);
  assert.equal(page.run("server.id"), "other");
  assert.equal(page.element("name").value, "Other learner");
  assert.equal(page.element("status").textContent, status);
});

test("a failed learner switch leaves old fields disabled until the target loads", async () => {
  const page = editor();
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[0].reject(new Error("temporarily offline"));
  await switching;
  assert.equal(page.element("name").disabled, true);
  assert.equal(page.element("save").disabled, true);
  assert.equal(page.element("reset").disabled, true);
  assert.equal(page.element("retryLoad").hidden, false);
  await page.element("save").onclick();
  assert.equal(page.requests.length, 1);
  const retrying = page.run("load()");
  assert.equal(page.requests[1].path, "/api/students/other");
  page.requests[1].resolve(profile(1, "Other learner", "other"));
  await retrying;
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.element("retryLoad").hidden, true);
});

test("a stalled learner switch immediately clears every visible record and the confirmed draft", async () => {
  const page = editor(), oldProfile = profile(1,"Private A name");
  oldProfile.concepts = [{name:"Private A concept",subject:"Private A subject",mastery:0.6,source:"manual",attempts:0,correct:0,notes:[]}];
  oldProfile.history = [{t:"Private A time",concept:"Private A concept",correct:false,question:"Private A question",answer:"Private A answer"}];
  page.run(`server = ${JSON.stringify(oldProfile)}; render();`);
  page.editName("Private A unsaved draft");
  page.element("newName").value = "Private A new concept";
  page.element("newSubject").value = "Private A new subject";
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  for (const id of ["name","grade","newName","newSubject","newMastery"])
    assert.equal(page.element(id).value,"",id);
  for (const id of ["exams","concepts","hist"])
    assert.doesNotMatch(page.element(id).innerHTML,/Private A|期中|数学/,id);
  assert.equal(page.element("meta").textContent,"");
  assert.equal(page.element("profileName").textContent,"载入中…");
  assert.equal(page.element("profileGrade").textContent,"");
  assert.equal(page.element("demoBadge").hidden,true);
  assert.equal(page.run("server"),null);
  assert.equal(page.run("dirty"),false);
  page.requests[0].resolve(profile(3,"Actual B name","other"));
  await switching;
  assert.equal(page.element("profileName").textContent,"Actual B name");
  assert.equal(page.element("name").value,"Actual B name");
});

test("a failed learner switch keeps the form and identity blank with usable retry", async () => {
  const page = editor({edition:"university"});
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  page.requests[0].reject(new Error("offline"));
  await switching;
  assert.equal(page.element("name").value,"");
  assert.equal(page.element("grade").value,"");
  assert.equal(page.element("meta").textContent,"");
  assert.doesNotMatch(page.element("profileName").textContent,/Saved name/);
  assert.equal(page.element("name").disabled,true);
  assert.equal(page.element("retryLoad").hidden,false);
  assert.equal(page.run("server"),null);
  for (const id of ["exams","concepts","hist"])
    assert.doesNotMatch(page.element(id).innerHTML,/期中|数学|Saved name/,id);
  const retrying = page.run("load()");
  page.requests[1].resolve(profile(2,"Actual B name","other"));
  await retrying;
  assert.equal(page.element("name").value,"Actual B name");
  assert.equal(page.element("name").disabled,false);
});

test("selected learner navigation updates before a pending GET and stays current when it fails", async () => {
  const page = editor({edition:"university"});
  assert.equal(page.element("classroomLink").href,"/?edition=university&student=demo");
  page.element("student").value = "other";
  const switching = page.element("student").onchange();
  assert.equal(page.requests[0].path,"/api/students/other");
  assert.equal(page.historyUrls.at(-1),"/profile?edition=university&student=other");
  assert.equal(page.element("classroomLink").href,"/?edition=university&student=other");
  assert.equal(page.element("recordingsLink").href,"/traces?edition=university&student=other");
  assert.equal(page.element("back").href,"/?edition=university&student=other");
  page.requests[0].reject(new Error("controlled profile failure"));
  await switching;
  assert.equal(page.historyUrls.at(-1),"/profile?edition=university&student=other");
  assert.equal(page.element("classroomLink").href,"/?edition=university&student=other");
  assert.equal(page.element("recordingsLink").href,"/traces?edition=university&student=other");
});

test("declining to discard a draft keeps the current learner and sends no load", async () => {
  const page = editor({confirm: () => false});
  page.editName("Keep this draft");
  page.element("student").value = "other";
  await page.element("student").onchange();
  assert.equal(page.run("sid"), "demo");
  assert.equal(page.element("student").value, "demo");
  assert.equal(page.element("name").value, "Keep this draft");
  assert.equal(page.run("dirty"), true);
  assert.equal(page.requests.length, 0);
  assert.equal(page.historyUrls.length,0);
  assert.equal(page.element("classroomLink").href,"/?edition=secondary&student=demo");
  assert.equal(page.element("recordingsLink").href,"/traces?edition=secondary&student=demo");
});

test("a pending save freezes edits and prevents a second write", async () => {
  const page = editor();
  page.editName("Saved name draft");
  const saving = page.element("save").onclick();
  for (const id of ["name", "grade", "examScore", "examDelete", "conceptSlider", "conceptDelete", "reset", "save", "discard"])
    assert.equal(page.element(id).disabled, true, id);
  page.editExam(95);
  assert.equal(page.run("exams[0].score"), 60);
  await page.element("save").onclick();
  assert.equal(page.requests.length, 1);
  page.requests[0].resolve(profile(2, "Saved name draft"));
  await saving;
  assert.equal(page.element("name").value, "Saved name draft");
  assert.equal(page.element("name").disabled, false);
  assert.equal(page.run("dirty"), false);
});

test("resetting the active learner uses its version and restores the loaded profile", async () => {
  const page = editor();
  page.editName("Draft to discard");
  const resetting = page.element("reset").onclick();
  page.requests[0].resolve(profile(2, "Reset learner"));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(page.requests[1].path, "/api/students/demo");
  page.requests[1].resolve(profile(2, "Reset learner"));
  await resetting;
  assert.equal(page.element("name").value, "Reset learner");
  assert.equal(page.run("dirty"), false);
  assert.equal(page.element("save").disabled, true);
  assert.equal(page.element("reset").disabled, false);
  assert.match(page.element("status").textContent, /已恢复初始档案/);
});

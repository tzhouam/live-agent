import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../public/assets/traces.js", import.meta.url), "utf8");
class Element {
  constructor(tag = "div") { this.tagName = tag; this.children = []; this.hidden = false; this.dataset = {}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this[name] = value; }
  removeAttribute(name) { delete this[name]; }
}
function library({edition = "secondary", storedEdition, student = "demo", mode} = {}) {
  const elements = new Map(), requests = [];
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  get("scopeNote").dataset.copy = "scope"; get("intro").dataset.copy = "intro";
  for (const link of ["classroom", "courses", "profile", "recordings"]) get(link + "Link").dataset.link = link;
  const document = {documentElement:{dataset:{}}, getElementById:get, querySelectorAll:selector=>
    selector === "[data-copy]" ? [get("scopeNote"), get("intro")] : selector === "[data-link]" ? ["classroom", "courses", "profile", "recordings"].map(link=>get(link + "Link")) : [], createElement:tag=>new Element(tag)};
  const query = new URLSearchParams({edition}); if (student) query.set("student",student); if (mode) query.set("mode",mode);
  const context = vm.createContext({document, URLSearchParams, Intl,
    location:{search:"?" + query.toString()},
    localStorage:{getItem:()=>storedEdition, setItem(){}},
    window:{LiveAgentAPI:{fetchJson(path) { return new Promise((resolve,reject)=>requests.push({path,resolve,reject})); }}},
  });
  vm.runInContext(source, context);
  return {get, document, requests, run:code=>vm.runInContext(code,context),
    async respond(sessions) { requests[0].resolve({sessions}); await new Promise(setImmediate); },
  };
}
function descendants(element) { return element.children.flatMap(child => typeof child === "string" ? [] : [child,...descendants(child)]); }
function session(videos = []) { return {id:"sess-test",mode:"private",student_id:"demo",updated_at:"2026-10-02T08:00:00+00:00",size_bytes:42,trace_url:"/traces/file/sess-test.jsonl",transcript_url:"/api/traces/sess-test/transcript?student=demo",videos}; }

test("empty recording library offers a classroom route without inventing sessions", async () => {
  const page = library({edition:"primary"});
  await page.respond([]);
  assert.equal(page.requests[0].path,"/api/traces?student=demo");
  assert.equal(page.get("emptyState").hidden,false);
  assert.equal(page.get("sessions").children.length,0);
  assert.equal(page.get("sessionCount").textContent,"已保存 0 段会话");
  assert.equal(page.run('pageLink("/")'),"/?edition=primary&student=demo");
});

test("saved video playback and downloads use actual media paths and part numbers", async () => {
  const page = library({edition:"university"});
  await page.respond([session([
    {name:"sess-test-part10.mp4",label:"presented part10",url:"/traces/file/sess-test-part10.mp4"},
    {name:"sess-test-part2.mp4",label:"presented part2",url:"/traces/file/sess-test-part2.mp4"},
    {name:"sess-test.mp4",label:"presented",url:"/traces/file/sess-test.mp4"},
    {name:"sess-test.generated.mp4",label:"generated",url:"/traces/file/sess-test.generated.mp4"},
  ])]);
  const nodes = descendants(page.get("sessions"));
  const video = nodes.find(node => node.tagName === "video");
  assert.equal(video.src,"/traces/file/sess-test.mp4");
  assert.equal(video.preload,"none");
  assert.equal(video.controls,true);
  const links = nodes.filter(node => node.tagName === "a");
  assert.equal(links.find(node => node.textContent === "Recording part 10").href,"/traces/file/sess-test-part10.mp4");
  assert.equal(links.find(node => node.textContent.includes("session record")).href,"/traces/file/sess-test.jsonl");
  assert.equal(links.find(node => node.textContent === "Generated material").href,"/traces/file/sess-test.generated.mp4");
  assert.equal(page.get("emptyState").hidden,true);
  assert.equal(page.document.documentElement.lang,"en");
});

test("generated-only files are not presented as a classroom replay", async () => {
  const page = library({edition:"university"});
  await page.respond([session([{name:"sess-test.generated.mp4",label:"generated",url:"/traces/file/sess-test.generated.mp4"}])]);
  const nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node => node.tagName === "video"),false);
  assert.equal(nodes.some(node => node.textContent === "No presented video was saved. The session record is still available below."),true);
  assert.equal(nodes.some(node => node.textContent === "Generated material may include content that was never shown in the session."),true);
});

test("browser avatar sessions clearly label server fallback video while preserving grouping and recording parts", async () => {
  const page=library({edition:"university"});
  await page.respond([session([
    {label:"presented part10",url:"/traces/file/sess-test-part10.mp4",visual_source:"server_video_fallback"},
    {label:"presented",url:"/traces/file/sess-test.mp4",visual_source:"server_video_fallback"},
    {label:"generated part2",url:"/traces/file/sess-test.generated-part2.mp4",visual_source:"server_video_fallback"},
  ])]);
  const nodes=descendants(page.get("sessions")),video=nodes.find(node=>node.tagName==="video");
  assert.equal(video.src,"/traces/file/sess-test.mp4");
  assert.match(video["aria-label"],/fallback avatar/);
  assert.ok(nodes.some(node=>node.textContent==="Server fallback video"));
  assert.ok(nodes.some(node=>node.textContent?.includes("movements are not recorded")));
  const downloads=nodes.filter(node=>node.tagName==="a");
  assert.equal(downloads.find(node=>node.textContent==="Download fallback video").href,"/traces/file/sess-test.mp4");
  assert.equal(downloads.find(node=>node.textContent==="Fallback video · Part 10").href,"/traces/file/sess-test-part10.mp4");
  assert.equal(downloads.find(node=>node.textContent==="Generated fallback material · Part 2").href,"/traces/file/sess-test.generated-part2.mp4");
});

test("fallback recording labels explain the missing browser appearance in Chinese too", async () => {
  const page=library({edition:"secondary"});
  await page.respond([session([{label:"presented",url:"/traces/file/sess-test.mp4",visual_source:"server_video_fallback"}])]);
  const nodes=descendants(page.get("sessions"));
  assert.ok(nodes.some(node=>node.textContent==="备用老师视频"));
  assert.ok(nodes.some(node=>node.textContent?.includes("其外观与动作没有录入这份视频")));
  assert.ok(nodes.some(node=>node.textContent==="下载备用视频"));
});

test("failed fetch exposes an actionable error and re-enables refresh", async () => {
  const page = library({edition:"university"});
  page.requests[0].reject(new Error("offline"));
  await new Promise(setImmediate);
  assert.match(page.get("status").textContent,/Try refreshing/);
  assert.match(page.get("status").className,/error/);
  assert.equal(page.get("refresh").disabled,false);
  assert.equal(page.get("sessions").children.length,0);
});

test("private libraries exclude other learners, public sessions and legacy unknown scope", async () => {
  const page = library({edition:"university"});
  await page.respond([session(), {...session(),id:"other",student_id:"other"}, {...session(),id:"public",mode:"public",student_id:null}, {...session(),id:"legacy",mode:null,student_id:null}]);
  assert.equal(page.requests[0].path,"/api/traces?student=demo");
  assert.equal(page.get("sessions").children.length,1);
  assert.match(page.get("scopeNote").textContent,/learner demo/);
  assert.match(page.get("scopeNote").textContent,/no account authentication/);
  assert.equal(descendants(page.get("sessions")).some(node=>node.textContent === "other"),false);
  assert.doesNotMatch(page.get("intro").textContent,/videos and notes/);
});

test("public libraries omit learner identity from requests and crosslinks", async () => {
  const page = library({edition:"university",student:"private-id",mode:"public"});
  const publicSession = {...session(),id:"public",mode:"public",student_id:null};
  await page.respond([session(),publicSession,{...session(),id:"legacy",mode:null,student_id:null}]);
  assert.equal(page.requests[0].path,"/api/traces?mode=public");
  assert.equal(page.get("sessions").children.length,1);
  assert.equal(page.run('pageLink("/")'),"/?edition=university&mode=public");
  assert.equal(page.get("profileLink").hidden,true);
  assert.equal(page.get("profileLink").href,undefined);
  assert.match(page.get("scopeNote").textContent,/public sessions only/);
});

test("a direct private library without a learner never fetches an operator index or guesses demo", () => {
  const page = library({edition:"university",student:null});
  assert.equal(page.requests.length,0);
  assert.equal(page.get("refresh").disabled,true);
  assert.match(page.get("status").textContent,/Choose a learner/);
  assert.equal(page.run('pageLink("/")'),"/?edition=university");
});

test("a reading aid shows input and ACK-associated planned scripts without claiming audio equivalence", async () => {
  const page = library({edition:"university"}); await page.respond([session()]);
  const nodes = descendants(page.get("sessions")), button = nodes.find(node=>node.textContent === "Read scripts & input");
  const reading = button.onclick();
  assert.equal(button["aria-expanded"],"true");
  assert.equal(page.requests[1].path,"/api/traces/sess-test/transcript?student=demo");
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"script_aid",verified_audio:false,omitted_partial_requests:[],entries:[
    {role:"user",text:"<img src=x onerror=alert(1)>",source:"utterance_end"},
    {role:"teacher",kind:"planned_script",text:"A saved explanation.\nSecond line.",source:"lock",presented:true,may_include_unplayed_words:true,presentation:{status:"unknown",chunks_acknowledged:[0],chunks_expected:null}},
    {role:"teacher",text:"Never presented",source:"lock",presented:false},
  ]});
  await reading;
  const textNodes = descendants(page.get("sessions"));
  assert.equal(textNodes.some(node=>node.textContent === "<img src=x onerror=alert(1)>"),true);
  assert.equal(textNodes.some(node=>node.textContent === "A saved explanation.\nSecond line."),true);
  assert.equal(textNodes.some(node=>node.textContent === "Never presented"),false);
  assert.equal(textNodes.some(node=>node.textContent?.includes("not an audio transcript or captions")),true);
  assert.equal(textNodes.some(node=>node.textContent === "Planned tutor script"),true);
  assert.equal(textNodes.some(node=>node.textContent?.includes("may include unplayed words")),true);
  assert.equal(textNodes.filter(node=>node.tagName === "li").length,2);
  button.onclick(); await button.onclick();
  assert.equal(page.requests.length,2); // Already-read text is not fetched again.
});

test("complete chunk acknowledgements remain unverified audio and omitted partial scripts are explained", async () => {
  const page = library({edition:"university"}); await page.respond([session()]);
  const reading = descendants(page.get("sessions")).find(node=>node.textContent === "Read scripts & input").onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"script_aid",verified_audio:false,omitted_partial_requests:[1],entries:[
    {role:"teacher",kind:"planned_script",text:"Planned words",source:"lock",presented:true,may_include_unplayed_words:true,presentation:{status:"complete",chunks_acknowledged:[0,1],chunks_expected:2}},
  ]});
  await reading;
  const nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node=>node.textContent === "All expected chunks were acknowledged; script words and actual audio are still unverified."),true);
  assert.equal(nodes.some(node=>node.textContent === "Planned scripts were omitted where complete chunk acknowledgements are missing. Missing acknowledgements do not prove playback stopped. This reading aid does not establish coverage of the recorded audio."),true);
  assert.equal(nodes.some(node=>node.textContent === "Planned words"),true);
});

test("a request missing complete chunk acknowledgements has an explicit reading-aid gap", async () => {
  const page = library(); await page.respond([session()]);
  const reading = descendants(page.get("sessions")).find(node=>node.textContent === "阅读讲稿与输入").onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"script_aid",verified_audio:false,omitted_partial_requests:[0],entries:[]});
  await reading;
  const nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node=>node.textContent === "没有收到完整片段确认的请求已省略计划讲稿。确认缺失不能证明播放中止；这份阅读参考也不能确定录音内容的覆盖情况。"),true);
  assert.equal(nodes.some(node=>node.textContent === "这份阅读参考暂时没有可显示的讲稿或输入。"),true);
  assert.equal(nodes.some(node=>node.tagName === "li"),false);
});

test("an empty script is explicit rather than invented from the video", async () => {
  const page = library(); await page.respond([session()]);
  const button = descendants(page.get("sessions")).find(node=>node.tagName === "button" && node.textContent === "阅读讲稿与输入");
  const reading = button.onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"scripted",verified_audio:false,entries:[]});
  await reading;
  assert.equal(descendants(page.get("sessions")).some(node=>node.textContent === "这份阅读参考暂时没有可显示的讲稿或输入。"),true);
});

test("transcript scope mismatches expose no content and allow retry", async () => {
  const page = library({edition:"university"}); await page.respond([session()]);
  const button = descendants(page.get("sessions")).find(node=>node.textContent === "Read scripts & input");
  const reading = button.onclick();
  page.requests[1].resolve({id:"sess-test",mode:"private",student_id:"other",entries:[{role:"user",text:"Other learner private text"}]});
  await reading;
  let nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node=>node.textContent === "Other learner private text"),false);
  assert.equal(nodes.some(node=>node.textContent === "Session text couldn’t be loaded. Try again."),true);
  const retrying = nodes.find(node=>node.textContent === "Retry session text").onclick();
  page.requests[2].resolve({id:"sess-test",mode:"private",student_id:"demo",kind:"scripted",verified_audio:false,entries:[]});
  await retrying;
  nodes = descendants(page.get("sessions"));
  assert.equal(nodes.some(node=>node.textContent === "Nothing is available in this reading aid."),true);
});

const params = new URLSearchParams(location.search), editions = ["primary", "secondary", "university", "live"];
let preferredEdition = "secondary";
try { preferredEdition = localStorage.getItem("liveAgent.edition") || preferredEdition; } catch (_) {}
const requestedEdition = params.get("edition");
const edition = editions.includes(requestedEdition) ? requestedEdition : editions.includes(preferredEdition) ? preferredEdition : "secondary";
const publicMode = params.get("mode") === "public";
const student = publicMode ? "" : params.get("student") || "", english = edition === "university";
try { localStorage.setItem("liveAgent.edition", edition); } catch (_) {}
const copy = english ? {
  skip:"Skip to content", brand:"YāLearn", courses:"Explore topics", brandSub:"A little clearer, every day", space:"My learning space", classroom:"Live classroom", profile:"Learning profile", recordings:"Session recordings", sideTitle:"Keep a good explanation close.", sideText:"Return to an idea and see what makes more sense the second time.", editionLabel:"Learning edition", privateSpace:"One-to-one learning · Local demo", back:"Back to study room ↗", eyebrow:"LEARNING, WORTH REVISITING", title:"A little reflection goes a long way.", intro:"Replay an explanation and collect your thoughts. Find the videos and session records actually saved from your sessions.", savedSessions:"Saved sessions", refresh:"↻ Refresh library", scope:"Showing private sessions for learner {student}. Older records without learner attribution are excluded. This trusted local service has no account authentication; library filtering does not control access to files.", loading:"Looking for saved sessions…", emptyEyebrow:"YOUR NEXT CHAPTER", emptyTitle:"Your first session is still ahead.", emptyText:"There are no saved sessions yet. Bring a question to the study room. Sessions recorded by the service will appear here after they finish.", emptyLink:"Go to your study room ↗", libraryNote:"Recordings show what was saved, not proof of topic mastery. Bring any remaining questions to your next session.", count:"{count} saved sessions", session:"Study session", noVideo:"No presented video was saved. The session record is still available below.", download:"Download recording", part:"Recording part {part}", details:"Session files", trace:"Download session record", generatedNote:"Generated material may include content that was never shown in the session.", generated:"Generated material", generatedPart:"Generated material · Part {part}", error:"We couldn’t load the library. Try refreshing the list.", navLabel:"Main navigation", videoLabel:"Recorded session from {date}"
} : {
  skip:"跳到主要内容", brand:"芽学", courses:edition === "primary" ? "找点新知识" : "探索课程", brandSub:"陪你把知识学明白", space:"我的学习空间", classroom:edition === "primary" ? "我的小课堂" : "私人课堂", profile:edition === "primary" ? "我的学习卡" : "学习档案", recordings:edition === "primary" ? "看看课堂记录" : "课堂记录", sideTitle:"学过的，还可以再看看。", sideText:"回到当时的讲解，把一个小疑问再想明白。", editionLabel:"学习阶段", privateSpace:"一对一学习 · 本地演示", back:"返回课堂 ↗", eyebrow:"LEARNING, WORTH REVISITING", title:edition === "primary" ? "再看一遍，又懂一点。" : "好好学过，慢慢回顾。", intro:edition === "primary" ? "想再听一次老师的讲解？保存好的课堂可以在这里重新看看。" : "重看一段讲解，整理一次思路。这里收好已保存的课堂视频和会话记录。", savedSessions:"已保存的课堂", refresh:"↻ 刷新列表", scope:"只显示学生「{student}」的私人课堂，没有学生归属的旧记录不显示。当前服务用于可信的本地环境，没有账号登录；列表筛选不等于文件访问权限隔离。", loading:"正在寻找已保存的课堂…", emptyEyebrow:"YOUR NEXT CHAPTER", emptyTitle:edition === "primary" ? "第一节课，还在等你呢。" : "第一节课，还在前面等你。", emptyText:"现在还没有保存的会话。先去课堂聊一个想学的问题；开启录制的会话结束后会出现在这里。", emptyLink:"开始学习 ↗", libraryNote:"回放是实际保存的课堂内容，不代表知识点已经掌握。可以把看完后仍有疑问的地方，带回下一次课堂。", count:"已保存 {count} 段会话", session:"学习课堂", noVideo:"这次会话没有保存已播放的视频，会话记录仍可下载。", download:"下载课堂回放", part:"课堂回放 · 第 {part} 部分", details:"会话文件", trace:"下载会话记录", generatedNote:"生成素材可能包含课堂中没有播放的内容。", generated:"生成素材", generatedPart:"生成素材 · 第 {part} 部分", error:"暂时无法载入课堂记录。请刷新列表重试。", navLabel:"主导航", videoLabel:"{date}的课堂录像"
};
function t(key, values = {}) { return String(copy[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? "")); }
Object.assign(copy, english ? {
  fallbackTitle:"Server fallback video", fallbackDownload:"Download fallback video", fallbackPart:"Fallback video · Part {part}",
  fallbackGenerated:"Generated fallback material", fallbackGeneratedPart:"Generated fallback material · Part {part}",
  fallbackVideoLabel:"Server fallback avatar recording from {date}",
  fallbackNote:"This file contains the server fallback avatar. The classroom used a browser VTuber; its appearance and movements are not recorded in this video.",
  chooseLearner:"Choose a learner in the study room to see their saved private sessions.",
  publicScope:"Showing public sessions only. Older records without clear scope are excluded. This trusted local service has no account authentication; library filtering does not control access to files.",
  transcript:"Read scripts & input", transcriptLabel:"Planned scripts and recorded input", transcriptNote:"This reading aid contains planned tutor scripts and recorded user input. Scripts may include words that were never played. This is not an audio transcript or captions, and is not a reliable equivalent of the spoken replay. Spoken words and timing have not been verified.",
  transcriptLoading:"Loading session text…", transcriptEmpty:"Nothing is available in this reading aid.", transcriptMissing:"Readable text is unavailable for this record.", transcriptError:"Session text couldn’t be loaded. Try again.", transcriptRetry:"Retry session text", tutorScript:"Planned tutor script", userInput:"Recorded user input", scriptUnknown:"Playback completion is unknown; this planned text may include unplayed words.", scriptComplete:"All expected chunks were acknowledged; script words and actual audio are still unverified.", partialOmitted:"Planned scripts were omitted where complete chunk acknowledgements are missing. Missing acknowledgements do not prove playback stopped. This reading aid does not establish coverage of the recorded audio."
} : {
  fallbackTitle:"备用老师视频", fallbackDownload:"下载备用视频", fallbackPart:"备用视频 · 第 {part} 部分",
  fallbackGenerated:"生成的备用素材", fallbackGeneratedPart:"生成的备用素材 · 第 {part} 部分",
  fallbackVideoLabel:"{date}的备用老师录像",
  fallbackNote:"这份文件保存的是服务器的备用老师画面。课堂当时使用了浏览器中的 VTuber；其外观与动作没有录入这份视频。",
  chooseLearner:"请先去课堂选择学生，再查看这个学生保存的私人课堂。",
  publicScope:"只显示公开会话，没有明确归属的旧记录不显示。当前服务用于可信的本地环境，没有账号登录；列表筛选不等于文件访问权限隔离。",
  transcript:"阅读讲稿与输入", transcriptLabel:"计划讲稿与保存的用户输入", transcriptNote:"这些文字仅供阅读参考，包括老师的计划讲稿和保存的用户输入。讲稿可能含有从未播放的内容，不是音频转写或字幕，也不能可靠替代录像中的声音。实际说出的文字和时间位置尚未核对。",
  transcriptLoading:"正在载入会话文字…", transcriptEmpty:"这份阅读参考暂时没有可显示的讲稿或输入。", transcriptMissing:"这份记录暂时没有可读文字。", transcriptError:"暂时无法载入会话文字，请重试。", transcriptRetry:"重试载入文字", tutorScript:"老师计划讲稿", userInput:"保存的用户输入", scriptUnknown:"播放是否完成尚不明确；计划讲稿可能含有未播放的文字。", scriptComplete:"已收到全部预期片段的播放确认；讲稿文字与实际声音仍未核对。", partialOmitted:"没有收到完整片段确认的请求已省略计划讲稿。确认缺失不能证明播放中止；这份阅读参考也不能确定录音内容的覆盖情况。"
});
copy.scope = publicMode ? t("publicScope") : student ? t("scope", {student}) : t("chooseLearner");
if (publicMode) {
  copy.privateSpace = english ? "Public sessions · Local demo" : "公开会话 · 本地演示";
  copy.intro = english ? "Return to saved public sessions. Find the videos and session records actually saved by this service." : "回顾已保存的公开会话。这里显示这台服务保存的公开录像和会话记录。";
}
function pageLink(path, selectedEdition = edition) {
  const [route,hash] = path.split("#"), query = new URLSearchParams({edition:selectedEdition});
  if (publicMode) query.set("mode", "public");
  else if (student) query.set("student", student);
  return route + "?" + query.toString() + (hash ? "#" + hash : "");
}
document.documentElement.lang = english ? "en" : "zh-CN";
document.documentElement.dataset.edition = edition;
document.title = t("recordings") + " · " + t("brand");
document.querySelectorAll("[data-copy]").forEach(el => { el.textContent = t(el.dataset.copy); });
const paths = {classroom:"/", courses:"/#courses", profile:"/profile", recordings:"/traces"};
document.querySelectorAll("[data-link]").forEach(el => {
  if (publicMode && el.dataset.link === "profile") { el.hidden = true; el.removeAttribute("href"); }
  else el.href = pageLink(paths[el.dataset.link]);
});
document.getElementById("mainNav").setAttribute("aria-label", t("navLabel"));
document.getElementById("editionSelect").setAttribute("aria-label", t("editionLabel"));
document.getElementById("editionSelect").value = edition;
document.getElementById("editionBadge").textContent = english ? "University & adult" : edition === "primary" ? "小学版" : "中学版";
document.getElementById("editionSelect").onchange = () => {
  const next = document.getElementById("editionSelect").value;
  if (!editions.includes(next)) return;
  try { localStorage.setItem("liveAgent.edition", next); } catch (_) {}
  location.href = pageLink("/traces", next);
};
function traceLink(url, label, className = "") {
  const link = document.createElement("a");
  link.href = url; link.textContent = label; link.className = className;
  return link;
}
function traceUpdateTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(english ? "en" : "zh-CN", {year:"numeric", month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"}).format(date);
}
function recordingPart(file) {
  const part = /(?:-|\s)part(\d+)$/.exec(file.label);
  return part ? Number(part[1]) : 1;
}
function fileSize(bytes) { return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`; }
function transcriptSection(session) {
  const section = document.createElement("section"); section.className = "session-transcript";
  if (!session.transcript_url) {
    const text = document.createElement("p"); text.textContent = t("transcriptMissing"); section.append(text); return section;
  }
  const button = document.createElement("button"); button.type = "button"; button.className = "secondary-button"; button.textContent = t("transcript");
  const panel = document.createElement("div"); panel.className = "transcript-panel"; panel.id = "transcript-" + session.id; panel.hidden = true;
  panel.setAttribute("role", "region"); panel.setAttribute("aria-label", t("transcriptLabel"));
  button.setAttribute("aria-expanded", "false"); button.setAttribute("aria-controls", panel.id);
  let loaded = false, pending = false;
  async function loadText() {
    if (loaded || pending) return;
    pending = true;
    const note = document.createElement("p"); note.className = "transcript-note"; note.textContent = t("transcriptNote");
    const status = document.createElement("p"); status.setAttribute("role", "status"); status.textContent = t("transcriptLoading");
    panel.replaceChildren(note, status);
    try {
      const transcript = await window.LiveAgentAPI.fetchJson(session.transcript_url);
      if (transcript.id !== session.id || !matchesScope(transcript)) throw new Error("Transcript scope mismatch");
      const entries = transcript.entries.filter(entry => entry.text && (entry.role === "user" || entry.role === "teacher" && entry.presented === true));
      const notices = [note];
      if (transcript.omitted_partial_requests?.length) {
        const omitted = document.createElement("p"); omitted.className = "script-caution"; omitted.textContent = t("partialOmitted"); notices.push(omitted);
      }
      if (!entries.length) { panel.replaceChildren(...notices, status); status.textContent = t("transcriptEmpty"); }
      else {
        panel.replaceChildren(...notices);
        const lines = document.createElement("ol"); lines.className = "transcript-lines";
        entries.forEach(entry => {
          const line = document.createElement("li"), label = document.createElement("strong"), text = document.createElement("p");
          label.textContent = t(entry.role === "teacher" ? "tutorScript" : "userInput"); text.textContent = entry.text;
          line.append(label);
          if (entry.role === "teacher") {
            const caution = document.createElement("p"); caution.className = "script-caution";
            caution.textContent = t(entry.presentation?.status === "complete" ? "scriptComplete" : "scriptUnknown"); line.append(caution);
          }
          line.append(text); lines.append(line);
        });
        panel.append(lines);
      }
      loaded = true;
    } catch (_) {
      status.textContent = t("transcriptError");
      const retry = document.createElement("button"); retry.type = "button"; retry.className = "ghost"; retry.textContent = t("transcriptRetry"); retry.onclick = loadText; panel.append(retry);
    } finally { pending = false; }
  }
  button.onclick = () => {
    panel.hidden = !panel.hidden; button.setAttribute("aria-expanded", String(!panel.hidden));
    if (!panel.hidden) return loadText();
  };
  section.append(button, panel); return section;
}
function matchesScope(session) { return publicMode ? session.mode === "public" && session.student_id == null : session.mode === "private" && session.student_id === student; }
function recordingCard(session) {
  const card = document.createElement("article"); card.className = "recording-card";
  const presented = session.videos.filter(video => video.label.startsWith("presented")).sort((a,b) => recordingPart(a) - recordingPart(b));
  const generated = session.videos.filter(video => video.label.startsWith("generated")).sort((a,b) => recordingPart(a) - recordingPart(b));
  const isFallback = file => file.visual_source === "server_video_fallback";
  const hasFallback = session.videos.some(isFallback);
  const when = traceUpdateTime(session.updated_at);
  if (presented.length) {
    const video = document.createElement("video"); video.controls = true; video.preload = "none"; video.playsInline = true;
    video.src = presented[0].url; video.setAttribute("aria-label", t(isFallback(presented[0]) ? "fallbackVideoLabel" : "videoLabel", {date:when})); card.append(video);
  } else {
    const empty = document.createElement("div"); empty.className = "recording-no-video";
    const icon = document.createElement("span"); icon.textContent = "▷"; icon.setAttribute("aria-hidden", "true");
    const text = document.createElement("p"); text.textContent = t("noVideo"); empty.append(icon, text); card.append(empty);
  }
  const content = document.createElement("div"); content.className = "recording-content";
  const title = document.createElement("h3"); title.textContent = t(hasFallback ? "fallbackTitle" : "session");
  const time = document.createElement("p"); time.className = "recording-time"; time.textContent = when; time.title = session.updated_at;
  content.append(title, time);
  if (hasFallback) {
    const note = document.createElement("p"); note.className = "transcript-note"; note.textContent = t("fallbackNote"); content.append(note);
  }
  if (presented.length) {
    const links = document.createElement("div"); links.className = "recording-downloads";
    presented.forEach(file => links.append(traceLink(file.url, recordingPart(file) === 1
      ? t(isFallback(file) ? "fallbackDownload" : "download")
      : t(isFallback(file) ? "fallbackPart" : "part", {part:recordingPart(file)}), "download-link")));
    content.append(links);
  }
  const details = document.createElement("details"); details.className = "file-details";
  const summary = document.createElement("summary"); summary.textContent = t("details");
  const id = document.createElement("p"); id.className = "session-id"; id.textContent = session.id;
  const files = document.createElement("div"); files.className = "file-list";
  files.append(traceLink(session.trace_url, `${t("trace")} · ${fileSize(session.size_bytes)}`));
  details.append(summary, id, files);
  if (generated.length) {
    const note = document.createElement("p"); note.textContent = t("generatedNote"); details.append(note);
    const generatedFiles = document.createElement("div"); generatedFiles.className = "file-list";
    generated.forEach(file => {
      const label = recordingPart(file) === 1 ? t(isFallback(file) ? "fallbackGenerated" : "generated")
        : t(isFallback(file) ? "fallbackGeneratedPart" : "generatedPart", {part:recordingPart(file)});
      generatedFiles.append(traceLink(file.url, label));
    });
    details.append(generatedFiles);
  }
  content.append(transcriptSection(session), details); card.append(content); return card;
}
async function loadTraces() {
  const status = document.getElementById("status"), refresh = document.getElementById("refresh");
  if (!publicMode && !student) {
    refresh.disabled = true; status.hidden = false; status.textContent = t("chooseLearner");
    return;
  }
  refresh.disabled = true; status.hidden = false; status.className = "load-message"; status.textContent = t("loading");
  try {
    const scope = publicMode ? new URLSearchParams({mode:"public"}) : new URLSearchParams({student});
    const response = await window.LiveAgentAPI.fetchJson("/api/traces?" + scope.toString());
    const sessions = response.sessions.filter(matchesScope);
    const body = document.getElementById("sessions"); body.replaceChildren(...sessions.map(recordingCard));
    document.getElementById("sessionCount").textContent = t("count", {count:sessions.length});
    document.getElementById("emptyState").hidden = sessions.length > 0;
    status.hidden = true;
  } catch (_) { status.textContent = t("error"); status.className = "load-message error"; }
  finally { refresh.disabled = false; }
}
document.getElementById("refresh").onclick = loadTraces;
loadTraces();

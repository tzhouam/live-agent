import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../public/assets/live.js', import.meta.url), 'utf8');
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
function assertRequestId(value) {
  assert.equal(typeof value, 'string');
  assert.ok(value.trim().length > 0 && value.length <= 64);
}

function page({ edition = 'primary', codec, bitmap } = {}) {
  const elements = new Map(), sockets = [], events = [], transitions = [], permissions = [];
  const timers = new Map();
  let nextTimer = 0;
  function element(id) {
    if (!elements.has(id)) {
      const node = { id, value: '', textContent: '', className: '', children: [], style: {}, dataset: {},
        hidden: false, disabled: false, width: 480, height: 864, clientWidth: 1000,
        clientHeight: 500, scrollHeight: 0, scrollTop: 0,
        appendChild(child) { child.parent = this; this.children.push(child); },
        contains(child) { return this.children.includes(child); },
        focus() { document.activeElement = this; },
        remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
        querySelector() { return null; },
        querySelectorAll(selector) { return selector.includes('.badge') ? this.children.filter(child => child.className === 'badge') : []; },
        setAttribute(name, value) { this[name] = value; },
        getAttribute(name) { return this[name] ?? null; }, removeAttribute(name) { delete this[name]; },
        getContext() { return { drawImage() {}, clearRect() {} }; },
        setPointerCapture() {}, hasPointerCapture() { return false; },
        play() { return Promise.resolve(); }, scrollIntoView() {},
      };
      Object.defineProperty(node, 'innerHTML', { get() { return this.html || ''; }, set(value) { this.html = value; this.children = []; } });
      node.classList = {
        contains(name) { return node.className.split(' ').includes(name); },
        add(name) { if (!this.contains(name)) node.className = `${node.className} ${name}`.trim(); },
        remove(name) { node.className = node.className.split(' ').filter(value => value !== name).join(' '); },
        toggle(name, value) { if (value) this.add(name); else this.remove(name); },
      };
      elements.set(id, node);
    }
    return elements.get(id);
  }
  const document = {
    hidden: false,
    getElementById(id) { return id === 'student' ? null : element(id); },
    createElement(type) { return element(`created-${elements.size}-${type}`); },
    querySelector() { return element('stage'); },
    querySelectorAll(selector) { return selector.includes('chip') ? element('chips').children : []; },
  };
  class AudioContext {
    constructor() { this.state = 'running'; this.currentTime = 0; this.destination = {}; }
    resume() { return Promise.resolve(); }
    createGain() { return { connect() { return this; }, gain: { setTargetAtTime() {} } }; }
    createBuffer(_channels, size) { return { getChannelData: () => new Float32Array(size) }; }
    createBufferSource() { return { connect() {}, start() {}, stop() {} }; }
  }
  class WebSocket {
    constructor(url) { this.url = url; this.readyState = 0; this.sent = []; sockets.push(this); }
    send(value) { if (this.failSend || this.readyState !== 1) throw new Error('Socket unavailable'); this.sent.push(value); }
    close() { this.readyState = 3; }
  }
  class MediaRecorder {
    constructor(stream) { this.stream = stream; this.state = 'inactive'; }
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      this.ondataavailable?.({ data: new Blob(['recorded audio']) });
      this.completed = this.onstop?.();
    }
  }
  const window = {
    AudioContext,
    location: { href: '/' },
    dispatchEvent(event) { events.push(event); },
    LiveAgentAPI: { websocketUrl() { return 'ws://frontend.test/ws'; } },
    LiveAgentProduct: {
      edition, t(_key, fallback) { return fallback; },
      examples() { return [{ label: 'Explain this step', text: '这一步我还没明白' }]; },
      sessionChanged(state, detail) { transitions.push({ state, detail }); },
    },
  };
  const context = vm.createContext({ document, window, WebSocket, MediaRecorder, Blob,
    AudioContext, CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    navigator: { mediaDevices: {
      addEventListener() {},
      getUserMedia(options) { const request = { ...deferred(), options }; permissions.push(request); return request.promise; },
    } },
    console: { warn() {}, error() {} }, performance: { now: () => 1000 },
    localStorage: { getItem() { return null; }, setItem() {} },
    innerHeight: 800, innerWidth: 1200, addEventListener() {}, requestAnimationFrame() {},
    setInterval(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
    clearInterval(id) { timers.delete(id); },
    setTimeout(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    createImageBitmap: bitmap || (() => Promise.resolve({ close() {} })),
    ...(codec ? { VideoDecoder: { isConfigSupported: codec } } : {}),
  });
  vm.runInContext(source, context);
  element('mode').value = 'private'; element('uid').value = 'actual-user'; element('sid').value = 'actual-student';
  const run = code => vm.runInContext(code, context);
  async function connect() { await element('connect').onclick(); return sockets.at(-1); }
  async function open(socket = sockets.at(-1)) { socket.readyState = 1; await socket.onopen(); }
  async function status(extra = {}, socket = sockets.at(-1)) {
    await socket.onmessage({ data: JSON.stringify({ type: 'status', session: 'actual-session',
      generator: 'mock', responder: 'rules', director: 'online', judge: 'mock',
      asr: false, attention: false, board: false, student: null, ...extra }) });
  }
  return { element, sockets, events, transitions, permissions, timers, run, connect, open, status };
}

function stream() {
  let stopped = 0;
  return { getTracks: () => [{ stop() { stopped++; } }], stopped: () => stopped };
}

test('rapid connect clicks produce one socket and input waits for backend status', async () => {
  const app = page();
  const first = app.element('connect').onclick();
  const second = app.element('connect').onclick();
  assert.equal(app.element('connect').disabled, true);
  await Promise.all([first, second]);
  assert.equal(app.sockets.length, 1);
  await app.open();
  assert.equal(app.element('text').disabled, true);
  assert.equal(app.element('talk').disabled, true);
  app.element('text').value = 'Keep this draft';
  assert.equal(app.run('sendText()'), false);
  assert.equal(app.element('text').value, 'Keep this draft');
  const hello = JSON.parse(app.sockets[0].sent[0]);
  assert.equal(hello.student, 'actual-student');
  assert.equal(hello.user_id, 'actual-user');
  await app.status();
  assert.equal(app.element('text').disabled, false);
  assert.equal(app.element('talk').disabled, true);
  assert.equal(app.run('sendText()'), true);
  assert.equal(app.element('text').value, '');
  assert.equal(JSON.parse(app.sockets[0].sent.at(-1)).text, 'Keep this draft');
  assert.equal(app.transitions.at(-1).detail.status.generator, 'mock');
  assert.equal(app.events.at(-2).type, 'live-agent:status');
  assert.equal(app.events.at(-1).type, 'live-agent:submitted');
});

test('public hello uses a public memory namespace and omits private learner identity', async () => {
  const app = page();
  app.element('mode').value = 'public';
  app.element('uid').value = 'learner:private-id';
  app.element('sid').value = 'private-id';
  await app.connect(); await app.open();
  const hello = JSON.parse(app.sockets[0].sent[0]);
  assert.equal(hello.mode, 'public');
  assert.equal(hello.user_id, 'public-preview');
  assert.equal(Object.hasOwn(hello, 'student'), false);
  assert.equal(app.sockets[0].sent[0].includes('private-id'), false);
});

test('failed connection resets controls and stale close cannot stop a reconnected session', async () => {
  const app = page({ edition: 'university' });
  const oldSocket = await app.connect();
  oldSocket.onerror();
  assert.equal(app.element('connect').disabled, false);
  assert.equal(app.element('text').disabled, true);
  assert.match(app.element('connectionError').textContent, /could not connect/);
  const socket = await app.connect();
  await app.open(socket); await app.status({}, socket);
  oldSocket.onclose();
  assert.equal(app.run('ready()'), true);
  assert.equal(app.element('connectionError').hidden, true);
  assert.equal(app.run('ws === null'), false);
});

test('connection failure preserves the retry button and writes only its message node', async () => {
  const app = page();
  const panel = app.element('connectionError'), message = app.element('connectionErrorText'), retry = app.element('connectionRetry');
  panel.children = [message, retry];
  panel.querySelector = selector => selector === '#connectionErrorText' ? message : null;
  const socket = await app.connect(); socket.onerror();
  assert.equal(panel.children.length, 2);
  assert.equal(panel.children[1], retry);
  assert.match(message.textContent, /连接不上/);
});

test('startup deadline releases an open socket without status and preserves the draft', async () => {
  const app = page();
  const socket = await app.connect(); await app.open(socket);
  app.element('text').value = 'Keep my question';
  app.timers.get(app.run('startupTimer'))();
  assert.equal(app.run('sessionState'), 'error');
  assert.equal(app.element('connect').disabled, false);
  assert.equal(app.element('text').value, 'Keep my question');
  assert.equal(socket.readyState, 3);
  assert.equal(app.timers.size, 0);
  await app.status({}, socket);
  assert.equal(app.run('sessionState'), 'error');
});

test('codec probe and late status from a disconnected socket cannot reach the next session', async () => {
  const supported = deferred();
  const app = page({ codec: () => supported.promise });
  const oldSocket = await app.connect();
  oldSocket.readyState = 1;
  const opening = oldSocket.onopen();
  app.element('disconnect').onclick();
  const socket = await app.connect();
  supported.resolve({ supported: true });
  await opening;
  assert.equal(oldSocket.sent.length, 0);
  await app.status({ persona: 'Stale tutor' }, oldSocket);
  assert.equal(app.run('sessionState'), 'connecting');
  await app.open(socket); await app.status({ persona: 'Current tutor' }, socket);
  assert.equal(app.element('title').textContent, 'Current tutor');
  assert.equal(app.timers.size, 3);
});

test('a failed send preserves the draft and IME composition does not submit', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.element('text').value = 'Unsent draft';
  app.sockets[0].failSend = true;
  assert.equal(app.run('sendText()'), false);
  assert.equal(app.element('text').value, 'Unsent draft');
  app.sockets[0].failSend = false;
  const before = app.sockets[0].sent.length;
  app.element('text').onkeydown({ key: 'Enter', isComposing: true, preventDefault() { throw new Error('Composition must not be handled'); } });
  assert.equal(app.sockets[0].sent.length, before);
});

test('lesson text forwards only explicit school context and ordinary messages keep their original shape', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.run('sendText("给我上一节数学分数的课", {subject: "数学", grade: 3, topic: "分数", basis: "textbook", student: "private-id", mastery: 0.1})');
  const lesson = JSON.parse(app.sockets[0].sent.at(-1));
  assert.deepEqual(lesson.lesson_context, { subject: '数学', grade: 3, topic: '分数' });
  assert.equal(lesson.text, '给我上一节数学分数的课');
  app.run('sendText("请再讲一遍")');
  assert.equal(Object.hasOwn(JSON.parse(app.sockets[0].sent.at(-1)), 'lesson_context'), false);
});

test('text packets preserve explicit activity tickets and correlate ordinary sends', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.run('sendText("给我一道练习题", {subject: "数学", grade: 3, topic: "分数"}, "practice-ticket-1")');
  assert.deepEqual(JSON.parse(app.sockets[0].sent.at(-1)), {type: 'text', text: '给我一道练习题', tp: 1000,
    request_id: 'practice-ticket-1', lesson_context: {subject: '数学', grade: 3, topic: '分数'}});
  app.run('sendText("给我上一节课", null, "lesson-ticket-2")');
  assert.deepEqual(JSON.parse(app.sockets[0].sent.at(-1)), {type: 'text', text: '给我上一节课', tp: 1000, request_id: 'lesson-ticket-2'});
  app.run('sendText("普通问题")');
  const ordinary = JSON.parse(app.sockets[0].sent.at(-1));
  assertRequestId(ordinary.request_id);
  assert.deepEqual(ordinary, {type: 'text', text: '普通问题', tp: 1000, request_id: ordinary.request_id});
  const packets = app.sockets[0].sent.length, events = app.events.length;
  app.element('text').value = 'Keep this draft';
  for (const invalid of [{id: 'invalid-ticket'}, '', '   ', 'x'.repeat(65), 123]) {
    assert.equal(app.run(`sendText(undefined, null, ${JSON.stringify(invalid)})`), false);
  }
  assert.equal(app.sockets[0].sent.length, packets);
  assert.equal(app.events.length, events);
  assert.equal(app.element('text').value, 'Keep this draft');
});

test('successful text sends emit one local submission with the ticket and failed sends emit none', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.run('profile = {id: "actual-profile"};');
  const packets = app.sockets[0].sent.length, events = app.events.length, hooks = app.transitions.length, timers = app.timers.size;
  assert.equal(app.run('sendText("给我一道练习题", null, "practice-ticket-1")'), true);
  assert.equal(app.sockets[0].sent.length, packets + 1);
  assert.equal(app.events.length, events + 1);
  assert.equal(app.events.at(-1).type, 'live-agent:submitted');
  assert.equal(app.events.at(-1).detail.request_id, 'practice-ticket-1');
  assert.equal(app.events.at(-1).detail.activity, true);
  assert.equal(JSON.parse(app.sockets[0].sent.at(-1)).request_id, app.events.at(-1).detail.request_id);

  assert.equal(app.run('sendText("普通问题")'), true);
  assert.equal(app.sockets[0].sent.length, packets + 2);
  assert.equal(app.events.length, events + 2);
  assertRequestId(app.events.at(-1).detail.request_id);
  assert.equal(app.events.at(-1).detail.request_id, JSON.parse(app.sockets[0].sent.at(-1)).request_id);
  assert.equal(app.events.at(-1).detail.activity, false);
  app.sockets[0].failSend = true;
  app.element('text').value = 'Keep my draft';
  assert.equal(app.run('sendText()'), false);
  assert.equal(app.events.length, events + 2);
  assert.equal(app.sockets[0].sent.length, packets + 2);
  assert.equal(app.element('text').value, 'Keep my draft');
  assert.equal(app.run('sendText("")'), false);
  assert.equal(app.events.length, events + 2);
  assert.equal(app.transitions.length, hooks);
  assert.equal(app.timers.size, timers);
  assert.equal(app.run('profile.id'), 'actual-profile');
  assert.equal(app.events.slice(events).every(event => event.type === 'live-agent:submitted'), true);
});

test('ordinary text and voice submissions get distinct bounded IDs across reconnects', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({asr: true});
  const ids = [];
  for (const text of ['First ordinary question', 'Second ordinary question']) {
    assert.equal(app.run(`sendText(${JSON.stringify(text)})`), true);
    const packet = JSON.parse(app.sockets[0].sent.at(-1));
    ids.push(packet.request_id);
    assert.equal(app.events.at(-1).detail.request_id, packet.request_id);
    assert.equal(app.events.at(-1).detail.activity, false);
  }
  const starting = app.element('talk').onpointerdown({pointerId: 1});
  app.permissions[0].resolve(stream()); await starting;
  const speech = JSON.parse(app.sockets[0].sent.at(-1));
  ids.push(speech.request_id);
  assert.equal(speech.type, 'speech_start');
  assert.equal(app.events.at(-1).detail.request_id, speech.request_id);
  assert.equal(app.events.at(-1).detail.activity, false);
  app.run('cancelSpeech();');
  app.element('disconnect').onclick();
  const socket = await app.connect(); await app.open(socket); await app.status({}, socket);
  assert.equal(app.run('sendText("After reconnect", null, null)'), true);
  ids.push(JSON.parse(socket.sent.at(-1)).request_id);
  ids.forEach(assertRequestId);
  assert.equal(new Set(ids).size, ids.length);
});

test('decoding from an ended session is discarded without acknowledging it on the new socket', async () => {
  const decoded = deferred();
  let closed = 0;
  const app = page({ bitmap: () => decoded.promise });
  const oldSocket = await app.connect(); await app.open(); await app.status();
  await oldSocket.onmessage({ data: JSON.stringify({ type: 'chunk', codec: 'jpeg', n_frames: 1, request: 1, chunk: 0 }) });
  await oldSocket.onmessage({ data: new ArrayBuffer(2) });
  const completing = oldSocket.onmessage({ data: new ArrayBuffer(2) });
  app.element('disconnect').onclick();
  const socket = await app.connect(); await app.open(socket); await app.status({}, socket);
  decoded.resolve({ close() { closed++; } });
  await completing;
  assert.equal(closed, 1);
  assert.equal(app.run('queue.length'), 0);
  assert.equal(socket.sent.some(value => JSON.parse(value).type === 'chunk_received'), false);
});

test('a fresh public session cannot inherit private board data when its first chunk has no board', async () => {
  const app = page();
  await app.connect(); await app.open(); await app.status();
  app.run(`lastBoard = {key: "private-board", title: "Private lesson", items: ["Private question"]};
    shownBoard = lastBoard; onScreen = {board: lastBoard};
    $("boardTitle").textContent = "Private lesson";
    $("boardItems").innerHTML = "Private question";
    $("board").classList.add("on");`);
  app.element('disconnect').onclick();
  app.element('mode').value = 'public';
  await app.connect();
  assert.equal(app.run('lastBoard'), null);
  assert.equal(app.run('onScreen'), null);
  assert.equal(app.element('boardTitle').textContent, '');
  assert.equal(app.element('boardItems').innerHTML, '');
  app.run(`schedule({meta: {request: 1, chunk: 0, width: 480, height: 864, sample_rate: 16000,
    duration: 1, n_frames: 1, fps: 24}, frames: [], pcm: new Int16Array([0, 0]), epoch});`);
  assert.equal(app.run('queue[0].board'), null);
});

test('ordinary playback interruption retains the current lesson board for following chunks', async () => {
  const app = page(); await app.connect();
  app.run('lastBoard = {key: "same-lesson"}; stopAll();');
  assert.equal(app.run('lastBoard.key'), 'same-lesson');
});

test('releasing while microphone permission is pending stops its stream and sends no speech', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ asr: true });
  const recording = app.element('talk').onpointerdown({ pointerId: 1 });
  app.element('talk').onpointerup();
  const granted = stream(); app.permissions[0].resolve(granted);
  await recording;
  assert.equal(granted.stopped(), 1);
  assert.equal(app.run('recorder'), null);
  assert.equal(app.sockets[0].sent.filter(value => JSON.parse(value).type === 'speech_start').length, 0);
  assert.equal(app.element('talk').classList.contains('recording'), false);
});

test('late camera permission after disconnect releases tracks and never activates preview', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ attention: true });
  const enabling = app.element('cam').onclick();
  app.element('disconnect').onclick();
  const granted = stream(); app.permissions[0].resolve(granted);
  await enabling;
  assert.equal(granted.stopped(), 1);
  assert.equal(app.element('camView').hidden, true);
  assert.equal(app.run('camStream'), null);
  assert.equal(app.timers.size, 0);
});

test('microphone denial restores controls with localized advice and no false speech start', async () => {
  const app = page({ edition: 'university' }); await app.connect(); await app.open(); await app.status({ asr: true });
  const recording = app.element('talk').onpointerdown({ pointerId: 1 });
  app.permissions[0].reject(Object.assign(new Error('Permission denied detail'), { name: 'NotAllowedError' }));
  await recording;
  assert.equal(app.run('micPressed'), false);
  assert.equal(app.element('talk').textContent, 'Hold to speak');
  assert.match(app.element('chat').children.at(-1).textContent, /Microphone permission was declined/);
  assert.equal(app.sockets[0].sent.filter(value => JSON.parse(value).type === 'speech_start').length, 0);
  assert.equal(app.events.some(event => event.type === 'live-agent:submitted'), false);
});

for (const successful of [true, false]) {
  test(`voice start ${successful ? 'success emits a local submission' : 'send failure emits no submission'}`, async () => {
    const app = page(); await app.connect(); await app.open(); await app.status({asr: true});
    app.run('profile = {id: "actual-profile"};');
    const socket = app.sockets[0], packets = socket.sent.length, events = app.events.length;
    const hooks = app.transitions.length, timers = app.timers.size;
    socket.failSend = !successful;
    const starting = app.element('talk').onpointerdown({pointerId: 1});
    assert.equal(app.events.length, events);
    const granted = stream(); app.permissions[0].resolve(granted); await starting;
    assert.equal(socket.sent.length, packets + (successful ? 1 : 0));
    assert.equal(app.events.length, events + (successful ? 1 : 0));
    if (successful) {
      const packet = JSON.parse(socket.sent.at(-1));
      assertRequestId(packet.request_id);
      assert.deepEqual(packet, {type: 'speech_start', request_id: packet.request_id});
      assert.equal(app.events.at(-1).type, 'live-agent:submitted');
      assert.equal(app.events.at(-1).detail.request_id, packet.request_id);
      assert.equal(app.events.at(-1).detail.activity, false);
      await app.element('talk').onpointerdown({pointerId: 2});
      assert.equal(app.permissions.length, 1);
      assert.equal(app.events.length, events + 1);
      app.run('cancelSpeech();');
    } else {
      assert.equal(app.run('recorder'), null);
      assert.equal(app.run('micPressed'), false);
      assert.ok(granted.stopped() > 0);
    }
    assert.equal(app.run('profile.id'), 'actual-profile');
    assert.equal(app.transitions.length, hooks);
    assert.equal(app.timers.size, timers);
    assert.equal(socket.sent.length, packets + (successful ? 1 : 0));
  });
}

test('repeated voice presses start one recording and release preserves audio metadata ordering', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ asr: true });
  const starting = app.element('talk').onpointerdown({ pointerId: 1 });
  app.permissions[0].resolve(stream()); await starting;
  app.run('window.activeRecording = recorder');
  await app.element('talk').onpointerdown({ pointerId: 2 });
  assert.equal(app.permissions.length, 1);
  app.element('talk').onpointerup();
  app.element('talk').onpointerleave({ pointerId: 1 });
  await app.run('window.activeRecording.completed');
  const sent = app.sockets[0].sent;
  assert.equal(JSON.parse(sent.at(-2)).type, 'audio_end');
  assert.equal(JSON.parse(sent.at(-2)).tp, 1000);
  assert.ok(sent.at(-1) instanceof ArrayBuffer);
  assert.equal(app.element('talk').disabled, false);
  assert.equal(app.run('micUploading'), false);
});

test('university chips keep localized labels and original backend answer values', async () => {
  const app = page({ edition: 'university' }); await app.connect(); await app.open(); await app.status();
  app.run('showExercise({concept: "Fractions", options: ["A", "B"]})');
  assert.equal(app.element('chips').children[0].textContent, 'Choose A');
  app.element('chips').children[0].onclick();
  assert.equal(JSON.parse(app.sockets[0].sent.at(-1)).text, '选 A');
  app.run('showExercise(null)');
  app.element('profEdit').onclick();
  assert.match(app.run('window.location.href'), /student=actual-student&edition=university/);
});

test('new exercise choices announce through the product event while composer focus stays put', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.element('text').focus();
  app.run('onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Fractions", question: "Choose a fraction", options: ["A"], option_texts: ["A. One half"]}})');
  assert.equal(app.run('document.activeElement === $("text")'), true);
  const event = app.events.findLast(event => event.type === 'live-agent:event');
  assert.equal(event.detail.data.question, 'Choose a fraction');
  assert.equal(app.element('chips').children[0]['aria-label'], '选 A: A. One half');
});

test('stale scoped exercise states and events leave current choices intact while ordinary state and profile still render', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({board: true});
  app.run(`window.LiveAgentProduct.acceptsActivity = requestId => requestId === "current-ticket";
    showExercise({request_id: "current-ticket", concept: "Current concept", options: ["B"], option_texts: ["Current choice"]});`);
  const currentChoice = app.element('chips').children[0]; currentChoice.focus();
  const profileEvents = app.events.filter(event => event.type === 'live-agent:profile').length;
  app.run(`onState({exercise: {request_id: "retired-ticket", concept: "Old concept", options: ["A"], option_texts: ["Old choice"]},
      lambda_s: 1.5, next_lock: 7, listening: true, erasure_gate_open: true, chains: []});
    onEvent({event: "lesson", data: {stage: "exercise_open", request_id: "retired-ticket", concept: "Old concept", options: ["A"]}});
    onEvent({event: "lesson", data: {stage: "exercise_closed", request_id: "retired-ticket"}});
    onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Unscoped old concept", options: ["A"]}});`);
  assert.equal(app.element('chips').children[0], currentChoice);
  assert.equal(app.run('document.activeElement === $("chips").children[0]'), true);
  assert.equal(app.run('currentExercise.request_id'), 'current-ticket');
  assert.equal(app.element('sLambda').textContent, '1.5');
  assert.equal(app.element('sReq').textContent, 7);
  assert.equal(app.element('flags').textContent, '聆听中');
  assert.equal(app.events.filter(event => event.type === 'live-agent:profile').length, profileEvents);
  assert.equal(app.events.findLast(event => event.type === 'live-agent:state').detail.exercise.request_id, 'retired-ticket');
  app.run('showProfile({id: "actual-student", name: "Current learner", concepts: [], exams: []});');
  assert.match(app.element('prof').innerHTML, /Current learner/);
  assert.equal(app.events.filter(event => event.type === 'live-agent:profile').length, profileEvents + 1);
  app.run('onEvent({event: "lesson", data: {stage: "exercise_closed", request_id: "current-ticket"}});');
  assert.equal(app.run('currentExercise'), null);
  assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
});

test('retired exercise snapshots cannot retain or resurrect chips through state or language refresh', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({board: true});
  app.run(`window.activityTicket = "old-ticket";
    window.LiveAgentProduct.acceptsActivity = requestId => requestId === window.activityTicket;
    showExercise({request_id: "old-ticket", concept: "Old concept", options: ["A"], option_texts: ["Old choice"]});
    window.activityTicket = "new-ticket";
    onState({exercise: {request_id: "old-ticket", concept: "Old concept", options: ["A"]}, erasure_gate_open: true, chains: []});`);
  assert.equal(app.run('currentExercise'), null);
  assert.equal(app.run('exerciseKey'), '');
  assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
  app.run(`window.activityTicket = "new-ticket";
    showExercise({request_id: "new-ticket", concept: "New concept", options: ["B"]});
    window.activityTicket = null; window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();`);
  assert.equal(app.run('currentExercise'), null);
  assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
  app.run('showExercise({concept: "Manual exercise", options: ["C"]});');
  assert.equal(app.element('chips').children[0].textContent, 'Choose C');
  app.run('showExercise(null);');
  assert.equal(app.run('currentExercise'), null);
});

test('the public restoreExercise method accepts the adopted owner and rejects a stale conflict', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({board: true});
  app.run(`window.currentOwner = "request-C";
    window.LiveAgentProduct.acceptsActivity = requestId => requestId === window.currentOwner;
    profile = {id: "actual-profile"};
    window.LiveAgentMedia.restoreExercise({request_id: "request-B", concept: "Existing question", options: ["B"]});`);
  assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
  const events = app.events.length, packets = app.sockets[0].sent.length, timers = app.timers.size, hooks = app.transitions.length;
  app.run(`window.currentOwner = "request-B";
    window.LiveAgentMedia.restoreExercise({request_id: "request-B", concept: "Existing question", options: ["B"], option_texts: ["Recovered B choice"]});`);
  assert.equal(app.element('chips').children[0].textContent, '选 B');
  assert.equal(app.element('chips').children[0]['aria-label'], '选 B: Recovered B choice');
  app.run(`window.currentOwner = "request-D";
    window.LiveAgentMedia.restoreExercise({request_id: "request-D", concept: "New question", options: ["D"]});
    window.LiveAgentMedia.restoreExercise({request_id: "request-B", concept: "Stale conflict", options: ["B"]});`);
  assert.equal(app.element('chips').children[0].textContent, '选 D');
  assert.equal(app.run('currentExercise.request_id'), 'request-D');
  assert.equal(app.events.length, events);
  assert.equal(app.sockets[0].sent.length, packets);
  assert.equal(app.timers.size, timers);
  assert.equal(app.transitions.length, hooks);
  assert.equal(app.run('profile.id'), 'actual-profile');
  app.run('onState({exercise: null, erasure_gate_open: true, chains: []});');
  assert.equal(app.run('currentExercise'), null);
  assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
});

test('modern ordinary submissions retire legacy unowned exercises without rejecting fresh-scope compatibility', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({board: true});
  app.run(`window.currentOwner = null;
    window.LiveAgentProduct.acceptsActivity = requestId => (requestId ?? null) === window.currentOwner;
    window.originalDispatch = window.dispatchEvent;
    window.dispatchEvent = event => {window.originalDispatch(event); if(event.type === "live-agent:submitted") window.currentOwner = event.detail.request_id;};
    window.LiveAgentMedia.restoreExercise({concept: "Legacy manual question", options: ["A"]});`);
  assert.equal(app.element('chips').children[0].textContent, '选 A');
  app.run('showExercise(null); sendText("A newer ordinary question");');
  const owner = app.events.at(-1).detail.request_id; assertRequestId(owner);
  app.run(`onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Late legacy question", options: ["L"]}});
    onState({exercise: {concept: "Late legacy state", options: ["L"]}, erasure_gate_open: true, chains: []});`);
  assert.equal(app.run('currentExercise'), null);
  assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
  app.run(`window.LiveAgentMedia.restoreExercise({request_id: ${JSON.stringify(owner)}, concept: "Current question", options: ["B"]});
    onState({exercise: {concept: "Late unscoped state", options: ["L"]}, erasure_gate_open: true, chains: []});`);
  assert.equal(app.element('chips').children[0].textContent, '选 B');
  assert.equal(app.run('currentExercise.request_id'), owner);
  app.run('onState({exercise: null, erasure_gate_open: true, chains: []});');
  assert.equal(app.run('currentExercise'), null);
});

test('replacing focused chips preserves a matching prompt and returns removed choices to the composer', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status();
  app.run('setChips([{label: "Original label", text: "这一步我还没明白"}], true)');
  app.element('chips').children[0].focus();
  app.run('setChips([{label: "New label", text: "这一步我还没明白"}], true)');
  assert.equal(app.run('document.activeElement === $("chips").children[0]'), true);
  app.run('setChips(["Different prompt"], true)');
  assert.equal(app.run('document.activeElement === $("text")'), true);
});

test('classroom mastery evidence and capability labels are visible and localized in English', async () => {
  const app = page({ edition: 'university' }); await app.connect(); await app.open(); await app.status();
  app.run(`showProfile({id: "actual-student", name: "Learner", grade: "Grade 8", exams: [],
    concepts: [{name: "Fractions", level: "partial", source: "exercise", mastery: 0.5, attempts: 3, correct: 2}]});`);
  const html = app.element('prof').innerHTML;
  assert.match(html, /tabindex="0" aria-describedby="concept-evidence-0"/);
  assert.match(html, /<p class="meta concept-evidence" id="concept-evidence-0">Partly understood · Uncalibrated estimate · Based on recorded practice · Recorded practice: 2\/3 correct<\/p>/);
  assert.doesNotMatch(html, /hover|据练习|无依据|已掌握|薄弱/);
  const badges = app.element('badges').children.map(node => node.textContent).join('\n');
  assert.match(badges, /Video: Mock video \(CPU preview\)/);
  assert.match(badges, /Responder: Rules \(preview\)/);
  assert.doesNotMatch(badges, /生成|质检|仅文字/);
});

test('English camera controls are localized on load and board progress labels use the current language', () => {
  const app = page({ edition: 'university' });
  assert.equal(app.element('cam').textContent, 'Enable focus check');
  assert.equal(app.element('focus').textContent, 'Focus check is off');
  assert.equal(app.run('boardSentenceLabel(2, 3)'), 'Sentence 2/3');
  const dot = app.element('progress-dot'), item = app.element('board-item');
  item.querySelector = selector => selector === '.dots' ? dot : null;
  app.element('boardItems').children = [item];
  app.run('shownBoard = {key: "actual-lesson", title: "原始课程标题", progress: [2, 3]}; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(dot['aria-label'], 'Sentence 2/3');
  assert.equal(app.element('boardTitle').innerHTML, '原始课程标题');
});

test('language refresh translates a connected session without replaying hooks or overwriting profile data', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ asr: true, attention: true });
  app.run('onEvent({event: "attention", data: {state: "focused", stable: "distracted", reason: "raw source reason"}}); profile = {id: "actual-profile"};');
  const hooks = app.transitions.length, events = app.events.length, packets = app.sockets[0].sent.length, timers = app.timers.size;
  app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(app.element('conn').textContent, 'Tutor ready');
  const badges = app.element('badges').children.map(node => node.textContent).join('\n');
  assert.match(badges, /Video: Mock video/);
  assert.doesNotMatch(badges, /生成|质检|仅文字/);
  assert.equal(app.element('focus').textContent, 'Focus check: Distracted (raw source reason)');
  assert.equal(app.element('cam').textContent, 'Enable focus check');
  assert.equal(app.run('profile.id'), 'actual-profile');
  assert.equal(app.transitions.length, hooks);
  assert.equal(app.events.length, events);
  assert.equal(app.sockets[0].sent.length, packets);
  assert.equal(app.timers.size, timers);
});

test('an edition switch translates error advice without restarting or replacing the specific error beforehand', async () => {
  const app = page();
  const failure = app.element('connectionError'), message = app.element('connectionErrorText'), retry = app.element('connectionRetry');
  failure.children = [message, retry];
  failure.querySelector = selector => selector === '#connectionErrorText' ? message : null;
  const socket = await app.connect(); socket.onerror();
  const original = message.textContent;
  assert.match(original, /连接不上/);
  app.run('window.LiveAgentMedia.refreshLanguage();');
  assert.equal(message.textContent, original);
  assert.equal(app.element('overlay').textContent, original);
  app.run('window.LiveAgentProduct.edition = "secondary"; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(message.textContent, original);
  assert.equal(app.element('overlay').textContent, original);
  app.run('profile = {id: "actual-profile"};');
  const hooks = app.transitions.length, events = app.events.length, packets = socket.sent.length, timers = app.timers.size;
  app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(app.run('sessionState'), 'error');
  assert.equal(app.element('overlay').textContent, 'Your session stopped. Please reconnect to continue.');
  assert.equal(message.textContent, app.element('overlay').textContent);
  assert.equal(app.element('overlay').style.display, 'flex');
  assert.equal(failure.hidden, false);
  assert.equal(failure.children[1], retry);
  assert.equal(app.element('conn').textContent, 'Disconnected');
  assert.equal(app.run('profile.id'), 'actual-profile');
  assert.equal(app.transitions.length, hooks);
  assert.equal(app.events.length, events);
  assert.equal(socket.sent.length, packets);
  assert.equal(app.timers.size, timers);
  assert.equal(app.sockets.length, 1);
  app.run('window.LiveAgentProduct.edition = "secondary"; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(message.textContent, '会话暂时中断了，请重新连接后继续。');
});

test('exercise language refresh preserves focused answers, backend values and readiness without replaying events', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ board: true });
  app.run(`onEvent({event: "lesson", data: {stage: "exercise_open", concept: "Fractions", question: "选一个分数",
    options: ["A", "B"], option_texts: ["A. 二分之一", "B. 三分之一"]}}); profile = {id: "actual-profile"};`);
  assert.deepEqual(app.element('chips').children.map(node => node.textContent), ['选 A', '选 B', '我不会']);
  app.element('chips').children[1].focus();
  const key = app.run('exerciseKey'), hooks = app.transitions.length, events = app.events.length;
  const packets = app.sockets[0].sent.length, timers = app.timers.size;
  app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
  const choices = app.element('chips').children;
  assert.deepEqual(choices.map(node => node.textContent), ['Choose A', 'Choose B', 'I’m not sure']);
  assert.deepEqual(choices.map(node => node.dataset.prompt), ['选 A', '选 B', '我不会']);
  assert.equal(choices[1]['aria-label'], 'Choose B: B. 三分之一');
  assert.equal(app.run('document.activeElement === $("chips").children[1]'), true);
  assert.equal(choices.every(node => node.classList.contains('answer') && !node.disabled), true);
  assert.equal(app.run('exerciseKey'), key);
  assert.equal(app.run('profile.id'), 'actual-profile');
  assert.equal(app.transitions.length, hooks);
  assert.equal(app.events.length, events);
  assert.equal(app.sockets[0].sent.length, packets);
  assert.equal(app.timers.size, timers);

  app.element('text').focus();
  app.run('sessionState = "connecting"; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(app.element('chips').children.every(node => node.disabled), true);
  assert.equal(app.run('document.activeElement === $("text")'), true);
  assert.equal(app.run('sessionState'), 'connecting');
  assert.equal(app.sockets[0].sent.length, packets);
  assert.equal(app.events.length, events);
  assert.equal(app.transitions.length, hooks);

  app.run('resetSessionView(); window.LiveAgentMedia.refreshLanguage();');
  assert.equal(app.run('currentExercise'), null);
  assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
});

for (const [name, end] of [
  ['End', app => app.element('disconnect').onclick()],
  ['backend error', app => app.sockets[0].onmessage({data: JSON.stringify({type: 'error', error: 'Service failed'})})],
  ['unclean close', app => app.sockets[0].onclose({code: 1006, wasClean: false})],
]) {
  test(`${name} clears exercise answers and accessible labels before language refresh`, async () => {
    const app = page(); await app.connect(); await app.open(); await app.status({board: true});
    app.run(`onEvent({event: "lesson", data: {stage: "exercise_open", concept: "PRIVATE CONCEPT", options: ["A", "B"],
      option_texts: ["PRIVATE CHOICE ONE", "PRIVATE CHOICE TWO"]}});`);
    assert.match(app.element('chips').children[0]['aria-label'], /PRIVATE CHOICE/);
    await end(app);
    const packets = app.sockets[0].sent.length, events = app.events.length;
    const assertCleared = () => {
      assert.equal(app.run('exerciseKey'), '');
      assert.equal(app.run('currentExercise'), null);
      assert.equal(app.element('chips').children.every(node => node.disabled), true);
      assert.equal(app.element('chips').children.some(node => node.classList.contains('answer')), false);
      assert.doesNotMatch(app.element('chips').children.map(node => node['aria-label'] || '').join(' '), /PRIVATE/);
    };
    assertCleared();
    app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
    assertCleared();
    assert.equal(app.sockets[0].sent.length, packets);
    assert.equal(app.events.length, events);
  });
}

test('English diagnostics translate authored detail strings across event branches', () => {
  const app = page({edition: 'university'});
  const events = [
    {event: 'utterance_end', data: {decision: {relation: 'replace', kind: 'memory', forget_term: 'term'}, recalled: ['source fact']}},
    {event: 'lock', data: {action: 'action', transcript: 'script', retry_of: 2, corrections: ['fix']}},
    {event: 'verdict', data: {kind: 'action', label: 'complied', rationale: 'raw rationale'}},
    {event: 'verdict', data: {kind: 'action', label: 'not_complied'}},
    {event: 'verdict', data: {kind: 'action', label: 'unknown'}},
    {event: 'verdict', data: {kind: 'speech', label: 'not_complied'}},
    {event: 'repair', data: {earliest_correctable: 3}},
    {event: 'completion_claim'}, {event: 'refusal', data: {reason: 'raw refusal'}}, {event: 'capacity_skip'},
    {event: 'narration_guard', data: {original: 'raw source wording'}},
    {event: 'playback_stop', data: {erasure: true, erasure_complete: true, deleted: 2}},
    {event: 'playback_stop', data: {erasure: true, erasure_complete: false}}, {event: 'playback_stop'},
    {event: 'audit', data: {issues: ['source issue']}}, {event: 'error', data: {where: 'model', error: 'source error'}},
    {event: 'lesson', data: {stage: 'outline', title: 'Topic', sections: [1, 2], adaptive: true,
      plan: [{title: 'Review', depth: 'review', exercise: true}, {title: 'Core', depth: 'core'}, {title: 'New', depth: 'new'}]}},
    {event: 'lesson', data: {stage: 'section', section: 1, title: 'Topic', lines: 2, points: 3, exercise: 'raw exercise'}},
    {event: 'lesson', data: {stage: 'section_failed', section: 1}},
    {event: 'lesson', data: {stage: 'section_failed', section: 1, attempt: 1}},
    {event: 'lesson', data: {stage: 'outline_failed'}}, {event: 'lesson', data: {stage: 'planned', title: 'Topic'}},
    {event: 'lesson', data: {stage: 'figure_judgement', title: 'Topic', judgements: [
      {point: 0, complexity: 2, need: true, why: 'source reason'}, {point: 1, need: false}]}},
    {event: 'lesson', data: {stage: 'figure', point: 0, kind: 'plot'}},
    {event: 'lesson', data: {stage: 'figure', point: 1, kind: 'illustration'}},
    {event: 'lesson', data: {stage: 'figure_failed', error: 'source error'}},
    {event: 'lesson', data: {stage: 'exercise', concept: 'Concept', exercise: 'raw exercise'}},
    {event: 'lesson', data: {stage: 'exercise_failed', error: 'source error'}},
    {event: 'lesson', data: {stage: 'exercise_timeout', concept: 'Concept'}},
    {event: 'lesson', data: {stage: 'grading_failed', error: 'source error'}},
    {event: 'lesson', data: {stage: 'profile_updated', changed: ['Concept']}},
    {event: 'lesson', data: {stage: 'exercise_graded', concept: 'Concept', correct: true, mastery: {before: 0.5, after: 0.6}}},
    {event: 'lesson', data: {stage: 'exercise_graded', concept: 'Concept', skipped: true}},
    {event: 'lesson', data: {stage: 'exercise_graded', concept: 'Concept', misconception: 'source misconception', mastery: {after: 0.4}}},
    {event: 'attention', data: {state: 'focused', reason: 'source reason', nudge: 'source reminder'}},
    {event: 'continuity', data: {anchor_removed: ['source anchor'], wrong: {anchor: ['attribute']}, corrections: ['fix'], target: 3}},
  ];
  app.run(`for (const event of ${JSON.stringify(events)}) onEvent({...event, t: 1, request: 2});`);
  const feed = app.element('feed').children.map(node => node.innerHTML).join('\n');
  const memory = app.element('memory').children.map(node => node.innerHTML).join('\n');
  assert.doesNotMatch(feed + memory, /\p{Script=Han}/u);
  assert.match(feed, /Retry #2/);
  assert.match(feed, /Section 2 prepared: Topic \(2 sentences, 3 board points\)/);
  assert.match(feed, /Point 1, complexity 2 → figure \(source reason\)/);
  assert.match(feed, /Estimated mastery 50% → 60%/);
  assert.match(feed, /Correction → #3/);
  assert.match(memory, /Deleted 2 records/);
});

test('English diagnostics retain original backend reasons, curriculum titles and user text', () => {
  const app = page({edition: 'university'});
  app.run(`onEvent({event: "utterance_end", data: {decision: {forget_term: "用户事实"}, recalled: ["原始记忆"]}});
    onEvent({event: "refusal", data: {reason: "后端原始原因"}});
    onEvent({event: "lesson", data: {stage: "outline", title: "一次函数", sections: []}});
    onEvent({event: "lesson", data: {stage: "figure_judgement", title: "一次函数", judgements: [{point: 0, need: true, why: "后端配图依据"}]}});
    onEvent({event: "narration_guard", data: {original: "原始说法"}});`);
  const feed = app.element('feed').children.map(node => node.innerHTML).join('\n');
  assert.match(feed, /Delete “用户事实”/);
  assert.match(feed, /后端原始原因/);
  assert.match(feed, /Lesson outline: 一次函数 \(0 sections\)/);
  assert.match(feed, /后端配图依据/);
  assert.match(feed, /Removed unverified completion wording: “原始说法”/);
  assert.match(app.element('memory').children[0].innerHTML, /Recalled: 原始记忆/);
});

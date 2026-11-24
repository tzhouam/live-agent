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

function page({ edition = 'primary', codec, bitmap, href = '/', avatar, videoDecoder } = {}) {
  const elements = new Map(), sockets = [], events = [], transitions = [], permissions = [];
  const dialogCloseEvents = [];
  const timers = new Map(), intervals = [];
  let nextTimer = 0;
  function element(id) {
    if (!elements.has(id)) {
      const node = { id, value: '', textContent: '', className: '', children: [], style: {}, dataset: {},
        hidden: false, disabled: false, open: false, width: 480, height: 864, clientWidth: 1000,
        clientHeight: 500, scrollHeight: 0, scrollTop: 0,
        appendChild(child) { child.parent = this; this.children.push(child); },
        contains(child) { return this.children.includes(child); },
        focus() { document.activeElement = this; },
        showModal() { this.returnFocus = document.activeElement; this.open = true; element('boardFigureClose').focus(); },
        close() {
          if (!this.open) return;
          this.open = false; this.returnFocus?.focus();
          dialogCloseEvents.push(() => this.onclose?.());
        },
        remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); },
        querySelector() { return null; },
        querySelectorAll(selector) { return selector.includes('.badge') ? this.children.filter(child => child.className === 'badge') : []; },
        setAttribute(name, value) { this[name] = value; },
        getAttribute(name) { return this[name] ?? null; }, removeAttribute(name) { delete this[name]; },
        getContext() { return { drawImage() {}, clearRect() {} }; },
        toDataURL() { return 'data:image/jpeg;base64,anBlZw=='; },
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
    location: { href },
    dispatchEvent(event) { events.push(event); },
    LiveAgentAPI: { websocketUrl() { return 'ws://frontend.test/ws'; } },
    LiveAgentProduct: {
      edition, t(_key, fallback) { return fallback; },
      examples() { return [{ label: 'Explain this step', text: '这一步我还没明白' }]; },
      sessionChanged(state, detail) { transitions.push({ state, detail }); },
    },
  };
  const context = vm.createContext({ document, window, WebSocket, MediaRecorder, Blob, URL,
    AudioContext, CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    navigator: { mediaDevices: {
      addEventListener() {},
      getUserMedia(options) { const request = { ...deferred(), options }; permissions.push(request); return request.promise; },
    } },
    console: { warn() {}, error() {} }, performance: { now: () => 1000 },
    localStorage: { getItem() { return null; }, setItem() {} },
    innerHeight: 800, innerWidth: 1200, addEventListener() {}, requestAnimationFrame() {},
    setInterval(callback, ms) { const id = ++nextTimer; timers.set(id, callback); intervals.push({id, ms}); return id; },
    clearInterval(id) { timers.delete(id); },
    setTimeout(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
    clearTimeout(id) { timers.delete(id); },
    createImageBitmap: bitmap || (() => Promise.resolve({ close() {} })),
    ...(avatar ? { createAvatarMock: avatar } : {}),
    ...(videoDecoder ? {VideoDecoder:videoDecoder,EncodedVideoChunk:class{constructor(data){Object.assign(this,data);}}}
      : codec ? { VideoDecoder: { isConfigSupported: codec } } : {}),
  });
  vm.runInContext(source, context);
  if (avatar) vm.runInContext('loadTeacherAvatar = async () => createAvatarMock', context);
  element('mode').value = 'private'; element('uid').value = 'actual-user'; element('sid').value = 'actual-student';
  const run = code => vm.runInContext(code, context);
  async function connect() { await element('connect').onclick(); return sockets.at(-1); }
  async function open(socket = sockets.at(-1)) { socket.readyState = 1; await socket.onopen(); }
  async function status(extra = {}, socket = sockets.at(-1)) {
    await socket.onmessage({ data: JSON.stringify({ type: 'status', session: 'actual-session',
      generator: 'mock', responder: 'rules', director: 'online', judge: 'mock',
      asr: false, attention: false, board: false, student: null, ...extra }) });
  }
  const flushDialogCloseEvents = () => { while (dialogCloseEvents.length) dialogCloseEvents.shift()(); };
  return { element, sockets, events, transitions, permissions, timers, intervals, run, connect, open, status, flushDialogCloseEvents };
}

function stream() {
  let stopped = 0;
  return { getTracks: () => [{ stop() { stopped++; } }], stopped: () => stopped };
}

function meshFixture({create, href = '/?avatar=mesh', bitmap} = {}) {
  const states = [], calls = {reset:0,destroy:0,capture:0};
  const rig = {active:true,model:'teacher-mesh-v1',render(state) {states.push({...state});},
    capture() {calls.capture++; return 'data:image/jpeg;base64,anBlZw==';},
    reset() {calls.reset++;},destroy() {calls.destroy++; this.active=false;}};
  let options;
  const app = page({href,bitmap,avatar:async value => {options=value; return create ? create(value,rig) : rig;}});
  return {...app,rig,states,calls,options:()=>options};
}
const meshStatus = {avatar:{renderer:'mesh',model:'teacher-mesh-v1',epoch:0,supported_capabilities:['idle_teach','explain']}};
async function readyMesh(app) { await app.connect(); await app.open(); await app.status(meshStatus); }
function meshChunk(app, chunk, {offset = chunk,duration = 2,request = 7,epoch = 0} = {}) {
  app.run(`schedule({meta:{request:${request},chunk:${chunk},width:480,height:864,sample_rate:16000,
    duration:1,n_frames:24,fps:24,avatar:{renderer:'mesh',model:'teacher-mesh-v1',gesture:'explain',
      request_time_s:${offset},request_duration_s:${duration},motion_time_s:${8+offset},epoch:${epoch}}},
    frames:[{close(){}}],pcm:new Int16Array(16000).fill(7000),epoch});`);
}
async function startJpegChunk(app, chunk=0, {mesh=true,nFrames=1,videoFrames,frameIndices}={}) {
  const socket=app.sockets.at(-1);
  const avatar=mesh?{avatar:{renderer:'mesh',model:'teacher-mesh-v1',epoch:0,gesture:'explain',
    request_time_s:chunk,request_duration_s:2,motion_time_s:chunk}}:{};
  const sparse=videoFrames==null?{}:{video_frames:videoFrames,video_frame_indices:frameIndices};
  await socket.onmessage({data:JSON.stringify({type:'chunk',request:7,chunk,width:480,height:864,
    sample_rate:16000,duration:1,n_frames:nFrames,fps:nFrames,...avatar,...sparse})});
  for(let i=0;i<(videoFrames??nFrames);i++)await socket.onmessage({data:new ArrayBuffer(4)});
  return {completion:socket.onmessage({data:new Int16Array(16000).buffer})};
}

test('mesh PCM schedules in order before hidden video decode and eventual frames support fallback', async () => {
  const first=deferred(),second=deferred(); let call=0;
  const app=meshFixture({bitmap:()=>[first.promise,second.promise][call++]});await readyMesh(app);
  const a=await startJpegChunk(app),b=await startJpegChunk(app,1);
  await a.completion;await b.completion;
  assert.equal(app.run('queue.length'),2);
  assert.equal(app.run('queue[0].frames.length'),0);
  assert.equal(app.run('queue[1].start===queue[0].end'),true);
  const start=app.run('queue[0].start');
  second.resolve({close(){}});await new Promise(setImmediate);
  assert.equal(app.run('queue[0].frames.length'),0);assert.equal(app.run('queue[1].frames.length'),1);
  app.rig.active=false;app.run('audioCtx.currentTime=.3;renderFrame(300);');
  assert.equal(app.run('window.LiveAgentMedia.avatarState().renderer'),'video');
  first.resolve({close(){}});await new Promise(setImmediate);
  app.run('audioCtx.currentTime=.6;renderFrame(600);');
  assert.equal(app.run('queue[0].frames.length'),1);
  assert.equal(app.run('queue[0].start'),start);
  assert.ok(app.run('queue[0].painted.size')>0);
});

test('legacy video keeps its decode gate and ordered playback when later chunks decode first', async () => {
  const first=deferred();let call=0;
  const app=page({bitmap:()=>call++===0?first.promise:Promise.resolve({close(){}})});
  await app.connect();await app.open();await app.status();
  const a=await startJpegChunk(app,0,{mesh:false}),b=await startJpegChunk(app,1,{mesh:false});
  await b.completion;assert.equal(app.run('queue.length'),0);
  first.resolve({close(){}});await a.completion;
  assert.equal(app.run('queue.length'),2);assert.equal(app.run('queue[0].meta.chunk'),0);
  assert.equal(app.run('queue[1].meta.chunk'),1);assert.equal(app.run('queue[1].start===queue[0].end'),true);
});

test('mesh reset closes late fallback decodes without restoring playback', async () => {
  const decoded=deferred();let closed=0;
  const app=meshFixture({bitmap:()=>decoded.promise});await readyMesh(app);
  const c=await startJpegChunk(app);await c.completion;assert.equal(app.run('queue.length'),1);
  app.run('stopAll()');decoded.resolve({close(){closed++;}});await new Promise(setImmediate);
  assert.equal(closed,1);assert.equal(app.run('queue.length'),0);assert.equal(app.run('decoding.length'),0);
});

test('retired mesh chunks close a late decode and completed video frames are released after AV retention', async () => {
  const decoded=deferred();let lateClosed=0;
  const mesh=meshFixture({bitmap:()=>decoded.promise});await readyMesh(mesh);
  const c=await startJpegChunk(mesh);await c.completion;
  mesh.run('audioCtx.currentTime=2;renderFrame(2000)');assert.equal(mesh.run('queue.length'),0);
  decoded.resolve({close(){lateClosed++;}});await new Promise(setImmediate);assert.equal(lateClosed,1);
  let closed=0;
  const video=page({bitmap:()=>Promise.resolve({close(){closed++;}})});
  await video.connect();await video.open();await video.status();
  const v=await startJpegChunk(video,0,{mesh:false});await v.completion;
  video.run('audioCtx.currentTime=1.3;renderFrame(1300)');assert.equal(closed,0);
  video.run('audioCtx.currentTime=2;renderFrame(2000)');assert.equal(closed,1);assert.equal(video.run('queue.length'),0);
});

test('reset also closes already decoded legacy chunks waiting behind an unresolved predecessor', async () => {
  const first=deferred();let calls=0,closed=0;
  const app=page({bitmap:()=>calls++===0?first.promise:Promise.resolve({close(){closed++;}})});
  await app.connect();await app.open();await app.status();
  const a=await startJpegChunk(app,0,{mesh:false}),b=await startJpegChunk(app,1,{mesh:false});
  await b.completion;assert.equal(app.run('decoding.length'),2);
  app.run('stopAll()');assert.equal(closed,1);
  first.resolve({close(){closed++;}});await a.completion;
  assert.equal(closed,2);assert.equal(app.run('queue.length'),0);
});

test('failed JPEG chunks release successful bitmaps while mesh speech continues', async () => {
  const failure=deferred();let calls=0,closed=0;
  const app=meshFixture({bitmap:()=>calls++===0?Promise.resolve({close(){closed++;}}):failure.promise});
  await readyMesh(app);const c=await startJpegChunk(app,0,{nFrames:2});await c.completion;
  assert.equal(app.run('queue.length'),1);
  failure.reject(new Error('Bad JPEG'));await new Promise(setImmediate);
  assert.equal(closed,1);assert.equal(app.run('queue.length'),1);assert.equal(app.run('queue[0].frames.length'),0);
});

test('failed H264 decoding closes its decoder, native frames, and partial bitmap output', async () => {
  let decoderClosed=0,frameClosed=0,bitmapClosed=0;
  class Decoder {
    constructor(callbacks){this.callbacks=callbacks;}
    configure(){}
    decode(){this.callbacks.output({close(){frameClosed++;}});}
    flush(){return Promise.reject(new Error('Invalid H264 segment'));}
    close(){decoderClosed++;}
  }
  const app=page({videoDecoder:Decoder,bitmap:()=>Promise.resolve({close(){bitmapClosed++;}})});
  await assert.rejects(app.run('decodeH264(new ArrayBuffer(4),{width:480,height:864,fps:24,sizes:[4]})'),/Invalid H264/);
  await new Promise(setImmediate);
  assert.equal(decoderClosed,1);assert.equal(frameClosed,1);assert.equal(bitmapClosed,1);
});

test('mesh preview is opt-in and negotiates only a loaded matching model', async () => {
  const legacy = meshFixture({href:'/'}); await legacy.connect(); await legacy.open();
  assert.equal(legacy.options(),undefined);
  assert.equal(Object.hasOwn(JSON.parse(legacy.sockets[0].sent[0]),'renderer'),false);
  const app = meshFixture(); await readyMesh(app);
  assert.equal(app.options().modelUrl,'/assets/teacher-mesh/rig-v7.json');
  assert.equal(app.options().fallbackCanvas,app.element('screen'));
  const hello = JSON.parse(app.sockets[0].sent[0]);
  assert.equal(hello.renderer,'mesh'); assert.equal(hello.avatar_model,'teacher-mesh-v1');
  assert.equal(hello.avatar_video_frames,true);
  assert.equal(app.run('window.LiveAgentMedia.avatarState().renderer'),'mesh');
  assert.equal(app.element('screenWrap').dataset.renderer,'mesh');
  assert.equal(app.element('overlay').style.display,'none');
  assert.equal(app.run('sessionStatus.avatar.supported_capabilities[1]'),'explain');
});

test('sparse standby JPEG frame counts preserve full PCM and fallback reports native painted indices', async () => {
  const app=meshFixture();await readyMesh(app);
  const c=await startJpegChunk(app,0,{nFrames:24,videoFrames:2,frameIndices:[0,12]});await c.completion;
  await new Promise(setImmediate);
  assert.equal(app.run('queue[0].frames.length'),2);assert.equal(app.run('queue[0].pcm.length'),16000);
  assert.equal(app.run('queue[0].meta.n_frames'),24);
  app.run('audioCtx.currentTime=.3;renderFrame(300)');
  const capture=app.sockets[0].sent.map(value=>JSON.parse(value)).find(packet=>packet.type==='avatar_frame');
  assert.equal(capture.frame,6);  // actual mesh evidence still uses the full native clock
  app.rig.active=false;app.run('audioCtx.currentTime=.4;renderFrame(400)');
  app.run('audioCtx.currentTime=.8;renderFrame(800)');
  assert.deepEqual(JSON.parse(app.run('JSON.stringify([...queue[0].painted])')),[0,12]);
  app.run('audioCtx.currentTime=1.2;renderFrame(1200)');
  const end=app.sockets[0].sent.map(value=>JSON.parse(value)).find(packet=>packet.type==='chunk_end');
  assert.equal(end.renderer,'video');assert.deepEqual(end.painted,[0,12]);
});

test('sparse H264 timestamps follow original frame positions without changing the full audio clock', async () => {
  const timestamps=[];
  class Decoder{
    constructor(callbacks){this.callbacks=callbacks;}
    configure(){}close(){}
    decode(chunk){timestamps.push(chunk.timestamp);this.callbacks.output({close(){}});}
    flush(){return Promise.resolve();}
  }
  const app=page({videoDecoder:Decoder});
  const frames=await app.run('decodeH264(new ArrayBuffer(8),{width:480,height:864,fps:24,n_frames:24,video_frames:2,video_frame_indices:[0,12],sizes:[4,4]})');
  assert.equal(frames.length,2);assert.deepEqual(timestamps,[0,500000]);frames.forEach(frame=>frame.close());
});

test('a failed model load and an older server preserve working video without changing legacy hello', async () => {
  const failed = meshFixture({create:async()=>{throw new Error('Missing model');}});
  await failed.connect(); await failed.open();
  assert.equal(Object.hasOwn(JSON.parse(failed.sockets[0].sent[0]),'renderer'),false);
  assert.equal(failed.element('screen').style.visibility,'visible');
  const oldServer = meshFixture(); await oldServer.connect(); await oldServer.open(); await oldServer.status();
  assert.equal(oldServer.calls.destroy,1);
  assert.equal(oldServer.run('window.LiveAgentMedia.avatarState().renderer'),'video');
  assert.equal(oldServer.run('window.LiveAgentMedia.captureAvatar()'),null);
  assert.equal(oldServer.run('sessionState'),'ready');
});

test('cancelled asynchronous model loading destroys its renderer without opening a stale socket', async () => {
  const pending = deferred(), started=deferred();
  const app = meshFixture({create:async(_options,rig)=>{started.resolve();await pending.promise;return rig;}});
  const connecting = app.connect();
  await started.promise;
  app.element('disconnect').onclick(); pending.resolve(); await connecting;
  assert.equal(app.calls.destroy,1); assert.equal(app.sockets.length,0);
  assert.equal(app.run('sessionState'),'disconnected');
});

test('mesh uses the heard audio clock across chunk seams and sends actual canvas evidence without puppet paints', async () => {
  const app = meshFixture(); await readyMesh(app); meshChunk(app,0); meshChunk(app,1);
  app.run('audioCtx.currentTime=0.8; renderFrame(800);');
  const first = app.states.at(-1);
  assert.ok(first.requestTime > 0.7 && first.requestTime < 0.8);
  assert.ok(first.mouthOpen > 0); assert.ok(first.motionTime > 8.7);
  const frames = app.sockets[0].sent.map(value=>JSON.parse(value)).filter(packet=>packet.type==='avatar_frame');
  assert.equal(frames.length,1); assert.equal(frames[0].renderer,'mesh');
  assert.equal(frames[0].image,'data:image/jpeg;base64,anBlZw==');
  assert.equal(frames[0].epoch,0); assert.equal(frames[0].frame,18);
  assert.ok(frames[0].request_time_s > 0.7);
  app.run('audioCtx.currentTime=1.04; renderFrame(1040);');
  const before = app.states.at(-1);
  app.run('audioCtx.currentTime=1.05; renderFrame(1050);');
  const after = app.states.at(-1);
  assert.ok(after.requestTime > before.requestTime);
  assert.ok(after.requestTime-before.requestTime < 0.02);
  assert.ok(after.motionTime-before.motionTime < 0.02);
  assert.ok(Math.abs(after.mouthOpen-before.mouthOpen) < 0.1);
  const end = app.sockets[0].sent.map(value=>JSON.parse(value)).find(packet=>packet.type==='chunk_end');
  assert.equal(end.renderer,'mesh'); assert.equal(end.model,'teacher-mesh-v1'); assert.deepEqual(end.painted,[]);
  app.run('audioCtx.currentTime=2.2; renderFrame(2200);');
  assert.equal(app.states.at(-1).mouthOpen,0);
  assert.equal(app.states.at(-1).gesture,'idle');
});

test('decoded mesh chunks report receipt with the negotiated epoch before scheduling', async () => {
  const app=meshFixture(); await readyMesh(app);
  const socket=app.sockets[0];
  await socket.onmessage({data:JSON.stringify({type:'chunk',request:7,chunk:0,width:480,height:864,
    sample_rate:16000,duration:1,n_frames:1,fps:1,avatar:{renderer:'mesh',model:'teacher-mesh-v1',epoch:0,
      gesture:'explain',request_time_s:0,request_duration_s:1,motion_time_s:0}})});
  await socket.onmessage({data:new ArrayBuffer(4)});
  await socket.onmessage({data:new Int16Array(16000).buffer});
  const received=socket.sent.map(value=>JSON.parse(value)).find(packet=>packet.type==='chunk_received');
  assert.equal(received.renderer,'mesh'); assert.equal(received.model,'teacher-mesh-v1'); assert.equal(received.epoch,0);
  assert.equal(app.run('queue.length'),1);
});

test('mesh stop resets speech immediately and rejects a stale decoded epoch before scheduling', async () => {
  const app = meshFixture(); await readyMesh(app); meshChunk(app,0);
  app.run('audioCtx.currentTime=0.5;renderFrame(500);');
  const before = app.calls.reset;
  await app.sockets[0].onmessage({data:JSON.stringify({type:'stop',epoch:1})});
  assert.equal(app.calls.reset,before+1); assert.equal(app.run('queue.length'),0);
  assert.equal(app.run('avatarMouthOpen'),0); assert.equal(app.run('window.LiveAgentMedia.avatarState().request'),undefined);
  // A chunk from an earlier server epoch arriving after stop must not resurrect the gesture.
  await app.sockets[0].onmessage({data:JSON.stringify({type:'chunk',request:7,chunk:2,width:480,height:864,
    sample_rate:16000,duration:1,n_frames:0,fps:24,avatar:{...meshStatus.avatar,epoch:0}})});
  await app.sockets[0].onmessage({data:new Int16Array([0]).buffer});
  assert.equal(app.run('queue.length'),0);
  app.run('audioCtx.currentTime=0.7;renderFrame(700);');
  assert.equal(app.states.at(-1).mouthOpen,0); assert.equal(app.states.at(-1).gesture,'idle');
  app.element('disconnect').onclick(); assert.equal(app.calls.destroy,1);
  assert.equal(app.run('window.LiveAgentMedia.captureAvatar()'),null);
});

test('runtime WebGL loss switches to decoded video and reports its real renderer in acknowledgements', async () => {
  const app = meshFixture(); await readyMesh(app); meshChunk(app,0);
  app.run('audioCtx.currentTime=0.3;renderFrame(300);');
  app.rig.active=false;
  app.run('audioCtx.currentTime=0.6;renderFrame(600);');
  assert.equal(app.run('window.LiveAgentMedia.avatarState().renderer'),'video');
  assert.equal(app.element('screen').style.visibility,'visible');
  assert.ok(app.run('queue[0].painted.size')>0);
  const fallback = app.sockets[0].sent.map(value=>JSON.parse(value)).find(packet=>packet.type==='avatar_renderer');
  assert.deepEqual(fallback,{type:'avatar_renderer',renderer:'video',epoch:0});
  app.run('audioCtx.currentTime=1.2;renderFrame(1200);');
  const end=app.sockets[0].sent.map(value=>JSON.parse(value)).find(packet=>packet.type==='chunk_end');
  assert.equal(end.renderer,'video'); assert.ok(end.painted.length>0);
});

test('avatar captures are bounded and missing captures never use decoded server frames', async () => {
  const app = meshFixture(); await readyMesh(app); meshChunk(app,0);
  app.rig.capture=()=>{throw new Error('No WebGL capture');};
  app.run('audioCtx.currentTime=0.3;renderFrame(300);');
  assert.equal(app.sockets[0].sent.map(value=>JSON.parse(value)).some(packet=>packet.type==='avatar_frame'),false);
  assert.equal(app.run('queue[0].painted'),undefined);
  app.rig.capture=()=>`data:image/jpeg;base64,${'a'.repeat(160000)}`;
  app.run('performance.now=()=>2000;audioCtx.currentTime=0.8;renderFrame(800);');
  assert.equal(app.sockets[0].sent.map(value=>JSON.parse(value)).some(packet=>packet.type==='avatar_frame'),false);
  assert.equal(app.run('window.LiveAgentMedia.avatarState().renderer'),'mesh');
});

const galleryImages = [
  {url:'/board/img/d000000000000001.png',caption:'Overview',point:null},
  {url:'/board/img/d000000000000002.png',caption:'First process',point:0},
  {url:'/board/img/p000000000000003.png',caption:'Second comparison',point:1},
];
function galleryFixture(app, {key = 'gallery-a', reveal = 0, figures = galleryImages, figure} = {}) {
  const active = figure === undefined ? figures.find(fig => fig.point === reveal) || figures.find(fig => fig.point === null) : figure;
  app.run(`showBoard(${JSON.stringify({key,title:'Visual lesson',items:['First','Second'],reveal,
    progress:[1,3],figures,figure:active || null})})`);
}

test('ready board visuals form a bounded navigation gallery with a current caption and enlarged selected image', () => {
  const app = page(); galleryFixture(app);
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[1].url);
  assert.equal(app.element('boardCap').innerHTML, 'First process');
  assert.equal(app.element('boardFigureCount').textContent, '2 / 3');
  assert.equal(app.element('boardPrevious').disabled, false);
  app.element('boardNext').onclick();
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
  assert.equal(app.element('boardCap').innerHTML, 'Second comparison');
  assert.equal(app.element('boardNext').disabled, true);
  assert.equal(app.run('shownBoard.figure.url'), galleryImages[1].url);
  assert.equal(app.run('JSON.stringify(shownBoard.progress)'), '[1,3]');
  app.run('openBoardFigure()');
  assert.equal(app.element('boardFigureLarge').getAttribute('src'), galleryImages[2].url);
  app.element('boardPrevious').onclick();
  assertDiagramClosed(app);
  app.element('boardPrevious').onclick();
  assert.equal(app.element('boardFigureCount').textContent, '1 / 3');
  assert.equal(app.element('boardPrevious').disabled, true);
});

test('manual gallery selection survives unchanged playback snapshots and new images but a point or board change restores automatic choice', () => {
  const app = page(); galleryFixture(app); app.element('boardNext').onclick();
  galleryFixture(app);  // a new chunk object carrying the same spoken point
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
  app.run(`boardFigureReady({board:'gallery-a',point:2,figure:{url:'/board/img/d000000000000004.png',caption:'Later detail'}})`);
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
  assert.equal(app.element('boardFigureCount').textContent, '3 / 4');
  galleryFixture(app, {reveal:1});
  assert.equal(app.run('boardGallerySelection'), null);
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
  app.element('boardPrevious').onclick();
  app.run('shownBoard.reveal=0; showBoard(shownBoard)'); // in-place point changes also restore alignment
  assert.equal(app.run('boardGallerySelection'), null);
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[1].url);
  galleryFixture(app, {key:'gallery-b',reveal:1});
  assert.equal(app.run('boardGallerySelection'), null);
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
});

test('future-point images are reachable without showing them automatically and late current images do not override manual browsing', () => {
  const app = page(); galleryFixture(app, {figures:[galleryImages[2]],figure:null});
  assert.equal(app.element('board').classList.contains('hasfig'), false);
  assert.equal(app.element('boardGallery').hidden, false);
  assert.equal(app.element('boardBrowse').hidden, false);
  assert.equal(app.element('boardBrowse').textContent, '查看配图 1');
  app.element('boardBrowse').onclick();
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
  app.run(`boardFigureReady({board:'gallery-a',point:0,figure:${JSON.stringify(galleryImages[1])}})`);
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
  assert.equal(app.element('boardFigureCount').textContent, '2 / 2');
  assert.equal(app.run('shownBoard.figure.url'), galleryImages[1].url);
});

test('a new spoken point without an image leaves earlier images available without automatically retaining the previous point', () => {
  const app = page(); galleryFixture(app, {figures:[galleryImages[1],galleryImages[2]]});
  app.element('boardNext').onclick();
  app.run('shownBoard.reveal=2; showBoard(shownBoard)');
  assert.equal(app.run('boardGallerySelection'), null);
  assert.equal(app.element('board').classList.contains('hasfig'), false);
  assert.equal(app.element('boardImg').getAttribute('src'), null);
  assert.equal(app.element('boardGallery').hidden, false);
  assert.equal(app.element('boardBrowse').textContent, '查看配图 2');
});

test('late gallery images populate matching queued boards without mixing other lessons or regressing to stale snapshots', () => {
  const app = page(); galleryFixture(app, {figures:[galleryImages[1]]});
  app.run(`queue.push({board:{key:'gallery-a',title:'Visual lesson',items:['First','Second'],reveal:1}});
    boardFigureReady({board:'other-lesson',point:1,figure:{url:'/board/img/d000000000000009.png',caption:'Other lesson'}});
    boardFigureReady({board:'gallery-a',point:1,figure:${JSON.stringify(galleryImages[2])}});`);
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[1].url);
  assert.equal(app.element('boardFigureCount').textContent, '1 / 2');
  assert.equal(app.run('queue[0].board.figures.length'), 2);
  app.run(`boardFigureReady({board:'gallery-a',point:1,figure:{url:'/board/img/p000000000000003.png',caption:'New caption'}})`);
  galleryFixture(app, {reveal:1,figures:[galleryImages[1],galleryImages[2]]});
  assert.equal(app.element('boardCap').innerHTML, 'New caption');
  assert.equal(app.run('JSON.stringify(shownBoard.figures)').includes('Other lesson'), false);
});

test('a whole-board collection fallback stays a whole-board figure when its late replacement arrives', () => {
  const app = page(); galleryFixture(app, {figures:[galleryImages[0],galleryImages[2]],figure:galleryImages[0]});
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[0].url);
  app.run(`boardFigureReady({board:'gallery-a',point:null,figure:{url:'/board/img/d000000000000004.png',caption:'Revised overview'}})`);
  assert.equal(app.element('boardImg').getAttribute('src'), '/board/img/d000000000000004.png');
  assert.equal(app.element('boardCap').innerHTML, 'Revised overview');
  assert.equal(app.element('boardFigureCount').textContent, '1 / 2');
  assert.equal(app.run('shownBoard._figurePoint'), null);
});

test('gallery validates ready paths and positions, deduplicates reused visuals and keeps navigation after an image failure', () => {
  const app = page();
  galleryFixture(app, {figures:[...galleryImages, {...galleryImages[1],point:2},
    {url:'javascript:alert(1)',caption:'Unsafe',point:3},
    {url:'/board/img/d000000000000004.png',caption:'Invalid point',point:-1}]});
  assert.equal(app.element('boardFigureCount').textContent, '2 / 3');
  app.element('boardImg').onerror();
  assert.equal(app.element('board').classList.contains('hasfig'), false);
  assert.equal(app.element('boardGallery').hidden, false);
  assert.equal(app.element('boardBrowse').hidden, false);
  app.element('boardNext').onclick();
  assert.equal(app.element('board').classList.contains('hasfig'), true);
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
  assert.equal(app.element('boardCap').innerHTML, 'Second comparison');
});

test('gallery labels localize without changing its manual choice or opening viewer', () => {
  const app = page({edition:'university'}); galleryFixture(app); app.element('boardNext').onclick();
  assert.equal(app.element('boardPrevious').textContent, 'Previous');
  assert.equal(app.element('boardNext').textContent, 'Next');
  assert.equal(app.element('boardFigureCount').getAttribute('aria-label'), 'Diagram 3 of 3');
  app.run('window.LiveAgentProduct.edition="secondary"; window.LiveAgentMedia.refreshLanguage()');
  assert.equal(app.element('boardPrevious').textContent, '上一张');
  assert.equal(app.element('boardNext').textContent, '下一张');
  assert.equal(app.element('boardFigureCount').getAttribute('aria-label'), '配图 3 / 3');
  assert.equal(app.element('boardImg').getAttribute('src'), galleryImages[2].url);
  assert.equal(app.element('boardFigureDialog').open, false);
});

test('privacy cleanup removes gallery snapshots, manual choice and enlarged private content from pending playback', () => {
  for (const cleanup of ['clearBoardFigures()', 'resetSessionView()',
    `onEvent({event:'playback_stop',t:0,request:0,data:{erasure:true,erasure_complete:false}})`]) {
    const app = page(); galleryFixture(app); app.element('boardNext').onclick(); app.run('openBoardFigure()');
    app.run(`pending={frames:[],meta:{board:{...shownBoard}}}; decoding=[{frames:[],meta:{board:{...shownBoard}}}]; ${cleanup}`);
    assertDiagramClosed(app);
    assert.equal(app.run('boardGallerySelection'), null);
    assert.equal(app.element('boardGallery').hidden, true);
    assert.equal(app.element('boardFigureCount').textContent, '');
    assert.equal(app.element('boardImg').getAttribute('src'), null);
    assert.equal(app.run('JSON.stringify(pending?.meta.board || {}).includes("figures")'), false);
    assert.equal(app.run('JSON.stringify(decoding[0]?.meta.board || {}).includes("figures")'), false);
  }
});

test('late figure readiness updates only its board point and queued playback retains it', () => {
  const app = page();
  app.run(`showBoard({key:'lesson-a-s0',title:'Lesson A',items:['first','second'],reveal:0,progress:[1,2]});
    onScreen={board:shownBoard}; queue.push({board:{key:'lesson-a-s0',title:'Lesson A',items:['first','second'],reveal:1}});`);
  app.run(`boardFigureReady({board:'lesson-b-s0',point:0,figure:{url:'/board/img/d000000000000001.png',caption:'Other lesson'}});
    boardFigureReady({board:'lesson-a-s0',point:1,figure:{url:'/board/img/d000000000000002.png',caption:'Second point'}});`);
  assert.equal(app.element('board').classList.contains('hasfig'), false);
  assert.equal(app.run('queue[0].board.figure.caption'), 'Second point');
  app.run(`onEvent({event:'lesson',t:0,request:0,data:{stage:'figure',board:'lesson-a-s0',point:0,
    figure:{url:'/board/img/d000000000000003.png',caption:'First &lt;point&gt;'}}});`);
  assert.equal(app.element('boardImg').getAttribute('src'), '/board/img/d000000000000003.png');
  assert.equal(app.element('boardCap').innerHTML, 'First &lt;point&gt;');
  assert.equal(app.run('shownBoard.reveal'), 0);
  assert.equal(app.run('JSON.stringify(shownBoard.progress)'), '[1,2]');
  app.run('showBoard(queue[0].board)');
  assert.equal(app.element('boardImg').getAttribute('src'), '/board/img/d000000000000002.png');
});

test('figures ready before playback are cached while a whole-board figure cannot replace a point figure', () => {
  const app = page();
  app.run(`boardFigureReady({board:'unique-a',point:1,figure:{url:'/board/img/p000000000000001.png',caption:'Point one'}});
    showBoard({key:'unique-a',title:'A',items:[],reveal:0,figure:{url:'/board/img/p000000000000002.png',caption:'Point zero'}});
    boardFigureReady({board:'unique-a',point:null,figure:{url:'/board/img/d000000000000003.png',caption:'Whole board'}});`);
  assert.equal(app.element('boardImg').getAttribute('src'), '/board/img/p000000000000002.png');
  app.run(`showBoard({key:'unique-a',title:'A',items:[],reveal:1})`);
  assert.equal(app.element('boardImg').getAttribute('src'), '/board/img/p000000000000001.png');
  app.run(`showBoard({key:'unique-a',title:'A',items:[],reveal:2})`);
  assert.equal(app.element('boardImg').getAttribute('src'), '/board/img/d000000000000003.png');
});

test('board content and captions refresh even when their key or image URL stays the same', () => {
  const app = page();
  app.run(`showBoard({key:'same',title:'Old',items:['Old item'],reveal:null,
    figure:{url:'/board/img/p000000000000001.png',caption:'Old caption'}});
    showBoard({key:'same',title:'Updated',items:['Updated item'],reveal:null,
    figure:{url:'/board/img/p000000000000001.png',caption:'Updated caption'}});`);
  assert.equal(app.element('boardTitle').innerHTML, 'Updated');
  assert.equal(app.element('boardItems').innerHTML, '<li>Updated item</li>');
  assert.equal(app.element('boardCap').innerHTML, 'Updated caption');
});

test('figure cache and displayed images are erased on disconnect and privacy deletion', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({board:true});
  app.run(`boardFigureReady({board:'private',point:0,figure:{url:'/board/img/d000000000000001.png',caption:'Private'}});
    showBoard({key:'private',title:'Private',items:[],reveal:0});`);
  app.element('disconnect').onclick();
  assert.equal(app.run('boardFigures.size'), 0);
  assert.equal(app.element('boardImg').getAttribute('src'), null);
  assert.equal(app.element('board').dataset.content, undefined);
  app.run(`boardFigureReady({board:'private',point:0,figure:{url:'/board/img/d000000000000001.png',caption:'Private'}});
    showBoard({key:'private',title:'Private',items:[],reveal:0});
    onEvent({event:'playback_stop',t:0,request:0,data:{erasure:true,erasure_complete:false}});`);
  assert.equal(app.run('boardFigures.size'), 0);
  assert.equal(app.run('shownBoard.figure'), undefined);
  assert.equal(app.element('board').classList.contains('hasfig'), false);
});

test('unsafe figure paths are rejected and failed images fall back to board text then retry', () => {
  const app = page();
  app.run(`showBoard({key:'a',title:'A',items:['Explanation'],reveal:null});
    boardFigureReady({board:'a',point:null,figure:{url:'javascript:alert(1)',caption:'Unsafe'}});`);
  assert.equal(app.element('boardImg').getAttribute('src'), null);
  app.run(`boardFigureReady({board:'a',point:null,figure:{url:'/board/img/d000000000000001.png',caption:'Diagram'}})`);
  assert.equal(app.element('board').classList.contains('hasfig'), true);
  app.run('openBoardFigure()');
  assert.equal(app.element('boardFigureDialog').open, true);
  app.element('boardImg').onerror();
  assert.equal(app.element('board').classList.contains('hasfig'), false);
  assert.equal(app.element('boardFigureDialog').open, false);
  assert.equal(app.element('boardFigureLarge').getAttribute('src'), null);
  assert.equal(app.element('boardItems').innerHTML, '<li>Explanation</li>');
  app.run('showBoard(shownBoard)');
  assert.equal(app.element('board').classList.contains('hasfig'), true);
});

function diagramFixture(app, { key = 'diagram-a', url = '/board/img/d000000000000001.png', caption = 'Diagram &lt;caption&gt;' } = {}) {
  app.run(`showBoard(${JSON.stringify({ key, title: 'Diagram lesson', items: ['Explanation'], reveal: 0, figure: { url, caption } })})`);
}

function assertDiagramClosed(app) {
  assert.equal(app.element('boardFigureDialog').open, false);
  assert.equal(app.element('boardFigureLarge').getAttribute('src'), null);
  assert.equal(app.element('boardFigureCaption').textContent, '');
  assert.equal(app.run('enlargedBoardFigure'), null);
}

test('diagram button and image keyboard controls open a labeled viewer with Close and Escape', () => {
  const app = page(); diagramFixture(app);
  assert.equal(app.element('boardImg').getAttribute('role'), 'button');
  assert.equal(app.element('boardImg').getAttribute('aria-controls'), 'boardFigureDialog');
  app.element('boardEnlarge').focus(); app.element('boardEnlarge').onclick();
  assert.equal(app.element('boardFigureDialog').open, true);
  assert.equal(app.run('document.activeElement.id'), 'boardFigureClose');
  assert.equal(app.element('boardFigureCaption').innerHTML, 'Diagram &lt;caption&gt;');
  app.element('boardFigureClose').onclick();
  assertDiagramClosed(app);
  assert.equal(app.run('document.activeElement.id'), 'boardEnlarge');
  app.flushDialogCloseEvents();
  for (const key of ['Enter', ' ']) {
    let prevented = false;
    app.element('boardImg').focus();
    app.element('boardImg').onkeydown({ key, preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
    assert.equal(app.element('boardFigureDialog').open, true);
    prevented = false;
    app.element('boardFigureDialog').oncancel({ preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
    assertDiagramClosed(app);
    assert.equal(app.run('document.activeElement.id'), 'boardImg');
    app.flushDialogCloseEvents();
  }
  app.element('boardImg').onkeydown({ key: 'ArrowRight', preventDefault() { assert.fail('unrelated key prevented'); } });
  assertDiagramClosed(app);
});

test('an asynchronous close event cannot close or clear a newly reopened diagram', () => {
  const app = page(); diagramFixture(app); app.run('openBoardFigure(); closeBoardFigure()');
  diagramFixture(app, { key: 'diagram-b', url: '/board/img/p000000000000002.png', caption: 'New diagram' });
  app.run('openBoardFigure()');
  app.flushDialogCloseEvents();
  assert.equal(app.element('boardFigureDialog').open, true);
  assert.equal(app.element('boardFigureLarge').getAttribute('src'), '/board/img/p000000000000002.png');
  assert.equal(app.element('boardFigureCaption').innerHTML, 'New diagram');
  assert.equal(app.run('enlargedBoardFigure.key'), 'diagram-b');
});

test('a native dialog close clears enlarged image state and alternative text', () => {
  const app = page(); diagramFixture(app); app.run('openBoardFigure()');
  app.element('boardFigureLarge').alt = 'Private image description';
  app.element('boardFigureDialog').close(); app.flushDialogCloseEvents();
  assertDiagramClosed(app);
  assert.equal(app.element('boardFigureLarge').alt, '课程配图');
});

test('switching board or figure closes the viewer while same-image captions stay current', () => {
  const app = page(); diagramFixture(app); app.run('openBoardFigure()');
  diagramFixture(app, { caption: 'Updated caption' });
  assert.equal(app.element('boardFigureDialog').open, true);
  assert.equal(app.element('boardFigureCaption').innerHTML, 'Updated caption');
  diagramFixture(app, { url: '/board/img/p000000000000002.png' }); assertDiagramClosed(app);
  app.run('openBoardFigure()'); diagramFixture(app, { key: 'diagram-b', url: '/board/img/p000000000000002.png' });
  assertDiagramClosed(app);
  app.run('openBoardFigure(); showBoard({key:"diagram-b",title:"No figure",items:[],reveal:1})');
  assertDiagramClosed(app);
});

test('disconnect, privacy deletion and new-session reset clear the enlarged diagram', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({ board: true });
  diagramFixture(app); app.run('openBoardFigure()'); app.element('disconnect').onclick();
  assertDiagramClosed(app); assert.equal(app.run('boardFigures.size'), 0);
  await app.connect(); await app.open(); await app.status({ board: true });
  diagramFixture(app); app.run(`openBoardFigure();
    onEvent({event:'playback_stop',t:0,request:0,data:{erasure:true,erasure_complete:false}})`);
  assertDiagramClosed(app);
  diagramFixture(app); app.run('openBoardFigure(); resetSessionView()');
  assertDiagramClosed(app);
  assert.equal(app.element('board').dataset.content, undefined);
  assert.equal(app.element('boardTitle').textContent, '');
  app.flushDialogCloseEvents(); assertDiagramClosed(app);
});

test('diagram controls localize on language refresh without closing the current image', () => {
  const app = page({ edition: 'university' });
  assert.equal(app.element('boardEnlarge').textContent, 'Enlarge diagram');
  assert.equal(app.element('boardFigureTitle').textContent, 'Lesson diagram');
  assert.equal(app.element('boardFigureClose').getAttribute('aria-label'), 'Close diagram');
  assert.equal(app.element('boardImg').getAttribute('aria-label'), 'Enlarge diagram');
  diagramFixture(app, { caption: '' }); app.run('openBoardFigure()');
  assert.equal(app.element('boardFigureLarge').alt, 'Lesson diagram');
  app.run('window.LiveAgentProduct.edition="secondary"; window.LiveAgentMedia.refreshLanguage()');
  assert.equal(app.element('boardEnlarge').textContent, '放大配图');
  assert.equal(app.element('boardFigureTitle').textContent, '课程配图');
  assert.equal(app.element('boardFigureClose').getAttribute('aria-label'), '关闭配图');
  assert.equal(app.element('boardFigureLarge').alt, '课程配图');
  assert.equal(app.element('boardFigureDialog').open, true);
  assert.equal(app.element('boardFigureLarge').getAttribute('src'), '/board/img/d000000000000001.png');
});

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
  app.run('camStream = {}; onEvent({event: "attention", data: {state: "focused", stable: "distracted", reason: "raw source reason"}}); profile = {id: "actual-profile"};');
  const hooks = app.transitions.length, events = app.events.length, packets = app.sockets[0].sent.length, timers = app.timers.size;
  app.run('window.LiveAgentProduct.edition = "university"; window.LiveAgentMedia.refreshLanguage();');
  assert.equal(app.element('conn').textContent, 'Tutor ready');
  const badges = app.element('badges').children.map(node => node.textContent).join('\n');
  assert.match(badges, /Video: Mock video/);
  assert.doesNotMatch(badges, /生成|质检|仅文字/);
  assert.equal(app.element('focus').textContent, 'Focus check: Focused · confirming (raw source reason)');
  assert.equal(app.element('focusLive').textContent, app.element('focus').textContent);
  assert.equal(app.element('cam').textContent, 'Stop focus check');
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

test('exercise presentation uses server MathML and safely preserves legacy or missing option text', () => {
  const app = page();
  app.run(`renderExerciseQuestion(document.getElementById('exerciseQuestion'), {
    question: '计算 $358 + 247$', question_html: '计算 <math><mn>358</mn><mo>+</mo><mn>247</mn></math>',
    option_texts: ['A. $605$', 'B. <img src=x>'], option_html: ['A. <math><mn>605</mn></math>']
  });`);
  assert.equal(app.element('exerciseQuestion').innerHTML,
    '计算 <math><mn>358</mn><mo>+</mo><mn>247</mn></math>\nA. <math><mn>605</mn></math>\nB. &lt;img src=x&gt;');
  app.run(`renderExerciseQuestion(document.getElementById('exerciseQuestion'), {
    question: '旧版 $x^2$ <script>x</script>', option_texts: ['A. <文字>']
  });`);
  assert.equal(app.element('exerciseQuestion').innerHTML, '旧版 $x^2$ &lt;script&gt;x&lt;/script&gt;\nA. &lt;文字&gt;');
});

test('camera sends a sharper aspect-preserving frame immediately and at a responsive cadence, then stops', async () => {
  const app = page(); await app.connect(); await app.open(); await app.status({attention:true});
  app.element('camView').videoWidth = 1280; app.element('camView').videoHeight = 720;
  const start = app.run('camOn()'), camera = stream(); app.permissions[0].resolve(camera);
  await start; await Promise.resolve();
  const packets = () => app.sockets[0].sent.map(v => JSON.parse(v)).filter(v => v.type === 'camera');
  assert.equal(packets().length, 1);
  assert.equal(app.run('camCanvas.width'), 640); assert.equal(app.run('camCanvas.height'), 360);
  assert.equal(app.permissions[0].options.video.width.ideal, 640);
  assert.equal(app.element('focusLive').hidden, false);
  const capture = app.intervals.find(v => v.ms === 1500);
  assert.ok(capture); const tick = app.timers.get(capture.id); tick();
  assert.equal(packets().length, 2);
  app.run('camOff()'); tick();
  assert.equal(packets().length, 2); assert.equal(camera.stopped(), 1);
  assert.equal(app.element('focusLive').hidden, true);
  app.run('onEvent({event:"attention",data:{state:"distracted",stable:"distracted",reason:"late result"}})');
  assert.equal(app.element('focusLive').hidden, true); assert.equal(app.run('latestAttention'), null);
});

test('visible focus feedback distinguishes confirming evidence and uncertainty from a stale confirmed verdict', () => {
  const app = page(); app.run('camStream = {};');
  app.run('onEvent({event:"attention",data:{state:"distracted",stable:"focused",reason:"转头"}})');
  assert.match(app.element('focusLive').textContent, /走神.*确认中/);
  app.run('onEvent({event:"attention",data:{state:"unknown",stable:null,reason:"画面遮挡"}})');
  assert.match(app.element('focusLive').textContent, /无法判断.*画面遮挡/);
  assert.doesNotMatch(app.element('focusLive').textContent, /专注\s*\(/);
  app.run('onEvent({event:"attention",data:{state:"distracted",stable:"distracted",reason:"使用手机"}})');
  assert.match(app.element('focusLive').textContent, /走神.*使用手机/);
  assert.doesNotMatch(app.element('focusLive').textContent, /确认中/);
});

#!/usr/bin/env python3
"""Exercise the actual browser mesh classroom against an isolated media fixture.

No teaching-model/provider calls, production sockets, learner files, or service
processes are used. The fixture carries recorded speech (when supplied), real
PCM/JPEG transport, captions and a board image. This checks rendering and media
integration; it does not measure generated teaching quality or human realism.

Run from the repository root: ``python3 scripts/teacher_mesh_check.py``.
Use ``--serve`` to leave the loopback fixture available for visual inspection.
All numbers in the report are measured locally or labelled configuration bounds.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import sys
import time
import wave
from urllib.parse import quote, unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from PIL import Image, ImageDraw
import uvicorn

from live_agent.backend.avatar import MODEL, decode_capture
from live_agent.backend.transport import WSTransport
from live_agent.generator.puppet import Pose
from live_agent.generator.puppet_art import render_frame
from live_agent.types import BlockScript, CanonProfile, Chunk
from live_agent.tts import TTS_RATE

TRANSCRIPT = "我们先看这张图。叶片利用阳光，把水和二氧化碳转化为养分。现在请你想一想：如果没有阳光，会发生什么？"
FIGURE_URL = "/board/img/0000000000000000.png"
PUBLIC = ROOT / "frontend/public"
DEFAULT_MODEL = PUBLIC / "assets/teacher-mesh/rig-v7.json"

# Overlay only the manifest inside this fixture's own frontend. A staged model
# also works with --serve without changing the running classroom's defaults.
STAGED_FRONTEND = """
import {createFrontendServer} from './frontend/server.mjs';
const server=createFrontendServer({backendUrl:process.env.BACKEND_URL});
const [serve]=server.listeners('request');server.removeListener('request',serve);
const manifest=Buffer.from(process.env.MESH_CHECK_MANIFEST,'base64');
server.on('request',(req,res)=>{
  if(req.url.split('?')[0]!==process.env.MESH_CHECK_MODEL_URL)return serve.call(server,req,res);
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{allow:'GET, HEAD'});res.end();return;}
  res.writeHead(200,{'content-type':'application/json; charset=utf-8','content-length':manifest.length,
    'cache-control':'no-store','x-content-type-options':'nosniff'});
  res.end(req.method==='HEAD'?undefined:manifest);
});
server.on('error',error=>{console.error(error.message);process.exitCode=1;});
server.listen(Number(process.env.PORT),process.env.HOST);
for(const signal of ['SIGINT','SIGTERM'])process.once(signal,()=>{server.close();server.closeAllConnections();});
"""


def staged_model(path: Path) -> tuple[dict, dict, list[Path]]:
    """Resolve a local manifest and bind every texture used by the staged rig."""
    public = PUBLIC.resolve()
    path = path.resolve(strict=True)
    if not path.is_relative_to(public) or path.suffix != ".json":
        raise ValueError("--model must be a JSON manifest inside frontend/public")
    source = path.read_bytes()
    rig = json.loads(source)
    if rig.get("version") != 1 or rig.get("model") != MODEL or rig.get("canvas") != [480, 864]:
        raise ValueError("--model must retain the supported teacher wire model and canvas")
    match = re.search(r'TEACHER_AVATAR_URL\s*=\s*[\"\']([^\"\']+)[\"\']', (PUBLIC / "assets/live.js").read_text())
    if not match:
        raise ValueError("Cannot locate the frontend's manifest request URL")
    requested_url = match.group(1)
    if not requested_url.startswith("/") or requested_url.startswith("//") or urlsplit(requested_url).query:
        raise ValueError("The frontend manifest request must be a local path")
    selected_url = "/" + quote(path.relative_to(public).as_posix(), safe="/")
    files = [path]

    def asset_url(name: str) -> str:
        parsed = urlsplit(name)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError(f"Staged model texture must be a local file: {name}")
        local_url = urljoin(selected_url, name)
        asset = (public / unquote(local_url).lstrip("/")).resolve(strict=True)
        if not asset.is_relative_to(public) or not asset.is_file():
            raise ValueError(f"Staged model texture escapes frontend/public: {name}")
        files.append(asset)
        return "/" + quote(asset.relative_to(public).as_posix(), safe="/")

    rig["background"] = asset_url(rig["background"])
    for layer in rig["layers"]:
        layer["asset"] = asset_url(layer["asset"])
    for hand in rig["hands"].values():
        if "asset" in hand:
            hand["asset"] = asset_url(hand["asset"])
        for side in hand.get("sides", {}).values():
            if "asset" in side:
                side["asset"] = asset_url(side["asset"])
    for segment in rig.get("arm_segments", []):
        segment["asset"] = asset_url(segment["asset"])
    served = json.dumps(rig, ensure_ascii=False).encode()
    identity = {"source_path": str(path.relative_to(ROOT)), "selected_url": selected_url,
                "requested_url": requested_url, "source_sha256": hashlib.sha256(source).hexdigest(),
                "served_manifest_sha256": hashlib.sha256(served).hexdigest(),
                "wire_model": rig["model"], "asset_revision": rig.get("asset_revision", 1)}
    return rig, identity, list(dict.fromkeys(files))


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def runtime_hashes(model_files: list[Path] = ()) -> dict[str, str]:
    files = [Path(__file__), ROOT / "frontend/public/assets/avatar-renderer.js", ROOT / "frontend/public/assets/teacher-rig.js",
             ROOT / "frontend/public/assets/live.js", ROOT / "frontend/public/assets/live.css", ROOT / "frontend/public/index.html",
             ROOT / "live_agent/backend/transport.py",
             ROOT / "live_agent/backend/avatar.py"]
    files.extend(sorted((ROOT / "frontend/public/assets/teacher-mesh").glob("rig-*.json")))
    files.extend(sorted((ROOT / "frontend/public/assets/teacher-mesh").glob("*.png")))
    files.extend(sorted((ROOT / "frontend/public/vendor/pixi").glob("*.mjs")))
    files.extend(model_files)
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files if path.is_file()}


def read_pcm(path: Path | None, rate_override: int | None = None) -> tuple[np.ndarray, int, str]:
    if path is not None:
        with wave.open(str(path), "rb") as wav:
            if wav.getsampwidth() != 2:
                raise ValueError("Recorded speech must be PCM16 WAV")
            rate = wav.getframerate()
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
            pcm = pcm.reshape(-1, wav.getnchannels()).mean(axis=1).astype("<i2")
        source = "existing recorded Mandarin speech; no provider called"
        known_previews = {ROOT / ".cache/teacher-gestures/speech.wav", ROOT / ".cache/teacher-motion/speech.wav"}
        if rate_override:
            source += f"; source header {rate}Hz overridden to configured {rate_override}Hz"
            rate = rate_override
        elif path.resolve() in known_previews and rate == 24000:
            # Those historical preview.py files labelled the puppet's TTS_RATE
            # samples as 24kHz. Preserve source bytes, restore their original
            # generator clock instead of slowing the voice in this recording.
            source += f"; historical preview header {rate}Hz corrected to generator TTS_RATE {TTS_RATE}Hz"
            rate = TTS_RATE
        return pcm, rate, source
    rate = 24000
    t = np.arange(12 * rate) / rate
    env = np.maximum(0, np.sin(2 * np.pi * 2.3 * t)) ** 2
    pcm = (7000 * env * np.sin(2 * np.pi * 190 * t)).astype("<i2")
    return pcm, rate, "offline syllable-shaped tones; not speech"


def figure_png() -> bytes:
    """A code-drawn fixture diagram; browser delivery is the tested behavior."""
    image = Image.new("RGB", (800, 400), "#f6f8ed")
    draw = ImageDraw.Draw(image)
    draw.ellipse((50, 50, 140, 140), fill="#ecc45d")
    draw.ellipse((315, 105, 540, 300), fill="#4b8e5b")
    draw.line((430, 290, 475, 350), fill="#335b3f", width=10)
    draw.line((160, 105, 325, 165), fill="#b79637", width=8)
    draw.polygon(((325, 165), (298, 140), (290, 170)), fill="#b79637")
    draw.line((530, 210, 700, 210), fill="#4b8e5b", width=8)
    draw.polygon(((700, 210), (670, 190), (670, 230)), fill="#4b8e5b")
    draw.ellipse((685, 160, 765, 240), fill="#96b766")
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


class MediaFixture:
    def __init__(self, pcm: np.ndarray, rate: int, sparse_fallback: bool = False):
        self.pcm = pcm
        self.rate = rate
        self.sparse_fallback = sparse_fallback
        self.messages: list[dict] = []
        self.sent: list[dict] = []
        self.connections: list[dict] = []
        self.errors: list[str] = []
        self.capture_validation: list[dict] = []
        self.sockets: set[WebSocket] = set()
        self.control_queues: dict[WebSocket, asyncio.Queue] = {}
        self.fallback_frame = render_frame(480, 864, Pose())
        self.figure = figure_png()
        self.app = FastAPI()
        self.app.get("/api/health")(lambda: {"status": "ok", "generator": "puppet", "protocol_version": 1})
        self.app.get("/api/students")(lambda: {"students": [{"id": "mesh-check", "name": "本地渲染检查"}]})
        self.app.get("/api/students/mesh-check")(lambda: {"id": "mesh-check", "name": "本地渲染检查", "grade": None,
                                                        "history": [], "concepts": {}, "exams": []})
        self.app.get("/api/curriculum/topics")(lambda: {"topics": []})
        self.app.get(FIGURE_URL)(lambda: Response(self.figure, media_type="image/png"))
        self.app.websocket("/ws")(self.websocket)

    async def control(self, kind: str) -> None:
        for q in tuple(self.control_queues.values()):
            await q.put(kind)

    async def websocket(self, ws: WebSocket) -> None:
        await ws.accept()
        self.sockets.add(ws)
        controls: asyncio.Queue = asyncio.Queue()
        self.control_queues[ws] = controls
        producer = None
        transport: WSTransport | None = None
        state = {"epoch": 0, "request": 1, "renderer": "video"}

        async def json_message(message: dict) -> None:
            await transport.send_json(message)

        async def request(request: int, gesture: str = "explain") -> None:
            # Four chunks [configuration], deliberately enough to cross the
            # boundaries while a whole gesture remains active.
            duration = min(30.0, len(self.pcm) / self.rate)
            size = max(1, int(duration * self.rate / 4))
            ep = state["epoch"]
            for ci in range(4):
                audio = self.pcm[ci * size:(ci + 1) * size]
                dur = len(audio) / self.rate
                chunk = Chunk(request_index=request, chunk_index=ci, n_frames=12, fps=12 / dur,
                              video=np.broadcast_to(self.fallback_frame, (12, *self.fallback_frame.shape)),
                              audio=audio.astype(np.float32) / 32768, sample_rate=self.rate,
                              meta={"avatar_gesture": gesture, "request_offset_s": ci * dur,
                                    "request_duration_s": duration, "motion_time_s": request * 15 + ci * dur})
                script = BlockScript(request_index=request, plan_version=1,
                                     canon=CanonProfile("mesh-check", "an adult teacher", "a classroom", "medium view", "recorded Mandarin"),
                                     action=gesture, transcript=TRANSCRIPT)
                if ci == 0:
                    script.board = {"key": f"mesh-check-{request}", "title": "叶片如何制造养分？",
                                    "items": ["叶片利用阳光，把水和二氧化碳转化为养分。"], "reveal": 0,
                                    "figure": {"url": FIGURE_URL, "caption": "阳光为叶片制造养分提供能量。"}}
                if state["epoch"] != ep:
                    return
                self.sent.append({"request": request, "chunk": ci, "epoch": ep, "duration_s": dur, "meta": chunk.meta})
                await transport.send_chunk(chunk, script)
                await asyncio.sleep(0.03)

        async def command_loop() -> None:
            nonlocal producer
            while True:
                kind = await controls.get()
                state["epoch"] += 1
                if producer is not None:
                    producer.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await producer
                await transport.stop_playback()
                if kind != "stop":
                    state["request"] += 1
                    producer = asyncio.create_task(request(state["request"], "wave" if kind == "wave" else "present"))

        commands = None
        try:
            hello = await ws.receive_json()
            self.connections.append(hello)
            mesh = hello.get("renderer") == "mesh" and hello.get("avatar_model") == MODEL
            state["renderer"] = "mesh" if mesh else "video"
            transport = WSTransport(ws, video_codec="jpeg", avatar_mesh=mesh,
                                    avatar_video_frames=self.sparse_fallback and hello.get("avatar_video_frames") is True)

            class FixtureObserver:
                class Log:
                    def emit(self, *args, **kwargs):
                        pass
                log = Log()

                def on_presented(self, *args, **kwargs):
                    pass

                def on_received(self, *args, **kwargs):
                    pass

            transport.orchestrator = FixtureObserver()
            status = {"type": "status", "session": "sess-local-mesh-check", "generator": "puppet", "mode": "private",
                      "director": "a2", "judge": "none", "responder": "isolated-media-fixture", "asr": False,
                      "attention": False, "board": True, "persona": "本地 VTuber 渲染检查", "student": None}
            if mesh:
                status["avatar"] = transport.avatar_status()
            await json_message(status)
            await asyncio.sleep(0.15)
            producer = asyncio.create_task(request(1))
            commands = asyncio.create_task(command_loop())
            while True:
                message = await ws.receive_json()
                if message.get("type") == "ping":
                    await json_message({"type": "pong", "t": message["t"], "ts": time.monotonic()})
                else:
                    # Image bytes stay separately in optional artifacts, never
                    # in the compact JSON protocol report.
                    logged = {k: v for k, v in message.items() if k != "image"}
                    logged["received_at_s"] = time.monotonic()
                    if message.get("type") == "avatar_frame":
                        decoded = decode_capture(message.get("image"))
                        logged["decoded_shape"] = list(decoded.shape) if decoded is not None else None
                        logged["image_sha256"] = hashlib.sha256(decoded.tobytes()).hexdigest() if decoded is not None else None
                        logged["backend_accepted"] = await transport.on_avatar_frame(message)
                        if logged["backend_accepted"] and not self.capture_validation:
                            duplicate = await transport.on_avatar_frame(message)
                            stale = await transport.on_avatar_frame({**message, "epoch": message["epoch"] - 1})
                            self.capture_validation.append({"accepted_actual_capture": True,
                                                            "duplicate_rejected": not duplicate,
                                                            "stale_epoch_rejected": not stale})
                    self.messages.append(logged)
                    if message.get("type") == "avatar_renderer":
                        logged["backend_accepted"] = transport.on_avatar_renderer(message)
                        state["renderer"] = "video"
                    if message.get("type") == "clock":
                        transport.on_clock(message)
                    if message.get("type") in ("chunk_start", "chunk_end", "chunk_received"):
                        transport.on_client_message(message)
                    if message.get("type") in ("text", "barge_in"):
                        await controls.put("replace")
        except (WebSocketDisconnect, RuntimeError):
            pass
        except Exception as exc:
            self.errors.append(repr(exc))
            raise
        finally:
            self.sockets.discard(ws)
            self.control_queues.pop(ws, None)
            for task in (producer, commands):
                if task:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                        await task


# Observe the same scheduled PCM sources that play through the real frontend;
# capture a second audio branch for a browser-produced recording. This does not
# replace AudioContext, its scheduling, or the renderer's animation clock.
AUDIO_OBSERVER = r"""(() => {
  window.__meshCheckAudio = [];
  window.__meshCheckTrace = [];
  window.__meshCheckRafTimes = [];
  const raf = time => {window.__meshCheckRafTimes.push(time);requestAnimationFrame(raf)};
  requestAnimationFrame(raf);
  window.__avTrace = window.__meshCheckTrace;
  const proto = (window.AudioContext || window.webkitAudioContext).prototype;
  const create = proto.createBufferSource;
  proto.createBufferSource = function(...args) {
    const source = create.apply(this, args), ctx = this;
    if (!window.__meshCheckAudioDestination) {
      window.__meshCheckAudioDestination = ctx.createMediaStreamDestination();
      window.__meshCheckAudioContext = ctx;
    }
    source.connect(window.__meshCheckAudioDestination);
    const start = source.start.bind(source);
    source.start = function(when, ...rest) {
      let sum = 0, peak = 0;
      if (source.buffer) for (const sample of source.buffer.getChannelData(0)) {
        sum += sample*sample; peak = Math.max(peak, Math.abs(sample));
      }
      window.__meshCheckAudio.push({when, contextTime:ctx.currentTime, performance_ms:performance.now(), state:ctx.state,
        samples:source.buffer?.length || 0, duration:source.buffer?.duration || 0,
        rms:Math.sqrt(sum/(source.buffer?.length || 1)), peak});
      return start(when, ...rest);
    };
    return source;
  };
})();"""


async def save_canvas(page, path: Path) -> Image.Image:
    data = await page.evaluate("""() => {
      const canvas=document.querySelector('.teacher-avatar-canvas');
      if(!canvas) throw new Error('Mesh avatar canvas missing');
      return canvas.toDataURL('image/png').split(',')[1];
    }""")
    path.write_bytes(base64.b64decode(data))
    return Image.open(path).convert("RGB")


async def save_gesture_snapshots(page, out: Path) -> dict:
    gestures = ("idle", "listen", "explain", "present", "point", "smile", "think", "nod", "shake", "wave")
    for gesture in gestures:
        for index, fraction in enumerate((0.2, 0.5, 0.8)):
            snapshot = await page.evaluate("""({gesture,fraction}) => {
              teacherAvatar.render({gesture,requestTime:5*fraction,duration:5,motionTime:20+5*fraction,mouthOpen:0.12,mouthRound:0.2});
              return document.querySelector('.teacher-avatar-canvas').toDataURL('image/png').split(',')[1];
            }""", {"gesture": gesture, "fraction": fraction})
            (out / f"gesture-{gesture}-{index}.png").write_bytes(base64.b64decode(snapshot))
    facial_states = [
        (f"blink-{index}", {"gesture": "idle", "requestTime": 0, "duration": 5, "motionTime": 17.8 + phase,
                             "mouthOpen": 0, "mouthRound": 0})
        for index, phase in enumerate((0, 0.045, 0.09, 0.175, 0.26))
    ]
    facial_states.extend((name, {"gesture": "idle", "requestTime": 0, "duration": 5, "motionTime": 20,
                                 "mouthOpen": opened, "mouthRound": rounded})
                         for name, opened, rounded in (("mouth-neutral", 0, 0), ("mouth-open", 0.9, 0), ("mouth-rounded", 0.75, 1)))
    for name, state in facial_states:
        snapshot = await page.evaluate("""state => {
          teacherAvatar.render(state);return document.querySelector('.teacher-avatar-canvas').toDataURL('image/png').split(',')[1];
        }""", state)
        (out / f"{name}.png").write_bytes(base64.b64decode(snapshot))
    return {"gestures": list(gestures), "poses_per_gesture": 3,
            "controlled_blink_frames": 5, "controlled_mouth_shapes": 3,
            "label": "actual WebGL renderer with controlled pose inputs; not live speech samples"}


async def start_recording(page, *, audio: bool = True) -> None:
    await page.evaluate("""audio => {
      const canvas=document.querySelector('.teacher-avatar-canvas');
      const stream=canvas.captureStream(24);
      if(audio)for(const track of window.__meshCheckAudioDestination.stream.getAudioTracks()) stream.addTrack(track);
      window.__meshCheckRecordingParts=[];
      const mime=['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'].find(x=>MediaRecorder.isTypeSupported(x));
      const recorder=window.__meshCheckRecorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:2500000});
      recorder.ondataavailable=e=>{if(e.data.size)window.__meshCheckRecordingParts.push(e.data)};
      recorder.start(250);
    }""", audio)


async def finish_recording(page, path: Path, *, audio: bool = True) -> dict:
    data = await page.evaluate("""async () => {
      const recorder=window.__meshCheckRecorder;
      await new Promise(resolve=>{recorder.onstop=resolve;recorder.stop()});
      const bytes=new Uint8Array(await new Blob(window.__meshCheckRecordingParts,{type:recorder.mimeType}).arrayBuffer());
      let binary='';for(let i=0;i<bytes.length;i+=16384)binary+=String.fromCharCode(...bytes.subarray(i,i+16384));
      return btoa(binary);
    }""")
    path.write_bytes(base64.b64decode(data))
    result = {"native_browser_recording": path.name, "audio": audio,
              "label": "actual WebGL canvas and actual scheduled PCM audio branch" if audio else
                       "actual WebGL canvas; controlled gesture clock; silent recording with no audio track"}
    if shutil.which("ffmpeg"):
        mp4 = path.with_suffix(".mp4")
        audio_flags = ["-c:a", "aac"] if audio else ["-an"]
        # Browser WebM timestamps use a fine time base. Without an explicit
        # output rate, ffmpeg can duplicate each captured canvas frame into a
        # 1000-fps MP4, making the review artifact unnecessarily hard to play.
        process = await asyncio.create_subprocess_exec("ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
                   "-vf", "fps=24", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                   *audio_flags, "-movflags", "+faststart", str(mp4),
                   stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError("Actual browser recording could not be converted: " + stderr.decode(errors="replace")[-500:])
        result["compatible_browser_recording"] = mp4.name
        result["compatible_video_fps_configuration"] = 24
    return result


async def save_gesture_motion(page, fixture: MediaFixture, out: Path) -> dict:
    """Record complete controlled gestures at their real elapsed playback time.

    The classroom RAF is paused only in this isolated browser while the same
    actual renderer is driven by a controlled RAF clock. Video has no audio.
    Pixel measurements locate changes; they are not a substitute for inspecting
    joint anatomy or a guarantee that all transparent mesh geometry is in frame.
    """
    await fixture.control("stop")
    await page.wait_for_function("queue.length===0 && document.querySelector('#caption').textContent===''")
    await page.evaluate("""async () => {rendering=false;await new Promise(requestAnimationFrame)}""")
    summary = {"label": "measured from actual renderer driven by controlled real-time RAF; silent gesture recordings",
               "configuration": {"duration_s": 5, "analysis_fps": 12, "video_capture_fps": 24}, "gestures": {}}
    try:
        for gesture in ("wave", "think"):
            await page.evaluate("teacherAvatar.reset()")
            await start_recording(page, audio=False)
            captures = await page.evaluate("""({gesture,duration,fps}) => new Promise((resolve,reject) => {
              const canvas=document.querySelector('.teacher-avatar-canvas'),samples=[];
              let start=null,lastCapture=-Infinity;
              const step=timestamp=>{
                try {
                  if(start===null)start=timestamp;
                  const elapsed=Math.min(duration,(timestamp-start)/1000);
                  const state={gesture,requestTime:elapsed,duration,motionTime:40+elapsed,mouthOpen:0,mouthRound:0};
                  teacherAvatar.render(state);
                  if(!teacherAvatar.active)throw new Error('Renderer stopped during controlled gesture');
                  if(elapsed-lastCapture>=1/fps-.003||elapsed>=duration){
                    samples.push({request_time_s:elapsed,performance_ms:performance.now(),
                      image:canvas.toDataURL('image/jpeg',.88).split(',')[1]});lastCapture=elapsed;
                  }
                  if(elapsed>=duration)resolve(samples);else requestAnimationFrame(step);
                }catch(error){reject(error)}
              };requestAnimationFrame(step);
            })""", {"gesture": gesture, "duration": 5, "fps": 12})
            recording = await finish_recording(page, out / f"gesture-{gesture}-motion.webm", audio=False)
            directory = out / f"gesture-{gesture}-motion"
            directory.mkdir(exist_ok=True)
            images, times, mean_changes, changed_fractions = [], [], [], []
            first = previous = changed = None
            for index, sample in enumerate(captures):
                raw = base64.b64decode(sample.pop("image"))
                path = directory / f"frame-{index:03}.jpg"
                path.write_bytes(raw)
                image = Image.open(io.BytesIO(raw)).convert("RGB")
                images.append(image)
                pixels = np.asarray(image).astype(np.int16)
                if first is None:
                    first = pixels
                    changed = np.zeros(pixels.shape[:2], dtype=bool)
                if previous is not None:
                    difference = np.abs(pixels - previous)
                    mean_changes.append(float(difference.mean()))
                    changed_fractions.append(float((difference.max(axis=2) >= 24).mean()))
                changed |= np.abs(pixels - first).max(axis=2) >= 24
                previous = pixels
                times.append(sample)
            assert len(images) >= 30, f"Insufficient native {gesture} motion samples"
            mean_changes = np.asarray(mean_changes)
            changed_fractions = np.asarray(changed_fractions)
            ys, xs = np.where(changed)
            bounds = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None
            edge_pixels = int(changed[0].sum() + changed[-1].sum() + changed[:, 0].sum() + changed[:, -1].sum())
            assert float(mean_changes.max()) > 0.2, f"Controlled {gesture} appears frozen"
            picks = np.linspace(0, len(images) - 1, 7).round().astype(int)
            width, height = 240, round(240 * images[0].height / images[0].width)
            montage = Image.new("RGB", (width * len(picks), height + 28), "#ffffff")
            draw = ImageDraw.Draw(montage)
            for position, index in enumerate(picks):
                montage.paste(images[index].resize((width, height)), (position * width, 28))
                draw.text((position * width + 8, 6), f"{gesture} {times[index]['request_time_s']:.2f}s", fill="#222222")
            montage.save(out / f"gesture-{gesture}-motion-montage.png")
            images[0].resize((240, height)).save(out / f"gesture-{gesture}-motion.gif", save_all=True,
                 append_images=[image.resize((240, height)) for image in images[1:]], duration=round(5000 / len(images)), loop=0)
            (directory / "timestamps.json").write_text(json.dumps(times, indent=2) + "\n")
            summary["gestures"][gesture] = {"samples": len(images), "last_request_time_s": times[-1]["request_time_s"],
                "recording": recording, "mean_absolute_rgb_change_per_step": {"median": float(np.median(mean_changes)),
                    "p95": float(np.percentile(mean_changes, 95)), "max": float(mean_changes.max())},
                "fraction_pixels_changed_at_least_24": {"median": float(np.median(changed_fractions)), "max": float(changed_fractions.max())},
                "changed_pixel_bounds_from_first_pose": bounds, "changed_boundary_pixels": edge_pixels,
                "bounds_limit": "changed pixels only; inspect montage/video for limb anatomy and clipping"}
    finally:
        await page.evaluate("teacherAvatar.reset();startRender()")
    return summary


async def wait_for_server(url: str) -> None:
    import urllib.request
    for _ in range(100):
        try:
            await asyncio.to_thread(urllib.request.urlopen, url, timeout=0.3)
            return
        except OSError:
            await asyncio.sleep(0.1)
    raise RuntimeError(f"Local fixture did not start: {url}")


async def run_checks(base: str, fixture: MediaFixture, out: Path, report: dict,
                     visual_only: bool = False, motion_only: bool = False,
                     selected_rig: dict | None = None) -> dict:
    from playwright.async_api import async_playwright

    report.update({"label": "measured locally with real Chromium WebGL frontend and an isolated protocol fixture",
              "ok": False, "scope": "rendering/media integration; no LLM evaluation, real learner changes or deployment",
              "checks": {}, "page_errors": [], "console_errors": [], "external_requests": [], "configuration_bounds": {
                  "capture_interval_ms": 160, "canvas_sample_count": 50, "browser_capture_fps": 24}})
    async def only_local(route) -> None:
        url = urlsplit(route.request.url)
        if url.scheme in ("http", "https", "ws", "wss") and url.hostname not in ("127.0.0.1", "localhost"):
            report["external_requests"].append(route.request.url)
            await route.abort()
        else:
            await route.continue_()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--autoplay-policy=no-user-gesture-required", "--enable-unsafe-swiftshader"])
        try:
            context = await browser.new_context(viewport={"width": 1440, "height": 1000})
            await context.route("**/*", only_local)
            await context.add_init_script(AUDIO_OBSERVER)
            page = await context.new_page()
            page.on("pageerror", lambda e: report["page_errors"].append(str(e)))
            page.on("console", lambda e: report["console_errors"].append(e.text) if e.type == "error" else None)
            await page.goto(base + "/?avatar=mesh&edition=secondary&student=mesh-check", wait_until="networkidle")
            await page.wait_for_function("!document.querySelector('#connect').disabled")
            await page.locator("#connect").click()
            await page.wait_for_function("sessionState==='ready' && window.LiveAgentMedia?.avatarState()?.renderer==='mesh'", timeout=60000)
            await page.wait_for_function("onScreen!==null && document.querySelector('#caption').textContent.includes('叶片')", timeout=30000)
            state = await page.evaluate("window.LiveAgentMedia.avatarState()")
            assert state["renderer"] == "mesh", state
            assert fixture.connections[-1].get("renderer") == "mesh", fixture.connections[-1]
            report["checks"]["actual_mesh_negotiation"] = state
            if selected_rig is not None:
                loaded_rig = await page.evaluate("teacherAvatar.rig")
                assert loaded_rig == selected_rig, "Browser loaded a different manifest than --model"
                report["checks"]["actual_loaded_model_matches_selection"] = {
                    "model": loaded_rig["model"], "asset_revision": loaded_rig.get("asset_revision", 1),
                    "served_manifest_sha256": report["selected_model"]["served_manifest_sha256"]}
            if fixture.sparse_fallback:
                assert fixture.connections[-1].get("avatar_video_frames") is True, fixture.connections[-1]
                standby = await page.evaluate("queue[0].meta")
                stride = max(1, int(np.ceil(standby["fps"] / 2)))
                expected_indices = list(range(0, standby["n_frames"], stride))
                assert standby.get("video_frame_indices") == expected_indices, standby
                assert standby.get("video_frames") == len(expected_indices) < standby["n_frames"], standby
                report["checks"]["negotiated_sparse_standby_video"] = {
                    "logical_frames": standby["n_frames"], "logical_fps": standby["fps"],
                    "transmitted_frames": standby["video_frames"], "source_indices": expected_indices,
                    "duration_s": standby["duration"], "sample_rate_hz": standby["sample_rate"],
                    "label": "measured actual chunk header; standby sampling only; full PCM remains scheduled"}
            await page.wait_for_function("document.querySelector('#boardImg').complete && document.querySelector('#boardImg').naturalWidth>0")
            assert await page.locator("#boardTitle").text_content() == "叶片如何制造养分？"
            report["checks"]["board_image_and_caption"] = True
            if visual_only or motion_only:
                await save_canvas(page, out / "portrait.png")
                report["checks"]["controlled_supported_gesture_snapshots"] = await save_gesture_snapshots(page, out)
                if motion_only:
                    report["checks"]["controlled_full_gesture_motion"] = await save_gesture_motion(page, fixture, out)
                report["scope"] = "controlled visual review only; not full acceptance"
                report["ok"] = True
                await page.locator("#disconnect").click()
                return report
            await page.evaluate("""() => {
              window.__meshCheckRenderTimes=[];window.__meshCheckPerformanceStart=performance.now();
              window.__meshCheckRenderStart=window.__avRenders||0;
              const render=teacherAvatar.render;
              teacherAvatar.render=function(...args){const start=performance.now();const result=render.apply(this,args);
                window.__meshCheckRenderTimes.push(performance.now()-start);return result};
            }""")
            await start_recording(page)
            frames = []
            timestamps = []
            for index in range(50):
                image = await save_canvas(page, out / f"frame-{index:03}.png")
                frames.append(image)
                timestamps.append(await page.evaluate("""(() => {const media=mediaTime(),q=queue.find(q=>media>=q.start&&media<q.end);return {
                  performance_ms:performance.now(),audio_s:audioCtx.currentTime,media_s:media,
                  avatar:window.LiveAgentMedia.avatarState(),expected_request_time_s:q? q.meta.avatar.request_time_s+media-q.start:null,
                  expected_motion_time_s:q? q.meta.avatar.motion_time_s+media-q.start:null,
                  caption:document.querySelector('#caption').textContent,
                  board_key:document.querySelector('#board').dataset.key};})()"""))
                await page.wait_for_timeout(160)
            await page.wait_for_function("queue.every(q=>q.endedSent)", timeout=35000)
            report["checks"]["actual_browser_recording"] = await finish_recording(page, out / "browser-avatar.webm")
            performance_data = await page.evaluate("""() => {
              const canvas=document.querySelector('.teacher-avatar-canvas'),gl=canvas.getContext('webgl2')||canvas.getContext('webgl'),info=gl.getExtension('WEBGL_debug_renderer_info');
              return {start:window.__meshCheckPerformanceStart,end:performance.now(),render_start:window.__meshCheckRenderStart,
                render_end:window.__avRenders||0,cpu_ms:window.__meshCheckRenderTimes,
                raf_ms:window.__meshCheckRafTimes.filter(t=>t>=window.__meshCheckPerformanceStart),
                renderer:info?gl.getParameter(info.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)};
            }""")
            cpu = np.asarray(performance_data.pop("cpu_ms"))
            raf = np.diff(performance_data.pop("raf_ms"))
            elapsed = (performance_data["end"] - performance_data["start"]) / 1000
            report["checks"]["performance_measured_during_capture"] = {
                "label": "measured locally in headless Chromium; native PNG snapshots and canvas/audio recording active; not device-display latency",
                "webgl_renderer": performance_data["renderer"], "elapsed_s": elapsed,
                "observed_frontend_render_loops_per_s": (performance_data["render_end"] - performance_data["render_start"]) / elapsed,
                "cpu_render_submission_ms": {"samples": len(cpu), "median": float(np.median(cpu)), "p95": float(np.percentile(cpu, 95)), "max": float(cpu.max())},
                "raf_interval_ms": {"samples": len(raf), "median": float(np.median(raf)), "p95": float(np.percentile(raf, 95)), "max": float(raf.max())}}
            # Native captures, rather than the old video canvas, form both the
            # preview and the visual inspection montage.
            unique = {hashlib.sha256(image.tobytes()).hexdigest() for image in frames}
            assert len(unique) > 5, "Actual WebGL canvas appears frozen"
            report["checks"]["animated_actual_canvas"] = {"samples": len(frames), "distinct_frames": len(unique), "native_size": list(frames[0].size)}
            frames[0].save(out / "after-mesh.png")
            spoken = [x for x in timestamps if x["expected_request_time_s"] is not None and x["avatar"].get("request") == 1]
            assert len(spoken) > 5, "Insufficient actual speech-frame clock samples"
            clock_error = max(abs(x["avatar"]["requestTime"] - x["expected_request_time_s"]) for x in spoken)
            assert clock_error < 0.15, clock_error
            chunks = sorted({x["avatar"]["chunk"] for x in spoken})
            assert len(chunks) >= 2, "No chunk boundary was sampled"
            assert all(a["avatar"]["requestTime"] <= b["avatar"]["requestTime"] for a, b in zip(spoken, spoken[1:])), "Gesture clock restarted at a chunk boundary"
            assert len({round(x["avatar"]["mouthOpen"], 2) for x in spoken}) > 3, "Audio-driven mesh mouth appears frozen"
            assert all("叶片" in x["caption"] and x["board_key"] == "mesh-check-1" for x in spoken)
            report["checks"]["audio_clock_and_chunk_continuity"] = {"sampled_chunks": chunks, "max_request_clock_error_s": clock_error,
                                                                    "mouth_variety": len({round(x["avatar"]["mouthOpen"], 2) for x in spoken})}
            selected = [frames[i] for i in (0, 9, 19, 29, 39, 49)]
            tile_w, tile_h = 240, round(240 * frames[0].height / frames[0].width)
            montage = Image.new("RGB", (tile_w * 6, tile_h), "white")
            for i, frame in enumerate(selected):
                montage.paste(frame.resize((tile_w, tile_h)), (i * tile_w, 0))
            montage.save(out / "motion-montage.png")
            small = [image.resize((240, tile_h)) for image in frames]
            small[0].save(out / "browser-avatar.gif", save_all=True, append_images=small[1:], duration=160, loop=0)
            (out / "frame-timestamps.json").write_text(json.dumps(timestamps, indent=2) + "\n")
            pcm_observed = await page.evaluate("window.__meshCheckAudio")
            assert any(item["rms"] > 0.005 and item["state"] == "running" for item in pcm_observed), pcm_observed
            report["checks"]["nonzero_pcm_scheduled_on_running_audio_context"] = pcm_observed
            report["checks"]["human_audibility"] = "not assessed; browser recording includes actual scheduled PCM"
            # Controlled poses inspect the other supported actions using the
            # same actual WebGL renderer. They supplement, and are labelled
            # separately from, the audio-clock-driven classroom recording.
            report["checks"]["controlled_supported_gesture_snapshots"] = await save_gesture_snapshots(page, out)
            report["checks"]["controlled_full_gesture_motion"] = await save_gesture_motion(page, fixture, out)
            layout = {}
            for name, width, height in (("desktop", 1440, 1000), ("tablet", 768, 1024), ("phone", 390, 844)):
                await page.set_viewport_size({"width": width, "height": height})
                await page.wait_for_timeout(250)
                metrics = await page.evaluate("""() => {
                  const canvas=document.querySelector('.teacher-avatar-canvas'),r=canvas.getBoundingClientRect(),wrap=document.querySelector('#screenWrap').getBoundingClientRect(),style=getComputedStyle(canvas);
                  const nativeRatio=canvas.width/canvas.height,contain=style.objectFit==='contain';
                  const contentWidth=contain?Math.min(r.width,r.height*nativeRatio):r.width,contentHeight=contain?contentWidth/nativeRatio:r.height;
                  return {ratio_error:Math.abs(contentWidth/contentHeight/nativeRatio-1),
                    element_ratio_error:Math.abs(r.width/r.height/nativeRatio-1),object_fit:style.objectFit,
                    horizontal_overflow:document.documentElement.scrollWidth>innerWidth+1,
                    canvas_in_stage:r.left>=wrap.left-1&&r.top>=wrap.top-1&&r.right<=wrap.right+1&&r.bottom<=wrap.bottom+1,
                    canvas_width:r.width,canvas_height:r.height,content_width:contentWidth,content_height:contentHeight,stage_width:wrap.width,stage_height:wrap.height};
                }""")
                assert metrics["ratio_error"] < 0.005 and not metrics["horizontal_overflow"] and metrics["canvas_in_stage"], (name, metrics)
                layout[name] = metrics
                await page.locator("#classroom").screenshot(path=str(out / f"{name}.png"))
            report["checks"]["responsive_aspect_and_stage_bounds"] = layout
            await page.set_viewport_size({"width": 1440, "height": 1000})

            # Start a fresh whole request and interrupt it while its mesh gesture
            # is active. The real stop message must clear audio and caption.
            await fixture.control("wave")
            await page.wait_for_function("onScreen?.meta.request===2", timeout=15000)
            await page.wait_for_timeout(500)
            await fixture.control("stop")
            await page.wait_for_function("queue.length===0 && document.querySelector('#caption').textContent===''")
            stopped_epoch = await page.evaluate("window.LiveAgentMedia.avatarState().epoch")
            await page.wait_for_timeout(200)
            assert not await page.evaluate("queue.some(q=>q.meta.request===2)")
            reset_state = await page.evaluate("window.LiveAgentMedia.avatarState()")
            assert reset_state.get("request") is None and reset_state.get("gesture") == "idle" and reset_state.get("mouthOpen") == 0, reset_state
            report["checks"]["interruption_cancels_audio_caption_and_stale_queue"] = {"epoch": stopped_epoch, "queue_empty": True}

            await fixture.control("replace")
            await page.wait_for_function("onScreen?.meta.request===3 && queue.length>0", timeout=15000)
            await page.wait_for_timeout(600)
            captures = [item for item in fixture.messages if item.get("type") == "avatar_frame"]
            assert captures and all(item.get("decoded_shape") for item in captures), captures
            assert all(item.get("renderer") == "mesh" and item.get("model") == MODEL for item in captures)
            accepted = [item for item in captures if item.get("backend_accepted")]
            assert len(accepted) > 3, "Actual backend rejected browser mesh evidence"
            assert fixture.capture_validation and all(all(item.values()) for item in fixture.capture_validation), fixture.capture_validation
            report["checks"]["actual_canvas_jpeg_evidence"] = {"captures": len(captures), "distinct_pixels": len({x["image_sha256"] for x in captures}),
                                                               "accepted_by_actual_backend": len(accepted), "epochs": sorted({x["epoch"] for x in captures}),
                                                               "decoded_shapes": sorted({tuple(x["decoded_shape"]) for x in captures})}
            report["checks"]["actual_backend_rejects_duplicate_and_stale_evidence"] = fixture.capture_validation
            mesh_acks = [x for x in fixture.messages if x.get("type") == "chunk_end" and x.get("renderer") == "mesh"]
            assert mesh_acks and all(not x.get("painted") for x in mesh_acks), mesh_acks
            report["checks"]["mesh_never_claims_fallback_frames_painted"] = True
            await page.locator("#disconnect").click()
            await page.wait_for_function("sessionState==='disconnected' && queue.length===0")
            assert await page.locator("#caption").text_content() == ""
            report["checks"]["disconnect_resets_playback"] = True

            await page.locator("#connect").click()
            await page.wait_for_function("sessionState==='ready' && onScreen?.meta.request===1", timeout=30000)
            assert await page.evaluate("window.LiveAgentMedia.avatarState().epoch") == 0
            report["checks"]["reconnect_starts_new_epoch"] = True
            await page.evaluate("""() => {
              const canvas=document.querySelector('.teacher-avatar-canvas'),gl=canvas.getContext('webgl2')||canvas.getContext('webgl');
              if(!gl)throw new Error('Actual renderer has no WebGL context');
              const extension=gl.getExtension('WEBGL_lose_context');
              if(!extension)throw new Error('WEBGL_lose_context unavailable');extension.loseContext();
            }""")
            await page.wait_for_function("window.LiveAgentMedia.avatarState().renderer==='video'", timeout=15000)
            await page.wait_for_timeout(150)
            assert any(x.get("type") == "avatar_renderer" and x.get("renderer") == "video" for x in fixture.messages)
            await page.locator("#screenWrap").screenshot(path=str(out / "runtime-webgl-fallback.png"))
            report["checks"]["runtime_context_loss_falls_back"] = True
            if fixture.sparse_fallback:
                await page.wait_for_function("queue.some(q=>q.painted?.size>0)")
                actual = await page.evaluate("queue.filter(q=>q.painted?.size).map(q=>({request:q.meta.request,chunk:q.meta.chunk,painted:[...q.painted],sources:q.meta.video_frame_indices}))")
                assert all(item["sources"] and set(item["painted"]).issubset(item["sources"]) for item in actual), actual
                report["checks"]["sparse_fallback_paints_native_indices"] = actual
                await fixture.control("replace")
                await page.wait_for_function("onScreen?.meta.request===2 && queue.some(q=>q.meta.request===2)")
                full = await page.evaluate("queue.find(q=>q.meta.request===2).meta")
                assert "video_frames" not in full and "video_frame_indices" not in full, full
                report["checks"]["future_fallback_chunks_restore_full_video"] = {"logical_frames": full["n_frames"], "codec": full["codec"]}
            await page.locator("#disconnect").click()
            await context.close()

            # Start-up failures should negotiate video from the beginning.
            for scenario in ("missing-model", "webgl-unavailable"):
                count = len(fixture.connections)
                context = await browser.new_context(viewport={"width": 1440, "height": 1000})
                await context.route("**/*", only_local)
                await context.add_init_script(AUDIO_OBSERVER)
                if scenario == "missing-model":
                    await context.route(base + report["selected_model"]["requested_url"], lambda route: route.abort())
                else:
                    await context.add_init_script("""(() => {const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...rest){return /^webgl/.test(type)?null:get.call(this,type,...rest)}})()""")
                page = await context.new_page()
                await page.goto(base + "/?avatar=mesh&edition=secondary&student=mesh-check", wait_until="networkidle")
                await page.wait_for_function("!document.querySelector('#connect').disabled")
                await page.locator("#connect").click()
                await page.wait_for_function("sessionState==='ready' && onScreen!==null", timeout=30000)
                assert len(fixture.connections) > count
                assert fixture.connections[-1].get("renderer") != "mesh", fixture.connections[-1]
                assert await page.evaluate("window.LiveAgentMedia.avatarState().renderer") == "video"
                await page.locator("#screenWrap").screenshot(path=str(out / f"{scenario}.png"))
                report["checks"][scenario + "_uses_video"] = True
                await page.locator("#disconnect").click()
                await context.close()
            assert not fixture.errors, fixture.errors
            assert not report["page_errors"], report["page_errors"]
            assert not report["external_requests"], report["external_requests"]
            report["checks"]["all_browser_assets_served_locally"] = True
            report["ok"] = True
        finally:
            await browser.close()
    return report


async def main(args: argparse.Namespace) -> None:
    selected_rig, model_identity, model_files = staged_model(args.model)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    pcm, rate, source = read_pcm(args.speech_wav, args.speech_rate)
    fixture = MediaFixture(pcm, rate, args.sparse_fallback)
    Image.fromarray(fixture.fallback_frame).save(out / "before-puppet.png")
    backend_port, frontend_port = available_port(), args.port or available_port()
    backend_url, base = f"http://127.0.0.1:{backend_port}", f"http://127.0.0.1:{frontend_port}"
    server = uvicorn.Server(uvicorn.Config(fixture.app, host="127.0.0.1", port=backend_port, log_level="warning"))
    # Uvicorn re-raises captured termination signals before an awaiting task can
    # clean up its sibling frontend. Own the parent lifecycle explicitly.
    server.capture_signals = contextlib.nullcontext
    parent_task = asyncio.current_task()
    def shutdown() -> None:
        server.should_exit = True
        if not args.serve:
            parent_task.cancel()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)
    task = asyncio.create_task(server.serve())
    log = (out / "frontend.log").open("wb")
    frontend = await asyncio.create_subprocess_exec("node", "--input-type=module", "-e", STAGED_FRONTEND, cwd=ROOT,
                     env={**os.environ, "HOST": "127.0.0.1", "PORT": str(frontend_port), "BACKEND_URL": backend_url,
                          "MESH_CHECK_MODEL_URL": model_identity["requested_url"],
                          "MESH_CHECK_MANIFEST": base64.b64encode(json.dumps(selected_rig, ensure_ascii=False).encode()).decode()},
                     stdout=log, stderr=log)
    report: dict = {"ok": False, "label": "measured locally", "audio_source": source}
    report["selected_model"] = model_identity
    report["audio_sample_rate_configured_hz"] = rate
    report["sparse_fallback_configured"] = args.sparse_fallback
    report["audio_samples_measured"] = len(pcm)
    if args.speech_wav:
        report["audio_source_sha256"] = hashlib.sha256(args.speech_wav.read_bytes()).hexdigest()
    input_hashes = runtime_hashes(model_files)
    started = time.monotonic()
    try:
        await wait_for_server(base + "/api/health")
        print(f"Local rendering fixture: {base}/?avatar=mesh&student=mesh-check", flush=True)
        print(f"Selected model: {model_identity['source_path']} (asset revision {model_identity['asset_revision']})", flush=True)
        if args.serve:
            print("Isolated prerecorded media fixture; no teaching model or saved learner memory.", flush=True)
            report["serve_only"] = True
            await task  # Uvicorn's signal handler exits here and the owned frontend is cleaned up below.
            return
        report = await run_checks(base, fixture, out, report, args.visual_only, args.motion_only, selected_rig)
        report["audio_source"] = source
        end_hashes = runtime_hashes(model_files)
        changed = [path for path, sha in input_hashes.items() if end_hashes.get(path) != sha]
        if changed:
            raise AssertionError(f"Runtime inputs changed during acceptance: {changed}")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except BaseException as exc:
        report["ok"] = False
        report["failure"] = repr(exc)
        raise
    finally:
        report["elapsed_s_measured"] = round(time.monotonic() - started, 3)
        report["runtime_sha256"] = input_hashes
        end_hashes = runtime_hashes(model_files)
        report["runtime_changed_during_check"] = [path for path, sha in input_hashes.items() if end_hashes.get(path) != sha]
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        (out / "protocol.json").write_text(json.dumps({"selected_model": model_identity,
                                                       "connections": fixture.connections, "sent": fixture.sent,
                                                       "received": fixture.messages, "errors": fixture.errors}, ensure_ascii=False, indent=2) + "\n")
        if frontend.returncode is None:
            frontend.terminate()
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(frontend.wait(), 5)
        if frontend.returncode is None:
            frontend.kill()
            await frontend.wait()
        server.should_exit = True
        await task
        log.close()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / ".cache/teacher-mesh/acceptance")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL,
                        help="local JSON manifest inside frontend/public; default is the current rig-v7.json")
    candidates = (ROOT / ".cache/teacher-gestures/speech.wav", ROOT / ".cache/teacher-motion/speech.wav")
    parser.add_argument("--speech-wav", type=Path, default=next((x for x in candidates if x.exists()), None))
    parser.add_argument("--speech-rate", type=int, help="explicit PCM sample-rate override for an incorrectly labelled recording")
    parser.add_argument("--serve", action="store_true", help="keep isolated local media fixture open instead of running checks")
    parser.add_argument("--visual-only", action="store_true", help="capture controlled native poses for artwork review; skips full acceptance")
    parser.add_argument("--motion-only", action="store_true", help="capture native poses and complete silent wave/think sequences; skips full acceptance")
    parser.add_argument("--sparse-fallback", action="store_true", help="negotiate low-rate standby video for mesh while preserving full PCM and logical frame timing")
    parser.add_argument("--port", type=int, default=0, help="local frontend port; default uses a free loopback port")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(arguments()))

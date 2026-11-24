"""Browser mesh negotiation and actual displayed-frame evidence, with no providers."""
import asyncio
import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from live_agent.backend.avatar import INTENTS, MODEL, decode_capture, negotiated
from live_agent.backend.transport import WSTransport
from live_agent.capability import CapabilityManifest, Decision, Status
from live_agent.types import CheckQuestion, Chunk, EventType, Verdict, VerdictLabel, now


class WS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))

    async def send_bytes(self, data):
        self.sent.append(bytes(data))


def jpeg(color=(0, 220, 0), size=(48, 64)):
    buf = io.BytesIO()
    Image.new('RGB', size, color).save(buf, format='JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def chunk(ci=0, offset=0):
    return Chunk(3, ci, 24, 24, video=np.full((24, 64, 48, 3), (220, 0, 0), np.uint8),
                 audio=np.zeros((32000, 2), np.float32), sample_rate=32000,
                 meta={'request_offset_s': offset, 'request_duration_s': 4.0,
                       'motion_time_s': 7.0 + offset, 'avatar_gesture': 'wave'})


def ack(kind, ci=0, renderer='mesh', epoch=0):
    return {'type': kind, 'request': 3, 'chunk': ci, 'renderer': renderer, 'model': MODEL, 'epoch': epoch,
            'painted': [] if renderer == 'mesh' else list(range(24))}


def capture(ci=0, frame=2, offset=0, epoch=0):
    return {'type': 'avatar_frame', 'request': 3, 'chunk': ci, 'renderer': 'mesh', 'model': MODEL,
            'epoch': epoch, 'frame': frame, 'request_time_s': offset + frame/24,
            'tp': 1000 + frame*1000/24, 'image': jpeg(), 'mime': 'image/jpeg'}


async def started(ci=0, offset=0):
    transport = WSTransport(WS(), avatar_mesh=True)
    await transport.send_chunk(chunk(ci, offset), SimpleNamespace(transcript=''))
    transport.on_client_message(ack('chunk_start', ci))
    return transport


def test_mesh_negotiation_requires_exact_model_teacher_and_puppet():
    hello = {'renderer': 'mesh', 'avatar_model': MODEL}
    assert negotiated(hello, generator='puppet', teacher=True)
    assert not negotiated({}, generator='puppet', teacher=True)
    assert not negotiated({**hello, 'avatar_model': 'unknown'}, generator='puppet', teacher=True)
    assert not negotiated(hello, generator='mock', teacher=True)
    assert not negotiated(hello, generator='puppet', teacher=False)


def test_runtime_subset_keeps_aliases_and_uses_existing_capability_degradation():
    manifest = CapabilityManifest.load(Path(__file__).resolve().parents[1] / 'configs/persona_teacher/capabilities.json')
    manifest.min_status = Status.DOCUMENTED
    manifest.supported_intents = INTENTS
    assert manifest.decide('wave').decision == Decision.EMIT
    drink = manifest.by_intent('drink_water')
    assert drink is not None
    assert manifest.decide('drink_water').decision in (Decision.DEGRADE, Decision.REFUSE)
    drink.degrade_to = '我用语言说明。'
    assert manifest.decide('drink_water').decision == Decision.DEGRADE
    assert manifest.match('drink_water') is drink


def test_mesh_header_contains_full_request_and_continuous_chunk_clock_legacy_unchanged():
    async def run():
        transport = WSTransport(WS(), avatar_mesh=True)
        await transport.send_chunk(chunk(2, 2), SimpleNamespace(transcript=''))
        avatar = transport.ws.sent[0]['avatar']
        assert avatar == {'renderer': 'mesh', 'model': MODEL, 'epoch': 0, 'gesture': 'wave',
                          'request_time_s': 2.0, 'request_duration_s': 4.0, 'motion_time_s': 9.0}
        assert transport.avatar_status()['supported_capabilities'] == sorted(INTENTS)
        legacy = WSTransport(WS())
        await legacy.send_chunk(chunk(), SimpleNamespace(transcript=''))
        assert 'avatar' not in legacy.ws.sent[0]
        await legacy.stop_playback()
        assert legacy.ws.sent[-1] == {'type': 'stop'}
    asyncio.run(run())


@pytest.mark.parametrize('mesh,opt_in', [(True, False), (True, None), (True, 'true'),
                                        (True, 1), (False, True)])
def test_standby_frames_require_explicit_bool_opt_in_and_negotiated_mesh(mesh, opt_in):
    async def run():
        transport = WSTransport(WS(), avatar_mesh=mesh, avatar_video_frames=opt_in)
        await transport.send_chunk(chunk(), SimpleNamespace(transcript=''))
        header = transport.ws.sent[0]
        assert 'video_frames' not in header and 'video_frame_indices' not in header
        assert header['n_frames'] == 24 and len(transport.ws.sent) == 26  # header,24JPEGs,PCM
        assert not transport._standby_frame_indices
    asyncio.run(run())


def test_sparse_standby_jpeg_preserves_media_clock_audio_and_original_recording():
    async def run():
        original = Chunk(3, 0, 34, 24,
                         video=np.stack([np.full((64, 48, 3), (i * 5, 0, 0), np.uint8) for i in range(34)]),
                         audio=np.full((45333, 2), 0.2, np.float32), sample_rate=32000)
        transport = WSTransport(WS(), avatar_mesh=True, avatar_video_frames=True)
        transport.recorder = SimpleNamespace(write=lambda ch: None)
        await transport.send_chunk(original, SimpleNamespace(transcript=''))
        header = transport.ws.sent[0]
        assert header['n_frames'] == 34 and header['fps'] == 24 and header['duration'] == 34/24
        assert header['video_frames'] == 3 and header['video_frame_indices'] == [0, 12, 24]
        assert len(transport.ws.sent) == 5  # header,3JPEGs,PCM
        for payload, native_index in zip(transport.ws.sent[1:4], [0, 12, 24]):
            pixels = np.asarray(Image.open(io.BytesIO(payload)))
            assert abs(int(pixels[5, 5, 0]) - native_index * 5) <= 3
        assert len(transport.ws.sent[-1]) == 90666
        assert np.all(np.frombuffer(transport.ws.sent[-1], dtype=np.int16) == int(0.2 * 32767))
        assert transport._sent[(3, 0)] is original and len(original.video) == 34
    asyncio.run(run())


def test_sparse_standby_h264_sizes_describe_transmitted_frames(monkeypatch):
    encoded = []

    def encoder(frames):
        encoded.append(frames)
        return b'AB', [1, 1]

    monkeypatch.setattr('live_agent.backend.transport.encode_h264', encoder)

    async def run():
        transport = WSTransport(WS(), video_codec='h264', avatar_mesh=True, avatar_video_frames=True)
        await transport.send_chunk(chunk(), SimpleNamespace(transcript=''))
        header = transport.ws.sent[0]
        assert header['codec'] == 'h264' and header['n_frames'] == 24
        assert header['video_frames'] == 2 and header['video_frame_indices'] == [0, 12]
        assert header['sizes'] == [1, 1] and len(encoded[0]) == 2
        assert transport.ws.sent[1] == b'AB' and len(transport.ws.sent[-1]) == 64000
    asyncio.run(run())


def test_sparse_standby_fallback_restores_future_full_video():
    async def run():
        transport = WSTransport(WS(), avatar_mesh=True, avatar_video_frames=True)
        await transport.send_chunk(chunk(), SimpleNamespace(transcript=''))
        assert transport.ws.sent[0]['video_frame_indices'] == [0, 12]
        assert transport.on_avatar_renderer({'renderer': 'video', 'epoch': 0})
        start = len(transport.ws.sent)
        await transport.send_chunk(chunk(1, 1), SimpleNamespace(transcript=''))
        header = transport.ws.sent[start]
        assert 'video_frames' not in header and 'video_frame_indices' not in header
        assert header['n_frames'] == 24 and len(transport.ws.sent) - start == 26
    asyncio.run(run())


def test_buffered_standby_video_qc_uses_only_transmitted_native_indices():
    async def run():
        original = chunk()
        for index, pixels in enumerate(original.video):
            pixels[:] = (index * 5, 0, 0)
        transport = WSTransport(WS(), avatar_mesh=True, avatar_video_frames=True)
        recorded, presented = [], []
        transport.recorder = SimpleNamespace(write=recorded.append)
        await transport.send_chunk(original, SimpleNamespace(transcript=''))
        assert transport.on_avatar_renderer({'renderer': 'video', 'epoch': 0})
        transport.orchestrator = SimpleNamespace(on_presented=lambda *a, **kw: presented.append(kw))
        transport.on_client_message(ack('chunk_start', renderer='video'))
        painted = {(3, 0): [0, 1, 12, 23]}
        evidence, issue = transport.visual_evidence(3, [original], painted)
        assert issue is None and evidence[0].meta['visual_source'] == 'server_video'
        assert evidence[0].video[:, 5, 5, 0].tolist() == [0, 60]  # native0,12; never native1 or23
        missing, _ = transport.visual_evidence(3, [original], {})
        assert len(missing[0].video) == 0  # omitted paint report never implies all hidden originals
        transport.on_client_message({**ack('chunk_end', renderer='video'), 'painted': [0, 1, 12, 23]})
        assert presented[0]['painted'] == [0, 12]
        assert recorded == [original] and len(recorded[0].video) == 24
        transport.evict_request(3)
        assert not transport._standby_frame_indices
    asyncio.run(run())


def test_sparse_standby_does_not_restrict_actual_browser_capture_indices():
    async def run():
        transport = WSTransport(WS(), avatar_mesh=True, avatar_video_frames=True)
        await transport.send_chunk(chunk(), SimpleNamespace(transcript=''))
        transport.on_client_message(ack('chunk_start'))
        assert await transport.on_avatar_frame(capture(frame=13))  # not a standby source frame
        evidence, issue = transport.visual_evidence(3, [chunk()], {(3, 0): []})
        assert issue is None and evidence[0].meta['visual_source'] == 'browser_mesh'
        assert evidence[0].video[0, 5, 5, 1] > 200
        await transport.stop_playback()
        assert not transport._standby_frame_indices
    asyncio.run(run())


def test_valid_capture_replaces_fallback_pixels_and_has_timestamp_metadata():
    async def run():
        transport = await started()
        assert await transport.on_avatar_frame(capture())
        evidence, issue = transport.visual_evidence(3, [chunk()], {(3, 0): []})
        assert issue is None and evidence[0].video.shape == (1, 64, 48, 3)
        assert evidence[0].video[0, 5, 5, 1] > 200  # green browser capture, not red server puppet
        assert evidence[0].meta['visual_source'] == 'browser_mesh'
        assert evidence[0].meta['avatar_capture_times'] == [2/24]
        assert evidence[0].meta['avatar_capture_timestamps'][0] > 0
        assert evidence[0].audio is not None
    asyncio.run(run())


@pytest.mark.parametrize('changes', [
    {'epoch': -1}, {'request': 999}, {'chunk': 9}, {'frame': 24}, {'frame': True},
    {'request_time_s': 2.5}, {'request_time_s': float('nan')}, {'tp': float('inf')},
    {'renderer': 'video'}, {'model': 'wrong'}, {'mime': 'image/png'},
    {'image': 'data:image/jpeg;base64,' + 'A'*160_001}, {'image': jpeg(size=(641, 64))},
])
def test_capture_rejects_unrelated_stale_malformed_or_unbounded_data(changes):
    async def run():
        transport = await started()
        assert not await transport.on_avatar_frame({**capture(), **changes})
        assert not transport._avatar_captures
    asyncio.run(run())


def test_capture_rejects_duplicate_nonmonotonic_and_resolution_change():
    async def run():
        transport = await started()
        assert await transport.on_avatar_frame(capture())
        assert not await transport.on_avatar_frame(capture())
        assert not await transport.on_avatar_frame(capture(frame=1))
        assert not await transport.on_avatar_frame({**capture(frame=3), 'image': jpeg(size=(47, 64))})
        assert len(transport._avatar_captures[(3, 0)]) == 1
    asyncio.run(run())


def test_missing_or_mixed_mesh_evidence_never_returns_puppet_frames_and_fallback_next_chunk_works():
    async def run():
        transport = await started()
        evidence, issue = transport.visual_evidence(3, [chunk()], {(3, 0): []})
        assert issue == 'avatar_frames_missing' and evidence[0].video is None
        assert await transport.on_avatar_frame(capture())
        assert transport.on_avatar_renderer({'renderer': 'video', 'epoch': 0})
        assert not await transport.on_avatar_frame(capture(frame=3))
        evidence, issue = transport.visual_evidence(3, [chunk()], {(3, 0): []})
        assert issue == 'avatar_renderer_changed_during_chunk' and evidence[0].video is None
        await transport.send_chunk(chunk(1, 1), SimpleNamespace(transcript=''))
        transport.on_client_message(ack('chunk_start', 1, 'video'))
        evidence, issue = transport.visual_evidence(3, [chunk(1, 1)], {(3, 1): [0, 2]})
        assert issue is None and len(evidence[0].video) == 2
        assert evidence[0].meta['visual_source'] == 'server_video'
        assert not transport.on_avatar_renderer({'renderer': 'mesh', 'epoch': 0})
    asyncio.run(run())


def test_stop_invalidates_pending_and_pre_start_captures():
    async def run():
        transport = WSTransport(WS(), avatar_mesh=True)
        await transport.send_chunk(chunk(), SimpleNamespace(transcript=''))
        assert not await transport.on_avatar_frame(capture())
        transport.on_client_message(ack('chunk_start'))
        assert await transport.on_avatar_frame(capture())
        await transport.stop_playback()
        assert transport.ws.sent[-1] == {'type': 'stop', 'epoch': 1}
        transport.on_client_message(ack('chunk_start'))
        assert not await transport.on_avatar_frame(capture())
        assert not transport._starts and not transport._avatar_captures
    asyncio.run(run())


def test_capture_count_has_chunk_and_request_bounds():
    async def run():
        transport = await started()
        for frame in range(12):
            assert await transport.on_avatar_frame(capture(frame=frame))
        assert not await transport.on_avatar_frame(capture(frame=12))
        await transport.send_chunk(chunk(1, 1), SimpleNamespace(transcript=''))
        transport.on_client_message(ack('chunk_start', 1))
        for frame in range(12):
            assert await transport.on_avatar_frame(capture(1, frame, 1))
        await transport.send_chunk(chunk(2, 2), SimpleNamespace(transcript=''))
        transport.on_client_message(ack('chunk_start', 2))
        assert not await transport.on_avatar_frame(capture(2, 0, 2))
        transport.evict_request(3)
        assert not transport._avatar_captures and not transport._announced
    asyncio.run(run())


def test_qc_missing_browser_captures_logs_unknown_without_invoking_judge():
    import test_pipeline as tp
    from live_agent.types import BlockScript

    class Judge:
        async def judge(self, *args):
            raise AssertionError('fallback pixels must not reach a mesh visual judge')

    async def run():
        orch, _ = tp.build(max_requests=1)
        transport = await started()
        orch.transport, transport.orchestrator = transport, orch
        orch.judge = Judge()
        orch.chunks[3] = [chunk()]
        orch.scripts[3] = BlockScript(3, 1, orch.director.ledger.canon, 'wave', '',
                                      checks=[CheckQuestion('q-mesh', 'Did she wave?')])
        await orch._run_checks_inner(3, now())
        verdict = next(event for event in orch.log.events if event.type == EventType.VERDICT)
        assert verdict.data['label'] == 'unknown'
        assert verdict.data['rationale'] == 'avatar_frames_missing'
    asyncio.run(run())


def test_qc_actual_browser_pixels_reach_visual_judge():
    import test_pipeline as tp
    from live_agent.types import BlockScript

    class Judge:
        async def judge(self, q, chunks, request, evidence_time):
            assert chunks[0].video[0, 5, 5, 1] > 200
            assert chunks[0].meta['visual_source'] == 'browser_mesh'
            return Verdict(q.qid, request, VerdictLabel.COMPLIED, 1, 'actual browser picture', evidence_time, now())

    async def run():
        orch, _ = tp.build(max_requests=1)
        transport = await started()
        assert await transport.on_avatar_frame(capture())
        orch.transport, transport.orchestrator = transport, orch
        orch.judge = Judge()
        orch.chunks[3] = [chunk()]
        orch.scripts[3] = BlockScript(3, 1, orch.director.ledger.canon, 'wave', '',
                                      checks=[CheckQuestion('q-mesh', 'Did she wave?')])
        await orch._run_checks_inner(3, now())
        verdict = next(event for event in orch.log.events if event.type == EventType.VERDICT)
        assert verdict.data['label'] == 'complied'
    asyncio.run(run())


@pytest.mark.parametrize('standby', [False, True])
def test_backend_mesh_session_negotiates_and_streams_fallback_video(tmp_path, standby):
    from fastapi.testclient import TestClient
    from live_agent.backend.app import build_app
    from live_agent.backend.config import parse_args

    config = Path(__file__).resolve().parents[1] / 'configs/persona_teacher'
    args = parse_args(['--generator', 'puppet', '--config', str(config), '--puppet-tts', 'synth',
                       '--llm-url', 'scripted', '--vlm-url', 'mock', '--asr-url', '', '--memory-db', '',
                       '--student-store', str(tmp_path / 'students'), '--log-dir', str(tmp_path / 'logs'),
                       '--dev-allow-uncalibrated'])
    with TestClient(build_app(args)) as client, client.websocket_connect('/ws') as ws:
        ws.send_json({'type': 'hello', 'renderer': 'mesh', 'avatar_model': MODEL,
                      'avatar_video_frames': standby})
        status = media = None
        for _ in range(150):
            msg = ws.receive()
            if 'text' not in msg:
                continue
            data = json.loads(msg['text'])
            if data['type'] == 'status':
                status = data
            elif data['type'] == 'chunk':
                media = data
            if status and media:
                break
        assert status['avatar']['model'] == MODEL
        assert status['avatar']['supported_capabilities'] == sorted(INTENTS)
        assert media['avatar']['request_duration_s'] > 0 and media['n_frames'] > 0
        assert media['codec'] == 'jpeg'  # fallback video still delivered
        if standby:
            assert media['video_frames'] == len(media['video_frame_indices']) < media['n_frames']
        else:
            assert 'video_frames' not in media and 'video_frame_indices' not in media


def test_mesh_trace_server_video_is_explicitly_labeled_fallback(tmp_path):
    from fastapi.testclient import TestClient
    from test_backend_api import backend

    directory = tmp_path / 'logs'
    directory.mkdir()
    event = {'type': 'audit', 'data': {'where': 'session_start', 'session_id': 'sess-mesh',
             'mode': 'private', 'student_id': 'demo', 'renderer': 'mesh', 'avatar_model': MODEL}}
    (directory / 'sess-mesh.jsonl').write_text(json.dumps(event) + '\n')
    (directory / 'sess-mesh.mp4').write_bytes(b'video')
    (directory / 'sess-mesh.generated.mp4').write_bytes(b'video')
    with TestClient(backend(tmp_path)) as client:
        videos = client.get('/api/traces?student=demo').json()['sessions'][0]['videos']
        assert len(videos) == 2
        assert {video['label'] for video in videos} == {'presented', 'generated'}
        assert all(video['visual_source'] == 'server_video_fallback' for video in videos)


def test_compiled_mesh_point_uses_finger_phrase_and_detects_point_without_changing_legacy():
    from live_agent.backend.avatar import configure_manifest
    from live_agent.generator.puppet import BROWSER_POINT_PHRASE, PuppetGenerator
    from live_agent.prompt.h3_compiler import compile_prompt
    from test_teacher_persona import _director, _ask

    reply = {'relation': 'new', 'kind': 'action', 'steps': [{'intent': 'point_board', 'line': ''}]}
    mesh, _, mesh_manifest = _director(reply)
    legacy, _, legacy_manifest = _director(reply)
    original = legacy_manifest.by_intent('point_board')
    configure_manifest(mesh_manifest)
    adapted = mesh_manifest.by_intent('point_board')
    assert adapted.cap_id == original.cap_id and adapted.check_question == original.check_question
    assert adapted.phrase == BROWSER_POINT_PHRASE and 'index finger' in adapted.phrase
    assert 'pointer' not in adapted.phrase
    assert 'wooden pointer' in original.phrase
    _ask(mesh, '指一下黑板')
    _ask(legacy, '指一下黑板')
    mesh_script, legacy_script = mesh.next_script(0), legacy.next_script(0)
    assert mesh_script.action == BROWSER_POINT_PHRASE
    assert legacy_script.action == original.phrase
    generator = PuppetGenerator(capabilities=[(cap.phrase, cap.intent) for cap in legacy_manifest.caps.values()])
    # The shared puppet generator was created from the original manifest. It must
    # recognize the session-only browser phrase without mutating legacy controls.
    compiled = compile_prompt(mesh_script, first_request=True)
    assert BROWSER_POINT_PHRASE in compiled
    assert generator.detect_animation(compiled) == 'point'
    assert generator.detect_animation(compile_prompt(legacy_script, first_request=True)) == 'point'

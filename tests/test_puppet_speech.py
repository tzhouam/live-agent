"""Speech timing preserves PCM and schedules from the duration the viewer receives."""
import asyncio
import numpy as np
import pytest

from live_agent.generator.puppet import PuppetGenerator
from live_agent.prompt.h3_compiler import compile_prompt
from live_agent.timeline import LockScheduler, SchedulerConfig
from live_agent.tts import TTS_RATE
from live_agent.types import BlockScript, CanonProfile


def prompt(line="这句话需要完整地说完。"):
    return compile_prompt(BlockScript(request_index=0, plan_version=1,
        canon=CanonProfile(persona_id="teacher", subject="a teacher", scene="classroom",
                           camera="medium shot", voice="Mandarin"), action="", transcript=line))


@pytest.mark.parametrize("seconds,timing", [(0.8,"natural"), (7.3,"natural"), (7.3,"fixed")])
def test_complete_utterance_survives_short_and_long_request_timing(seconds,timing):
    # Distinct nonzero samples through the last word expose truncation or a gap
    # inserted between chunks; no network or audio provider is involved.
    source=np.linspace(-.35,.35,round(seconds*TTS_RATE),dtype=np.float32)
    class Voice:
        async def synthesize(self,text): return source.copy()
    async def check():
        generator=PuppetGenerator(tts=Voice(),size=(180,100),speech_timing=timing)
        await generator.start()
        try:
            await generator.submit(0,prompt())
            chunks=[]
            async for chunk in generator.chunks():
                chunks.append(chunk)
                if len(chunks)==4: break
            assert [chunk.chunk_index for chunk in chunks]==[0,1,2,3]
            audio=np.concatenate([chunk.audio[:,0] for chunk in chunks])
            assert np.array_equal(audio[:len(source)],source)
            assert len(audio)-len(source)>=round(.2*TTS_RATE)
            duration=sum(chunk.duration_s for chunk in chunks)
            assert chunks[0].meta['request_duration_s']==pytest.approx(duration)
            assert duration>=seconds+.2
            if seconds<1 and timing=="natural": assert duration<2
            for chunk in chunks:
                assert chunk.video.shape[0]==chunk.n_frames
                assert chunk.audio.shape[0]==int(chunk.n_frames/generator.info.fps*TTS_RATE)
        finally: await generator.close()
    asyncio.run(check())


def test_silent_fillers_keep_the_nominal_animation_layout():
    async def check():
        generator=PuppetGenerator(size=(180,100))
        await generator.start()
        try:
            await generator.submit(0,prompt(""))
            chunks=[]
            async for chunk in generator.chunks():
                chunks.append(chunk)
                if len(chunks)==4: break
            assert [chunk.n_frames for chunk in chunks]==[39,34,34,17]
            assert not any(np.any(chunk.audio) for chunk in chunks)
        finally: await generator.close()
    asyncio.run(check())


def test_scheduler_uses_actual_previous_duration_for_lock_and_repair_planning():
    scheduler=LockScheduler(SchedulerConfig(lambda_prior_s=1,sigma_s=.25))
    scheduler.on_presented(0,100)
    scheduler.on_duration(0,2)
    assert scheduler.lock_time(1)==pytest.approx(100.75)
    assert scheduler.planned_lock(1)==pytest.approx(100.75)
    scheduler.on_duration(0,7.5)
    assert scheduler.lock_time(1)==pytest.approx(106.25)
    assert scheduler.planned_lock(1)==pytest.approx(106.25)


@pytest.mark.parametrize('duration',[2.0,7.5])
def test_full_duration_is_available_before_the_first_chunk_is_forwarded(duration):
    from types import SimpleNamespace
    from live_agent.types import Chunk
    import test_pipeline as pipeline

    async def check():
        orchestrator,_=pipeline.build(max_requests=1)
        async def chunks():
            # Deliberately never deliver the final chunk: scheduling must know
            # the full duration while the first chunk is being sent.
            yield Chunk(0,0,12,24,meta={'request_duration_s':duration})
        async def send(chunk,script):
            assert orchestrator.sched.durations[0]==pytest.approx(duration*orchestrator.sched.cfg.time_scale)
        orchestrator.gen=SimpleNamespace(chunks=chunks,timings=[],info=orchestrator.gen.info)
        orchestrator.transport=SimpleNamespace(send_chunk=send)
        orchestrator.scripts[0]=SimpleNamespace(transcript='')
        await orchestrator._chunk_loop()
        assert len(orchestrator.chunks[0])==1
    asyncio.run(check())

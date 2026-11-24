"""A ready figure must reach an already visible board without waiting for a new clip."""
import asyncio
import hashlib
import json

import pytest

from fastapi.testclient import TestClient

from live_agent.backend.config import parse_args
from live_agent.backend.app import build_app
from live_agent.backend.transport import panel_event
from live_agent.lesson import Board, LessonPlanner, set_figure
from live_agent.llm import ScriptedLLM
from live_agent.timeline import EventLog
from live_agent.types import EventType, Utterance, now
import test_pipeline as pipeline


def test_plot_ready_event_contains_served_image_and_escaped_caption(tmp_path):
    orchestrator,_=pipeline.build(max_requests=1)
    orchestrator.figure_dir=tmp_path
    orchestrator.log=EventLog()
    figure=set_figure(Board("lesson:one","曲线",["要点"]),
                       {"plot":{"functions":["x**2"],"x":[-2,2]},"caption":"图<script>"})
    asyncio.run(orchestrator._make_plot(figure))
    event=next(event for event in orchestrator.log.events if event.type==EventType.LESSON)
    packet=panel_event(event,0)
    assert packet['data']['board']=='lesson:one'
    assert packet['data']['figure']=={'url':figure.url,'caption':'图&lt;script&gt;'}
    assert (tmp_path/figure.url.rsplit('/',1)[1]).is_file()


def test_exact_diagram_ready_does_not_depend_on_a_remote_ocr_call(tmp_path):
    orchestrator,_=pipeline.build(max_requests=1)
    orchestrator.log=EventLog()
    class Maker:
        exact_labels=True
        out_dir=tmp_path
        async def make(self,prompt,seed=42): return '/board/img/d0123456789abcde.png'
    class Judge:
        @property
        def vlm(self): return object()  # any attempted OCR with this object fails
    orchestrator.image_maker=Maker()
    orchestrator.judge=Judge()
    figure=set_figure(Board('diagram-board','流程',['光合作用']),{'prompt':'标注「阳光」','caption':'叶片'})
    asyncio.run(orchestrator._make_figure(figure))
    packet=panel_event(orchestrator.log.events[-1],0)
    assert packet['data']['stage']=='figure' and packet['data']['kind']=='diagram'
    assert packet['data']['figure']['url']==figure.url


def test_diagram_resource_is_served_without_allowing_path_traversal(tmp_path,monkeypatch):
    from live_agent.backend import resources
    from PIL import Image
    name='d0123456789abcde.png'
    Image.new('RGB',(32,24),'white').save(tmp_path/name)
    monkeypatch.setattr(resources,'BOARD_IMAGES',tmp_path)
    args=parse_args(['--generator','mock','--llm-url','scripted','--asr-url','','--vlm-url','mock',
                    '--memory-db','','--student-store',str(tmp_path/'students'),'--log-dir',str(tmp_path/'logs')])
    with TestClient(build_app(args)) as client:
        response=client.get('/board/img/'+name)
        assert response.status_code==200 and response.headers['content-type']=='image/png'
        assert response.headers['cache-control']=='no-store'
        assert client.get('/board/img/d../secret.png').status_code==404


def test_lesson_section_keys_are_unique_even_when_the_topic_repeats():
    def reply(messages):
        if '课程大纲' in messages[-1]['content']:
            return json.dumps({'title':'同一课','sections':[{'title':'第一节','goal':'解释'}],'intro':['开始。']})
        return json.dumps({'board':{'title':'第一节'},'points':[{'text':'要点','lines':['这是解释。']}]})
    async def check():
        planner=LessonPlanner(ScriptedLLM(reply),name='林老师',bio='')
        a=await planner.outline('同一课'); b=await planner.outline('同一课')
        first=await planner.section(a,0,[]); second=await planner.section(b,0,[])
        assert first[0].board.key!=second[0].board.key
        assert first[0].board.figures==second[0].board.figures==[]
        assert planner.intro_lines(a)[0].board.key!=planner.intro_lines(b)[0].board.key
    asyncio.run(check())


def test_ordinary_knowledge_answer_automatically_generates_a_browsable_visual_collection(tmp_path):
    def reply(messages):
        prompt=messages[-1]['content']
        if '教学设计专家' in prompt:
            assert prompt.count('叶片利用阳光制造养分。')==1
            return json.dumps({'points':[{'i':i,'need':True,'complexity':1,
                'figure':{'prompt':f'植物关系图{i}','caption':f'图{i}<说明>'}} for i in range(3)]})
        return json.dumps({'kind':'content','relation':'chat','steps':[{'line':'叶片利用阳光制造养分。'}],
                           'board':{'title':'植物营养','items':['原料','能量来源','产物']}})
    class Maker:
        exact_labels=True
        out_dir=tmp_path
        def __init__(self):self.prompts=[]
        async def make(self,prompt,seed=42):
            self.prompts.append(prompt)
            return '/board/img/d'+hashlib.sha256(prompt.encode()).hexdigest()[:15]+'.png'
    async def check():
        orchestrator,_=pipeline.build(max_requests=1)
        orchestrator.director.llm=ScriptedLLM(reply)
        orchestrator.answer_boards=True
        orchestrator.image_maker=maker=Maker()
        await orchestrator.on_user_utterance(Utterance('u','user','植物如何获得营养？',now()))
        while orchestrator._aux:
            await asyncio.gather(*list(orchestrator._aux))
        segments=list(orchestrator.director.queue)
        board=next(s.board for s in segments if s.board is not None)
        assert all(s.reveal is None for s in segments)  # never invent sentence-to-point alignment
        assert len(maker.prompts)==3
        view=board.view(None)
        assert len(view['figures'])==3 and view['figure']['url']==view['figures'][0]['url']
        assert [f['point'] for f in view['figures']]==[None,1,2]
        assert view['figures'][0]['caption']=='图0&lt;说明&gt;'
        events=[panel_event(event,0) for event in orchestrator.log.events
                if event.type==EventType.LESSON and event.data.get('stage')=='figure']
        assert len(events)==3 and all(event['data']['board']==board.key for event in events)
        await orchestrator._judge_answer_figures(board,['叶片利用阳光制造养分。'])
        assert len(maker.prompts)==3  # unchanged clips never replan the same board
    asyncio.run(check())


def test_answer_visual_planning_preserves_an_existing_overview_and_deduplicates_content(tmp_path):
    board=Board('answer-one','关系',['甲','乙','丙'])
    original=set_figure(board,{'prompt':'现有概览','caption':'概览'})
    original.url='/board/img/d000000000000000.png'
    calls=[]
    def reply(messages):
        calls.append(messages)
        return json.dumps({'points':[
            {'i':0,'need':True,'figure':{'prompt':'现有概览'}},
            {'i':1,'need':True,'figure':{'prompt':'新示意图','caption':'第二点'}}]})
    class Maker:
        exact_labels=True
        out_dir=tmp_path
        async def make(self,prompt,seed=42):return '/board/img/d000000000000001.png'
    async def check():
        orchestrator,_=pipeline.build(max_requests=1)
        orchestrator.director.llm=ScriptedLLM(reply)
        orchestrator.image_maker=Maker()
        await asyncio.gather(orchestrator._judge_answer_figures(board,['整段讲解']),
                             orchestrator._judge_answer_figures(board,['整段讲解']))
        while orchestrator._aux:await asyncio.gather(*list(orchestrator._aux))
        assert len(calls)==1 and board.figures[0] is original
        assert len(board.figures)==2 and board.figures[1].point==1
        assert board.view(None)['figure']['url']==original.url
        assert len(board.view(None)['figures'])==2
    asyncio.run(check())


def test_answer_board_keys_are_unique_across_director_sessions():
    a,_=pipeline.build();b,_=pipeline.build()
    assert a.director.answer_board({'title':'题目','items':['要点']}).key!=b.director.answer_board({'title':'题目','items':['要点']}).key


@pytest.mark.parametrize('location',('caption','prompt','plot'))
def test_erasure_cancels_late_images_and_removes_board_only_content_from_script_snapshots(tmp_path,location):
    from live_agent.director.director import Segment
    from live_agent.memory_bridge import MemoryBridge
    from live_agent.types import BlockScript

    async def check():
        orchestrator,_=pipeline.build()
        orchestrator.memory=MemoryBridge(str(tmp_path/'memory.sqlite'),user_id='u',stream_id='s',
                                          session_id='erasure-images',mode='private')
        board=Board('private-board','普通标题',['普通要点'])
        spec={'prompt':'画一个普通关系图','caption':'普通图注'}
        if location=='plot':spec['plot']={'functions':['x'],'title':'私人<标记>'}
        else:spec[location]='私人<标记>'
        figure=set_figure(board,spec)
        figure.url='/board/img/d000000000000010.png'
        clean=Board('clean-board','保留内容',['公开的知识'])
        original=BlockScript(0,1,orchestrator.director.ledger.canon,'','这是一句普通讲解。',
                             board=board.view(None))
        unaffected=BlockScript(1,1,orchestrator.director.ledger.canon,'','保留这句讲解。',
                               board=clean.view(None))
        orchestrator.scripts={0:original,1:unaffected}
        orchestrator.director.queue.append(Segment(None,1,line='这是一句普通讲解。',board=board))
        started,cancelled=asyncio.Event(),asyncio.Event()
        class Maker:
            exact_labels=True
            out_dir=tmp_path
            async def make(self,prompt,seed=42):
                started.set()
                try:await asyncio.Event().wait()
                finally:cancelled.set()
        late=set_figure(board,{'prompt':'绘制第二点','caption':'未完成图片'},point=0)
        orchestrator.image_maker=Maker()
        orchestrator.director.pending_figures.append(late)
        orchestrator._make_figures()
        await asyncio.wait_for(started.wait(),1)
        orchestrator._answer_figure_boards.add(board.key)
        assert await orchestrator._erase('私人<标记>')
        assert cancelled.is_set() and not late.url and not orchestrator._aux
        assert original.board is None and unaffected.board==clean.view(None)
        assert not orchestrator._answer_figure_boards and not orchestrator.director.pending_figures
        next_script=orchestrator.director.next_script(2)
        assert next_script.transcript=='这是一句普通讲解。' and next_script.board is None
        assert not any(event.type==EventType.LESSON and event.data.get('stage')=='figure'
                       for event in orchestrator.log.events)
        orchestrator.memory.store.close()
    asyncio.run(check())

"""Teaching review must affect presentation without rewriting user intent or learner facts."""
import asyncio
import json
import pytest
import test_director
import test_pipeline
from live_agent.llm import ScriptedLLM
from live_agent.teaching_quality import RUBRIC, review_material
from live_agent.lesson import Board, LessonLine, Outline


def verdict(passed=True, critical=False):
    scores = {key: 2 for key in RUBRIC}
    if not passed: scores['reasoning'] = 0
    return {'scores': scores, 'evidence': {key: '第一条讲稿给出了依据与对应例子。' for key in RUBRIC},
            'problems': [] if passed else ['只有结论，没有说明原因。'], 'fix': '展开一个具体例子说明原因。',
            'critical_errors': ['计算结果错误。'] if critical else []}


DRAFT = {'relation':'chat','kind':'content','memory_note':None,
         'board':{'title':'分数','items':['同分母相加']},'steps':[{'intent':'','line':'分母不变，分子相加。'}]}
REPAIR = {'steps':[{'intent':'drink_tea','line':'每一份的大小没变，只是份数增加。'}],
          'board':{'title':'分数','items':['每份大小不变，份数相加']},'memory_note':'用户已掌握分数','profile_update':{'grade':'大学'}}


def answer(responses):
    director = test_director.make(replies=responses)
    director.teaching_review = True
    result = test_director.say(director,'为什么同分母分数相加，分母不变？')
    return director, result


def test_weak_answer_is_rewritten_and_reviewed_before_it_is_queued():
    director, result = answer([DRAFT,verdict(False),REPAIR,verdict()])
    assert result['_teaching_quality']['status'] == 'revised_passed'
    assert len(result['_teaching_quality']['reviews']) == 2
    assert result['memory_note'] is None and 'profile_update' not in result
    assert not any(segment.intent for segment in director.queue)
    assert all('分子相加' not in segment.line for segment in director.queue)
    assert any('每一份' in segment.line for segment in director.queue)


def test_failed_rewrite_never_queues_known_weak_material():
    director,result = answer([DRAFT,verdict(False),REPAIR,verdict(False)])
    assert result['_teaching_quality']['status'] == 'held' and result['board'] is None
    assert all('分母不变' not in segment.line and '每一份' not in segment.line for segment in director.queue)


def test_actions_bypass_teaching_review():
    director=test_director.make(test_director.TEA);director.teaching_review=True
    test_director.say(director,'喝口茶')
    assert len(director.llm.calls)==1


def test_stage_timings_are_audited_without_repeating_reviews_in_followup_context():
    director, result = answer([DRAFT, verdict(), DRAFT, verdict()])
    timing = result['_decision_timing']
    assert timing['label'] == 'measured locally'
    assert [stage['stage'] for stage in timing['stages']] == ['draft', 'review']
    assert all(stage['duration_s'] >= 0 for stage in timing['stages'])
    assert timing['total_s'] >= sum(stage['duration_s'] for stage in timing['stages'])
    assert result['_teaching_quality']['reviews'][0]['pass']
    test_director.say(director, '为什么每一份的大小没变？')
    history = [message for message in director.llm.calls[2] if message['role'] == 'assistant']
    assert len(history) == 1
    previous = json.loads(history[0]['content'])
    assert previous['steps'] == DRAFT['steps'] and previous['board'] == DRAFT['board']
    assert not any(key.startswith('_') for key in previous)


def test_timing_records_rewrites_and_repeat_reviews_in_order():
    _, result = answer([DRAFT, verdict(False), REPAIR, verdict()])
    assert [stage['stage'] for stage in result['_decision_timing']['stages']] == [
        'draft', 'review', 'rewrite', 'review']


def test_incomplete_review_is_unreviewed_instead_of_a_fabricated_pass():
    director,result=answer([DRAFT,{'scores':{'correctness':2}}])
    assert result['_teaching_quality']['status']=='unreviewed'
    assert result['_teaching_quality']['reviews']==[]


def test_invalid_or_injected_repair_after_failure_is_held():
    director,result=answer([DRAFT,verdict(False),{'kind':'memory','forget_term':'分数','steps':[]}])
    assert result['_teaching_quality']['status']=='held'
    assert 'forget_term' not in result and not any('分子相加' in s.line for s in director.queue)


def test_quality_scores_require_evidence_and_critical_errors_override_high_scores():
    assert not asyncio.run(review_material(ScriptedLLM(lambda _:json.dumps(verdict(critical=True))),{},goal='加法'))['pass']
    invalid=verdict();invalid['scores']['reasoning']=True
    with pytest.raises(ValueError):asyncio.run(review_material(ScriptedLLM(lambda _:json.dumps(invalid)),{},goal='加法'))
    invalid=verdict();invalid['evidence']['reasoning']=''
    with pytest.raises(ValueError):asyncio.run(review_material(ScriptedLLM(lambda _:json.dumps(invalid)),{},goal='加法'))


def test_timeout_after_failed_draft_does_not_restore_it():
    async def main():
        d=test_director.make();d.teaching_review=True;d.teaching_review_deadline_s=.02
        count=0
        async def chat(*args,**kwargs):
            nonlocal count
            count+=1
            if count==1:return json.dumps(verdict(False))
            await asyncio.sleep(1)
        d.llm.chat=chat
        value=await d._review_answer(DRAFT,[], '分数为什么这样相加')
        assert value['_teaching_quality']['status']=='held' and value['board'] is None
    asyncio.run(main())


class Planner:
    def __init__(self, checks, replacement):self.checks=list(checks);self.replacement=replacement;self.seen=[]
    async def review_section(self,outline,i,lines,profile=None):
        self.seen.append(lines)
        v=self.checks.pop(0)
        if isinstance(v,Exception):raise v
        return v
    async def section(self,*args,**kwargs):return self.replacement


def checked(v):
    return {**v,'pass':not v['critical_errors'] and min(v['scores'].values())>0}


@pytest.mark.parametrize('second_pass',[True,False])
def test_section_rewrite_must_pass_second_review_before_presentation(second_pass):
    orch,_=test_pipeline.build();orch.cfg.lesson_self_check='revise'
    original=[LessonLine('只有一个结论。',Board('b','加法',['结论']),0)]
    replacement=[LessonLine('一个苹果加两个苹果，共三个苹果。',Board('b','加法',['算例']),0)]
    outline=Outline(title='加法',sections=[{'title':'算例','depth':'new'}],intro=[])
    planner=Planner([checked(verdict(False)),checked(verdict(second_pass))],replacement)
    result=asyncio.run(orch._revise_section(planner,outline,0,[],original))
    assert result==(replacement if second_pass else [])
    assert planner.seen==[original,replacement]


def test_failed_section_review_does_not_present_unreviewed_content():
    orch,_=test_pipeline.build();orch.cfg.lesson_self_check='revise'
    outline=Outline(title='加法',sections=[{'title':'算例'}],intro=[])
    planner=Planner([RuntimeError('judge unavailable')],[])
    assert asyncio.run(orch._revise_section(planner,outline,0,[],[LessonLine('结论',None,None)]))==[]


@pytest.mark.parametrize('passed',[True,False])
def test_first_lesson_section_is_reviewed_before_it_can_enter_backlog(passed):
    orch,_=test_pipeline.build();orch.cfg.lesson_self_check='revise'
    def generate(messages):
        if messages[0]['role']=='system':
            payload=json.loads(messages[-1]['content'])
            return json.dumps(verdict(True if 'outline' in payload.get('material',{}) else passed))
        prompt=messages[-1]['content']
        if '课程大纲' in prompt:return json.dumps({'title':'加法','sections':[{'title':'算例','goal':'理解加法','depth':'new'}],'intro':['今天讲加法。']})
        return json.dumps({'board':{'title':'算例'},'points':[{'text':'合并数量','lines':['一个苹果加两个苹果，共三个苹果。']}],'summary':['相加就是合并数量。']})
    orch.director.llm=ScriptedLLM(generate)
    async def main():
        await orch._lesson_loop('加法')
        await asyncio.sleep(0)
        if orch._aux:await asyncio.gather(*list(orch._aux))
    asyncio.run(main())
    stages=[e.data.get('stage') for e in orch.log.events]
    assert 'check' in stages
    if passed:
        assert stages.index('check')<stages.index('section')
        assert any('苹果' in s.line for s in orch.director.lesson_backlog)
    else:
        assert 'section' not in stages and 'quality_hold' in stages
        assert not any('苹果' in s.line for s in orch.director.lesson_backlog)


def test_exact_fraction_checks_catch_spoken_counterexample_and_reversed_figure_label():
    from live_agent.teaching_quality import arithmetic_errors
    question='为什么五分之二加五分之一，分母不变？'
    material={'steps':[{'line':'如果分母也相加，就变成八分之三了。'}],
              'board':{'figure':{'prompt':'标注「共三分之五」。'}}}
    errors=arithmetic_errors(material,question)
    assert any('错误示范' in error for error in errors) and any('图注' in error for error in errors)
    material['steps'][0]['line']='如果分母也相加，就变成十分之三了。'
    material['board']['figure']['prompt']='标注「共五分之三」。'
    assert not arithmetic_errors(material,question)
    assert arithmetic_errors({'board':{'items':[r'$\frac{2}{5}+\frac{1}{5}=\frac{3}{10}$']}},'分数加法')


def test_editorial_pass_cannot_override_exact_arithmetic_error():
    v=asyncio.run(review_material(ScriptedLLM(lambda _:json.dumps(verdict())),
        {'board':{'items':[r'$\frac{2}{5}+\frac{1}{5}=\frac{3}{10}$']}},goal='分数加法'))
    assert not v['pass'] and v['scores']['correctness']==0 and v['critical_errors']


def test_held_answer_does_not_trigger_an_unreviewed_board_fallback():
    orch,_=test_pipeline.build();orch.answer_boards=True
    orch.director.teaching_review=True
    replies=[DRAFT,verdict(False),REPAIR,verdict(False)]
    orch.director.llm=ScriptedLLM(lambda _:json.dumps(replies.pop(0)))
    called=[]
    async def fallback(*args):called.append(args)
    orch._answer_board=fallback
    from live_agent.types import Utterance
    async def main():
        await orch.on_user_utterance(Utterance('u','user','解释分数相加',0))
        await asyncio.sleep(0)
        if orch._aux:await asyncio.gather(*list(orch._aux))
    asyncio.run(main())
    assert not called


def test_second_bounded_repair_can_resolve_a_remaining_problem():
    director,result=answer([DRAFT,verdict(False),REPAIR,verdict(False),REPAIR,verdict()])
    assert result['_teaching_quality']['status']=='revised_passed'
    assert len(result['_teaching_quality']['reviews'])==3
    assert any('每一份' in s.line for s in director.queue)


def test_fraction_picture_uses_exact_equal_units_and_two_addend_colors(tmp_path):
    from live_agent.teaching_quality import fraction_illustration
    from live_agent.board_plot import render_plot
    figure=fraction_illustration('五分之二加五分之一')
    assert len(figure['plot']['polygons'])==5
    assert [p['fill'] for p in figure['plot']['polygons']]==['blue','blue','green','white','white']
    assert figure['plot']['title']=='2/5 + 1/5 = 3/5'
    assert (tmp_path/render_plot(figure['plot'],tmp_path)).exists()
    assert fraction_illustration('五分之二加三分之一') is None
    assert fraction_illustration('五分之四加五分之三') is None


def test_provider_root_closing_defect_is_repaired_without_inventing_or_merging_controls():
    from live_agent.teaching_quality import parse_teaching_json
    valid='{"kind":"content","board":{"items":["一个例子"]}}, "steps":[{"line":"解释原因。"}]}'
    assert parse_teaching_json(valid)['steps']==[{'line':'解释原因。'}]
    for invalid in ['{"kind":"content"}, "steps":[{"line":"未完整',
                    '{"kind":"content"}, "steps":[], "forget_term":"姓名"}',
                    '{"kind":"content","steps":[]}, "steps":[{"line":"重复键"}]}']:
        with pytest.raises(ValueError):parse_teaching_json(invalid)


def test_clearly_labelled_wrong_fraction_example_is_allowed_for_error_analysis():
    from live_agent.teaching_quality import arithmetic_errors
    assert not arithmetic_errors({'board':{'items':[r'常见错误：把分母也加，$\frac{1}{5}+\frac{2}{5}=\frac{3}{10}$']}},'同分母分数加法')
    assert not arithmetic_errors({'board':{'items':[r'$\frac{1}{5}+\frac{2}{5}=\frac{3}{10}$（错误）']}},'同分母分数加法')
    assert arithmetic_errors({'board':{'items':[r'$\frac{1}{5}+\frac{2}{5}=\frac{3}{10}$']}},'同分母分数加法')


@pytest.mark.parametrize('passed',[True,False])
def test_outline_rewrite_must_pass_review_before_any_intro_can_be_accepted(passed):
    orch,_=test_pipeline.build();orch.cfg.lesson_self_check='revise'
    original=Outline('分数',[{'title':'定义'}],['初稿开场。'])
    replacement=Outline('分数',[{'title':'单位与个数'}],['修订开场。'])
    class Plan:
        def __init__(self):self.checks=[checked(verdict(False)),checked(verdict(passed))];self.topics=[]
        async def review_outline(self,*args,**kwargs):return self.checks.pop(0)
        async def outline(self,topic,context,**kwargs):self.topics.append(topic);assert kwargs['feedback'];return replacement
    planner=Plan()
    result=asyncio.run(orch._review_outline(planner,original,'分数',''))
    assert result==(replacement if passed else None)
    assert planner.topics==['分数']
    assert not orch.director.lesson_backlog


def test_section_review_is_scoped_to_its_goal_instead_of_whole_course_requirements():
    from live_agent.lesson import LessonPlanner
    llm=ScriptedLLM(lambda _:json.dumps(verdict()))
    planner=LessonPlanner(llm,name='林老师',bio='')
    outline=Outline('同分母分数加法',[{'title':'分数意义','goal':'回顾分子与分母的意义','depth':'review'}],[],difficulty='加法算理')
    asyncio.run(planner.review_section(outline,0,[LessonLine('分母表示整体被平均分成几份。',Board('b','意义',['分子与分母']),0)]))
    payload=json.loads(llm.calls[0][-1]['content'])
    assert '回顾分子与分母的意义' in payload['goal'] and '同分母分数加法' not in payload['goal']
    assert '不要求前置/复习小节讲完后续主课' in payload['guidance']

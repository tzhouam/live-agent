"""Real-browser student UI checks against isolated CPU services, never the user's profiles.

Usage: python3 scripts/student_frontend_check.py [--shots DIRECTORY]
Mock sessions verify transport/UX. Explicit synthetic lesson events verify rendering only.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def event_fixture(page, event, **data):
    """Deliver a synthetic wire event through both real browser event handlers."""
    page.evaluate("packet=>onMessage({data:JSON.stringify({type:'event',t:0,request:0,...packet})})", {'event': event, 'data': data})


def lesson_fixture(page, **data):
    event_fixture(page, 'lesson', **data)


def exercise_snapshot_fixture(page, exercise):
    page.evaluate("exercise=>onMessage({data:JSON.stringify({type:'state',exercise,erasure_gate_open:true,chains:[]})})", exercise)


def question_fixture(owner, label):
    return {'request_id': owner, 'concept': label, 'kind': 'choice', 'question': label + ' question',
            'options': ['A', 'B'], 'option_texts': ['A. ' + label + ' first', 'B. ' + label + ' second']}


def assert_question(page, owner, label):
    assert page.locator('#exerciseCard').is_visible()
    assert label + ' question' in page.locator('#exerciseQuestion').inner_text()
    assert label + ' second' in page.locator('#exerciseAnnouncement').text_content()
    assert page.locator('#chips .answer').count() == 3
    assert page.evaluate('currentExercise?.request_id ?? null') == owner
    assert page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', owner)


def open_question_fixture(page, owner, label):
    assert page.evaluate('owner=>sendText("Controlled lesson activity", undefined, owner)', owner)
    assert page.evaluate('window.__requestIds.at(-1)') == owner
    assert page.evaluate('window.__submissions.at(-1).activity') is True
    lesson_fixture(page, stage='exercise_open', **question_fixture(owner, label))
    assert_question(page, owner, label)


def ordinary_fixture(page, text):
    previous = page.evaluate('window.__requestIds.at(-1)')
    page.locator('#text').fill(text)
    page.locator('#text').press('Enter')
    owner = page.evaluate('window.__requestIds.at(-1)')
    assert isinstance(owner, str) and owner and owner != previous
    assert page.evaluate('window.__submissions.at(-1).activity') is False
    return owner


def activity_owner_checks(page, results):
    """Controlled wire outcomes: real input IDs, rendering and ownership; no model qualification."""
    old_owner = 'fixture-replacement-B'
    open_question_fixture(page, old_owner, 'Old lesson B')
    new_owner = ordinary_fixture(page, '给我上一节新主题的课')
    assert_question(page, old_owner, 'Old lesson B')
    assert not page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', new_owner)
    # Ordering captured from actual Orchestrator/Director and LessonPlanner with
    # controlled is_answer:false and kind:lesson replies: applied C decision,
    # C outline/section/planned, late B close, then C's newly posed question.
    event_fixture(page, 'utterance_end', request_id=new_owner, speaker='user', text='给我上一节新主题的课')
    event_fixture(page, 'utterance_end', request_id=new_owner, applied=True,
                  decision={'kind': 'lesson', 'topic': 'Replacement C'})
    assert_question(page, old_owner, 'Old lesson B')
    lesson_fixture(page, request_id=new_owner, stage='outline', title='Replacement C outline',
                   sections=['Replacement C section'])
    assert 'Replacement C outline' in page.locator('#lessonStatus').inner_text()
    assert page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', new_owner)
    assert not page.locator('#exerciseCard').is_visible()
    assert not page.locator('#chips .answer').count()
    lesson_fixture(page, request_id=new_owner, stage='section', title='Replacement C section', section=0)
    lesson_fixture(page, request_id=new_owner, stage='planned', title='Replacement C outline')
    prepared = page.locator('#lessonStatus').inner_text()
    lesson_fixture(page, request_id=old_owner, stage='exercise_closed')
    assert page.locator('#lessonStatus').inner_text() == prepared
    lesson_fixture(page, stage='exercise_open', **question_fixture(new_owner, 'Replacement C'))
    assert_question(page, new_owner, 'Replacement C')
    lesson_fixture(page, stage='exercise_open', **question_fixture(old_owner, 'Stale old B'))
    exercise_snapshot_fixture(page, question_fixture(old_owner, 'Stale old B'))
    assert_question(page, new_owner, 'Replacement C')
    results.append({'manual lesson replacement': 'actual backend ordering adopts ordinary C plan and question; late B close/open/state cannot overwrite C'})

    answer_owner = ordinary_fixture(page, 'B')
    assert_question(page, new_owner, 'Replacement C')
    lesson_fixture(page, request_id=new_owner, stage='exercise_graded', correct=True)
    lesson_fixture(page, request_id=new_owner, stage='exercise_closed')
    event_fixture(page, 'utterance_end', request_id=answer_owner, applied=True,
                  decision={'kind': 'chat', 'exercise_result': {'correct': True}})
    assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
    assert page.locator('#exerciseCard').is_visible()
    assert not page.locator('#chips .answer').count()
    assert page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', new_owner)
    answer_status = page.locator('#lessonStatus').inner_text()
    lesson_fixture(page, request_id=answer_owner, stage='outline', title='Retired answer outline')
    lesson_fixture(page, stage='exercise_open', **question_fixture(answer_owner, 'Retired answer'))
    exercise_snapshot_fixture(page, question_fixture(answer_owner, 'Retired answer'))
    assert page.locator('#lessonStatus').inner_text() == answer_status
    assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
    assert not page.locator('#chips .answer').count()
    results.append({'answer creator': 'ordinary answer ID retains creator grading/closure and feedback; its terminal decision cannot revive an activity'})

    old_owner = 'fixture-newer-candidate-B'
    open_question_fixture(page, old_owner, 'Shown B')
    retired_owner = ordinary_fixture(page, 'Older ordinary C')
    newest_owner = ordinary_fixture(page, 'Newer ordinary D')
    assert retired_owner != newest_owner
    event_fixture(page, 'utterance_end', request_id=retired_owner, applied=False, decision={'kind': 'lesson', 'topic': 'Old C'})
    event_fixture(page, 'utterance_end', request_id=retired_owner, applied=True, decision={'kind': 'chat'})
    lesson_fixture(page, request_id=retired_owner, stage='outline', title='Old C outline')
    lesson_fixture(page, stage='exercise_open', **question_fixture(retired_owner, 'Old C'))
    exercise_snapshot_fixture(page, question_fixture(retired_owner, 'Old C'))
    assert_question(page, old_owner, 'Shown B')
    lesson_fixture(page, request_id=newest_owner, stage='outline', title='Current D outline')
    assert 'Current D outline' in page.locator('#lessonStatus').inner_text()
    lesson_fixture(page, stage='exercise_open', **question_fixture(newest_owner, 'Current D'))
    assert_question(page, newest_owner, 'Current D')
    results.append({'newer candidate': 'newer ordinary D survives old C terminal outcomes and rejects old C activity events/snapshot'})

    decision_outcomes = {
        'not_applied': {'applied': False, 'decision': {'kind': 'lesson', 'topic': 'Superseded C'}},
        'nonactivity': {'applied': True, 'decision': {'kind': 'chat'}},
        'null_not_applied': {'applied': False, 'decision': None},
        'false_not_applied': {'applied': False, 'decision': False},
        'missing_not_applied': {'applied': False},
        'null_applied': {'applied': True, 'decision': None},
        'false_applied': {'applied': True, 'decision': False},
    }
    for terminal in (*decision_outcomes, 'outline_failed', 'exercise_failed'):
        old_owner = 'fixture-terminal-B-' + terminal
        open_question_fixture(page, old_owner, 'Terminal B ' + terminal)
        failed_owner = ordinary_fixture(page, 'Candidate C ' + terminal)
        if terminal in decision_outcomes:
            event_fixture(page, 'utterance_end', request_id=failed_owner, **decision_outcomes[terminal])
            assert_question(page, old_owner, 'Terminal B ' + terminal)
        else:
            lesson_fixture(page, request_id=failed_owner, stage=terminal, error='Controlled activity failure')
            assert not page.locator('#exerciseCard').is_visible()
            assert not page.locator('#chips .answer').count()
            assert page.evaluate('currentExercise===null')
        terminal_status = page.locator('#lessonStatus').inner_text()
        terminal_question = page.locator('#exerciseQuestion').inner_text()
        lesson_fixture(page, request_id=failed_owner, stage='outline', title='Terminal C revival')
        lesson_fixture(page, stage='exercise_open', **question_fixture(failed_owner, 'Terminal C revival'))
        exercise_snapshot_fixture(page, question_fixture(failed_owner, 'Terminal C revival'))
        assert page.locator('#lessonStatus').inner_text() == terminal_status
        assert page.locator('#exerciseQuestion').inner_text() == terminal_question
        assert not page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', failed_owner)
        if terminal in decision_outcomes:
            assert_question(page, old_owner, 'Terminal B ' + terminal)
        else:
            assert not page.locator('#exerciseCard').is_visible()
            assert not page.locator('#chips .answer').count()
        results.append({'terminal candidate': terminal, 'outcome': 'late correlated outline/open/snapshot cannot revive the retired C'})

    for creator_kind in ('known', 'legacy_null'):
        old_owner = 'fixture-existing-B-' + creator_kind
        open_question_fixture(page, old_owner, 'Visible B ' + creator_kind)
        input_owner = ordinary_fixture(page, 'New lesson while B waits ' + creator_kind)
        creator = old_owner if creator_kind == 'known' else None
        existing = question_fixture(input_owner, 'Authoritative B ' + creator_kind)
        lesson_fixture(page, stage='exercise_existing', exercise_request_id=creator, **existing)
        assert_question(page, creator, 'Authoritative B ' + creator_kind)
        # Existing-question resolution arrives before the final decision on the
        # backend path that blocks a new lesson with a standalone question.
        event_fixture(page, 'utterance_end', request_id=input_owner, applied=True,
                      decision={'kind': 'lesson', 'topic': 'Blocked new lesson'})
        lesson_fixture(page, stage='exercise_existing', exercise_request_id=creator,
                       **question_fixture(input_owner, 'Consumed C recovery'))
        lesson_fixture(page, request_id=input_owner, stage='outline', title='Consumed C outline')
        exercise_snapshot_fixture(page, question_fixture(input_owner, 'Consumed C snapshot'))
        assert_question(page, creator, 'Authoritative B ' + creator_kind)
        answer_owner = ordinary_fixture(page, 'B')
        assert_question(page, creator, 'Authoritative B ' + creator_kind)
        lesson_fixture(page, request_id=creator, stage='exercise_graded', correct=True)
        lesson_fixture(page, request_id=creator, stage='exercise_closed')
        event_fixture(page, 'utterance_end', request_id=answer_owner, applied=True,
                      decision={'kind': 'chat', 'exercise_result': {'correct': True}})
        assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
        assert not page.locator('#chips .answer').count()
        results.append({'visible question recovery': creator_kind, 'outcome': 'latest ordinary C recovers existing creator before its decision; candidate is consumed and creator-owned answer feedback persists'})

    old_owner = 'fixture-snapshot-B'
    open_question_fixture(page, old_owner, 'Snapshot old B')
    snapshot_owner = ordinary_fixture(page, 'New activity C with only a state snapshot')
    exercise_snapshot_fixture(page, question_fixture(snapshot_owner, 'Snapshot C'))
    assert_question(page, snapshot_owner, 'Snapshot C')
    lesson_fixture(page, request_id=old_owner, stage='exercise_closed')
    assert_question(page, snapshot_owner, 'Snapshot C')
    lesson_fixture(page, request_id=snapshot_owner, stage='exercise_closed')
    results.append({'actual snapshot adoption': 'nonnull latest ordinary C question is adopted; old B closure cannot clear it'})

    for action in ('practice', 'startLesson'):
        page.locator('#' + action).click()
        owner = page.evaluate('window.__requestIds.at(-1)')
        waiting_status = page.locator('#lessonStatus').inner_text()
        assert page.locator('#startLesson').is_disabled()
        assert page.locator('#practice').is_disabled()
        for correlation in ({'request_id': 'UNRELATED-OLD-ERROR'}, {'request_id': None}, {}):
            event_fixture(page, 'error', where='lesson', error='Delayed unrelated failure', **correlation)
            assert page.locator('#lessonStatus').inner_text() == waiting_status
            assert page.locator('#startLesson').is_disabled()
            assert page.locator('#practice').is_disabled()
            assert page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', owner)
        event_fixture(page, 'error', request_id=owner, where='lesson', error='Matching activity failure')
        assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
        assert not page.locator('#startLesson').is_disabled()
        assert not page.locator('#practice').is_disabled()
        failed_status = page.locator('#lessonStatus').inner_text()
        event_fixture(page, 'utterance_end', request_id=owner, applied=True,
                      decision={'kind': 'exercise' if action == 'practice' else 'lesson', 'topic': 'Late failed activity'})
        lesson_fixture(page, request_id=owner, stage='outline', title='Failed activity revival')
        lesson_fixture(page, stage='exercise_open', **question_fixture(owner, 'Failed activity revival'))
        exercise_snapshot_fixture(page, question_fixture(owner, 'Failed activity revival'))
        assert page.locator('#lessonStatus').inner_text() == failed_status
        assert not page.locator('#exerciseCard').is_visible()
        assert not page.locator('#chips .answer').count()
        page.locator('#practice').click()
        next_owner = page.evaluate('window.__requestIds.at(-1)')
        assert next_owner != owner
        next_status = page.locator('#lessonStatus').inner_text()
        event_fixture(page, 'error', request_id=owner, where='lesson', error='Delayed failed activity error')
        assert page.locator('#lessonStatus').inner_text() == next_status
        lesson_fixture(page, stage='exercise_open', **question_fixture(next_owner, 'Retry after ' + action))
        assert_question(page, next_owner, 'Retry after ' + action)
        lesson_fixture(page, request_id=next_owner, stage='exercise_closed')
        results.append({'correlated activity error': action, 'outcome': 'unrelated/null/missing IDs leave B waiting; matching error resolves B, rejects late B activity, and permits a successful retry'})

    for action, terminal in (('practice', 'null_not_applied'), ('startLesson', 'false_not_applied'),
                             ('practice', 'missing_not_applied'), ('startLesson', 'null_applied')):
        page.locator('#' + action).click()
        owner = page.evaluate('window.__requestIds.at(-1)')
        assert page.locator('#startLesson').is_disabled()
        assert page.locator('#practice').is_disabled()
        event_fixture(page, 'utterance_end', request_id=owner, **decision_outcomes[terminal])
        status = page.locator('#lessonStatus').inner_text()
        assert ('replaced by a newer action' if decision_outcomes[terminal]['applied'] is False else 'did not start') in status
        assert not page.locator('#startLesson').is_disabled()
        assert not page.locator('#practice').is_disabled()
        lesson_fixture(page, request_id=owner, stage='outline', title='Falsy pending revival')
        lesson_fixture(page, stage='exercise_open', **question_fixture(owner, 'Falsy pending revival'))
        exercise_snapshot_fixture(page, question_fixture(owner, 'Falsy pending revival'))
        assert page.locator('#lessonStatus').inner_text() == status
        assert not page.locator('#exerciseCard').is_visible()
        assert not page.locator('#chips .answer').count()
        assert not page.evaluate('owner=>LiveAgentProduct.acceptsActivity(owner)', owner)
        results.append({'falsy pending decision': terminal, 'action': action,
                        'outcome': 'matching terminal outcome unlocks both buttons with truthful status and rejects late activity/snapshot'})


def recoverable_input_checks(page, results):
    """Synthetic failure packets use the real media/product handlers on the connected CPU socket."""
    def fail(owner, code='response_failed', superseded=False):
        page.evaluate("packet=>onMessage({data:JSON.stringify({type:'input_error',recovered:!packet.superseded,...packet})})",
                      {'request_id': owner, 'code': code, 'superseded': superseded})

    page.locator('#startLesson').click()
    lesson_owner = page.evaluate('window.__requestIds.at(-1)')
    fail(lesson_owner)
    assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
    assert 'send your question again' in page.locator('#chat .msg.sys').last.inner_text()
    assert page.evaluate("sessionState === 'ready' && ws.readyState === 1")
    assert not page.locator('#text').is_disabled() and not page.locator('#startLesson').is_disabled()

    page.locator('#practice').click()
    practice_owner = page.evaluate('window.__requestIds.at(-1)')
    waiting_status, chat_count = page.locator('#lessonStatus').inner_text(), page.locator('#chat .msg').count()
    for owner, superseded in ((lesson_owner, False), (practice_owner, True), (None, False)):
        fail(owner, superseded=superseded)
        assert page.locator('#lessonStatus').inner_text() == waiting_status
        assert page.locator('#chat .msg').count() == chat_count
        assert page.locator('#practice').is_disabled()
    fail(practice_owner)
    assert 'practice question could not be prepared' in page.locator('#lessonStatus').inner_text()
    assert not page.locator('#practice').is_disabled()

    page.locator('#practice').click()
    question_owner = page.evaluate('window.__requestIds.at(-1)')
    lesson_fixture(page, stage='exercise_open', **question_fixture(question_owner, 'After input failure'))
    assert_question(page, question_owner, 'After input failure')
    page.locator('#text').fill('Answer that needs a retry')
    page.locator('#text').press('Enter')
    answer_owner = page.evaluate('window.__requestIds.at(-1)')
    fail(answer_owner, 'voice_empty')
    assert 'No speech was recognized' in page.locator('#chat .msg.sys').last.inner_text()
    assert_question(page, question_owner, 'After input failure')
    chat_count = page.locator('#chat .msg').count()
    page.evaluate("packet=>onMessage({data:JSON.stringify({type:'transcript',...packet})})",
                  {'request_id': lesson_owner, 'text': 'Obsolete voice transcript'})
    assert page.locator('#chat .msg').count() == chat_count
    page.locator('#chips .answer').first.click()
    lesson_fixture(page, request_id=question_owner, stage='exercise_graded', correct=True)
    assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
    lesson_fixture(page, request_id=question_owner, stage='exercise_closed')
    assert page.evaluate("sessionState === 'ready' && ws.readyState === 1")
    results.append({'recoverable input': 'matching failures release pending activities, old failures/transcripts are ignored, question survives failed answer and retry succeeds on the same socket'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shots', type=Path)
    args = parser.parse_args()
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='student-ui-') as directory:
        scratch = Path(directory)
        backend_port, front_port = port(), port()
        while backend_port == front_port:
            front_port = port()
        logs = [(scratch / name).open('w') for name in ('backend.log', 'frontend.log')]
        backend = subprocess.Popen(['python3', '-m', 'live_agent.backend.app', '--host', '127.0.0.1', '--port', str(backend_port), '--config', 'configs/persona_teacher', '--generator', 'mock', '--llm-url', 'scripted', '--vlm-url', 'mock', '--asr-url', '', '--memory-db', '', '--students', 'demo,learner', '--student-store', str(scratch / 'students'), '--log-dir', str(scratch / 'sessions'), '--dev-allow-uncalibrated'], cwd=ROOT, stdout=logs[0], stderr=subprocess.STDOUT)
        env = {**os.environ, 'HOST': '127.0.0.1', 'PORT': str(front_port), 'BACKEND_URL': f'http://127.0.0.1:{backend_port}'}
        frontend = subprocess.Popen(['node', 'frontend/server.mjs'], cwd=ROOT, env=env, stdout=logs[1], stderr=subprocess.STDOUT)
        origin = f'http://127.0.0.1:{front_port}'
        try:
            for _ in range(150):
                try:
                    with urlopen(origin + '/api/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(.1)
            else:
                raise AssertionError('isolated services did not start')
            with sync_playwright() as browser:
                chromium = browser.chromium.launch(headless=True)
                context = chromium.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                for edition in ('primary', 'secondary', 'university'):
                    for width in (1440, 390, 320):
                        page.set_viewport_size({'width': width, 'height': 1000 if width == 1440 else 844})
                        page.goto(origin + '/?edition=' + edition)
                        page.wait_for_function("!document.getElementById('connect').disabled")
                        page.wait_for_selector('.course-card')
                        assert page.locator('html').get_attribute('lang') == ('en' if edition == 'university' else 'zh-CN')
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (edition, width, 'horizontal overflow')
                        assert page.locator('#diagnostics').get_attribute('open') is None
                        for nav in ('Live classroom', 'Explore topics', 'Learning profile', 'Session recordings') if edition == 'university' else ('我的小课堂','找点新知识','我的学习卡','看看课堂记录') if edition == 'primary' else ('私人课堂','探索课程','学习档案','课堂记录'):
                            assert page.get_by_role('navigation').get_by_role('link', name=nav, exact=True).count() == 1
                        assert page.locator('#helpOpen').is_visible()
                        assert page.locator('#profileDisclaimer').inner_text()
                        assert page.locator('#runtimeNotice').is_visible()
                        page.locator('.course-card').first.click()
                        assert page.locator('#lessonTopic').input_value()
                        assert page.locator('#startLesson').is_disabled()
                        page.locator('#helpOpen').evaluate('(button)=>button.click()')
                        assert page.locator('#helpDialog').is_visible()
                        page.keyboard.press('Escape')
                        assert not page.locator('#helpDialog').is_visible()
                        if args.shots:
                            page.evaluate('scrollTo(0,0)')
                            page.screenshot(path=str(args.shots / f'classroom-{edition}-{width}.png'), full_page=True)
                            if width == 1440:
                                page.screenshot(path=str(args.shots / f'classroom-{edition}-preview.png'))
                        results.append({'edition': edition, 'width': width, 'layout': 'passed'})
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.goto(origin + '/?edition=secondary')
                page.wait_for_function("!document.getElementById('connect').disabled")
                page.locator('#notes').fill('Student A private note')
                page.locator('#sid').select_option('learner')
                assert page.locator('#notes').input_value() == ''
                page.locator('#notes').fill('Student B private note')
                page.locator('#sid').select_option('demo')
                assert page.locator('#notes').input_value() == 'Student A private note'
                page.reload()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert page.locator('#notes').input_value() == 'Student A private note'
                with page.expect_download() as exported:
                    page.locator('#exportNotes').click()
                assert Path(exported.value.path()).read_text() == 'Student A private note'
                page.evaluate("""() => {window.__originalStorageSet=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new Error('controlled storage failure');};}""")
                page.locator('#notes').fill('Unsaved fixture note')
                assert '失败' in page.locator('#noteStatus').inner_text()
                page.locator('#edition').select_option('university')
                assert 'Could not save' in page.locator('#noteStatus').inner_text()
                page.locator('#edition').select_option('secondary')
                assert '失败' in page.locator('#noteStatus').inner_text()
                page.evaluate('() => {Storage.prototype.setItem=window.__originalStorageSet;}')
                page.locator('#notes').fill('Student A private note')
                results.append({'notes': 'persist, isolate and export passed'})
                page.locator('#edition').select_option('university')
                assert 'Example profile' in page.locator('#sid').inner_text()
                assert page.locator('html').get_attribute('lang') == 'en'
                assert 'edition=university' in page.locator('#profLink').get_attribute('href')
                page.reload()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert page.locator('#edition').input_value() == 'university'
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'", timeout=15000)
                assert page.locator('#talk').is_disabled()
                assert page.locator('#startLesson').is_disabled()
                assert 'Video preview' in page.locator('#runtimeNotice').inner_text()
                assert 'cannot create lessons' in page.locator('#runtimeNotice').inner_text()
                page.locator('#text').fill('请讲慢一点')
                page.locator('#text').press('Enter')
                assert page.locator('#chat .msg.user').last.inner_text() == '请讲慢一点'
                page.wait_for_function('queue.length > 0', timeout=15000)
                dimensions = page.locator('#screen').bounding_box()
                ratio = page.evaluate('canvas.width/canvas.height')
                assert abs(dimensions['width']/dimensions['height'] - ratio) < .01
                # Synthetic capability fixtures verify UI gating and the actual outgoing text contract only.
                # Real CPU transport was checked above. Keep unrelated preview snapshots
                # from replacing the controlled activity fixtures below.
                page.evaluate("""() => {ws.onmessage=null;window.__sentTexts=[];window.__lessonContexts=[];window.__requestIds=[];window.__submissions=[];window.addEventListener('live-agent:submitted',event=>window.__submissions.push(event.detail));const original=ws.send.bind(ws);ws.send=data=>{try{const packet=JSON.parse(data);if(packet.type==='text'){window.__sentTexts.push(packet.text);window.__requestIds.push(packet.request_id);if(packet.lesson_context)window.__lessonContexts.push(packet.lesson_context);return;}}catch{};original(data);};window.LiveAgentProduct.sessionChanged('ready',{status:{generator:'mock',responder:'llm',board:true}});}""")
                assert 'cannot create lessons' not in page.locator('#runtimeNotice').inner_text()
                page.locator('#gradeFilter').select_option('3')
                page.locator('#subjectFilter').select_option('数学')
                page.locator('.course-card').first.click()
                page.locator('#startLesson').click()
                assert '小学三年级数学' in page.evaluate('window.__sentTexts.at(-1)')
                assert page.evaluate('window.__lessonContexts.at(-1).grade')==3
                assert page.evaluate('window.__lessonContexts.at(-1).subject')=='数学'
                assert page.evaluate('window.__lessonContexts.at(-1).topic')==page.locator('#lessonTopic').input_value()
                assert page.locator('#startLesson').is_disabled()
                assert page.locator('#practice').is_disabled()
                lesson_fixture(page, request_id=page.evaluate('window.__requestIds.at(-1)'), stage='outline', title='Catalogue lesson fixture')
                page.locator('#practice').click()
                assert '小学三年级数学' in page.evaluate('window.__sentTexts.at(-1)')
                assert page.evaluate('window.__lessonContexts.at(-1).grade')==3
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:'UNRELATED-OLD-TURN',decision:{kind:'chat'}}}}))")
                assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),decision:{kind:'chat'}}}}))")
                assert 'did not start' in page.locator('#lessonStatus').inner_text()
                # A rejected activity clears its owner. Legacy no-ID events must
                # remain retired even when the current owner becomes null again.
                legacy_status = page.locator('#lessonStatus').inner_text()
                lesson_fixture(page, stage='outline', title='LEGACY AFTER REJECTED INPUT')
                lesson_fixture(page, stage='exercise_open', question='LEGACY AFTER REJECTED INPUT', options=['A'], option_texts=['A. Stale answer'])
                exercise_snapshot_fixture(page, {'question':'LEGACY AFTER REJECTED INPUT','options':['A'],'option_texts':['A. Stale answer']})
                assert page.locator('#lessonStatus').inner_text() == legacy_status
                assert not page.locator('#exerciseCard').is_visible()
                assert not page.locator('#chips .answer').count()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__requestIds.at(-1),stage:'exercise_failed'}}}))")
                assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
                # B is being prepared, with its open packet deliberately held.
                # A generated question alone must not unlock another activity C.
                page.locator('#practice').click()
                held_owner = page.evaluate('window.__requestIds.at(-1)')
                assert isinstance(held_owner, str) and held_owner
                assert page.evaluate('window.__submissions.at(-1).activity') is True
                assert page.locator('#startLesson').is_disabled()
                assert page.locator('#practice').is_disabled()
                page.evaluate("owner=>window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:owner,applied:true,decision:{kind:'exercise'}}}}))", held_owner)
                held_question = {'request_id':held_owner, 'stage':'exercise_open', 'concept':'Held practice B', 'kind':'choice', 'question':'Held B question', 'options':['A','B'], 'option_texts':['A. Held first answer','B. Held second answer']}
                sent_before_open = page.evaluate('window.__sentTexts.length')
                lesson_fixture(page, request_id=held_owner, stage='exercise', concept='Held practice B', exercise='Held B question')
                assert 'question is prepared' in page.locator('#lessonStatus').inner_text()
                assert not page.locator('#exerciseCard').is_visible()
                assert page.locator('#startLesson').is_disabled()
                assert page.locator('#practice').is_disabled()
                for button in ('#practice', '#startLesson'):
                    page.locator(button).evaluate('(button)=>{button.click();button.onclick?.();}')
                assert page.evaluate('window.__sentTexts.length') == sent_before_open
                lesson_fixture(page, **held_question)
                assert 'Held B question' in page.locator('#exerciseQuestion').inner_text()
                assert 'Held second answer' in page.locator('#exerciseAnnouncement').text_content()
                assert page.locator('#chips .answer').count() == 3
                assert page.locator('#startLesson').is_disabled()
                assert page.locator('#practice').is_disabled()
                lesson_fixture(page, request_id=held_owner, stage='exercise_closed')
                assert not page.locator('#practice').is_disabled()
                results.append({'activity preparation':'waiting and generated B keep both buttons locked until the held open packet arrives'})

                # A newer ordinary request C retires pending B; neither owned nor
                # legacy delayed packets may restore its question, choices or status.
                page.locator('#practice').click()
                retired_owner = page.evaluate('window.__requestIds.at(-1)')
                lesson_fixture(page, request_id=retired_owner, stage='exercise', concept='Retired B', exercise='Retired B question')
                page.locator('#text').fill('Newer ordinary C while B is pending')
                page.locator('#text').press('Enter')
                newer_owner = page.evaluate('window.__requestIds.at(-1)')
                assert isinstance(newer_owner, str) and newer_owner and newer_owner != retired_owner
                assert page.evaluate('window.__submissions.at(-1).activity') is False
                retired_status = page.locator('#lessonStatus').inner_text()
                assert 'replaced by a newer action' in retired_status
                for owner in (retired_owner, None):
                    late_question = {'stage':'exercise_open','question':'DELAYED RETIRED QUESTION','options':['A'],'option_texts':['A. DELAYED RETIRED CHOICE']}
                    if owner is not None:
                        late_question['request_id'] = owner
                    lesson_fixture(page, **({'request_id':owner} if owner is not None else {}), stage='outline', title='DELAYED RETIRED OUTLINE')
                    lesson_fixture(page, **late_question)
                    exercise_snapshot_fixture(page, late_question)
                    assert page.locator('#lessonStatus').inner_text() == retired_status
                    assert not page.locator('#exerciseCard').is_visible()
                    assert 'DELAYED' not in page.locator('#exerciseAnnouncement').text_content()
                    assert not page.locator('#chips .answer').count()

                # The server may already have opened B while its packet was held.
                # Only the correlated C recovery may restore B's creator identity.
                recovery = {'stage':'exercise_existing','exercise_request_id':retired_owner,'concept':'Recovered B','kind':'choice','question':'Server-owned B question','options':['A','B'],'option_texts':['A. Existing first answer','B. Existing second answer']}
                lesson_fixture(page, **{**recovery,'request_id':'UNRELATED-OLD-C'})
                assert not page.locator('#exerciseCard').is_visible()
                lesson_fixture(page, **{**recovery,'request_id':newer_owner})
                assert 'Server-owned B question' in page.locator('#exerciseQuestion').inner_text()
                assert page.locator('#chips .answer').count() == 3
                assert page.evaluate('currentExercise.request_id') == retired_owner
                assert page.locator('#practice').is_disabled()
                recovered_status = page.locator('#lessonStatus').inner_text()
                lesson_fixture(page, **{**recovery,'request_id':newer_owner,'question':'STALE SECOND C RECOVERY'})
                assert page.locator('#lessonStatus').inner_text() == recovered_status
                assert 'Server-owned B question' in page.locator('#exerciseQuestion').inner_text()
                assert 'STALE SECOND' not in page.locator('#exerciseAnnouncement').text_content()
                page.locator('#text').fill('An ordinary answer to restored B')
                page.locator('#text').press('Enter')
                answer_id = page.evaluate('window.__requestIds.at(-1)')
                assert isinstance(answer_id, str) and answer_id not in (retired_owner, newer_owner)
                assert page.evaluate('window.__submissions.at(-1).activity') is False
                assert page.evaluate('currentExercise.request_id') == retired_owner
                lesson_fixture(page, request_id=retired_owner, stage='exercise_graded', correct=True)
                assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
                lesson_fixture(page, request_id=retired_owner, stage='exercise_closed')
                assert 'question is closed' in page.locator('#lessonStatus').inner_text()
                assert not page.locator('#chips .answer').count()
                results.append({'activity retirement and recovery':'new ordinary IDs reject delayed owned/legacy events; correlated existing question restores creator-owned answers'})
                page.locator('#practice').click()
                page.evaluate("window.__oldActivity=window.__requestIds.at(-1);window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__oldActivity,applied:true,decision:{kind:'exercise'}}}}))" )
                assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
                page.evaluate("sendText('Newer ordinary question')")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__oldActivity,applied:true,decision:{kind:'exercise'}}}}))")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__oldActivity,stage:'exercise_open',question:'LATE OLD QUESTION'}}}))")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                assert 'LATE OLD QUESTION' not in page.locator('#exerciseQuestion').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__oldActivity,stage:'outline',title:'LATE OLD OUTLINE'}}}))")
                assert 'Waiting for the question' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),applied:false,decision:{kind:'exercise'}}}}))")
                assert 'replaced by a newer action' in page.locator('#lessonStatus').inner_text()
                page.locator('#lessonTopic').fill('Custom empty-topic fixture')
                page.locator('#startLesson').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'utterance_end',data:{request_id:window.__requestIds.at(-1),decision:{kind:'lesson',topic:''}}}}))")
                assert 'did not start' in page.locator('#lessonStatus').inner_text()
                page.locator('#startLesson').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__requestIds.at(-1),stage:'outline_failed'}}}))")
                assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
                page.evaluate("sendText('Ordinary text after failed outline')")
                assert 'could not be prepared' in page.locator('#lessonStatus').inner_text()
                page.locator('#practice').click()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__requestIds.at(-1),stage:'exercise_open',question:'Successful practice fixture'}}}))")
                assert 'question is ready' in page.locator('#lessonStatus').inner_text()
                page.evaluate("window.__answerOwner=window.__requestIds.at(-1);sendText('An ordinary answer to the current exercise')")
                assert page.evaluate('window.__requestIds.at(-1) !== window.__answerOwner && typeof window.__requestIds.at(-1) === "string"')
                assert page.evaluate('window.__submissions.at(-1).activity') is False
                assert page.locator('#exerciseCard').is_visible()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__answerOwner,stage:'exercise_graded',correct:true}}}))")
                assert 'marked this answer correct' in page.locator('#exerciseFeedback').inner_text()
                page.evaluate("window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{request_id:window.__answerOwner,stage:'exercise_closed'}}}))")
                assert 'question is closed' in page.locator('#lessonStatus').inner_text()
                results.append({'activity outcomes':'correlated decisions, empty-topic lesson, successful practice and failures resolve status'})
                activity_owner_checks(page, results)
                recoverable_input_checks(page, results)
                page.evaluate("LiveAgentProduct.sessionChanged('ready',{status:{generator:'taomate_h3',responder:'rules',board:true}})")
                assert 'Video preview' not in page.locator('#runtimeNotice').inner_text()
                assert page.locator('#startLesson').is_disabled()
                results.append({'capability fixtures':'video/responder independently gated; catalogue grade/subject preserved'})
                page.locator('#disconnect').click()
                page.wait_for_function("sessionState === 'disconnected'")
                results.append({'session': 'real CPU connect, text, media and disconnect passed'})
                # A changed learner must not inherit the previous classroom before connecting.
                assert page.locator('#chat .msg').count()
                page.evaluate("""() => {document.getElementById('boardTitle').textContent='LEARNER A BOARD';document.getElementById('memory').textContent='LEARNER A MEMORY';document.getElementById('feed').textContent='LEARNER A EVENTS';}""")
                page.locator('#sid').select_option('learner')
                assert not page.locator('#chat .msg').count()
                assert page.locator('#boardTitle').inner_text()==''
                assert page.locator('#memory').inner_text()==''
                assert page.locator('#feed').inner_text()==''
                assert page.locator('#lessonTopic').input_value()==''
                assert page.evaluate('lastBoard===null && onScreen===null')
                page.locator('#sid').select_option('demo')
                results.append({'learner boundary':'previous chat, media, board, memory and goal clear before reconnect'})
                # Synthetic events are deliberate rendering fixtures, not a generated teaching result.
                page.locator('#edition').select_option('secondary')
                page.evaluate("""() => {showExercise({concept:'Language fixture',kind:'mcq',question:'Which value?',options:['A','B'],option_texts:['A. One','B. Two']});window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'planned'}}}));}""")
                page.evaluate("""() => {window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_open',concept:'Fixture',question:'Which value?',options:['A','B'],option_texts:['A. One','B. Two']}}}));window.__exerciseAnnounced=document.getElementById('exerciseAnnouncement').textContent;window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_graded',correct:false}}}));window.dispatchEvent(new CustomEvent('live-agent:state',{detail:{exercise:null}}));}""")
                assert '有误' in page.locator('#exerciseFeedback').inner_text()
                page.locator('#edition').select_option('university')
                assert page.locator('#exerciseCard').is_visible()
                assert 'A. One' in page.locator('#exerciseQuestion').inner_text()
                assert 'incorrect' in page.locator('#exerciseFeedback').inner_text()
                assert 'feedback is ready' in page.locator('#lessonStatus').inner_text()
                assert 'Choose A' in page.locator('#chips').inner_text()
                page.evaluate('showExercise(null)')
                assert 'Which value?' in page.evaluate('window.__exerciseAnnounced')
                page.evaluate("""() => {window.dispatchEvent(new CustomEvent('live-agent:event',{detail:{event:'lesson',data:{stage:'exercise_open',question:'STALE AFTER ERROR'}}}));finishSession(ws,connectionAttempt,'error','连接发生错误，请重试。');}""")
                assert not page.locator('#exerciseCard').is_visible()
                assert page.locator('#exerciseAnnouncement').text_content()==''
                page.locator('#edition').select_option('secondary')
                page.locator('#edition').select_option('university')
                assert 'session stopped' in page.locator('#overlay').inner_text()
                assert 'session stopped' in page.locator('#connectionErrorText').inner_text()
                results.append({'exercise fixture': 'full question, choices, persistent feedback and active language switch passed'})
                # Abort pre-session profile loads on connecting; public status must be authoritative.
                held_profiles = []
                page.route('**/api/students/learner', lambda route: held_profiles.append(route))
                page.evaluate("""() => {const original=LiveAgentAPI.fetchJson;window.LiveAgentAPI={...LiveAgentAPI,fetchJson:async(...args)=>{try{return await original(...args);}finally{if(args[0]==='/api/students/learner')window.__lateProfileCompleted=true;}}};}""")
                page.locator('#sid').select_option('learner')
                page.wait_for_function('true')
                for _ in range(100):
                    if held_profiles:
                        break
                    page.wait_for_timeout(10)
                assert held_profiles, 'late profile fixture did not intercept the request'
                page.locator('#text').evaluate("node=>node.value='PRIVATE DRAFT'")
                page.evaluate("""() => {document.getElementById('caption').textContent='PRIVATE CAPTION';document.getElementById('boardTitle').textContent='PRIVATE BOARD';document.getElementById('memory').textContent='PRIVATE MEMORY';document.getElementById('lessonTopic').value='PRIVATE TOPIC';document.getElementById('exerciseAnnouncement').textContent='PRIVATE QUESTION';document.getElementById('stepPractice').classList.add('current');}""")
                page.locator('#diagnostics').evaluate('(node)=>node.open=true')
                page.locator('#mode').select_option('public')
                assert not page.locator('#profCard').is_visible()
                assert not page.locator('.student-picker').is_visible()
                assert not page.locator('#chat .msg').count()
                assert page.locator('#text').input_value()==''
                assert page.locator('#caption').inner_text()==''
                assert page.locator('#memory').inner_text()==''
                assert page.locator('#lessonTopic').input_value()==''
                assert page.locator('#exerciseAnnouncement').text_content()==''
                assert 'student=' not in page.url and 'mode=public' in page.url
                assert not page.locator('#profileNav').is_visible()
                assert page.locator('#stepPractice').get_attribute('class')!='current'
                assert 'A starting point' in page.locator('#suggestionLabel').inner_text()
                assert page.locator('#notes').input_value() == ''
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'", timeout=15000)
                held_profiles[0].fulfill(status=200, content_type='application/json', body=json.dumps({'id':'learner','name':'Delayed private name','grade':'初一','version':1,'exams':[],'concepts':[]}))
                page.wait_for_function('window.__lateProfileCompleted === true')
                page.wait_for_timeout(50)
                assert 'Delayed private name' not in page.locator('#prof').inner_text()
                assert page.evaluate('profile === null')
                assert page.locator('#uid').input_value()=='public-preview'
                assert 'student=' not in page.locator('#tracesNav').get_attribute('href')
                assert 'mode=public' in page.locator('#tracesNav').get_attribute('href')
                page.locator('#disconnect').click()
                page.reload()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert page.locator('#mode').input_value()=='public'
                assert not page.locator('#profCard').is_visible()
                results.append({'privacy': 'public classroom clears private data, identity, screen-reader question and survives reload'})
                assert not errors, errors
                # Service errors and retry use real page logic with a controlled HTTP failure.
                page.unroute('**/api/students/learner')
                page.route('**/api/health',lambda route:route.fulfill(status=503,content_type='text/plain',body='Unavailable'))
                page.goto(origin+'/?edition=university')
                page.wait_for_selector('#connectionError:not([hidden])')
                assert page.locator('#connect').is_disabled()
                assert 'not available' in page.locator('#connectionErrorText').inner_text()
                page.unroute('**/api/health')
                page.locator('#connectionRetry').click()
                page.wait_for_function("!document.getElementById('connect').disabled")
                assert not page.locator('#connectionError').is_visible()
                results.append({'recovery':'HTTP service failure and retry passed'})
                page.route('**/api/students',lambda route:route.fulfill(status=200,content_type='application/json',body='{"students":[]}'))
                page.goto(origin+'/?edition=university')
                page.wait_for_selector('#connectionError:not([hidden])')
                page.locator('#diagnostics').evaluate('(node)=>node.open=true')
                page.locator('#mode').select_option('public')
                assert not page.locator('#connect').is_disabled()
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'")
                page.locator('#disconnect').click()
                results.append({'public without profiles':'healthy public mode remains usable'})
                page.route('**/api/curriculum/topics',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps({'topics':[{'subject':'','grade':3,'topic':'INVALID EMPTY SUBJECT'},{'subject':'数学','grade':3,'topic':''},{'subject':'   ','grade':3,'topic':'INVALID BLANK SUBJECT'},{'subject':'数学','grade':3,'topic':'  Valid catalogue fixture  ','basis':'textbook'}]})))
                page.goto(origin+'/?edition=primary&mode=public')
                page.wait_for_selector('.course-card')
                assert page.locator('.course-card').count()==1
                page.locator('.course-card').click()
                assert page.locator('#lessonTopic').input_value()=='Valid catalogue fixture'
                page.locator('#connect').click()
                page.wait_for_function("sessionState === 'ready'")
                page.evaluate("() => {window.__paddedPackets=[];const original=ws.send.bind(ws);ws.send=data=>{const packet=JSON.parse(data);if(packet.type==='text'){window.__paddedPackets.push(packet);return;}original(data);};LiveAgentProduct.sessionChanged('ready',{status:{generator:'mock',responder:'llm',board:true}});}")
                page.locator('#startLesson').click()
                assert page.evaluate('window.__paddedPackets.at(-1).lesson_context.topic')=='Valid catalogue fixture'
                lesson_fixture(page, request_id=page.evaluate('window.__paddedPackets.at(-1).request_id'), stage='outline', title='Padded catalogue lesson fixture')
                page.locator('#practice').click()
                assert page.evaluate('window.__paddedPackets.at(-1).lesson_context.topic')=='Valid catalogue fixture'
                page.locator('#disconnect').click()
                results.append({'catalogue validation':'blank subjects/topics excluded; padded chapter keeps canonical lesson/practice context'})
                context.close()
                chromium.close()
        finally:
            for process in (frontend, backend):
                process.terminate()
            for process in (frontend, backend):
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            for log in logs:
                log.close()
    print(json.dumps({'measured_locally': results, 'page_errors': errors}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

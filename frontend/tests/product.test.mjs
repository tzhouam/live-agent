// product.js: the live edition (D-068) is a non-teaching live agent — classroom UI hidden,
// no catalogue/learner requests, connect works without learner profiles.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../public/assets/product.js', import.meta.url), 'utf8');

function page({ search = '' } = {}) {
  const elements = new Map(), selectors = new Map(), fetches = [], handlers = new Map();
  const storage = new Map();
  function element(id) {
    if (!elements.has(id)) {
      const node = { id, value: '', textContent: '', className: '', placeholder: '', href: '',
        hidden: false, disabled: false, dataset: {}, style: {},
        appendChild(child) { this.children.push(child); },
        append(...children) {
          this.children.push(...children);
          if (this.value === '' && children[0] && children[0].value) this.value = children[0].value; // select auto-selects
        },
        contains(child) { return this.children.includes(child); },
        replaceChildren() { this.children.length = 0; },
        addEventListener() {}, setAttribute(name, value) { this[name] = value; },
        getAttribute() { return null; }, focus() {}, scrollIntoView() {},
      };
      node.children = [];
      Object.defineProperty(node, 'options', { get() { return this.children; } });
      Object.defineProperty(node, 'innerHTML', { get() { return this.html || ''; }, set(value) { this.html = value; } });
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
  const selector = name => {
    if (!selectors.has(name)) selectors.set(name, element('sel:' + name));
    return selectors.get(name);
  };
  const document = {
    title: '', documentElement: { dataset: {}, lang: '' },
    getElementById: id => element(id),
    createElement: type => element(`created-${elements.size}-${type}`),
    querySelector: name => selector(name),
    querySelectorAll: () => [],
  };
  const api = {
    async fetchJson(path) {
      fetches.push(path);
      if (path === '/api/health') return { status: 'ok', generator: 'mock' };
      if (path === '/api/students') return { students: [{ id: 'demo', name: '示例', grade: 3, saved: false }] };
      if (path === '/api/students/demo') return { id: 'demo', name: '示例', grade: 3, version: 1 };
      if (path === '/api/curriculum/topics') return { topics: [] };
      throw new Error('unexpected fetch ' + path);
    },
  };
  const window = {
    location: { href: 'http://localhost/' + search, search },
    history: { replaceState() {} },
    localStorage: { getItem: key => storage.get(key) ?? null, setItem(key, value) { storage.set(key, value); } },
    LiveAgentAPI: api,
    addEventListener(type, handler) {
      handlers.set(type, [...(handlers.get(type) || []), handler]);
    },
    dispatchEvent(event) { for (const handler of handlers.get(event.type) || []) handler(event); },
  };
  const context = vm.createContext({ document, window, location: window.location, history: window.history,
    localStorage: window.localStorage, URL, URLSearchParams, AbortController,
    setTimeout(callback) { return callback; }, clearTimeout() {},
    console: { warn() {}, error() {} } });
  vm.runInContext(source, context);
  element('mode').append(element('modeOpt0'), element('modeOpt1'));
  element('mode').value = 'private';
  async function ready() {
    for (const handler of handlers.get('DOMContentLoaded') || []) handler();
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
  }
  const dispatch = (type, detail) => window.dispatchEvent({ type, detail });
  return { element, selector, fetches, storage, ready, dispatch };
}

test('the live edition hides classroom UI and requests no teaching endpoints', async () => {
  const p = page({ search: '?edition=live' });
  await p.ready();
  assert.equal(p.element('edition').value, 'live');
  assert.ok(p.element('courses').hidden, 'catalogue section hidden');
  assert.ok(p.selector('.lesson-card').hidden, 'lesson request card hidden');
  assert.ok(p.element('board').hidden && !p.element('board').classList.contains('on'), 'board hidden');
  assert.ok(p.element('profCard').hidden, 'learner profile card hidden');
  assert.deepEqual(p.fetches, ['/api/health'], 'no learner list and no catalogue request');
  assert.equal(p.element('connect').disabled, false, 'entering the live room needs no learner profile');
  assert.equal(p.element('connectionError').hidden, true);
  assert.equal(p.element('uid').value, 'live-guest', 'memory identifier defaults for a live guest');
  assert.equal(p.storage.get('liveAgent.edition'), 'live');
});

test('the live edition treats a boardless rules-responder status as normal', async () => {
  const p = page({ search: '?edition=live' });
  await p.ready();
  p.dispatch('live-agent:status', { board: false, responder: 'rules', generator: 'puppet' });
  assert.equal(p.element('runtimeNotice').textContent, '', 'no noTeacher / rulesLesson warning');
  assert.ok(p.element('startLesson').disabled && p.element('practice').disabled);
});

test('classroom editions keep the catalogue, board and learner flow', async () => {
  const p = page({ search: '?edition=secondary' });
  await p.ready();
  assert.ok(!p.element('courses').hidden && !p.selector('.lesson-card').hidden);
  assert.ok(!p.element('board').hidden && p.element('board').classList.contains('on'));
  assert.ok(p.fetches.includes('/api/students') && p.fetches.includes('/api/curriculum/topics'));
  assert.equal(p.element('uid').value, 'learner:demo');
});

test('switching editions hides and restores the classroom surface', async () => {
  const p = page({ search: '?edition=secondary' });
  await p.ready();
  p.element('edition').value = 'live';
  p.element('edition').onchange();
  assert.ok(p.element('courses').hidden && p.selector('.lesson-card').hidden && p.element('board').hidden);
  p.element('edition').value = 'secondary';
  p.element('edition').onchange();
  assert.ok(!p.element('courses').hidden && !p.selector('.lesson-card').hidden);
  assert.ok(!p.element('board').hidden && p.element('board').classList.contains('on'));
  assert.ok(!p.element('profCard').hidden, 'profile card restored (private mode)');
});

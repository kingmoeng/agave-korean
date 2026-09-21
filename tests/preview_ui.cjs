// Optional DOM logic check, not a browser/rasterizer test.
// npm install --prefix .cache/preview-check --no-save --no-package-lock linkedom@0.18.12
// node tests/preview_ui.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {parseHTML} = require('../.cache/preview-check/node_modules/linkedom');
const root = path.resolve(__dirname, '..');
const page = fs.readFileSync(path.join(root, 'preview/index.html'), 'utf8');

async function run(failFonts) {
  const {document, window} = parseHTML(page);
  // FontFaceSet/canvas require a real browser; simulate their success/failure only.
  const loads = [];
  Object.defineProperty(document, 'fonts', {value: {load: (font, sample) => {
    loads.push([font, sample]);
    return failFonts ? Promise.reject(new Error('simulated load failure')) : Promise.resolve([{}]);
  }}});
  const createElement = document.createElement.bind(document);
  document.createElement = tag => {
    const node = createElement(tag);
    if (tag === 'canvas') node.getContext = () => ({font: '', measureText: () => ({width: 16})});
    return node;
  };
  for (const [id,value] of [['size','16'],['weight','both']]) {
    Object.defineProperty(document.querySelector('#'+id), 'value', {value, writable:true});
  }
  let reloads = 0;
  vm.runInNewContext(document.querySelector('script').textContent, {document, location:{reload:()=>reloads++}, console});
  await new Promise(resolve => setImmediate(resolve));
  const cards = [...document.querySelectorAll('article')];
  const sections = [...document.querySelectorAll('article section')];
  assert(cards.length >= 1);
  assert.equal(sections.length, cards.length * 2);
  assert.equal(loads.length, sections.length);
  for (const section of sections) {
    assert.equal(section.dataset.loaded, String(!failFonts));
    assert.equal(section.querySelector('.status').classList.contains('error'), failFonts);
    const href = section.querySelector('a').getAttribute('href');
    const url = new URL(href, 'file://' + path.join(root, 'preview/index.html'));
    assert(fs.statSync(url.pathname).size > 0);
    assert.match(url.search, /\?v=[a-f0-9]{12}$/);
  }
  const change = (id,value) => {
    const node = document.querySelector('#'+id);
    node.value = value;
    node.dispatchEvent(new window.Event('change'));
  };
  change('size','12');
  assert.equal(document.documentElement.style.getPropertyValue('--size'),'12px');
  change('weight','bold');
  for (const section of sections) assert.equal(section.hidden, section.dataset.weight !== 'bold');
  change('weight','both');
  assert(sections.every(section => !section.hidden));
  const filter = document.querySelector('#filters input');
  filter.checked = false;
  filter.dispatchEvent(new window.Event('change'));
  assert(cards[0].classList.contains('hidden'));
  const custom = document.querySelector('#custom');
  custom.value = '<img src=x onerror=alert(1)> 한글';
  custom.dispatchEvent(new window.Event('input'));
  for (const sample of document.querySelectorAll('.custom-sample')) {
    assert.equal(sample.textContent, custom.value);
    assert.equal(sample.children.length, 0);
  }
  const guides = document.querySelector('#guides');
  guides.checked = false;
  guides.dispatchEvent(new window.Event('change'));
  assert(!document.querySelector('main').classList.contains('guided'));
  document.querySelector('#reload').dispatchEvent(new window.Event('click'));
  assert.equal(reloads,1);
  console.log(`PASS preview DOM (${failFonts ? 'font failure' : 'font success'} simulation): ${cards.length} sources, ${sections.length} weights, controls and local TTF links`);
}
run(false).then(()=>run(true)).catch(error=>{console.error(error);process.exitCode=1;});

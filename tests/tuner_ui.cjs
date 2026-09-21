// Optional DOM logic check for the scale tuner, not a browser/rasterizer test.
// npm install --prefix .cache/preview-check --no-save --no-package-lock linkedom@0.18.12
// node tests/tuner_ui.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {parseHTML} = require('../.cache/preview-check/node_modules/linkedom');
const root = path.resolve(__dirname, '..');
const page = fs.readFileSync(path.join(root, 'preview/tuner.html'), 'utf8');
const data = JSON.parse(page.match(/^const data = (.+);$/m)[1]);
const agave = data.agave.weights.regular;
const preset = data.sources[0].transform;
const box = 2 * agave.cell;

// Agave: 2048 upem, 1024 cell, M inked 64..960. Donor: full-width syllable inked .1..0.9em.
const INK = {
  latin: {width: 500, actualBoundingBoxLeft: -31.25, actualBoundingBoxRight: 468.75, actualBoundingBoxAscent: 625, actualBoundingBoxDescent: 0},
  korean: {width: 1000, actualBoundingBoxLeft: -100, actualBoundingBoxRight: 900, actualBoundingBoxAscent: 800, actualBoundingBoxDescent: 100},
};

const tick = () => new Promise(resolve => setImmediate(resolve));

function run(failFonts, token = 'test-token') {
  const {document, window} = parseHTML(page);
  const posts = [];
  const fetch = (url, options) => {
    const body = JSON.parse(options.body);
    posts.push([url, body]);
    const reply = url === '/apply'
      ? {ok: true, transform: {...preset, ...body.transform, scale_x: body.transform.scale ?? body.transform.scale_x,
                               scale_y: body.transform.scale ?? body.transform.scale_y}, previous: preset}
      : {ok: true, transform: preset, outputs: [{weight: 'regular', korean_characters: 11266, overhang_count: 0, vertical_bounds: [-544, 1568]}]};
    return Promise.resolve({ok: true, json: () => Promise.resolve(reply)});
  };
  // linkedom tracks neither <select> selection nor checkbox defaults; pin what a browser reports.
  for (const box of document.querySelectorAll('input[type=checkbox]')) box.checked = box.hasAttribute('checked');
  for (const [id, value] of [['source', data.sources[0].id], ['weight', 'regular'], ['size', '16']]) {
    Object.defineProperty(document.querySelector('#' + id), 'value', {value, writable: true});
  }
  const loads = [];
  Object.defineProperty(document, 'fonts', {value: {load: (font, sample) => {
    loads.push([font, sample]);
    return failFonts ? Promise.reject(new Error('simulated load failure')) : Promise.resolve([{}]);
  }}});
  window.Element.prototype.getBoundingClientRect = function () { return {top: 0, left: 0, width: 0, height: 0}; };
  const createElement = document.createElement.bind(document);
  document.createElement = tag => {
    const node = createElement(tag);
    if (tag === 'canvas') {
      const context = {font: '', measureText: text => INK[text === 'M' ? 'latin' : 'korean']};
      node.getContext = () => context;
    }
    return node;
  };
  const Option = function (text, value) {
    const node = createElement('option');
    node.textContent = text;
    node.setAttribute('value', value);
    return node;
  };
  const context = {document, window, Option, console, Promise, navigator: {}, localStorage: undefined,
                   URLSearchParams, fetch, location: {search: token ? `?token=${token}` : '', reload: () => {}}};
  vm.runInNewContext(document.querySelector('script').textContent, context);
  return new Promise(resolve => setImmediate(() => resolve({document, window, loads, posts}))); 
}

function control(document, window, id, value) {
  const node = document.querySelector('#' + id);
  if (node.getAttribute('type') === 'checkbox') node.checked = value;
  else node.value = value;
  node.dispatchEvent(new window.Event('input'));
  node.dispatchEvent(new window.Event('change'));
}

function slider(document, window, key, value) {
  const node = document.querySelector(`.slider[data-key="${key}"] input[type=number]`);
  node.value = String(value);
  node.dispatchEvent(new window.Event('input'));
}

async function main() {
  let {document, window, loads} = await run(false);
  assert.equal(loads.length, 2, 'both the Agave face and the donor face are loaded');
  assert.match(document.querySelector('#status').textContent, /로드 완료/);

  // Korean is the only thing that becomes a two-cell box; the rest stays Agave text.
  control(document, window, 'custom', '<img src=x onerror=alert(1)> 가A힣');
  let panes = [...document.querySelectorAll('.specimen')];
  assert.equal(panes.length, 2, 'preset pane and candidate pane');
  const cells = [...panes[1].querySelectorAll('.kr')];
  assert.deepEqual(cells.map(cell => cell.textContent), ['가', '힣']);
  assert.equal(panes[1].textContent, '<img src=x onerror=alert(1)> 가A힣');
  assert.equal(panes[1].querySelectorAll('img').length, 0);

  // A Korean cell is two Agave cells wide and the donor draws at scale x font-size.
  const style = key => panes[1].style.getPropertyValue(key);
  assert.equal(style('--cell2'), `${2 * agave.cell / agave.upem * 16}px`);
  assert.equal(style('--cell1'), `${agave.cell / agave.upem * 16}px`);
  assert.equal(style('--sy'), String(preset.scale_y));
  assert.equal(style('--dy'), `${-preset.y_offset / agave.upem * 16}px`);
  assert.equal(style('--kr-margin'), '-32px');
  assert.equal(panes[1].classList.contains('nonuniform'), false, 'a uniform scale needs no CSS transform');

  // Readout: the donor ink is .8em wide, so the pair of side gaps is box - .8 * upem * scale_x.
  const gap = box - 0.8 * agave.upem * preset.scale_x;
  const latinGap = agave.cell - (INK.latin.actualBoundingBoxRight + INK.latin.actualBoundingBoxLeft) / 1000 * agave.upem;
  const readout = [...document.querySelectorAll('#readout tr')].map(row => row.textContent);
  assert.match(readout[0], new RegExp(String(Math.round(gap))));
  assert.match(readout[1], new RegExp(String(Math.round(latinGap))));
  assert.match(readout[2], new RegExp(`${(gap / latinGap).toFixed(2)}×`), 'Korean sits far looser than Latin');

  // Fitting the Latin gap is the horizontal scale that leaves 128 units of side bearing.
  const fitted = Number(((box - latinGap) / (0.8 * agave.upem)).toFixed(4));
  document.querySelector('#fit').dispatchEvent(new window.Event('click'));
  assert.equal(document.querySelector('.slider[data-key="scale_x"] input[type=number]').value, String(fitted));
  panes = [...document.querySelectorAll('.specimen')];
  assert.equal(panes[1].classList.contains('nonuniform'), true, 'one axis moved, so the ratio is drawn');
  assert.match(document.querySelector('#json').textContent, new RegExp(`"scale_x": ${fitted}`));
  assert.match(document.querySelector('#json').textContent, new RegExp(`"scale_y": ${preset.scale_y}`));
  assert.match(document.querySelector('#cli').textContent, new RegExp(`--scale-x ${fitted} --scale-y ${preset.scale_y}`));
  assert.equal(document.querySelector('#verdict div').className, '', 'matching the Latin gap still fits the cell');
  assert.match([...document.querySelectorAll('#readout tr')][2].textContent, /1\.00×/);

  // Pushing both axes far enough must name the two ways it breaks, not just one.
  control(document, window, 'split', false);
  slider(document, window, 'scale', 1.3);
  const verdict = [...document.querySelectorAll('#verdict div')];
  assert.equal(verdict.length, 2);
  assert(verdict.every(note => note.className === 'bad'));
  assert.match(verdict[0].textContent, /두 칸 밖으로/);
  assert.match(verdict[1].textContent, /ascent/);

  // A uniform scale collapses back to one key, which is what the preset should carry.
  slider(document, window, 'scale', 0.95);
  assert.match(document.querySelector('#json').textContent, /"scale": 0\.95/);
  assert.equal(/scale_x/.test(document.querySelector('#json').textContent), false);
  assert.match(document.querySelector('#cli').textContent, new RegExp(`--scale 0.95 --x-offset ${preset.x_offset} --y-offset ${preset.y_offset}`));

  document.querySelector('#reset').dispatchEvent(new window.Event('click'));
  assert.equal(document.querySelector('.slider[data-key="scale"] input[type=number]').value, String(preset.scale));

  control(document, window, 'compare', false);
  assert.equal(document.querySelectorAll('.specimen').length, 1);
  control(document, window, 'size', '24');
  assert.equal(document.querySelector('.specimen').style.getPropertyValue('--cell2'), `${2 * agave.cell / agave.upem * 24}px`);

  // Saving writes the preset through the server that served this page, then the A side follows.
  let posts;
  ({document, window, posts} = await run(false));
  assert.equal(document.querySelector('#apply-panel').classList.contains('hidden'), false);
  assert.equal(document.querySelector('#build').disabled, false, 'nothing changed yet, so a build is honest');
  slider(document, window, 'scale', 0.923);
  assert(document.querySelector('#saved').classList.contains('dirty'));
  assert.equal(document.querySelector('#build').disabled, true, 'a build would not match the sliders');

  document.querySelector('#save').dispatchEvent(new window.Event('click'));
  await tick(); await tick();
  assert.deepEqual(posts.at(-1), ['/apply', {token: 'test-token', id: data.sources[0].id,
                                             transform: {scale: 0.923, x_offset: preset.x_offset, y_offset: preset.y_offset}}]);
  assert.equal(document.querySelector('#saved').classList.contains('dirty'), false);
  assert.match(document.querySelector('#saved').textContent, new RegExp(`sources/${data.sources[0].id}\\.json`));
  assert.equal(document.querySelector('#build').disabled, false);

  document.querySelector('#build').dispatchEvent(new window.Event('click'));
  await tick(); await tick();
  assert.deepEqual(posts.at(-1), ['/build', {token: 'test-token', id: data.sources[0].id}]);
  assert.match(document.querySelector('#log').textContent, /빌드 완료/);
  assert.match(document.querySelector('#log').textContent, /셀 이탈 0/);

  document.querySelector('#revert').dispatchEvent(new window.Event('click'));
  await tick(); await tick();
  assert.deepEqual(posts.at(-1)[1].transform, preset, 'revert puts the previous preset back');

  // A copied page has no server behind it, so it only offers the JSON block.
  ({document} = await run(false, null));
  assert(document.querySelector('#apply-panel').classList.contains('hidden'));
  assert.match(document.querySelector('#json').textContent, /"scale"/);

  ({document} = await run(true));
  assert(document.querySelector('#status').classList.contains('error'));
  assert.match(document.querySelector('#status').textContent, /로드 실패/);
  console.log('PASS tuner DOM: cell wrapping, CSS geometry, readout, fit, save/build/revert, static fallback, font-failure path');
}

main().catch(error => { console.error(error); process.exitCode = 1; });

const el = (id) => document.getElementById(id);
const statusEl = el('status');
const serverInfo = el('serverInfo');

const soulPath = el('soulPath');
const baseText = el('baseText');
const addendumText = el('addendumText');
const addendumTitle = el('addendumTitle');
const diffBox = el('diffBox');
const combinedBox = el('combinedBox');
const sealPath = el('sealPath');

const slidersEl = el('sliders');
const vowAlwaysEl = el('vowAlways');
const vowNeverEl = el('vowNever');
const vowAskFirstEl = el('vowAskFirst');
const essStressEl = el('essStress');
const essExcitedEl = el('essExcited');
const essGroupEl = el('essGroup');
const essHumorEl = el('essHumor');
const essBoundariesEl = el('essBoundaries');

function setStatus(ok, msg) {
  statusEl.textContent = msg;
  statusEl.classList.toggle('ok', ok);
  statusEl.classList.toggle('bad', !ok);
}

async function jpost(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const txt = await r.text();
  let data;
  try { data = JSON.parse(txt); } catch { throw new Error(`Bad JSON from ${path}: ${txt.slice(0, 200)}`); }
  if (!r.ok || data.ok === false) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

async function jget(path) {
  const r = await fetch(path, { cache: 'no-store' });
  const data = await r.json();
  if (!r.ok || data.ok === false) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

const AXES = [
  { key: 'warmth', label: 'Warmth', left: 'clinical', right: 'deeply warm' },
  { key: 'dry_humor', label: 'Dry humor', left: 'none', right: 'frequent' },
  { key: 'weirdness', label: 'Weirdness', left: 'grounded', right: 'surreal' },
  { key: 'verbosity', label: 'Verbosity', left: 'terse', right: 'expansive' },
  { key: 'directness', label: 'Directness', left: 'gentle', right: 'blunt' },
  { key: 'initiative', label: 'Initiative', left: 'waits', right: 'proactive' },
  { key: 'risk_tolerance', label: 'Risk tolerance', left: 'cautious', right: 'bold' },
  { key: 'playfulness', label: 'Playfulness', left: 'serious', right: 'playful' },
  { key: 'formality', label: 'Formality', left: 'casual', right: 'formal' },
  { key: 'boundary_strictness', label: 'Boundary strictness', left: 'flexible', right: 'strict' }
];

function renderSliders() {
  const frag = document.createDocumentFragment();

  for (const axis of AXES) {
    const wrap = document.createElement('div');
    wrap.className = 'sliderRow';

    const name = document.createElement('div');
    name.className = 'name';
    name.style.fontFamily = 'var(--mono)';
    name.style.fontSize = '11px';
    name.style.color = 'rgba(220,255,245,.80)';
    name.textContent = `${axis.label} (1=${axis.left} … 10=${axis.right})`;

    const range = document.createElement('input');
    range.type = 'range';
    range.min = '1';
    range.max = '10';
    range.step = '1';
    range.value = '5';
    range.id = `slider_${axis.key}`;

    const val = document.createElement('div');
    val.className = 'val';
    val.id = `sliderVal_${axis.key}`;
    val.textContent = `${range.value}/10`;

    range.addEventListener('input', () => { val.textContent = `${range.value}/10`; });

    const rule = document.createElement('input');
    rule.className = 'sliderRule';
    rule.id = `rule_${axis.key}`;
    rule.placeholder = 'One-sentence rule (optional)';

    // Layout: name spans full row on narrow screens.
    // On wide screens: name + slider + value, then rule spans full width.
    wrap.appendChild(name);
    wrap.appendChild(range);
    wrap.appendChild(val);

    const ruleRow = document.createElement('div');
    ruleRow.style.gridColumn = '1 / -1';
    ruleRow.appendChild(rule);

    const outer = document.createElement('div');
    outer.style.display = 'grid';
    outer.style.gap = '6px';
    outer.appendChild(wrap);
    outer.appendChild(ruleRow);

    frag.appendChild(outer);
  }

  slidersEl.innerHTML = '';
  slidersEl.appendChild(frag);
}

function linesToBullets(txt) {
  return (txt || '')
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function getRawInputs() {
  const sliders = AXES.map((a) => {
    const value = parseInt(el(`slider_${a.key}`).value, 10);
    const rule = (el(`rule_${a.key}`).value || '').trim();
    return { key: a.key, label: a.label, value, rule };
  });

  const vows = {
    always: linesToBullets(vowAlwaysEl.value),
    never: linesToBullets(vowNeverEl.value),
    ask_first: linesToBullets(vowAskFirstEl.value)
  };

  const essence = {
    stressed: (essStressEl.value || '').trim(),
    excited: (essExcitedEl.value || '').trim(),
    group_chat: (essGroupEl.value || '').trim(),
    humor: (essHumorEl.value || '').trim(),
    boundaries: (essBoundariesEl.value || '').trim()
  };

  return { sliders, vows, essence };
}

function generateAddendumMarkdown(title, raw) {
  const safeTitle = (title || '').trim() || 'Soul tuning addendum';

  const sliderBullets = raw.sliders.map((s) => {
    const base = `- ${s.label}: ${s.value}/10`;
    return s.rule ? `${base} — ${s.rule}` : base;
  });

  const alwaysBullets = raw.vows.always.map((s) => `- ${s}`);
  const neverBullets = raw.vows.never.map((s) => `- ${s}`);
  const askBullets = raw.vows.ask_first.map((s) => `- ${s}`);

  const defaultsExtra = [];
  if (raw.essence.humor) defaultsExtra.push(`- Humor notes: ${raw.essence.humor}`);

  const boundariesExtra = [];
  if (raw.essence.boundaries) boundariesExtra.push(`- Boundary notes: ${raw.essence.boundaries}`);

  const response = [];
  if (raw.essence.stressed) response.push(`- If user is stressed: ${raw.essence.stressed}`);
  if (raw.essence.excited) response.push(`- If user is excited: ${raw.essence.excited}`);
  if (raw.essence.group_chat) response.push(`- If in a group chat: ${raw.essence.group_chat}`);

  const parts = [];
  parts.push(`# ${safeTitle}`);
  parts.push('');

  parts.push('## Defaults');
  parts.push(...(sliderBullets.length ? sliderBullets : ['- (fill sliders above)']));
  if (alwaysBullets.length) {
    parts.push('');
    parts.push('### Always');
    parts.push(...alwaysBullets);
  }
  if (defaultsExtra.length) {
    parts.push('');
    parts.push(...defaultsExtra);
  }
  parts.push('');

  parts.push('## Boundaries');
  if (neverBullets.length) {
    parts.push('### Never');
    parts.push(...neverBullets);
  } else {
    parts.push('- (add Never vows)');
  }
  parts.push('');
  if (askBullets.length) {
    parts.push('### Ask first');
    parts.push(...askBullets);
  } else {
    parts.push('- (add Ask-first vows)');
  }
  if (boundariesExtra.length) {
    parts.push('');
    parts.push(...boundariesExtra);
  }
  parts.push('');

  parts.push('## Response patterns');
  parts.push(...(response.length ? response : ['- (fill essence prompts above)']));
  parts.push('');

  return parts.join('\n');
}

const TEMPLATE = `# Addendum (copy into standalone addendum file)\n\n## Defaults\n-\n\n## Boundaries\n-\n\n## Response patterns\n-\n`;

el('insertTemplate').addEventListener('click', () => {
  if (!addendumText.value.trim()) addendumText.value = TEMPLATE;
});

el('generateAddendum').addEventListener('click', () => {
  const raw = getRawInputs();
  addendumText.value = generateAddendumMarkdown(addendumTitle.value, raw);
});

el('loadBase').addEventListener('click', async () => {
  try {
    setStatus(true, 'loading…');
    const data = await jpost('/api/load', { soulPath: soulPath.value });
    baseText.value = data.baseText;
    serverInfo.textContent = data.serverInfo;
    setStatus(true, 'connected');
  } catch (e) {
    setStatus(false, `error: ${e.message}`);
  }
});

async function doPreview(apply) {
  const addText = addendumText.value;
  if (!addText.trim()) throw new Error('Addendum is empty');

  const body = {
    soulPath: soulPath.value,
    addendumText: addText,
    addendumTitle: addendumTitle.value,
    rawInputs: getRawInputs(),
    apply: !!apply
  };

  const data = await jpost(apply ? '/api/apply' : '/api/preview', body);
  baseText.value = data.baseText;
  diffBox.textContent = data.diffText || '(no diff)';
  combinedBox.textContent = data.combinedText;
  sealPath.textContent = data.sealPath;
  serverInfo.textContent = data.serverInfo;
}

el('preview').addEventListener('click', async () => {
  try {
    setStatus(true, 'previewing…');
    await doPreview(false);
    setStatus(true, 'preview ready');
  } catch (e) {
    setStatus(false, `error: ${e.message}`);
  }
});

el('apply').addEventListener('click', async () => {
  try {
    const ok = confirm('Apply will overwrite SOUL.md after creating a timestamped backup. Proceed?');
    if (!ok) return;
    setStatus(true, 'applying…');
    await doPreview(true);
    setStatus(true, 'applied');
  } catch (e) {
    setStatus(false, `error: ${e.message}`);
  }
});

(async function boot() {
  renderSliders();
  try {
    const health = await jget('/api/health');
    serverInfo.textContent = health.serverInfo;
    setStatus(true, 'connected');
  } catch {
    setStatus(false, 'disconnected');
  }
})();

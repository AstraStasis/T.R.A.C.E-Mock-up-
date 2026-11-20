const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

let state, experiments = [], experimentError = null;
let page = 'experiments', selectedExperiment = 4, model = '7476', tab = 'hardware', examples = false;
let selectedNodes = new Set(['N01', 'N02', 'N03', 'N04', 'N07']), map = {}, busy = false;
let logic = {a: 0, b: 0, j: 0, k: 0, q: 0};
// Procedure confirmations guide the student through the documented order of work.
// They are a teaching aid in this mock-up, not an electrical safety interlock.
let checks = {wiring: false, power: false}, checkKey = null;
const main = $('#main');

async function api(path, body) {
  const r = await fetch('/api/concept/' + path, {method: body === undefined ? 'GET' : 'POST', headers: {'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(8000)});
  const data = await r.json();
  if (!r.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Request rejected');
  return data;
}
function toast(s) { $('#toast').textContent = s; $('#toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('#toast').hidden = true, 4500); }
async function action(fn) { if (busy) return; busy = true; try { await fn(); } catch (e) { toast(e.message); } finally { busy = false; } }
function heading(k, t, d) { return `<div class="heading"><h1>${({experiments:'Experiments',monitor:'Breadboard monitor',virtual:'Virtual IC',connection:'Connection'})[page]}</h1></div>`; }
function modelData() { return state.models.find(m => m.id === model); }
function resetMap() { map = Object.fromEntries(modelData().signals.map(s => [s.name, s.node])); }
function navigate(p) {
  page = ['experiments', 'monitor', 'virtual', 'connection'].includes(p) ? p : 'experiments';
  location.hash = page;
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  render();
}
function render() {
  ({experiments: experimentView, monitor: monitorView, virtual: virtualView, connection: connectionView}[page])();
  main.dataset.page = page;
  if (page === 'monitor') {
    const profile = main.querySelectorAll(':scope > .panel')[1];
    if (profile) foldPanel(profile, 'Example settings');
  }
  if (page === 'virtual' && tab === 'hardware') {
    const table = main.querySelector('.split > .panel table');
    const rows = Array.from(table.tBodies[0].rows);
    const midpoint = Math.ceil(rows.length / 2);
    table.tHead.innerHTML = '<tr><th>Signal</th><th>Node group</th><th>State</th><th>Signal</th><th>Node group</th><th>State</th></tr>';
    rows.forEach(row => row.cells[1].remove());
    rows.slice(midpoint).forEach((row, index) => {
      while (row.firstChild) rows[index].appendChild(row.firstChild);
      row.remove();
    });
    const procedurePanel = main.querySelector('.procedure-panel');
    if (procedurePanel) foldPanel(procedurePanel, 'Session procedure');
    const wiringPanel = main.querySelector('#port-area')?.closest('.panel');
    if (wiringPanel) foldPanel(wiringPanel, 'Breadboard mapping');
  }
  if (page === 'connection') {
    const acknowledgement = main.querySelector(':scope > .panel');
    if (acknowledgement) foldPanel(acknowledgement, 'Command details');
  }
}

const expandedPanels = new Set();
function foldPanel(panel, title) {
  const details = document.createElement('details');
  details.className = 'optional-panel';
  const summary = document.createElement('summary');
  summary.textContent = title;
  panel.before(details);
  details.append(summary, panel);
  details.open = expandedPanels.has(title);
  details.addEventListener('toggle', () => {
    if (details.isConnected) details.open ? expandedPanels.add(title) : expandedPanels.delete(title);
  });
}

/* ---------------- Experiments ---------------- */

const positions = {1: [2, 2, 19, 15], 2: [22, 2, 14, 15], 3: [37, 2, 19, 15], 4: [57, 2, 19, 15], 5: [77, 2, 21, 15], 6: [77, 18, 21, 39], 7: [77, 58, 21, 7], 8: [88, 66, 10, 32], 9: [77, 66, 10, 32], 10: [62, 66, 14, 32], 11: [52, 66, 9, 32], 12: [37, 66, 14, 32], 13: [22, 64, 14, 34], 14: [2, 18, 19, 25], 15: [2, 44, 19, 54]};
const statusText = {complete: 'Complete', partial: 'Partial · from sketches', awaiting: 'Awaiting manual'};
function expData(n) { return experiments.find(e => e.id === n) || {id: n}; }
function completeness(e) { return e.title && e.inputs && e.outputs && e.truth_table && e.source ? 'complete' : (e.title || e.inputs || e.outputs || e.truth_table) ? 'partial' : 'awaiting'; }
function truthTable(t) {
  return `<div class="table-scroll"><table class="tt"><thead><tr>${t.columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${t.rows.map(r => `<tr>${r.map(v => `<td class="v${esc(v)}">${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function experimentView() {
  const experiment = expData(selectedExperiment);
  main.innerHTML = heading() + `<p>Experiment ${selectedExperiment}${experiment.title ? ' - ' + esc(experiment.title) : ''}</p>
    <div class="sketch-layout"><section class="panel locator"><h2>Experiment board</h2><div class="board" aria-label="Physical experiment locator">${Object.entries(positions).map(([number, position]) => `<button data-exp="${number}" class="exp ${Number(number) === selectedExperiment ? 'selected' : ''}" style="left:${position[0]}%;top:${position[1]}%;width:${position[2]}%;height:${position[3]}%">E${number}</button>`).join('')}</div>
    </section><aside class="panel"><h2>Physical inputs</h2><div class="switch-list">${(experiment.inputs || []).map(label => `<div class="switch-label">${esc(label)}</div>`).join('') || '<p>Labels awaiting laboratory manual.</p>'}</div>${experiment.truth_table ? truthTable(experiment.truth_table) : ''}${experimentError ? `<p>${esc(experimentError)}</p>` : ''}</aside></div>`;
}

function expandedExperimentReference() {
  const e = expData(selectedExperiment), title = e.title || 'Title awaiting laboratory manual', status = completeness(e);
  const controls = e.inputs || [];
  main.innerHTML = heading('EXPERIMENT REFERENCE', `Experiment ${selectedExperiment} · ${esc(title)}`, 'Locate the physical controls. Perform the activity on the trainer.') +
    (experimentError ? `<div class="notice warning">Experiment reference data could not be loaded: ${esc(experimentError)}</div>` : '') +
    `<div class="split"><section class="panel"><div class="bar"><h2>Trainer locator</h2><span class="badge">Concept · top view</span></div>
    <div class="board" aria-label="Physical experiment locator">${Object.entries(positions).map(([n, p]) => `<button data-exp="${n}" aria-pressed="${Number(n) === selectedExperiment}" class="exp ${Number(n) === selectedExperiment ? 'selected' : ''} ${completeness(expData(Number(n)))}" style="left:${p[0]}%;top:${p[1]}%;width:${p[2]}%;height:${p[3]}%" aria-label="Experiment ${n}">E${n}</button>`).join('')}<div class="board-center"><strong>CENTRAL BREADBOARD</strong>830-point placeholder<br>Instrumented contacts to be defined</div></div>
    <p class="footnote">PCB 430 × 405 mm · Enclosure 444 × 419 mm. Layout follows Project Sketches, Rev S3. Concept only; not fabrication data.</p></section>
    <aside class="stack"><section class="panel"><div class="bar"><p class="eyebrow">PHYSICAL CONTROLS</p><span class="badge ${status}">${statusText[status]}</span></div>
    <h2 style="margin-top:12px">${controls.length ? 'Input column' : 'Refer to the laboratory manual'}</h2>
    <div class="switch-list">${controls.map(c => `<div class="switch-label">${esc(c)}</div>`).join('') || '<p class="muted">The supplied concept does not identify this activity’s exact input labels.</p>'}</div>
    <div class="row"><span>Power</span><strong>Individual branch switch</strong></div>
    <div class="row"><span>Outputs</span><strong>${e.outputs ? esc(e.outputs.join(', ')) : 'Indicators on trainer, grouped by figure'}</strong></div>
    <p class="footnote">These labels are a locator, not remote controls. No experiment power or input switching is performed by this application.</p></section>
    <section class="panel"><h2>Laboratory reference</h2>${e.truth_table ? `<p class="muted">Expected behavior from the approved manual. Compare with the physical indicators.</p>${truthTable(e.truth_table)}` : '<div class="placeholder-table"><strong>Expected truth table / sequence</strong><span>Awaiting entry from the approved laboratory manual.</span></div><p class="muted">Use the approved manual for the circuit, truth table or expected sequence. Record observations in the activity sheet.</p>'}
    <div class="notice">Predefined experiments operate through their own physical switches, LEDs and display, independently of this reference view.</div>
    ${e.source ? `<p class="footnote">Source: ${esc(e.source)}</p>` : '<p class="footnote">Activity details await the official experiment list; titles are not inferred from earlier demonstration data.</p>'}</section></aside></div>
    <div class="split" style="margin-top:22px"><section class="panel"><h2>Experiment index</h2><div class="table-scroll"><table><thead><tr><th>Block</th><th>Title</th><th>Inputs</th><th>Reference data</th></tr></thead><tbody>${Array.from({length: 15}, (_, i) => expData(i + 1)).map(x => `<tr class="${x.id === selectedExperiment ? 'current' : ''}"><td><button class="link" data-exp="${x.id}">E${x.id}</button></td><td>${x.title ? esc(x.title) : '<span class="muted">—</span>'}</td><td>${x.inputs ? esc(x.inputs.length > 3 ? `${x.inputs[0]} … ${x.inputs.at(-1)}` : x.inputs.map(l => l.split(' / ')[0]).join(', ')) : '<span class="muted">—</span>'}</td><td><span class="badge ${completeness(x)}">${statusText[completeness(x)]}</span></td></tr>`).join('')}</tbody></table></div><p class="footnote">Entries come from <span class="mono">data/concept_experiments.json</span>. Fill titles, labels and truth tables from the approved manual.</p></section>
    <section class="panel"><h2>Predefined experiment procedure</h2><ol class="procedure">
    <li>Select the experiment. Locate its input switches, output indicators and individual power switch.</li>
    <li>With the experiment power off, inspect the controls and any connections required. Set the initial input combination.</li>
    <li>Enable the experiment branch. Change the inputs through the required combinations and observe the LEDs or display.</li>
    <li>Compare the physical outputs with the manual’s truth table or expected sequence. Record observations on the activity sheet.</li>
    <li>Switch off the experiment branch after the exercise.</li></ol><p class="footnote">From the TRACE Concept of Operation, “Predefined experiment operation”.</p></section></div>`;
}

/* ---------------- Breadboard monitor ---------------- */

function monitorView() {
  main.innerHTML = heading('INSTRUMENTED BREADBOARD', 'See the supported node groups.', 'Each group represents connected contacts, not an independent measurement at every socket.') +
    `<div class="bar"><label class="check"><input id="examples" type="checkbox" ${examples ? 'checked' : ''}>Show offline example values</label><span class="badge">Hardware coverage: not reported</span></div><div id="measurement-source" class="notice"></div>
    <section class="panel"><div class="bar"><h2>Central breadboard</h2><span class="badge">Illustrative sensing map</span></div><div class="node-scroll"><div id="nodes" class="nodeboard"></div></div>
    <div class="model-legend"><span>Upper: A–E</span><span>Lower: F–J</span><span>Highlighted: selected example groups</span></div>
    <h2 style="margin-top:24px">Monitored node groups</h2><div class="table-scroll"><table><thead><tr><th>View</th><th>Node</th><th>Group</th><th>Voltage</th><th>Logic state</th><th>Freshness</th><th>Sequence</th></tr></thead><tbody id="measurements"></tbody></table></div>
    <p class="footnote">Multiplexed samples are taken at different times. Missing, invalid or stale readings are unavailable, never shown as zero volts.</p></section>
    <section class="panel" style="margin-top:22px"><h2>Example logic profile</h2><p class="muted">LOW and HIGH thresholds classify valid measurements. Between thresholds is UNDEFINED, not a diagnosis of a wiring fault.</p>
    <div class="fields"><label>LOW at or below (mV)<input id="low" type="number" value="${state.profile.low_mv}"></label><label>HIGH at or above (mV)<input id="high" type="number" value="${state.profile.high_mv}"></label><label>Offline data condition<select id="sample-condition"><option value="normal">Normal example</option><option value="stale">Stale samples</option><option value="invalid">Invalid samples</option></select></label></div>
    <button data-action="profile" ${state.outputs_enabled ? 'disabled' : ''}>Apply example profile</button></section>`;
  updateMeasurements();
  $('#sample-condition').value = state.sample_scenario || 'normal';
}
function updateMeasurements() {
  if (!$('#measurements')) return;
  $('#measurement-source').textContent = examples ? 'OFFLINE EXAMPLES · Demonstration values only. No trainer connected.' : state.session_id ? 'SESSION SIMULATION · Generated samples, not live hardware measurements.' : 'HARDWARE DISCONNECTED · All live readings are unavailable. Enable offline examples to inspect the presentation.';
  const rows = state.measurements;
  const measurements = $('#measurements');
  const selection = [...selectedNodes].join(',');
  const readings = JSON.stringify(rows);
  if (measurements.dataset.readings === readings && measurements.dataset.selection === selection) return;
  measurements.dataset.readings = readings;
  measurements.dataset.selection = selection;
  $('#measurements').innerHTML = rows.map(r => `<tr><td><input type="checkbox" data-node="${r.id}" aria-label="Show ${r.id}" ${selectedNodes.has(r.id) ? 'checked' : ''}></td><td>${r.id}</td><td>${r.column} / ${r.half}</td><td>${r.mv == null ? '—' : (r.mv / 1000).toFixed(2) + ' V'}</td><td class="${r.state}">${r.state}</td><td>${r.age_ms == null ? 'No sample' : r.age_ms > 3000 ? 'Stale · ' + r.age_ms + ' ms' : r.age_ms + ' ms ago'}</td><td>${r.sequence ?? '—'}</td></tr>`).join('');
  const board = $('#nodes');
  const highlights = JSON.stringify(rows.filter(r => selectedNodes.has(r.id)).map(r => [r.id, r.column, r.half, r.state]));
  if (board.dataset.highlights === highlights) return;
  board.dataset.highlights = highlights;
  board.innerHTML = ['A-E', 'F-J'].map((half, side) => `${side ? '<div class="gap"></div>' : ''}${Array.from({length: 63}, (_, i) => {
    const r = rows.find(n => n.column === i + 1 && n.half === half && selectedNodes.has(n.id));
    return `<div class="node ${r ? 'monitored ' + r.state : ''}" title="${i + 1} / ${half}${r ? ' · ' + r.id + ' ' + r.state : ' · not mapped'}">${(i % 5 === 0 || r) ? `<span class="num">${i + 1}</span>` : ''}•<br>•<br>•<br>•<br>•</div>`;
  }).join('')}`).join('');
}

/* ---------------- Virtual IC ---------------- */

function mapMatchesConfiguration() { return state.configuration?.model === model && Object.entries(map).every(([name, node]) => state.configuration.assignments[name] === node); }
function liveStates() { return state.signal_states && mapMatchesConfiguration() ? Object.fromEntries(state.signal_states.map(s => [s.name, s])) : null; }
function conflicts() {
  const by = {};
  for (const [name, node] of Object.entries(map)) (by[node] ??= []).push(name);
  return Object.entries(by).filter(([, names]) => names.length > 1);
}
function portStrip() {
  const m = modelData(), live = liveStates(), cols = Array.from({length: 13}, (_, i) => i + 12), by = {};
  for (const s of m.signals) (by[map[s.name]] ??= []).push(s);
  const row = half => cols.map(c => {
    const key = `${c}/${half}`, sigs = by[key] || [], usable = state.port_nodes.includes(key), lv = sigs.length === 1 && live ? live[sigs[0].name] : null;
    const cls = sigs.length > 1 ? 'conflict' : sigs.length ? sigs[0].direction : usable ? 'free' : 'reserved';
    const tip = `${key} · ${sigs.length ? sigs.map(s => `${s.name} ${s.direction}`).join(', ') : usable ? 'available port node' : 'outside the example port'}`;
    return `<div class="pcell ${cls} ${lv ? 'live ' + lv.state : ''}" title="${esc(tip)}"><span class="pcol">${c}</span><strong>${sigs.map(s => esc(s.name)).join('<br>') || (usable ? '·' : '')}</strong>${lv ? `<small>${lv.state}</small>` : ''}</div>`;
  }).join('');
  const clash = conflicts();
  const overview = ['A-E', 'F-J'].map((half, side) => `${side ? '<div class="gap"></div>' : ''}${Array.from({length: 63}, (_, i) => {
    const sigs = by[`${i + 1}/${half}`] || [], cls = sigs.length > 1 ? 'conflict' : sigs[0]?.direction || '';
    return `<div class="node ${cls}" title="${i+1}/${half}: ${esc(sigs.map(s=>s.name).join(', ') || 'unassigned')}">${i%5===0?`<span class="num">${i+1}</span>`:''}•<br>•<br>•<br>•<br>•</div>`;
  }).join('')}`).join('');
  return `<p class="footnote">Full 63-column breadboard · A–E above, F–J below. Assigned port groups highlighted.</p><div class="node-scroll"><div class="nodeboard port-overview">${overview}</div></div><p class="footnote">Port A detail · columns 12–24</p><div class="port-scroll"><div class="port-strip"><div class="phalf">A–E</div>${row('A-E')}<div class="pdivider"></div><div class="phalf">F–J</div>${row('F-J')}</div></div>
    <div class="model-legend"><span><i class="key input"></i>Input</span><span><i class="key output"></i>Output</span><span><i class="key free"></i>Available port node</span><span><i class="key conflict"></i>Conflict</span>${live ? '<span><i class="key HIGH"></i>Simulated HIGH</span>' : ''}</div>
    ${clash.length ? `<div class="notice warning">Node conflict: ${clash.map(([n, names]) => `${esc(names.join(' and '))} share ${esc(n)}`).join('; ')}. The configuration request will be rejected.</div>` : ''}`;
}
function updatePortArea() { const el = $('#port-area'); if (el) el.innerHTML = portStrip(); }
function liveCell(s, live) {
  if (!live) return 'Unavailable';
  const v = live[s.name];
  return s.direction === 'input'
    ? `<button class="pin ${v.state}" data-input="${esc(s.name)}" data-value="${v.state === 'HIGH' ? 0 : 1}" aria-label="Set ${esc(s.name)} ${v.state === 'HIGH' ? 'LOW' : 'HIGH'}">${v.state}</button>`
    : `<span class="pin ${v.state}">${v.state}</span>`;
}
function procedure() {
  const s = state, live = !!s.session_id && s.phase !== 'interlocked';
  const finished = live && s.cycle_completed && !s.outputs_enabled && !s.configuration;
  const steps = [
    {title: 'Prepare session', detail: 'Start the example session. A real trainer reports identity, nodes, models and limits here.', done: live},
    {title: 'Configure model & map', detail: 'Review each signal, direction and node group, then request configuration.', done: live && (!!s.configuration || finished)},
    {title: 'Verify wiring, power off', detail: 'Keep emulation inactive and circuit supply off while wiring to the assigned nodes.', done: live && (checks.wiring || s.outputs_enabled || finished), confirm: 'wiring', label: 'Wiring checked with emulation inactive and supply off'},
    {title: 'Activate', detail: 'Active is shown only after the matching acknowledgement. Then apply circuit supply.', done: live && (s.outputs_enabled || finished)},
    {title: 'Deactivate & power off', detail: 'Confirm output disable, then remove circuit power before changing model, map or wiring.', done: finished && checks.power, confirm: 'power', label: 'Output disable acknowledged and circuit power removed'}];
  const current = steps.findIndex(x => !x.done);
  // Keep each confirmation visible (and reversible) while its stage applies.
  const showConfirm = {wiring: live && s.phase === 'configured', power: finished};
  return `<section class="panel procedure-panel"><div class="bar"><h2>Guided procedure</h2><span class="badge">${current < 0 ? 'Session cycle complete' : `Step ${current + 1} of 5`}</span></div>
    <ol class="steps">${steps.map((x, i) => `<li class="${x.done ? 'done' : i === current ? 'current' : ''}"><span class="dot">${x.done ? '✓' : i + 1}</span><div><strong>${x.title}</strong><p>${x.detail}</p>${x.confirm && showConfirm[x.confirm] ? `<label class="check"><input type="checkbox" data-confirm="${x.confirm}" ${checks[x.confirm] ? 'checked' : ''}>${x.label}</label>` : ''}</div></li>`).join('')}</ol>
    <p class="footnote">Order of work from the Concept of Operation. Confirmations are student acknowledgements in this mock-up, not an electrical interlock.</p></section>`;
}
function virtualView() {
  const m = modelData(), active = state.outputs_enabled, live = liveStates();
  const mapMatches = mapMatchesConfiguration();
  main.innerHTML = heading('VIRTUAL IC / HARDWARE EMULATION', 'Configure the function. Know the interface.', 'The trainer will execute supported logic locally through assigned input and output nodes.') +
    `<div class="tabs"><button data-tab="hardware" class="${tab === 'hardware' ? 'active' : ''}">Trainer configuration</button><button data-tab="offline" class="${tab === 'offline' ? 'active' : ''}">Offline behavior check</button></div>` +
    (tab === 'offline' ? offlineView() : `<div class="bar"><label style="min-width:260px">Candidate model<select id="model" ${active ? 'disabled' : ''}>${state.models.map(i => `<option value="${i.id}" ${i.id === model ? 'selected' : ''}>${i.id} · ${i.title}</option>`).join('')}</select></label><span class="badge">One virtual IC at a time</span></div>
    <div class="notice ${model === '7476' ? 'warning' : ''}">${esc(m.variant)}. ${model === '7476' ? 'The proposed map can be reviewed, but executable support remains unavailable.' : 'Offline session simulation can exercise this model’s configuration lifecycle.'}</div>
    ${procedure()}
    <div class="split"><aside class="stack"><section class="panel"><p class="eyebrow">TRAINER STATUS</p><div class="state-title">Disconnected / INACTIVE</div>
    <div class="row"><span>Device support</span><strong>Not reported</strong></div><div class="row"><span>Clock / response limit</span><strong>Not reported</strong></div><div class="row"><span>Output loading</span><strong>Not reported</strong></div><div class="row"><span>Live signal states</span><strong>Unavailable</strong></div>
    <div class="toolbar"><button disabled>Activate on trainer</button></div><p class="footnote">No physical USB trainer is connected to this concept interface. Offline checks do not enable hardware outputs.</p></section>
    <section class="panel"><h2>Offline session rehearsal</h2><div id="session-summary"></div>
    <div class="toolbar"><button data-action="configure" ${!state.session_id || active || model === '7476' || state.phase === 'interlocked' ? 'disabled' : ''}>Configure example</button><button data-action="activate" ${state.phase !== 'configured' || !mapMatches || !checks.wiring ? 'disabled' : ''}>Activate example</button><button data-action="deactivate" ${!state.session_id || state.phase === 'interlocked' ? 'disabled' : ''}>Deactivate example</button></div>
    ${state.phase === 'configured' && !checks.wiring ? '<p class="muted">Confirm step 3 of the guided procedure before activation.</p>' : ''}
    ${live ? '<div class="notice">SIMULATED PIN REPORTS · Select an input state in the port map to imitate a wired switch. Outputs are calculated by the rehearsal service, not measured.</div>' : ''}
    <a href="#connection">Manage example session →</a><p class="footnote">Configuration and activation are separate requests. State changes follow a matching simulated acknowledgement.</p></section></aside>
    <section class="panel"><div class="bar"><h2>Proposed logical port map</h2><span class="badge">Port A · ${m.version}</span></div><p class="muted">Logical signal assignments, not physical IC package pin numbers.</p>
    <div class="table-scroll"><table><thead><tr><th>Signal</th><th>Direction</th><th>Node group</th><th>${live ? 'Simulated state' : 'Live state'}</th></tr></thead><tbody>${m.signals.map(s => `<tr><td>${s.name}</td><td>${s.direction.toUpperCase()}</td><td><select data-signal="${s.name}" aria-label="Node for ${s.name}" ${active ? 'disabled' : ''}>${state.port_nodes.map(n => `<option ${map[s.name] === n ? 'selected' : ''}>${n}</option>`).join('')}</select></td><td>${liveCell(s, live)}</td></tr>`).join('')}</tbody></table></div>
    <p class="footnote">Example assignments only. “/” means active LOW. Power and common reference are separate from these logical signals. Conflicting node assignments are rejected.</p></section></div>
    <section class="panel" style="margin-top:22px"><div class="bar"><h2>Breadboard wiring view</h2><span class="badge">Columns 12–24 of 63 · example Port A</span></div><p class="muted">Where each logical signal connects on the central breadboard. Updates as you change the map.</p><div id="port-area">${portStrip()}</div></section>
    <div class="notice">Keep emulation inactive and circuit power off while changing wiring. Deactivate and confirm output disable before changing the model or map. Follow the laboratory procedure.</div>`);
  if (tab === 'hardware') updateSessionSummary();
}
function offlineView() {
  return `<section class="panel compact"><p class="eyebrow">OFFLINE ONLY · NO TRAINER COMMANDS</p><h2 style="margin-top:14px">Explore logical behavior</h2><p class="muted">These calculated examples do not establish hardware support, clock performance or a connection.</p>
  <div class="logic-check"><section class="panel"><h3>NAND gate</h3><div class="toolbar"><button data-bit="a" class="${logic.a ? 'on' : ''}">A = ${logic.a}</button><button data-bit="b" class="${logic.b ? 'on' : ''}">B = ${logic.b}</button></div><p>Calculated Y</p><div class="large-number">${1 - (logic.a & logic.b)}</div></section>
  <section class="panel"><h3>Generic JK state step</h3><div class="toolbar"><button data-bit="j" class="${logic.j ? 'on' : ''}">J = ${logic.j}</button><button data-bit="k" class="${logic.k ? 'on' : ''}">K = ${logic.k}</button></div><button data-action="jk-step">Apply logical step</button><p class="large-number">Q ${logic.q} <small>/Q ${1 - logic.q}</small></p><button data-action="jk-reset">Reset example state</button></section></div>
  <p class="footnote">JK: 00 hold, 01 reset, 10 set, 11 toggle. This is not a complete 7476 variant model: no clock-edge, asynchronous-control or timing claim is made.</p></section>`;
}
function updateSessionSummary() {
  const el = $('#session-summary'); if (!el) return;
  el.innerHTML = `<p><strong>${esc(state.phase.toUpperCase())}</strong></p><p class="muted">Simulated output enable: ${state.outputs_enabled ? 'ENABLED' : 'DISABLED'}</p>${state.configuration ? `<p class="mono">Configuration ${state.configuration.id.slice(0, 12)}<br>Model ${state.configuration.model}</p>` : ''}${state.reason ? `<p class="notice warning">${esc(state.reason)}</p>` : ''}`;
}

/* ---------------- Connection ---------------- */

function connectionView() {
  main.innerHTML = heading('DEVICE SERVICE', 'Connection &amp; operating state', 'USB identifies the trainer and its capabilities before hardware configuration is enabled.') +
    `<div class="split"><section class="panel"><p class="eyebrow">PHYSICAL TRAINER</p><h2 style="margin-top:14px">No current hardware session</h2>${[['USB trainer', 'Disconnected'], ['Device / firmware identity', 'Not reported'], ['Protocol / model versions', 'Not reported'], ['Available sensing nodes', 'Not reported'], ['Supported ICs', 'Not reported'], ['Electrical and timing limits', 'Not reported']].map(([k, v]) => `<div class="row"><span>${k}</span><strong>${v}</strong></div>`).join('')}<p class="footnote">This revision is a desktop-browser concept. The versioned USB service and actual MCU firmware remain integration work. USB power is not assumed sufficient for the trainer’s regulated circuit supply.</p></section>
    <section class="panel"><p class="eyebrow">OFFLINE TEST FACILITY</p><h2 style="margin-top:14px">Rehearse a trainer session</h2><p class="muted">Exercise configuration, acknowledgements, output-disable status and interruptions without claiming connected hardware.</p>
    <div class="toolbar"><button class="primary" data-action="connect" ${state.outputs_enabled ? 'disabled' : ''}>${state.session_id ? 'Restart example session' : 'Start example session'}</button><button data-action="disconnect" ${!state.session_id ? 'disabled' : ''}>Disconnect example</button><button data-action="trip" ${!state.session_id || state.phase === 'interlocked' ? 'disabled' : ''}>Simulate protection trip</button></div>
    <div id="session-summary"></div><div class="lifecycle">${['disconnected', 'connected and inactive', 'configured', 'active', 'interlocked'].map(s => `<span class="step ${state.phase === s ? 'current' : ''}">${s}</span>`).join('')}</div>
    <p class="footnote">Example heartbeat timeout: 5 s. Loss or restart disables simulated output drive and clears configuration. Reconnection never automatically resumes activation.</p></section></div>
    <section class="panel" style="margin-top:22px"><h2>Latest example acknowledgement</h2><div class="mono">${state.last_ack ? esc(JSON.stringify(state.last_ack, null, 2)) : 'No command acknowledgement received.'}</div><div class="notice">Hardware activation must match the accepted configuration and session. Sending a command alone must never display Active.</div></section>`;
  updateSessionSummary();
}

/* ---------------- State and events ---------------- */

async function refresh(redraw = false) {
  const previous = state;
  state = await api('state?examples=' + examples);
  if (!Object.keys(map).length) resetMap();
  // Another window may have activated a different accepted configuration.
  if (state.outputs_enabled && state.configuration && !mapMatchesConfiguration()) {
    model = state.configuration.model;
    map = {...state.configuration.assignments};
  }
  const cid = state.configuration?.id ?? null;
  if (!state.session_id || state.phase === 'interlocked') { checks = {wiring: false, power: false}; checkKey = null; }
  else if (cid && cid !== checkKey) { checks = {wiring: false, power: false}; checkKey = cid; }
  const changed = previous && (previous.phase !== state.phase || previous.configuration?.id !== state.configuration?.id || previous.pending !== state.pending || previous.last_ack?.id !== state.last_ack?.id);
  if (redraw) render();
  else if (page === 'monitor') updateMeasurements();
  else if ((changed || JSON.stringify(previous?.signal_states) !== JSON.stringify(state.signal_states)) && ['virtual', 'connection'].includes(page)) render();
}
async function command(actionName) {
  toast('Waiting for simulated acknowledgement…');
  await api('command', {action: actionName, ...(actionName === 'configure' ? {model, assignments: map} : {}), ...(actionName === 'activate' ? {config_id: state.configuration?.id} : {})});
  await refresh(true);
  toast('Example command acknowledged. Hardware remains disconnected.');
}
document.addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  if (b.dataset.page) { navigate(b.dataset.page); return; }
  if (b.dataset.exp) { selectedExperiment = Number(b.dataset.exp); render(); window.scrollTo({top: 0}); return; }
  if (b.dataset.tab) { tab = b.dataset.tab; render(); return; }
  if (b.dataset.bit) { logic[b.dataset.bit] ^= 1; render(); return; }
  if (b.dataset.input) { action(async () => { await api('rehearsal-input', {signal: b.dataset.input, value: Number(b.dataset.value)}); await refresh(true); }); return; }
  action(async () => {
    const a = b.dataset.action;
    if (['connect', 'disconnect', 'configure', 'activate', 'deactivate', 'trip'].includes(a)) await command(a);
    if (a === 'profile') { await api('profile', {low_mv: Number($('#low').value), high_mv: Number($('#high').value), scenario: $('#sample-condition').value}); await refresh(); toast('Offline measurement profile applied'); }
    if (a === 'jk-step') { logic.q = logic.j ? (logic.k ? 1 - logic.q : 1) : (logic.k ? 0 : logic.q); render(); }
    if (a === 'jk-reset') { logic.q = 0; render(); }
  });
});
document.addEventListener('change', e => {
  const t = e.target;
  if (t.id === 'model') { model = t.value; checks.wiring = false; resetMap(); render(); }
  if (t.dataset.signal) { map[t.dataset.signal] = t.value; checks.wiring = false; render(); }
  if (t.dataset.confirm) { checks[t.dataset.confirm] = t.checked; render(); }
  if (t.id === 'examples') { examples = t.checked; action(() => refresh()); }
  if (t.dataset.node) { t.checked ? selectedNodes.add(t.dataset.node) : selectedNodes.delete(t.dataset.node); updateMeasurements(); }
});
window.addEventListener('hashchange', () => { if (page !== location.hash.slice(1)) navigate(location.hash.slice(1)); });

try {
  await Promise.all([refresh(), api('experiments').then(data => {
    experiments = data.experiments;
  }).catch(error => { experimentError = error.message; })]);
  if (state.configuration) { model = state.configuration.model; map = {...state.configuration.assignments}; checkKey = state.configuration.id; checks.wiring = state.outputs_enabled; }
  navigate(location.hash.slice(1) || 'experiments');
  setInterval(async () => {
    try { if (state.session_id) await api('heartbeat', {}); await refresh(); }
    catch (e) {
      toast('Local service unavailable. Hardware status remains disconnected.');
      Object.assign(state, {phase: 'disconnected', session_id: null, configuration: null, outputs_enabled: false, signal_states: null, cycle_completed: false});
      checks = {wiring: false, power: false}; checkKey = null;
      state.measurements = state.measurements.map(r => ({...r, mv: null, state: 'UNAVAILABLE', valid: false, age_ms: null}));
      if (page === 'monitor') updateMeasurements(); else if (['virtual', 'connection'].includes(page)) render();
    }
  }, 1000);
} catch (e) { main.innerHTML = `<p class="notice warning">Local service unavailable: ${esc(e.message)}. Start or restart TRACE and reload.</p>`; }

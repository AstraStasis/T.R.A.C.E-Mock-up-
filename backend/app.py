import asyncio
import contextlib
import csv
import io
import json
import math
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

from backend.logic import Comparison, load_data, classify, decode_events, mismatch_windows, calibration
from backend.transport import SerialDevice
from simulator.device import Simulator

ROOT = Path(__file__).resolve().parent.parent


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Thresholds(StrictModel):
    low: int = Field(800, ge=0, le=5499)
    high: int = Field(2000, ge=1, le=5500)


class CaptureConfig(StrictModel):
    ch: list[str] = Field(min_length=1, max_length=16)
    rate: int = Field(1_000_000, ge=1)
    depth: int = Field(20000, ge=2)
    pre: int = Field(2000, ge=1)
    source: str
    edge: str = 'rise'
    continuous: bool = False
    experiment: str | None = None


class SimConfig(StrictModel):
    scenario: str = 'normal'
    inputs: int | None = Field(None, ge=0, le=3)


class DockCommand(StrictModel):
    action: str
    ic: str | None = None
    pin: int | None = None
    value: int | None = Field(None, ge=0, le=1)
    vcc_mv: int = 4980
    gnd_mv: int = 0


class CalibrationRow(StrictModel):
    channel: str
    reference_mv: float
    tolerance_mv: float = Field(50, ge=0)


class Runtime:
    def __init__(self):
        self.channels, self.experiments = load_data(ROOT / 'data')
        self.ids = {c['id'] for c in self.channels}
        self.ics = json.loads((ROOT / 'data/ics/library.json').read_text())
        self.engines = {e['id']: Comparison(e) for e in self.experiments}
        self.mode = os.getenv('TRACE_DEVICE', 'simulator')
        if self.mode not in ('simulator', 'serial'):
            raise ValueError('TRACE_DEVICE must be simulator or serial')
        self.device = Simulator(self.channels, self.ics) if self.mode == 'simulator' else SerialDevice(os.getenv('TRACE_SERIAL_PORT', '/dev/ttyACM0'))
        self.settings = {'low': 800, 'high': 2000}
        path = ROOT / 'runtime/settings.json'
        if path.exists():
            self.settings = Thresholds(**json.loads(path.read_text())).model_dump()
            classify(0, **self.settings)
        self.values, self.comparisons = {}, {}
        self.capabilities = {}
        self.last_frame = 0
        self.linked = False
        self.capture = None
        self.pending = None
        self.capture_status = 'idle'
        self.continuous = False
        self.cfg = None
        self.dock = {'ic': None, 'state': 'released', 'vcc_mv': None, 'gnd_mv': None, 'pins': {}}
        self.error = None
        self.command_lock = asyncio.Lock()
        self.calibrations = []
        self.last_ack = None

    async def send(self, msg):
        msg['id'] = secrets.token_hex(6)
        await self.device.command(msg)

    async def arm(self):
        self.pending = {'capture_id': secrets.token_hex(8), 'ev': [], 'next_seq': 0}
        self.capture_status = 'armed'
        await self.send({'t': 'cap_arm', 'capture_id': self.pending['capture_id']})

    async def consume(self):
        async for msg in self.device.messages():
            try:
                await self.ingest(msg)
            except (ValueError, KeyError, TypeError) as exc:
                self.error = f'Device message rejected: {exc}'
                if msg.get('t', '').startswith('cap_'):
                    self.capture_status, self.continuous, self.pending = 'error', False, None

    async def ingest(self, m):
        t = m['t']
        if t == 'hello':
            if m.get('protocol') != 1:
                raise ValueError('Unsupported firmware protocol')
            for key in ('max_channels', 'max_rate_hz', 'max_depth'):
                if type(m.get(key)) is not int or m[key] < 1:
                    raise ValueError('Invalid device capabilities')
            self.capabilities = m
            self.linked = True
            await self.send({'t': 'cfg', 'vl': self.settings['low'], 'vh': self.settings['high'], 'scan_hz': 1000})
            await self.send({'t': 'watch', 'ids': sorted(self.ids)})
        elif t == 'frame':
            values = {}
            for c in m['ch']:
                if c['id'] not in self.ids or type(c['mv']) is not int or not -500 <= c['mv'] <= 6000:
                    raise ValueError('Invalid voltage channel')
                values[c['id']] = c['mv']
            self.values = values
            self.last_frame = time.monotonic()
            self.linked = bool(self.capabilities)
            self.comparisons = {k: e.update(values, **self.settings) for k, e in self.engines.items()}
        elif t == 'disconnected':
            self.linked, self.values, self.pending, self.continuous = False, {}, None, False
            self.capture_status = 'disconnected'
            self.capabilities = {}
            self.dock = {'ic': None, 'state': 'unknown', 'pins': {}, 'vcc_mv': None, 'gnd_mv': None}
            self.error = 'Board not linked'
        elif t == 'cap_data':
            if not self.pending or m['capture_id'] != self.pending['capture_id']:
                return
            if m['seq'] != self.pending['next_seq']:
                raise ValueError('Missing or out-of-order capture chunk')
            if m['seq'] == 0:
                if (m['ch'] != self.cfg.ch or m['depth'] != self.cfg.depth
                    or not isinstance(m['dt'], (int, float)) or not math.isfinite(m['dt']) or m['dt'] <= 0
                    or abs(m['dt'] - 1_000_000_000 / self.cfg.rate) > 1e-6
                    or type(m['trigger_index']) is not int or not 0 <= m['trigger_index'] < m['depth']):
                    raise ValueError('Capture metadata does not match configuration')
                self.pending.update({k: m[k] for k in ('ch', 'depth', 'dt', 't0', 'trigger_index')})
            if len(self.pending['ev']) + len(m['ev']) > self.cfg.depth:
                raise ValueError('Too many capture events')
            self.pending['ev'].extend(m['ev'])
            self.pending['next_seq'] += 1
        elif t == 'cap_done':
            if not self.pending or m['capture_id'] != self.pending['capture_id']:
                return
            if self.pending['next_seq'] != m['chunks'] or not self.pending['ev']:
                raise ValueError('Incomplete capture')
            if type(m.get('dropped_samples', 0)) is not int or m.get('dropped_samples', 0) < 0:
                raise ValueError('Invalid dropped-sample count')
            capture = self.pending
            decode_events(capture['ev'], capture['depth'], len(capture['ch']))
            capture.update(overflow=bool(m['overflow']), dropped_samples=m.get('dropped_samples', 0), mode=self.mode)
            exp = next((e for e in self.experiments if e['id'] == self.cfg.experiment), None)
            capture['expected'] = exp.get('expected_waveforms', {}) if exp else {}
            capture['mismatches'] = mismatch_windows(capture, capture['expected'])
            self.capture, self.pending, self.capture_status = capture, None, 'complete'
            if self.continuous:
                await self.arm()
        elif t == 'cap_stopped':
            self.pending, self.capture_status = None, 'stopped'
        elif t == 'vic_status':
            self.dock = m
        elif t == 'ack':
            self.last_ack = m
        elif t == 'err':
            self.error = str(m.get('msg', 'Device error'))

    def snapshot(self):
        fresh = self.linked and time.monotonic()-self.last_frame < 3
        values = self.values if fresh else {}
        return {'mode': self.mode, 'linked': fresh, 'capabilities': self.capabilities,
                'settings': self.settings, 'channels': {k: {'mv': v, 'state': classify(v, **self.settings)} for k, v in values.items()},
                'experiments': self.comparisons if fresh else {}, 'dock': self.dock if fresh else {'ic': None, 'state': 'unknown', 'pins': {}},
                'capture_status': self.capture_status, 'capture_id': self.capture['capture_id'] if self.capture else None,
                'error': self.error, 'last_ack': self.last_ack}


@asynccontextmanager
async def lifespan(app):
    app.state.runtime = Runtime()
    task = asyncio.create_task(app.state.runtime.consume())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title='TRACE local board API', lifespan=lifespan, docs_url=None, redoc_url=None)
from backend.concept import router as concept_router
app.include_router(concept_router)


@app.exception_handler(ValueError)
async def invalid_operation(request, exc):
    return JSONResponse(status_code=409, content={'detail': str(exc)})


@app.middleware('http')
async def local_headers(request, call_next):
    # No cross-origin state changes; browser clients use the same local origin.
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD') and origin and origin != str(request.base_url).rstrip('/'):
        return Response('Cross-origin request refused', status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    return response


def runtime():
    return app.state.runtime


@app.get('/api/bootstrap')
async def bootstrap():
    r = runtime()
    return {'channels': r.channels, 'experiments': r.experiments, 'ics': r.ics,
            'wifi': os.getenv('TRACE_WIFI_NAME', 'TRACE-07'), 'url': os.getenv('TRACE_PUBLIC_URL', 'http://trace.local'),
            'diagnostics_enabled': bool(os.getenv('TRACE_RESEARCH_PIN')), 'state': r.snapshot()}


@app.get('/api/state')
async def state(): return runtime().snapshot()


@app.get('/api/qr.svg')
async def qr():
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(os.getenv('TRACE_PUBLIC_URL', 'http://trace.local'), image_factory=qrcode.image.svg.SvgPathImage)
    return Response(img.to_string(), media_type='image/svg+xml')


@app.post('/api/settings')
async def settings(body: Thresholds):
    r = runtime()
    try: classify(0, body.low, body.high)
    except ValueError as e: raise HTTPException(422, str(e))
    async with r.command_lock:
        await r.send({'t': 'cfg', 'vl': body.low, 'vh': body.high, 'scan_hz': 1000})
        r.settings = body.model_dump()
        (ROOT / 'runtime').mkdir(exist_ok=True)
        temp = ROOT / 'runtime/settings.tmp'
        temp.write_text(json.dumps(r.settings))
        temp.replace(ROOT / 'runtime/settings.json')
        for e in r.engines.values(): e.reset()
    return r.settings


@app.post('/api/experiments/{eid}/reset')
async def reset(eid: str):
    if eid not in runtime().engines: raise HTTPException(404, 'Unknown experiment')
    runtime().engines[eid].reset()
    return {'ok': True}


@app.post('/api/simulator')
async def simulator(body: SimConfig):
    r = runtime()
    if r.mode != 'simulator': raise HTTPException(409, 'Only available in simulator mode')
    if body.scenario not in ('normal', 'fault', 'floating', 'glitch', 'overflow'): raise HTTPException(422, 'Unknown scenario')
    await r.send({'t': 'sim_set', **body.model_dump()})
    return {'ok': True}


@app.post('/api/capture/start')
async def start_capture(body: CaptureConfig):
    r = runtime()
    caps = r.capabilities
    if not r.snapshot()['linked']: raise HTTPException(409, 'Board not linked')
    if (len(set(body.ch)) != len(body.ch) or not set(body.ch) <= r.ids or body.source not in body.ch
        or len(body.ch) > caps.get('max_channels', 0) or body.rate > caps.get('max_rate_hz', 0)
        or body.depth > caps.get('max_depth', 0) or body.pre >= body.depth or body.edge not in ('rise', 'fall', 'either')
        or body.experiment is not None and body.experiment not in r.engines):
        raise HTTPException(422, 'Capture configuration exceeds device limits or contains invalid channels/trigger')
    async with r.command_lock:
        if r.pending: raise HTTPException(409, 'Stop the active capture before reconfiguring')
        r.cfg, r.continuous = body, body.continuous
        await r.send({'t': 'cap_cfg', 'ch': body.ch, 'rate': body.rate, 'depth': body.depth, 'pre': body.pre,
                      'trig': {'src': body.source, 'edge': body.edge}})
        await r.arm()
    return {'status': 'armed'}


@app.post('/api/capture/stop')
async def stop_capture():
    r = runtime()
    async with r.command_lock:
        r.continuous = False
        await r.send({'t': 'cap_stop'})
        r.pending, r.capture_status = None, 'stopped'
    return {'status': 'stopped'}


@app.get('/api/capture')
async def capture(): return runtime().capture


@app.get('/api/capture/export/{fmt}')
async def export_capture(fmt: str):
    c = runtime().capture
    if not c: raise HTTPException(404, 'No capture available')
    if fmt == 'json': return Response(json.dumps(c), media_type='application/json', headers={'Content-Disposition':'attachment; filename=trace-capture.json'})
    if fmt != 'vcd': raise HTTPException(404, 'Use json or vcd')
    lines = ['$timescale 1ns $end', '$scope module TRACE $end']
    for i, ch in enumerate(c['ch']): lines.append(f'$var wire 1 c{i} {ch} $end')
    lines += ['$upscope $end', '$enddefinitions $end']
    for sample, mask in decode_events(c['ev'], c['depth'], len(c['ch'])):
        lines.append(f'#{round(sample*c["dt"])}')
        lines.extend(f'{(mask >> i)&1}c{i}' for i in range(len(c['ch'])))
    return Response('\n'.join(lines)+'\n', media_type='text/plain', headers={'Content-Disposition':'attachment; filename=trace-capture.vcd'})


@app.post('/api/dock')
async def dock(body: DockCommand):
    r = runtime()
    if not r.snapshot()['linked']: raise HTTPException(409, 'Board not linked')
    msg = {'t': 'vic_' + body.action}
    if body.action == 'load':
        if body.ic not in {i['id'] for i in r.ics}: raise HTTPException(422, 'Unknown IC')
        if r.mode == 'serial' and not r.capabilities.get('vic_supported', []).__contains__(body.ic):
            raise HTTPException(409, 'Firmware does not advertise this IC')
        msg['ic'] = body.ic
    elif body.action == 'pin':
        if r.mode != 'simulator': raise HTTPException(409, 'Simulated input controls only')
        ic = next((i for i in r.ics if i['id'] == r.device.ic), None)
        if not ic or body.value is None or body.pin not in [p['number'] for p in ic['pins'] if p['direction']=='input']:
            raise HTTPException(422, 'Only active IC input pins can be toggled')
        msg.update(pin=body.pin, value=body.value)
    elif body.action == 'power':
        if r.mode != 'simulator': raise HTTPException(409, 'Simulated power controls only')
        msg.update(vcc_mv=body.vcc_mv, gnd_mv=body.gnd_mv)
    elif body.action != 'release': raise HTTPException(422, 'Unknown dock action')
    try:
        async with r.command_lock: await r.send(msg)
    except ValueError as e: raise HTTPException(409, str(e))
    return {'status': 'command sent; awaiting device status'}


def require_pin(request):
    pin = os.getenv('TRACE_RESEARCH_PIN')
    if not pin or not secrets.compare_digest(request.headers.get('X-Research-Pin', ''), pin):
        raise HTTPException(403, 'Researcher PIN required; set TRACE_RESEARCH_PIN on the server')


@app.get('/api/diagnostics')
async def diagnostics(request: Request):
    require_pin(request)
    rows = runtime().calibrations
    return {'rows': rows, 'pass_rate': sum(r['passed'] for r in rows)/len(rows)*100 if rows else None}


@app.post('/api/diagnostics')
async def record(body: CalibrationRow, request: Request):
    require_pin(request)
    r = runtime()
    value = r.snapshot()['channels'].get(body.channel)
    if not value: raise HTTPException(422, 'No fresh measurement for channel')
    row = {**body.model_dump(), 'measured_mv': value['mv'], **calibration(value['mv'], body.reference_mv),
           'passed': abs(value['mv']-body.reference_mv) <= body.tolerance_mv, 'mode': r.mode}
    r.calibrations.append(row)
    return row


@app.get('/api/diagnostics/export')
async def export_diagnostics(request: Request):
    require_pin(request)
    rows = runtime().calibrations
    s = io.StringIO()
    if rows:
        writer = csv.DictWriter(s, fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
    return Response(s.getvalue(), media_type='text/csv')


@app.websocket('/ws')
async def websocket(ws: WebSocket):
    origin = ws.headers.get('origin')
    if origin and origin.split('://',1)[-1] != ws.headers.get('host'):
        await ws.close(code=1008); return
    await ws.accept()
    try:
        while True:
            await ws.send_json(runtime().snapshot())
            await asyncio.sleep(.1)
    except (WebSocketDisconnect, RuntimeError, OSError): pass


@app.get('/')
async def home(): return FileResponse(ROOT / 'frontend/concept.html')


@app.get('/legacy')
async def legacy(): return FileResponse(ROOT / 'frontend/index.html')


app.mount('/assets', StaticFiles(directory=ROOT / 'frontend', check_dir=False), name='assets')

"""November concept mock-up. No simulated session is represented as USB hardware."""
import asyncio
import json
import time
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix='/api/concept')
EXPERIMENT_FILE = Path(__file__).resolve().parent.parent / 'data/concept_experiments.json'
TRUTH_VALUES = {'0', '1', 'X'}


def validate_experiments(items):
    """Experiment reference data is entered from the approved manual; reject malformed entries."""
    if (not isinstance(items, list) or len(items) != 15
            or any(not isinstance(e, dict) or type(e.get('id')) is not int for e in items)
            or sorted(e['id'] for e in items) != list(range(1, 16))):
        raise ValueError('Experiment data must contain exactly E1..E15')
    for e in items:
        for key in ('title', 'source'):
            if e.get(key) is not None and (not isinstance(e[key], str) or not e[key].strip()):
                raise ValueError(f'E{e["id"]}: {key} must be text or null')
        for key in ('inputs', 'outputs'):
            value = e.get(key)
            if value is not None and (not isinstance(value, list) or not value
                                      or not all(isinstance(v, str) and v.strip() for v in value)):
                raise ValueError(f'E{e["id"]}: {key} must be a non-empty list of labels or null')
        table = e.get('truth_table')
        if table is not None:
            if not isinstance(table, dict):
                raise ValueError(f'E{e["id"]}: truth_table must be an object or null')
            cols, rows = table.get('columns'), table.get('rows')
            if (not isinstance(cols, list) or not cols or not all(isinstance(c, str) and c for c in cols)
                    or len(set(cols)) != len(cols) or not isinstance(rows, list) or not rows):
                raise ValueError(f'E{e["id"]}: truth_table needs unique columns and at least one row')
            if any(not isinstance(r, list) or len(r) != len(cols)
                   or any(not isinstance(v, str) or v not in TRUTH_VALUES for v in r) for r in rows):
                raise ValueError(f'E{e["id"]}: each truth_table row must match columns and use "0", "1" or "X"')
    return sorted(items, key=lambda e: e['id'])


def load_experiments(path=EXPERIMENT_FILE):
    return validate_experiments(json.loads(path.read_text(encoding='utf-8'))['experiments'])

NODES = [
    {'id': 'N01', 'column': 3, 'half': 'A-E', 'example_mv': 120},
    {'id': 'N02', 'column': 7, 'half': 'F-J', 'example_mv': 4640},
    {'id': 'N03', 'column': 12, 'half': 'A-E', 'example_mv': 1250},
    {'id': 'N04', 'column': 20, 'half': 'F-J', 'example_mv': 80},
    {'id': 'N07', 'column': 51, 'half': 'A-E', 'example_mv': None},
]
PORT_NODES = [f'{col}/{half}' for half in ('A-E', 'F-J') for col in range(15, 22)]
MODELS = {
    '7476': {'id': '7476', 'title': 'Dual JK flip-flop', 'version': 'concept-1',
             'variant': 'Not selected; clock edge and asynchronous rules unresolved',
             'demo_supported': False,
             'signals': [{'name': f'{section}{name}' if not name.startswith('/') else f'/{section}{name[1:]}',
                          'direction': 'output' if name in ('Q', '/Q') else 'input',
                          'node': f'{15+i}/{half}'}
                         for section, half in ((1, 'A-E'), (2, 'F-J'))
                         for i, name in enumerate(('J', 'K', 'CLK', '/PRE', '/CLR', 'Q', '/Q'))]},
    '74LS00': {'id': '74LS00', 'title': 'Quad two-input NAND', 'version': 'demo-1',
               'variant': 'Logical demonstration; no electrical or timing equivalence',
               'demo_supported': True,
               'signals': [{'name': f'{gate}{name}', 'direction': 'output' if name == 'Y' else 'input',
                            'node': PORT_NODES[(gate-1)*3+i]}
                           for gate in range(1, 5) for i, name in enumerate(('A', 'B', 'Y'))]},
}


def state_for(mv, valid=True, age_ms=0, low=800, high=2000):
    if not valid or mv is None or age_ms > 3000:
        return 'UNAVAILABLE'
    return 'LOW' if mv <= low else 'HIGH' if mv >= high else 'UNDEFINED'


def evaluate(model, inputs):
    """Logical outputs for rehearsal reports. Only models with demo_supported are evaluated."""
    if model == '74LS00':
        return {f'{g}Y': 1 - (inputs.get(f'{g}A', 0) & inputs.get(f'{g}B', 0)) for g in range(1, 5)}
    raise ValueError('No executable logical model for this IC')


def validate_map(model, assignments):
    if model not in MODELS:
        raise ValueError('Unknown model')
    names = {s['name'] for s in MODELS[model]['signals']}
    if set(assignments) != names:
        raise ValueError('Every logical signal requires exactly one node assignment')
    if any(node not in PORT_NODES for node in assignments.values()):
        raise ValueError('Unavailable or reserved node assignment')
    if len(set(assignments.values())) != len(assignments):
        raise ValueError('Node conflict: the example interface requires exclusive signal ownership')


class ConceptSession:
    def __init__(self):
        self.reset()

    def reset(self):
        self.session_id = None
        self.configuration = None
        self.phase = 'disconnected'
        self.outputs_enabled = False
        self.last_heartbeat = 0
        self.last_ack = None
        self.pending = False
        self.reason = None
        self.low, self.high = 800, 2000
        self.scenario = 'normal'
        self.inputs = {}
        self.cycle_completed = False

    def check_watchdog(self):
        if self.session_id and self.phase != 'interlocked' and time.monotonic()-self.last_heartbeat > 5:
            self.outputs_enabled = False
            self.configuration = None
            self.inputs = {}
            self.cycle_completed = False
            self.phase = 'interlocked'
            self.reason = 'Demonstration heartbeat expired; output enable cleared. Reconnect explicitly.'

    def signal_states(self):
        """Simulated pin reports exist only while the rehearsal session is acknowledged Active."""
        if not (self.outputs_enabled and self.configuration):
            return None
        model = self.configuration['model']
        outputs = evaluate(model, self.inputs)
        rows = []
        for s in MODELS[model]['signals']:
            level = self.inputs.get(s['name'], 0) if s['direction'] == 'input' else outputs[s['name']]
            rows.append({'name': s['name'], 'direction': s['direction'],
                         'node': self.configuration['assignments'][s['name']],
                         'state': 'HIGH' if level else 'LOW', 'source': 'simulated rehearsal report'})
        return rows

    def set_input(self, signal, value):
        self.check_watchdog()
        if self.pending:
            raise ValueError('Wait for the pending acknowledgement')
        if type(value) is not int or value not in (0, 1):
            raise ValueError('Input value must be 0 or 1')
        if not (self.outputs_enabled and self.configuration):
            raise ValueError('Rehearsal inputs are available only while the example configuration is Active')
        model = MODELS[self.configuration['model']]
        if signal not in {s['name'] for s in model['signals'] if s['direction'] == 'input'}:
            raise ValueError('Only input signals of the active model can be changed')
        self.inputs[signal] = value
        return self.snapshot()

    def snapshot(self):
        self.check_watchdog()
        return {'hardware_connected': False, 'source': 'offline session simulator' if self.session_id else 'design preview',
                'session_id': self.session_id, 'phase': self.phase, 'outputs_enabled': self.outputs_enabled,
                'configuration': self.configuration, 'last_ack': self.last_ack, 'pending': self.pending,
                'reason': self.reason, 'profile': {'id': 'example-ttl', 'low_mv': self.low, 'high_mv': self.high},
                'hardware_limits': None, 'signal_states': self.signal_states(),
                'cycle_completed': self.cycle_completed, 'sample_scenario': self.scenario,
                'demo_capabilities': {'models': ['74LS00'], 'nodes': PORT_NODES} if self.session_id else None}

    def measurements(self, examples=False):
        self.check_watchdog()
        available = examples or bool(self.session_id and self.phase != 'interlocked')
        rows = []
        for index, node in enumerate(NODES):
            age = 5000 if self.scenario == 'stale' else 25 + index*31
            valid = available and node['example_mv'] is not None and self.scenario != 'invalid'
            mv = node['example_mv'] if valid else None
            status = state_for(mv, valid, age, self.low, self.high)
            rows.append({**node, 'mv': mv if status != 'UNAVAILABLE' else None,
                         'valid': valid and age <= 3000, 'age_ms': age if available else None,
                         'state': status, 'sequence': int(time.monotonic()*2) if available else None,
                         'source': 'offline example' if examples else 'session simulation' if available else 'unavailable'})
        return rows

    async def command(self, action, model=None, assignments=None, config_id=None):
        self.check_watchdog()
        if self.pending:
            raise ValueError('Wait for the pending acknowledgement')
        if action == 'connect':
            if self.outputs_enabled:
                raise ValueError('Deactivate before starting another example session')
            self.reset()
            self.session_id = uuid.uuid4().hex
            self.last_heartbeat = time.monotonic()
            self.phase = 'connected and inactive'
        elif action == 'disconnect':
            self.reset()
        else:
            if not self.session_id or self.phase == 'interlocked':
                raise ValueError('Start an offline session simulation first')
            if action == 'configure':
                if self.outputs_enabled:
                    raise ValueError('Deactivate and await output-disable acknowledgement before changing configuration')
                validate_map(model, assignments or {})
                if not MODELS[model]['demo_supported']:
                    raise ValueError('7476 variant is unresolved. Its map is a proposal, not an executable model')
            elif action == 'activate':
                if self.phase != 'configured' or not self.configuration or config_id != self.configuration['id']:
                    raise ValueError('Activation must reference the current accepted configuration')
            elif action not in ('deactivate', 'trip'):
                raise ValueError('Unknown session command')
            self.pending = True
            session_id = self.session_id
            request_id = uuid.uuid4().hex
            try:
                # Simulated firmware acknowledgement. Real transport must replace this boundary.
                await asyncio.sleep(.15)
                self.check_watchdog()
                if self.session_id != session_id or self.phase == 'interlocked':
                    raise ValueError('Session changed before acknowledgement')
                if action == 'configure':
                    self.configuration = {'id': uuid.uuid4().hex, 'model': model,
                                          'version': MODELS[model]['version'], 'assignments': assignments.copy()}
                    self.phase = 'configured'
                    self.inputs = {}
                    self.cycle_completed = False
                elif action == 'activate':
                    self.outputs_enabled = True
                    self.phase = 'active'
                else:
                    self.cycle_completed = action == 'deactivate' and self.outputs_enabled
                    self.outputs_enabled = False
                    self.inputs = {}
                    self.phase = 'interlocked' if action == 'trip' else 'connected and inactive'
                    self.configuration = None
                    self.reason = 'Simulated protection trip. Reconnect and configure again.' if action == 'trip' else None
                self.last_ack = {'id': request_id, 'action': action, 'session_id': session_id,
                                 'configuration_id': self.configuration['id'] if self.configuration else None,
                                 'outputs_enabled': self.outputs_enabled, 'source': 'simulated acknowledgement'}
            finally:
                self.pending = False
        return self.snapshot()


session = ConceptSession()


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: str
    model: str | None = None
    assignments: dict[str, str] | None = None
    config_id: str | None = None


class Profile(BaseModel):
    low_mv: int = Field(800, ge=0, le=5499)
    high_mv: int = Field(2000, ge=1, le=5500)
    scenario: str = 'normal'


class RehearsalInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    signal: str
    value: int = Field(ge=0, le=1)


@router.get('/experiments')
async def experiments():
    try:
        return {'experiments': load_experiments()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(500, f'Experiment reference data invalid: {exc}')


@router.post('/rehearsal-input')
async def rehearsal_input(body: RehearsalInput):
    try:
        return session.set_input(body.signal, body.value)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.get('/state')
async def state(examples: bool = False):
    return {**session.snapshot(), 'measurements': session.measurements(examples),
            'models': list(MODELS.values()), 'port_nodes': PORT_NODES}


@router.post('/command')
async def command(body: Command):
    try:
        return await session.command(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post('/heartbeat')
async def heartbeat():
    session.check_watchdog()
    if session.session_id and session.phase != 'interlocked':
        session.last_heartbeat = time.monotonic()
    return session.snapshot()


@router.post('/profile')
async def profile(body: Profile):
    if body.low_mv >= body.high_mv or body.scenario not in ('normal', 'stale', 'invalid'):
        raise HTTPException(422, 'Invalid thresholds or sample scenario')
    if session.outputs_enabled or session.pending:
        raise HTTPException(409, 'Deactivate before changing the logic profile')
    session.low, session.high, session.scenario = body.low_mv, body.high_mv, body.scenario
    session.configuration = None
    if session.phase == 'configured': session.phase = 'connected and inactive'
    return session.snapshot()

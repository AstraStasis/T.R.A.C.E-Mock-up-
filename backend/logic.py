"""Pure measurement, experiment, and digital capture logic. All times are ns."""
import json
from pathlib import Path


def classify(mv, low=800, high=2000):
    if not 0 <= low < high <= 5500:
        raise ValueError('Thresholds require 0 <= LOW < HIGH <= 5500 mV')
    if mv is None:
        return 'UNKNOWN'
    return 'LOW' if mv <= low else 'HIGH' if mv >= high else 'FLOATING'


def validate_experiment(e, channel_ids):
    for key in ('id', 'title', 'inputs', 'outputs', 'truth_table', 'sequential'):
        if key not in e:
            raise ValueError(f'Missing experiment field: {key}')
    signals = e['inputs'] + e['outputs']
    if not e['inputs'] or not e['outputs']:
        raise ValueError('Inputs and outputs must be nonempty')
    if len({s['ch'] for s in signals}) != len(signals):
        raise ValueError('Duplicate experiment channels')
    if any(s['ch'] not in channel_ids for s in signals):
        raise ValueError('Unmapped experiment channel')
    seen = set()
    for row in e['truth_table']:
        if len(row['in']) != len(e['inputs']) or len(row['out']) != len(e['outputs']):
            raise ValueError('Truth-table width does not match signals')
        if any(type(v) is not int or v not in (0, 1) for v in row['in'] + row['out']):
            raise ValueError('Truth-table values must be bits')
        key = tuple(row['in'])
        if key in seen:
            raise ValueError('Duplicate truth-table inputs')
        seen.add(key)
    if e['sequential']:
        if not e.get('clock') or not e.get('steps') or e['clock'] not in channel_ids:
            raise ValueError('Sequential experiment needs mapped clock and steps')
        for step in e['steps']:
            if len(step['out']) != len(e['outputs']) or any(v not in (0, 1) for v in step['out']):
                raise ValueError('Invalid expected sequential step')
    for ch, events in e.get('expected_waveforms', {}).items():
        if ch not in channel_ids or not events or events[0][0] != 0:
            raise ValueError('Expected waveform requires mapped channel and initial state at zero')
        if any(t < 0 or v not in (0, 1) for t, v in events):
            raise ValueError('Invalid waveform event')
        if any(events[i][0] <= events[i-1][0] for i in range(1, len(events))):
            raise ValueError('Waveform times must increase')
    return e


def load_data(root):
    channels = json.loads((root / 'channels.json').read_text())
    ids = [c['id'] for c in channels]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate channel ID')
    experiments = [validate_experiment(json.loads(p.read_text()), ids)
                   for p in sorted((root / 'experiments').glob('*.json'))]
    if len({e['id'] for e in experiments}) != len(experiments):
        raise ValueError('Duplicate experiment ID')
    return channels, experiments


class Comparison:
    def __init__(self, experiment):
        self.e = experiment
        self.reset()

    def reset(self):
        self.rows = {}
        self.step = -1
        self.last_clock = None

    def update(self, values, low=800, high=2000):
        def signal(s):
            mv = values.get(s['ch'])
            return dict(s, mv=mv, state=classify(mv, low, high))
        ins, outs = [signal(s) for s in self.e['inputs']], [signal(s) for s in self.e['outputs']]
        bits = [1 if s['state'] == 'HIGH' else 0 if s['state'] == 'LOW' else None for s in ins]
        index = next((i for i, r in enumerate(self.e['truth_table']) if r['in'] == bits), None)
        expected = self.e['truth_table'][index]['out'] if index is not None else None
        if self.e['sequential']:
            clock = classify(values.get(self.e['clock']), low, high)
            if self.last_clock == 'LOW' and clock == 'HIGH':
                self.step += 1
            self.last_clock = clock
            index = self.step if 0 <= self.step < len(self.e['steps']) else None
            expected = self.e['steps'][index]['out'] if index is not None else None
        for n, s in enumerate(outs):
            s['expected'] = expected[n] if expected is not None else None
            s['result'] = ('Not tested' if expected is None else 'UNKNOWN' if s['state'] == 'UNKNOWN'
                           else 'MATCH' if s['state'] == ('HIGH' if expected[n] else 'LOW') else 'DIFF')
        result = ('Not tested' if expected is None or any(s['state'] == 'UNKNOWN' for s in outs)
                  else 'MATCH' if all(s['result'] == 'MATCH' for s in outs) else 'DIFF')
        if index is not None and result != 'Not tested':
            self.rows[index] = {'result': result, 'observed': [s['state'] for s in outs]}
        differences = [f"{s['name']}: expected {'HIGH' if s['expected'] else 'LOW'}, measured {s['state']} ({s['mv']} mV)."
                       for s in outs if s['result'] == 'DIFF']
        return {'inputs': ins, 'outputs': outs, 'active_row': index, 'rows': self.rows.copy(),
                'tested': len(self.rows), 'result': result,
                'observation': ' '.join(differences) or ('Measured outputs match the expected row.' if result == 'MATCH'
                                                       else 'Waiting for valid input and output measurements.')}


def decode_events(events, depth, count):
    """Delta in samples, bit zero is channel zero. First event must be at zero."""
    if type(depth) is not int or depth < 1 or not 1 <= count <= 16 or not events:
        raise ValueError('Invalid capture dimensions')
    decoded, cursor = [], 0
    for i, event in enumerate(events):
        if len(event) != 2:
            raise ValueError('Event requires delta and mask')
        delta, mask = event
        if type(delta) is not int or type(mask) is not int or delta < 0 or not 0 <= mask < (1 << count):
            raise ValueError('Invalid capture event')
        if (i == 0 and delta != 0) or (i > 0 and delta == 0):
            raise ValueError('Initial delta must be zero; later deltas must be positive')
        cursor += delta
        if cursor >= depth:
            raise ValueError('Event exceeds capture depth')
        decoded.append([cursor, mask])
    return decoded


def mismatch_windows(capture, expected):
    """Compare piecewise-constant digital states, aligned at capture start."""
    events = decode_events(capture['ev'], capture['depth'], len(capture['ch']))
    dt, end = capture['dt'], capture['depth'] * capture['dt']
    if dt <= 0:
        raise ValueError('Sample interval must be positive')
    result = []
    for bit, channel in enumerate(capture['ch']):
        ref = expected.get(channel)
        if not ref:
            continue
        actual = [[s * dt, (mask >> bit) & 1] for s, mask in events]
        boundaries = sorted({0, end} | {t for t, _ in actual} | {t for t, _ in ref if 0 <= t < end})
        ai = ri = 0
        for start, stop in zip(boundaries, boundaries[1:]):
            while ai + 1 < len(actual) and actual[ai + 1][0] <= start:
                ai += 1
            while ri + 1 < len(ref) and ref[ri + 1][0] <= start:
                ri += 1
            a, r = actual[ai][1], ref[ri][1]
            if a != r:
                if result and result[-1]['channel'] == channel and result[-1]['end_ns'] == start and result[-1]['expected'] == r:
                    result[-1]['end_ns'] = stop
                else:
                    result.append({'channel': channel, 'start_ns': start, 'end_ns': stop, 'expected': r, 'measured': a})
    return result


def calibration(measured, reference):
    return {'absolute_error_mv': abs(measured - reference),
            'percentage_error': abs(measured-reference)/abs(reference)*100 if reference else None}

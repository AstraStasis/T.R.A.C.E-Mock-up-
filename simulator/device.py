import asyncio
import math
import time
from backend.protocol import decode, encode

CAPABILITIES = {'protocol': 1, 'mode': 'simulator', 'max_channels': 16,
                'max_rate_hz': 10_000_000, 'max_depth': 200_000,
                'scan_hz': 1000, 'publish_hz': 10, 'vic_max_hz': 1000,
                'hardware_verified': False}


def evaluate_ic(ic, pins):
    """Combinational logic only; never an electrical or timing model."""
    out = {}
    for gate in ic.get('gates', []):
        args = [pins.get(str(p), 0) for p in gate['inputs']]
        op = gate['op']
        value = {'AND': lambda: int(all(args)), 'NAND': lambda: int(not all(args)),
                 'OR': lambda: int(any(args)), 'NOT': lambda: 1-args[0]}[op]()
        out[str(gate['output'])] = value
    if ic['id'] == '74138':
        enabled = pins.get('6', 0) == 1 and pins.get('4', 0) == pins.get('5', 0) == 0
        address = sum(pins.get(str(p), 0) << i for i, p in enumerate([1, 2, 3]))
        out = {str(p): int(not (enabled and i == address)) for i, p in enumerate([15, 14, 13, 12, 11, 10, 9, 7])}
    if ic['id'] == '7483':
        a = sum(pins.get(str(p), 0) << i for i, p in enumerate([10, 8, 3, 1]))
        b = sum(pins.get(str(p), 0) << i for i, p in enumerate([11, 7, 4, 16]))
        total = a + b + pins.get('13', 0)
        out = {str(p): (total >> i) & 1 for i, p in enumerate([9, 6, 2, 15, 14])}
    return out


class Simulator:
    def __init__(self, channels, ics):
        self.channels, self.ics = channels, {i['id']: i for i in ics}
        self.queue = asyncio.Queue()
        self.scenario = 'normal'
        self.manual = None
        self.watched = [c['id'] for c in channels]
        self.cap_cfg = None
        self.capture_task = None
        self.counter = 0
        self.ic = None
        self.pins = {}
        self.vcc, self.gnd = 4980, 0
        self.q = [0, 0]
        self.clocks = [0, 0]

    async def emit(self, msg):
        await self.queue.put(decode(encode(msg)))

    async def messages(self):
        await self.emit({'t': 'hello', **CAPABILITIES})
        await self.vic_status()
        try:
            while True:
                try:
                    yield await asyncio.wait_for(self.queue.get(), .1)
                except asyncio.TimeoutError:
                    step = self.manual if self.manual is not None else int(time.monotonic()/2) % 4
                    a, b = (step >> 1) & 1, step & 1
                    now = time.monotonic()
                    vals = {'EXP1_A': a, 'EXP1_B': b, 'EXP1_Y': a & b, 'EXP4_A': a, 'EXP4_B': b}
                    vals.update({f'EXP4_Y{i}': int(step == i) for i in range(4)})
                    if self.scenario in ('fault', 'glitch'):
                        vals['EXP4_Y2'] = 0
                        vals['EXP1_Y'] = 1 - (a & b)
                    ch = []
                    for n, c in enumerate(self.channels):
                        bit = vals.get(c['id'], (int(now * (2 if n % 3 == 0 else 1)) >> (n % 3)) & 1)
                        mv = 4980 + round(8*math.sin(now+n)) if bit else 35+round(5*math.sin(now+n))
                        if self.scenario == 'floating' and c['id'] in ('BB10B', 'EXP1_B', 'EXP4_B'):
                            mv = 1450
                        if c['id'] in self.watched:
                            ch.append({'id': c['id'], 'mv': mv})
                    yield decode(encode({'t': 'frame', 'ts': round(now*1000), 'ch': ch}))
        finally:
            if self.capture_task:
                self.capture_task.cancel()

    async def command(self, cmd):
        cmd = decode(encode(cmd))
        kind = cmd['t']
        if kind == 'watch':
            self.watched = cmd['ids']
        elif kind == 'sim_set':
            self.scenario = cmd.get('scenario', self.scenario)
            self.manual = cmd.get('inputs', self.manual)
        elif kind == 'cap_cfg':
            self.cap_cfg = cmd
        elif kind == 'cap_arm':
            if self.capture_task and not self.capture_task.done():
                raise ValueError('Capture already armed')
            self.capture_task = asyncio.create_task(self.capture(cmd['capture_id']))
        elif kind == 'cap_stop':
            if self.capture_task:
                self.capture_task.cancel()
            await self.emit({'t': 'cap_stopped'})
        elif kind == 'vic_power':
            self.vcc, self.gnd = cmd['vcc_mv'], cmd['gnd_mv']
            if not self.power_ok():
                self.ic = None
            await self.vic_status()
        elif kind == 'vic_load':
            if not self.power_ok():
                raise ValueError('Dock power outside accepted range')
            self.ic = cmd['ic']
            self.pins, self.q, self.clocks = {}, [0, 0], [0, 0]
            if self.ic == '7474':
                self.pins = {str(p): 1 for p in (1, 4, 10, 13)}
            await self.vic_status()
        elif kind == 'vic_release':
            self.ic = None
            await self.vic_status()
        elif kind == 'vic_pin':
            self.pins[str(cmd['pin'])] = cmd['value']
            await self.vic_status()
        elif kind not in ('cfg', 'hello'):
            raise ValueError('Unsupported command')
        if kind == 'hello':
            await self.emit({'t': 'hello', **CAPABILITIES})
        await self.emit({'t': 'ack', 'cmd': kind, 'id': cmd.get('id')})

    def power_ok(self):
        return 4500 <= self.vcc <= 5500 and abs(self.gnd) <= 100

    async def vic_status(self):
        if self.ic:
            if self.ic == '7474':
                for i, (pre, clr, d, clk, q, nq) in enumerate([(4, 1, 2, 3, 5, 6), (10, 13, 12, 11, 9, 8)]):
                    p, c = self.pins.get(str(pre), 1), self.pins.get(str(clr), 1)
                    clock = self.pins.get(str(clk), 0)
                    if not p and not c:
                        self.pins[str(q)] = self.pins[str(nq)] = 1
                        self.clocks[i] = clock
                        continue
                    if not p: self.q[i] = 1
                    elif not c: self.q[i] = 0
                    elif not self.clocks[i] and clock: self.q[i] = self.pins.get(str(d), 0)
                    self.clocks[i] = clock
                    self.pins[str(q)], self.pins[str(nq)] = self.q[i], 1-self.q[i]
            else:
                self.pins.update(evaluate_ic(self.ics[self.ic], self.pins))
        await self.emit({'t': 'vic_status', 'ic': self.ic, 'vcc_mv': self.vcc, 'gnd_mv': self.gnd,
                         'state': 'ready' if self.ic else 'released' if self.power_ok() else 'power fault',
                         'pins': self.pins if self.ic else {}, 'max_hz': 1000, 'hardware_verified': False})

    async def capture(self, capture_id):
        cfg = self.cap_cfg
        await asyncio.sleep(.15)
        depth, pre, channels = cfg['depth'], cfg['pre'], cfg['ch']
        source = channels.index(cfg['trig']['src'])
        edge = cfg['trig']['edge']
        period = max(1, round(cfg['rate'] / 1000))

        def value(channel, step):
            a, b = (step >> 1) & 1, step & 1
            if channel.endswith('_A'): return a
            if channel.endswith('_B'): return b
            if channel == 'EXP1_Y': return (a & b) ^ int(self.scenario == 'fault')
            if channel.startswith('EXP4_Y'):
                output = int(channel[-1])
                return 0 if self.scenario == 'fault' and output == 2 else int((step % 4) == output)
            column = int(channel[2:4])
            if column >= 15: return column % 2  # static logic levels
            return (step >> ((column-1) % 4)) & 1

        target = None
        for step in range(1, 33):
            before, after = value(channels[source], step-1), value(channels[source], step)
            if before != after and (edge == 'either' or edge == 'rise' and after == 1 or edge == 'fall' and after == 0):
                target = step
                break
        if target is None:
            # Static selected source cannot trigger. Remain armed until cancelled.
            return
        phase = target * period - pre
        points = {0, pre}
        first = (-phase) % period
        points.update(range(first, depth, period))
        glitch_start = max(1, depth//2)
        glitch_end = min(depth-1, glitch_start + max(1, round(cfg['rate'] / 1_000_000)))
        if self.scenario == 'glitch': points |= {glitch_start, glitch_end}
        events, previous, mask = [], 0, None
        for sample in sorted(points):
            if sample >= depth: continue
            step = (sample + phase) // period
            new = sum(value(ch, step) << bit for bit, ch in enumerate(channels))
            if self.scenario == 'glitch' and glitch_start <= sample < glitch_end:
                glitch_bit = next((i for i in reversed(range(len(channels))) if i != source), source)
                new ^= 1 << glitch_bit
            if new != mask:
                events.append([sample-previous, new])
                previous, mask = sample, new
        await self.emit({'t': 'cap_data', 'capture_id': capture_id, 'seq': 0, 't0': 0,
                         'dt': 1_000_000_000/cfg['rate'], 'depth': depth, 'ch': channels,
                         'trigger_index': pre, 'ev': events})
        await self.emit({'t': 'cap_done', 'capture_id': capture_id, 'chunks': 1,
                         'overflow': self.scenario == 'overflow', 'dropped_samples': 32 if self.scenario == 'overflow' else 0})

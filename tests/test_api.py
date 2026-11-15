import asyncio
import time
import pytest
from fastapi.testclient import TestClient
from backend.app import app, Runtime, CaptureConfig
from backend.logic import decode_events


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('TRACE_DEVICE','simulator')
    monkeypatch.setenv('TRACE_RESEARCH_PIN','test-pin')
    with TestClient(app) as c:
        for _ in range(40):
            if c.get('/api/state').json()['linked']:break
            time.sleep(.02)
        yield c


def test_bootstrap_and_offline_assets(client):
    b=client.get('/api/bootstrap').json()
    assert len(b['experiments'])==2 and len(b['ics'])==7
    assert b['state']['mode']=='simulator'
    assert client.get('/').status_code==200
    assert client.get('/assets/app.js').status_code==200
    assert '<svg' in client.get('/api/qr.svg').text
    assert client.post('/api/simulator',json={'scenario':'fault','inputs':3}).status_code==200
    time.sleep(.15)
    assert client.get('/api/state').json()['experiments']['EXP1']['result']=='DIFF'


def test_validation_and_cross_origin(client):
    assert client.post('/api/settings',json={'low':2000,'high':800}).status_code==422
    assert client.post('/api/simulator',json={'inputs':4}).status_code==422
    assert client.post('/api/simulator',json={},headers={'Origin':'https://other.example'}).status_code==403
    assert client.post('/api/experiments/UNKNOWN/reset').status_code==404


def test_capture_single_trigger_and_export(client):
    cfg={'ch':['BB01A','BB02A'],'rate':1000000,'depth':2000,'pre':200,'source':'BB01A','edge':'fall','experiment':'EXP4'}
    assert client.post('/api/capture/start',json=cfg).status_code==200
    assert client.post('/api/capture/start',json=cfg).status_code==409
    time.sleep(.3)
    c=client.get('/api/capture').json()
    events=decode_events(c['ev'],c['depth'],2)
    assert c['trigger_index']==200
    assert next(mask&1 for sample,mask in events if sample==200)==0
    assert events[0][1]&1==1
    assert client.get('/api/capture/export/vcd').text.startswith('$timescale 1ns')
    assert client.get('/api/capture/export/json').json()['capture_id']==c['capture_id']
    assert client.post('/api/capture/start',json={**cfg,'rate':10000001}).status_code==422
    assert client.post('/api/capture/start',json={**cfg,'ch':['BB01A','BB01A']}).status_code==422


def test_continuous_stop_and_overflow(client):
    client.post('/api/simulator',json={'scenario':'overflow'})
    cfg={'ch':['BB01A'],'rate':100000,'depth':1000,'pre':100,'source':'BB01A','continuous':True}
    client.post('/api/capture/start',json=cfg)
    time.sleep(.25); first=client.get('/api/capture').json()['capture_id']
    time.sleep(.25); second=client.get('/api/capture').json()
    assert first!=second['capture_id'] and second['overflow']
    client.post('/api/capture/stop',json={})
    time.sleep(.1); assert client.get('/api/state').json()['capture_status']=='stopped'


def test_dock_power_guard_and_input_direction(client):
    assert client.post('/api/dock',json={'action':'load','ic':'7400'}).status_code==200
    assert client.post('/api/dock',json={'action':'pin','pin':3,'value':1}).status_code==422
    for p in [1,2]:client.post('/api/dock',json={'action':'pin','pin':p,'value':1})
    time.sleep(.05); assert client.get('/api/state').json()['dock']['pins']['3']==0
    client.post('/api/dock',json={'action':'power','vcc_mv':4000,'gnd_mv':0})
    assert client.post('/api/dock',json={'action':'load','ic':'7400'}).status_code==409
    time.sleep(.05); assert client.get('/api/state').json()['dock']['ic'] is None


def test_d_flip_flop_rising_edge_and_async_clear(client):
    client.post('/api/dock',json={'action':'load','ic':'7474'})
    for p,v in [(2,1),(3,1)]:client.post('/api/dock',json={'action':'pin','pin':p,'value':v})
    time.sleep(.05); assert client.get('/api/state').json()['dock']['pins']['5']==1
    client.post('/api/dock',json={'action':'pin','pin':2,'value':0})
    time.sleep(.05); assert client.get('/api/state').json()['dock']['pins']['5']==1
    client.post('/api/dock',json={'action':'pin','pin':1,'value':0})
    time.sleep(.05); assert client.get('/api/state').json()['dock']['pins']['5']==0


def test_diagnostics_pin_and_no_fake_measurements(client):
    assert client.get('/api/diagnostics').status_code==403
    h={'X-Research-Pin':'test-pin'}
    r=client.post('/api/diagnostics',headers=h,json={'channel':'EXP1_A','reference_mv':0,'tolerance_mv':5000})
    assert r.status_code==200 and r.json()['percentage_error'] is None and r.json()['mode']=='simulator'
    assert client.get('/api/diagnostics',headers=h).json()['pass_rate']==100
    assert 'simulator' in client.get('/api/diagnostics/export',headers=h).text


def test_websocket(client):
    with client.websocket_connect('/ws') as ws:
        assert ws.receive_json()['mode']=='simulator'


def test_default_capture_matches_reference_and_glitch_differs(client):
    cfg={'ch':['EXP4_A','EXP4_B','EXP4_Y0','EXP4_Y1','EXP4_Y2','EXP4_Y3'],
         'rate':1000000,'depth':20000,'pre':2000,'source':'EXP4_A','experiment':'EXP4'}
    client.post('/api/capture/start',json=cfg)
    time.sleep(.25)
    assert client.get('/api/capture').json()['mismatches']==[]
    client.post('/api/simulator',json={'scenario':'glitch'})
    client.post('/api/capture/start',json=cfg)
    time.sleep(.25)
    windows=client.get('/api/capture').json()['mismatches']
    assert len(windows)==1 and windows[0]['end_ns']-windows[0]['start_ns']==1000


def test_sixteen_channels_and_static_source(client):
    ch=[f'BB{i:02}A' for i in range(1,17)]
    cfg={'ch':ch,'source':'BB01A','rate':10000000,'depth':200000,'pre':20000}
    client.post('/api/capture/start',json=cfg);time.sleep(.25)
    capture=client.get('/api/capture').json()
    assert len(capture['ch'])==16
    assert decode_events(capture['ev'],capture['depth'],16)
    client.post('/api/capture/start',json={**cfg,'source':'BB16A'})
    time.sleep(.25)
    assert client.get('/api/state').json()['capture_status']=='armed'
    client.post('/api/capture/stop',json={})


def test_capture_rejects_out_of_order_and_stale_messages():
    async def check():
        r=Runtime();r.cfg=CaptureConfig(ch=['BB01A'],source='BB01A',depth=10,pre=2)
        r.pending={'capture_id':'new','ev':[],'next_seq':0}
        await r.ingest({'t':'cap_done','capture_id':'old'})
        assert r.pending['capture_id']=='new'
        with pytest.raises(ValueError):await r.ingest({'t':'cap_data','capture_id':'new','seq':2})
        await r.ingest({'t':'disconnected'})
        assert r.pending is None and not r.snapshot()['linked']
    asyncio.run(check())


def test_concept_experiment_and_rehearsal_endpoints(client):
    exps=client.get('/api/concept/experiments').json()['experiments']
    assert len(exps)==15 and exps[3]['title']=='NOR and NAND gates'
    client.post('/api/concept/command',json={'action':'disconnect'})
    assert client.post('/api/concept/rehearsal-input',json={'signal':'1A','value':1}).status_code==409
    assert client.post('/api/concept/rehearsal-input',json={'signal':'1A','value':2}).status_code==422
    client.post('/api/concept/command',json={'action':'connect'})
    st=client.get('/api/concept/state').json()
    m=next(x for x in st['models'] if x['id']=='74LS00')
    cfg=client.post('/api/concept/command',json={'action':'configure','model':'74LS00','assignments':{s['name']:s['node'] for s in m['signals']}}).json()
    client.post('/api/concept/command',json={'action':'activate','config_id':cfg['configuration']['id']})
    r=client.post('/api/concept/rehearsal-input',json={'signal':'1A','value':1}).json()
    assert {x['name']:x['state'] for x in r['signal_states']}['1A']=='HIGH'
    assert r['hardware_connected'] is False
    client.post('/api/concept/command',json={'action':'disconnect'})

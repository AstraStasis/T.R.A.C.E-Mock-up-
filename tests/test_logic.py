import copy
import json
from pathlib import Path
import pytest
from backend.logic import classify, load_data, validate_experiment, Comparison, decode_events, mismatch_windows, calibration
from backend.protocol import decode, encode
from simulator.device import evaluate_ic

ROOT = Path(__file__).resolve().parents[1]
channels, experiments = load_data(ROOT/'data')


@pytest.mark.parametrize('mv,expected',[(0,'LOW'),(800,'LOW'),(801,'FLOATING'),(1999,'FLOATING'),(2000,'HIGH'),(5000,'HIGH'),(None,'UNKNOWN')])
def test_threshold_boundaries(mv,expected):
    assert classify(mv)==expected


@pytest.mark.parametrize('lo,hi',[(900,800),(800,800),(-1,2000),(800,6000)])
def test_threshold_validation(lo,hi):
    with pytest.raises(ValueError): classify(1000,lo,hi)


def test_truth_table_matching_fault_and_missing():
    c=Comparison(experiments[0])
    assert c.update({'EXP1_A':5000,'EXP1_B':5000,'EXP1_Y':5000})['result']=='MATCH'
    assert c.update({'EXP1_A':5000,'EXP1_B':5000,'EXP1_Y':0})['result']=='DIFF'
    assert c.update({'EXP1_A':5000,'EXP1_B':1400,'EXP1_Y':0})['active_row'] is None
    assert c.update({'EXP1_A':5000,'EXP1_B':5000})['result']=='Not tested'
    assert len(c.rows)==1
    c.reset(); assert c.rows=={}


@pytest.mark.parametrize('bad', ['width','channel','duplicate','bit'])
def test_experiment_validation(bad):
    e=copy.deepcopy(experiments[0])
    if bad=='width': e['truth_table'][0]['out']=[0,1]
    if bad=='channel': e['inputs'][0]['ch']='MISSING'
    if bad=='duplicate': e['truth_table'].append(e['truth_table'][0])
    if bad=='bit': e['truth_table'][0]['out']=[2]
    with pytest.raises(ValueError): validate_experiment(e,{c['id'] for c in channels})


def test_sequential_steps_require_observed_rising_edge():
    e=copy.deepcopy(experiments[0]);e.update(sequential=True,clock='EXP1_A',steps=[{'out':[1]},{'out':[0]}])
    c=Comparison(validate_experiment(e,{c['id'] for c in channels}))
    assert c.update({'EXP1_A':5000,'EXP1_B':0,'EXP1_Y':5000})['active_row'] is None
    c.update({'EXP1_A':0,'EXP1_B':0,'EXP1_Y':5000})
    assert c.update({'EXP1_A':5000,'EXP1_B':0,'EXP1_Y':5000})['result']=='MATCH'
    assert c.update({'EXP1_A':5000,'EXP1_B':0,'EXP1_Y':5000})['active_row']==0


@pytest.mark.parametrize('events',[[[1,0]],[[0,0],[0,1]],[[0,4]],[[0,0],[10,1]],[[0,-1]],[[0,0],[1.5,1]]])
def test_invalid_capture(events):
    with pytest.raises(ValueError):decode_events(events,10,2)


def test_capture_decode_and_overlay():
    c={'ev':[[0,0],[3,1],[4,0]],'depth':10,'ch':['A'],'dt':100}
    assert decode_events(c['ev'],10,1)==[[0,0],[3,1],[7,0]]
    assert mismatch_windows(c,{'A':[[0,0],[500,1],[800,0]]})==[
        {'channel':'A','start_ns':300,'end_ns':500,'expected':0,'measured':1},
        {'channel':'A','start_ns':700,'end_ns':800,'expected':1,'measured':0}]
    assert mismatch_windows(c,{'A':[[0,0],[300,1],[700,0]]})==[]


def test_zero_reference_and_percentage_error():
    assert calibration(20,0)['percentage_error'] is None
    assert calibration(4900,5000)['percentage_error']==2


def test_protocol_rejects_invalid_and_roundtrips():
    msg={'t':'frame','ts':10,'ch':[{'id':'BB01A','mv':4980}]}
    assert decode(encode(msg))==msg
    for raw in [b'[]',b'{"t":12}',b'{"t":"frame","mv":NaN}',b'x'*262145]:
        with pytest.raises(ValueError):decode(raw)


library=json.loads((ROOT/'data/ics/library.json').read_text())
@pytest.mark.parametrize('id,fn',[('7400',lambda a,b:1-(a&b)),('7408',lambda a,b:a&b),('7432',lambda a,b:a|b)])
def test_all_quad_gate_truth_tables(id,fn):
    ic=next(i for i in library if i['id']==id)
    for gate in ic['gates']:
        for a in [0,1]:
            for b in [0,1]:
                assert evaluate_ic(ic,{str(gate['inputs'][0]):a,str(gate['inputs'][1]):b})[str(gate['output'])]==fn(a,b)


def test_inverter_decoder_and_full_adder_exhaustive():
    inv=next(i for i in library if i['id']=='7404')
    for gate in inv['gates']:
        for a in [0,1]: assert evaluate_ic(inv,{str(gate['inputs'][0]):a})[str(gate['output'])]==1-a
    dec=next(i for i in library if i['id']=='74138')
    for a in range(8):
        out=evaluate_ic(dec,{'1':a&1,'2':(a>>1)&1,'3':a>>2,'6':1,'4':0,'5':0})
        assert list(out.values())==[int(i!=a) for i in range(8)]
    assert all(evaluate_ic(dec,{'6':0}).values())
    adder=next(i for i in library if i['id']=='7483')
    for a in range(16):
        for b in range(16):
            for carry in [0,1]:
                pins={str(p):(a>>i)&1 for i,p in enumerate([10,8,3,1])}
                pins.update({str(p):(b>>i)&1 for i,p in enumerate([11,7,4,16])});pins['13']=carry
                out=evaluate_ic(adder,pins)
                assert sum(out[str(p)]<<i for i,p in enumerate([9,6,2,15,14]))==a+b+carry

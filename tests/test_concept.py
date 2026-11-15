import asyncio
import time
import pytest
from backend.concept import ConceptSession, MODELS, validate_map, state_for


def assignments(model='74LS00'):
    return {s['name']: s['node'] for s in MODELS[model]['signals']}


@pytest.mark.parametrize('mv,valid,age,expected',[(800,True,0,'LOW'),(2000,True,0,'HIGH'),(1250,True,0,'UNDEFINED'),(None,True,0,'UNAVAILABLE'),(0,False,0,'UNAVAILABLE'),(5000,True,4000,'UNAVAILABLE')])
def test_measurement_meaning(mv,valid,age,expected):
    assert state_for(mv,valid,age)==expected


def test_map_conflicts_and_reserved_nodes():
    good=assignments();validate_map('74LS00',good)
    for bad in [{**good,'1Y':good['1A']},{**good,'1Y':'VCC'},{'1Y':good['1Y']}]:
        with pytest.raises(ValueError):validate_map('74LS00',bad)


def test_disconnected_examples_never_imply_hardware():
    s=ConceptSession()
    assert not s.snapshot()['hardware_connected']
    assert all(r['state']=='UNAVAILABLE' for r in s.measurements())
    assert s.measurements(True)[2]['state']=='UNDEFINED'
    assert not s.snapshot()['outputs_enabled']


def test_activation_lifecycle_ack_and_restart():
    async def check():
        s=ConceptSession()
        with pytest.raises(ValueError):await s.command('activate')
        await s.command('connect')
        await s.command('configure','74LS00',assignments())
        cid=s.configuration['id']
        with pytest.raises(ValueError):await s.command('activate',config_id='old')
        task=asyncio.create_task(s.command('activate',config_id=cid))
        await asyncio.sleep(.01)
        assert s.pending and not s.outputs_enabled
        await task
        assert s.outputs_enabled and s.last_ack['configuration_id']==cid
        with pytest.raises(ValueError):await s.command('configure','74LS00',assignments())
        await s.command('deactivate')
        assert not s.outputs_enabled and s.configuration is None
        await s.command('disconnect');await s.command('connect')
        assert s.phase=='connected and inactive' and not s.outputs_enabled
    asyncio.run(check())


def test_watchdog_and_protection_invalidate_configuration():
    async def check():
        s=ConceptSession();await s.command('connect')
        await s.command('configure','74LS00',assignments())
        await s.command('activate',config_id=s.configuration['id'])
        s.last_heartbeat=time.monotonic()-6
        assert s.snapshot()['phase']=='interlocked'
        assert not s.outputs_enabled and s.configuration is None
        with pytest.raises(ValueError):await s.command('activate')
        await s.command('connect');await s.command('trip')
        assert s.phase=='interlocked'
    asyncio.run(check())


def test_unresolved_7476_is_not_executable():
    async def check():
        s=ConceptSession();await s.command('connect')
        with pytest.raises(ValueError,match='variant'):await s.command('configure','7476',assignments('7476'))
        assert not s.outputs_enabled
    asyncio.run(check())


def test_rehearsal_pin_reports_only_while_active():
    from backend.concept import EXPERIMENT_FILE  # noqa: F401  (module import check)
    async def check():
        s=ConceptSession()
        assert s.snapshot()['signal_states'] is None
        await s.command('connect');await s.command('configure','74LS00',assignments())
        assert s.snapshot()['signal_states'] is None
        with pytest.raises(ValueError):s.set_input('1A',1)
        await s.command('activate',config_id=s.configuration['id'])
        states={r['name']:r for r in s.snapshot()['signal_states']}
        assert states['1A']['state']=='LOW' and states['1Y']['state']=='HIGH'
        assert all(r['source']=='simulated rehearsal report' for r in states.values())
        s.set_input('1A',1);s.set_input('1B',1)
        states={r['name']:r['state'] for r in s.snapshot()['signal_states']}
        assert states['1Y']=='LOW' and states['2Y']=='HIGH'
        with pytest.raises(ValueError):s.set_input('1Y',0)
        with pytest.raises(ValueError):s.set_input('9Z',1)
        await s.command('deactivate')
        assert s.snapshot()['signal_states'] is None and s.inputs=={}
    asyncio.run(check())


def test_watchdog_clears_rehearsal_inputs():
    async def check():
        s=ConceptSession();await s.command('connect')
        await s.command('configure','74LS00',assignments())
        await s.command('activate',config_id=s.configuration['id'])
        s.set_input('1A',1)
        s.last_heartbeat=time.monotonic()-6
        assert s.snapshot()['signal_states'] is None and s.inputs=={}
    asyncio.run(check())


def test_experiment_data_file_is_valid_and_not_fabricated():
    from backend.concept import load_experiments
    items=load_experiments()
    assert [e['id'] for e in items]==list(range(1,16))
    assert items[3]['title']=='NOR and NAND gates'
    assert items[3]['inputs']==['A / SWA','B / SWB','C / SWC']
    assert items[5]['inputs'][0]=='I7' and items[5]['inputs'][-1]=='I0'
    assert all(e['truth_table'] is None for e in items)


@pytest.mark.parametrize('mutate',[
    lambda d: d.__setitem__(0, None),
    lambda d: d[0].update(id='1'),
    lambda d: d[0].update(truth_table=[]),
    lambda d: d[0].update(truth_table={'columns':['A'],'rows':[[{}]]}),
    lambda d: d.pop(),
    lambda d: d[0].update(title=''),
    lambda d: d[0].update(inputs=[]),
    lambda d: d[0].update(truth_table={'columns':['A','Y'],'rows':[['0']]}),
    lambda d: d[0].update(truth_table={'columns':['A','Y'],'rows':[['0','2']]}),
    lambda d: d[0].update(truth_table={'columns':['A','A'],'rows':[['0','1']]}),
])
def test_experiment_validation_rejects_malformed(mutate):
    import copy
    from backend.concept import load_experiments, validate_experiments
    data=copy.deepcopy(load_experiments());mutate(data)
    with pytest.raises(ValueError):validate_experiments(data)


def test_experiment_validation_accepts_truth_table():
    import copy
    from backend.concept import load_experiments, validate_experiments
    data=copy.deepcopy(load_experiments())
    data[3]['truth_table']={'columns':['A','B','Y'],'rows':[['0','0','1'],['1','X','0']]}
    assert validate_experiments(data)[3]['truth_table']['rows'][1]==['1','X','0']


def test_shutdown_only_completes_an_activated_cycle():
    async def check():
        s=ConceptSession();await s.command('connect')
        await s.command('deactivate')
        assert not s.snapshot()['cycle_completed']
        await s.command('configure','74LS00',assignments())
        await s.command('activate',config_id=s.configuration['id'])
        await s.command('deactivate')
        assert s.snapshot()['cycle_completed']
        await s.command('configure','74LS00',assignments())
        assert not s.snapshot()['cycle_completed']
    asyncio.run(check())


@pytest.mark.parametrize('value',[-1,2,True,'1',None])
def test_rehearsal_rejects_invalid_logic_values(value):
    async def check():
        s=ConceptSession();await s.command('connect')
        await s.command('configure','74LS00',assignments())
        await s.command('activate',config_id=s.configuration['id'])
        with pytest.raises(ValueError):s.set_input('1A',value)
    asyncio.run(check())

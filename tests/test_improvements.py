import sys,inspect,pickle
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from stage2_abm.model import *

def observation(name,value):
    return Observation(name,value,0,1,'digital:0',name)

def test_uncertainty_uses_visible_evidence_and_does_not_touch_memory():
    m=Memory([Case({'digital_open0':1.,'age0':1.},{'onsite_open0':1.},0,0,'test') for _ in range(5)])
    before=pickle.dumps(m)
    target,details=select_practice_target([observation('open0',1),observation('open1',1)],m,Config(),1)
    assert target=='open1' and details[1]['entropy']>details[0]['entropy']
    assert pickle.dumps(m)==before
    assert list(inspect.signature(select_practice_target).parameters)==['observations','memory','cfg','tick']

def test_missing_exit_has_priority():
    assert select_practice_target([observation('open0',1)],Memory(),Config(),1)[0]=='open1'

def test_venue_rejects_opposite_signal_only_when_enabled():
    m=Memory([Case({'digital_open0':1.,'age0':1.},{'onsite_open0':1.},0,0,'test')])
    obs=[observation('open0',0)]
    assert venue_estimates(obs,m,Config(),1)[0]['open0']==1
    assert venue_estimates(obs,m,Config(matched_venue_signal=True),1)[0]['open0']==0

def test_command_small_support_falls_back_without_using_outcome_sign():
    info={'open0':1,'open1':1};features={'open0':1}
    cases=[Case(features,{'completed':60,'v_completed':12},0,0,'test',
        {'published_plan':0,'publish':6,'scenario':scenario_key(DISTANCES,(6,5)),
         'routes':(0,0,0),'priority':[0,1,2]}) for _ in range(2)]
    cfg=Config(exact_execution_match=True,command_min_support=3)
    assert command_score(0,info,features,Memory(cases),DISTANCES,(6,5),6,cfg)[1]==[]
    cases.append(deepcopy(cases[0]))
    assert len(command_score(0,info,features,Memory(cases),DISTANCES,(6,5),6,cfg)[1])==3

def test_no_extra_practice_slots_or_budget():
    cfg=Config(adaptive_practice=True)
    for e in range(12):
        state=TeamSnapshot([Memory() for _ in ROLES])
        r=simulate(world(961001,'unit',e,cfg),state,'G2',cfg,learn=True,trace=True)
        actions=r['trace']['actions']
        assert sum(a['action']=='practice_observe' for a in actions)<=1
        assert all(sum(a['role']==role for a in actions)<=cfg.budget for role in range(4))
        for d in r['target_choices']:assert d['selected'] in ('open0','open1')

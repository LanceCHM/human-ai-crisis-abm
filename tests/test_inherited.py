import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from stage2_abm.model import *
import hashlib,pickle
def digest(obj):return hashlib.sha256(pickle.dumps(obj)).hexdigest()

def test_world_pairing():
    w=world(7,'train',2,Config())
    assert w==world(7,'train',2,Config())
    assert len(w.regions)==60 and sum(w.vulnerable)==12
    assert sorted(w.regions.count(z) for z in range(3))==[12,20,28]

def test_every_role_has_initial_observed_cases():
    c=Config();team=initial_team(10,c)
    assert all(len(m.cases)>=12 for m in team.memories)
    assert all('completed' in case.labels for m in team.memories for case in m.cases if case.source=='mixed-visible')

def test_memory_hand_calculation():
    m=Memory([Case({'warn0':0},{'fail0':0},0,0,'a'),Case({'warn0':1},{'fail0':1},0,0,'b')])
    assert abs(m.predict({'warn0':0},'fail0',.35,Config())-1/3)<1e-12
    assert m.predict({'n0':5},'fail0',.35,Config())==.35

def test_holdout_is_read_only():
    c=Config();team=initial_team(6,c);h=digest(team)
    w=world(6,'holdout',0,c)
    a=simulate(w,team,'G1',c,trace=True)
    b=simulate(w,team,'G1',c,trace=True)
    assert a==b and digest(team)==h
    for msg in a['trace']['messages']:assert msg['processed']>=msg['sent']+1

def test_no_ai_manipulation_is_inert():
    c=Config();s=initial_team(7,c);w=world(7,'holdout',0,c)
    assert simulate(w,s,'G0',c)==simulate(w,s,'G0',c,manipulate=True)

def test_public_capacity_and_conservation():
    c=Config();w=world(9,'public',0,c)
    out=execute_public(w.regions,w.vulnerable,w.order,w.distances,w.capacities,(0,0,0),[0,1,2],1,lambda t:(False,False),True)
    assert out['completed']<=60 and out['v_completed']<=12
    for t in range(1,15):assert out['arrivals'].count(t)<=6
    for row in out['trajectory']:assert len([p for p,_ in row['helpers'] if p>=0])==len(set(p for p,_ in row['helpers'] if p>=0))

def test_hand_computed_single_exit():
    out=execute_public([0]*60,[False]*60,list(range(60)),((3.,5.),)*3,(1,1),(0,0,0),[0,1,2],1,lambda t:(False,False))
    # First arrival tick 4, one exit admits one per tick through tick 14.
    assert out['completed']==11

def test_visible_information_controls_route():
    assert routes(4,{'open0':0,'open1':1},DISTANCES)==(1,1,1)
    assert not legal(0,{'open0':0},DISTANCES)

def test_memory_learning_changes_forecast():
    c=Config();m=Memory();before=m.predict({'warn0':1},'fail0',.35,c)
    m.add({'warn0':1},{'fail0':1},'observed-closure',c)
    assert before==.35 and m.predict({'warn0':1},'fail0',.35,c)==1

def test_role_whitelist_and_packet_availability():
    import pytest
    c=Config(field_available=0.)
    w=world(1,'privacy',0,c)
    with pytest.raises(ValueError):channel(w,3,2,c,True,'open0')
    with pytest.raises(ValueError):channel(w,2,2,c,True,'open0')
    assert all(o.value is None for o in channel(w,0,2,c,True,'open0'))

def test_command_supervises_through_paid_messages():
    c=Config();s=initial_team(123,c)
    r=simulate(world(123,'supervision',0,c),s,'G1',c,trace=True)
    commands=[a for a in r['trace']['actions'] if a['role']==3]
    assert all(a['action'] not in ('observe','requested_observe') for a in commands)

def test_all_closed_means_explicit_wait():
    info={'open0':0,'open1':0}
    assert not legal(4,info,DISTANCES)
    assert choose_plan(info,DISTANCES,(6,5),6,Config())==-1

def test_conflict_denominator_uses_relevant_received_fields():
    report=AIReport((),{'open0':1.,'open1':0.,'warn0':0.},0,0)
    assert conflict_ratio({},report,DISTANCES)==0
    assert conflict_ratio({'open0':1.,'open1':1.},report,DISTANCES)==0
    assert conflict_ratio({'open0':0.},report,DISTANCES)==1

def test_fixed_release_and_budget():
    c=Config();s=initial_team(3,c)
    for group in ('G0','G1','G2'):
        r=simulate(world(3,'fixed',1,c),s,group,c,fixed=True,trace=True)
        assert r['publish']==6
        for actor in range(4):
            acts=[x for x in r['trace']['actions'] if x['role']==actor]
            assert len(acts)<=6 and len({a['tick'] for a in acts})==len(acts)

def test_policy_has_no_world_parameter():
    import inspect
    for function in (prediction,choose_plan,score_plan,ai_report):assert 'w' not in inspect.signature(function).parameters

def test_branch_reachability():
    c=Config();s=initial_team(123,c);counts={k:0 for k in ('direct_adopt','verification','verified','practice_complete')}
    for e in range(50):
        for g in ('G1','G2'):
            r=simulate(world(123,'branches',e,c),s,g,c,manipulate=True)
            for k in counts:counts[k]+=r[k]
    assert all(counts.values()),counts

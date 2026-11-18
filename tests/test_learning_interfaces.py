import sys
from pathlib import Path
from copy import deepcopy
import pickle
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from stage2_abm.model import *

def obs(name,value,observed=0,available=1,onsite=False):
    source=f'test:0:0:{name}:{available}:{int(onsite)}'
    return Observation(name,value,observed,available,source,source)

def test_venue_pair_uses_pre_observation_features_and_actual_label():
    d=obs('open0',0); warning=obs('warn0',1)
    field=obs('open0',1,2,2,True)
    pair=venue_training_pairs([d,warning],[field],2)[0]
    assert pair['features']=={'digital_open0':0,'age0':2.,'warn0':1}
    assert pair['labels']=={'onsite_open0':1}
    assert field.original not in pair['provenance']['feature_evidence']
    assert not venue_training_pairs([d],[obs('open0',None,2,2,True)],2)

def test_venue_probability_threshold_and_exact_age():
    case=Case({'digital_open0':0,'age0':1.},{'onsite_open0':1.},0,0,'observed')
    memory=Memory([case]);cfg=Config()
    p,s=venue_estimates([obs('open0',0)],memory,cfg,1)
    assert p['open0']==1 and s['open0']['cases']==[0]
    p,s=venue_estimates([obs('open0',0)],memory,cfg,2)
    assert p['open0']==0 and s['open0']['kind']=='fallback'

def test_venue_current_field_evidence_overrides_memory():
    case=Case({'digital_open0':1,'age0':1.},{'onsite_open0':1.},0,0,'observed')
    evidence=[obs('open0',1),obs('open0',0,1,1,True)]
    pred=prediction(evidence,Memory([case]),Config(),role=0,tick=1)
    assert pred['open0']==0
    assert merge_judgments(evidence,{'open0':1})['open0']==0

def test_venue_constructed_memory_changes_route_without_extra_observation():
    cfg=Config();evidence=[obs('open0',1),obs('open1',1)]
    m=Memory([Case({'digital_open0':1,'age0':1.},{'onsite_open0':0.},0,0,'observed')])
    a=prediction(evidence,Memory(),cfg,role=0,tick=1)
    b=prediction(evidence,m,cfg,role=0,tick=1)
    assert routes(4,a,DISTANCES)!=(routes(4,b,DISTANCES))
    assert len(evidence)==2

def experience(plan=0,publish=3,completed=60,features=None):
    return Case(features or {'open0':1},{'completed':completed,'v_completed':12},0,0,'actual-feedback',
        {'published_plan':plan,'publish':publish,'scenario':scenario_key(DISTANCES,(6,5)),
         'routes':(0,0,0),'priority':[0,1,2]})

def test_command_score_uses_observed_action_and_common_features_only():
    cfg=Config();m=Memory([experience()]);info={'open0':1,'open1':1}
    score,support=command_score(0,info,{'open0':1},m,DISTANCES,(6,5),3,cfg)
    assert score[:2]==(1.,1.) and support==[0]
    for p,t,features in [(1,3,{'open0':1}),(0,6,{'open0':1}),(0,3,{'n0':12})]:
        a,s=command_score(p,info,features,m,DISTANCES,(6,5),t,cfg)
        base=score_plan(p,info,DISTANCES,(6,5),t,cfg)
        assert not s and a==(base[0]/60,base[1]/12,base[2])

def test_command_missing_feedback_and_scenario_fall_back():
    c=experience();del c.labels['v_completed']
    assert not command_score(0,{'open0':1},{'open0':1},Memory([c]),DISTANCES,(6,5),3,Config())[1]
    assert not command_score(0,{'open0':1},{'open0':1},Memory([experience()]),DISTANCES,(4,7),3,Config())[1]

def test_command_exact_configuration_match_is_enforced():
    c=experience();c.decision['priority']=[2,1,0]
    assert not command_score(0,{'open0':1},{'open0':1},Memory([c]),DISTANCES,(6,5),3,Config(exact_execution_match=True))[1]

def test_command_constructed_feedback_can_change_candidate_ranking():
    cfg=Config();info={'open0':1,'open1':1}
    base=choose_plan(info,DISTANCES,(6,5),3,cfg)
    target=next(p for p in range(6) if p!=base)
    m=Memory([experience(p,completed=60 if p==target else 0) for p in range(6)])
    result=max(range(6),key=lambda p:(*command_score(p,info,{'open0':1},m,DISTANCES,(6,5),3,cfg)[0],-p))
    assert result==target

def test_fixed_trust_and_read_only_testing():
    cfg=Config();team=initial_team(810000,cfg)
    assert all(m.trust==.5 for m in team.memories)
    before=pickle.dumps(team)
    simulate(world(810000,'test',0,cfg),team,'G1',cfg)
    assert before==pickle.dumps(team)
    simulate(world(810000,'train',0,cfg),team,'G1',cfg,learn=True)
    assert all(m.trust==.5 for m in team.memories)

def test_observation_cases_are_bounded_and_have_provenance():
    cfg=Config();team=TeamSnapshot([Memory() for _ in ROLES])
    r=simulate(world(810000,'test',0,cfg),team,'G2',cfg,learn=True,trace=True)
    cases=[c for c in team.memories[0].cases if c.source=='venue-observation']
    assert len(cases)<=2
    for c in cases:
        assert c.provenance['label_id'] not in c.provenance['feature_evidence']
        assert c.provenance['label_observed']>=c.provenance['digital_observed']
    command=team.memories[3].cases[-1]
    assert command.decision['published_plan']==r['plan']
    assert command.decision['publish']==r['publish']
    assert 'completed' not in command.features

def test_delayed_release_does_not_change_preparation_cutoff():
    cfg=Config(deadline=4);team=initial_team(810002,cfg)
    r=simulate(world(810002,'diag',0,cfg),team,'G0',cfg,fixed=True,release_at=6,trace=True)
    assert r['publish']==6
    assert not [a for a in r['trace']['actions'] if 4<a['tick']<=6]
    assert all(row['tick']<=4 or 'cached_valid' in row for row in r['candidate_log'])
    with pytest.raises(ValueError):simulate(world(1,'x',0,cfg),team,'G0',cfg,release_at=6)

def test_direct_adoption_does_not_search_all_candidates():
    cfg=Config();team=initial_team(810001,cfg)
    found=False
    for event in range(30):
        r=simulate(world(810001,'adopt-test',event,cfg),team,'G1',cfg,trace=True)
        if r['direct_adopt']:
            found=True
            assert not r['command_scores']
            break
    assert found

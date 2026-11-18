import sys,pickle
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from stage2_abm.model import *

def test_alternation_uses_public_task_index_when_learning_frozen():
    cfg=Config(practice_policy='alternating');m=Memory()
    assert [choose_practice_exit([],m,cfg,1,(970000,'test',i))[0] for i in range(6)]==['open0','open1']*3

def test_random_is_reproducible_and_separate_from_hazard_stream():
    cfg=Config(practice_policy='random');m=Memory()
    xs=[choose_practice_exit([],m,cfg,1,(970000,'test',i))[0] for i in range(50)]
    assert set(xs)=={'open0','open1'}
    assert xs==[choose_practice_exit([],m,cfg,1,(970000,'test',i))[0] for i in range(50)]
    assert 10<xs.count('open0')<40

def test_invalid_policy():
    with pytest.raises(ValueError):Config(practice_policy='oracle')
    with pytest.raises(ValueError):Config(adaptive_practice=True,practice_policy='random')

def test_audit_logging_does_not_change_learning():
    cfg=Config(adaptive_practice=True);a=initial_team(972001,cfg);b=deepcopy(a)
    for e in range(8):
        w=world(972001,'unit',e,cfg)
        x=simulate(w,a,'G2',cfg,learn=True,trace=False);y=simulate(w,b,'G2',cfg,learn=True,trace=True)
        assert x['completion']==y['completion'] and asdict(a)==asdict(b)

def test_memory_reset_does_not_mutate_original():
    initial=initial_team(972002,Config());state=deepcopy(initial)
    for i in range(3):simulate(world(972002,'unit',i,Config()),state,'G2',Config(),learn=True)
    before=asdict(state);reset=deepcopy(state);reset.memories[0]=deepcopy(initial.memories[0])
    simulate(world(972002,'test',0,Config()),reset,'G0',Config(),fixed=True,trace=True)
    assert asdict(state)==before

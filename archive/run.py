from pathlib import Path
import sys,json,gzip,pickle,hashlib,time,argparse,statistics
from itertools import combinations
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent;PREV=ROOT.parent/'v3_流程改进'
sys.path.insert(0,str(ROOT/'src'))
from stage2_abm.model import *
ARMS=('G1','G2','S3','R','ALT')

def digest(s):return hashlib.sha256(pickle.dumps(s)).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def hashes():return {str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*.py')) if '__pycache__' not in str(p)}
def config(a):return Config(adaptive_practice=a=='S3',practice_policy={'R':'random','ALT':'alternating'}.get(a,'legacy'))

def worker(seed):
    out=ROOT/'runs';dest=out/f'{seed}.json';raw=out/f'{seed}.jsonl.gz'
    if dest.exists():
        r=json.loads(dest.read_text());assert sha(raw)==r['raw_sha256'];return seed
    cfg=Config();initial=TeamSnapshot([Memory() for _ in ROLES]);states={};rows=[];cache={};n=0
    tmp=raw.with_suffix('.tmp')
    with gzip.open(tmp,'wt',encoding='utf8',compresslevel=1) as log:
        def write(r,meta,local):
            nonlocal n
            acts=r['trace']['actions'];assert all(sum(a['role']==role for a in acts)<=6 for role in range(4))
            assert sum(a['action']=='practice_observe' for a in acts)<=1
            assert r['publish']<=6 and all(m['processed']>m['sent'] for m in r['trace']['messages'])
            assert sum(t>0 for t in r['trace']['public'][-1]['done'])==r['completed']
            log.write(json.dumps(dict(r,**meta),default=asdict,separators=(',',':'))+'\n');n+=1
        for e in range(12):
            r=simulate(world(seed,'r017-initial',e,cfg),initial,'G0',cfg,learn=True,trace=True)
            write(r,{'kind':'initial','episode':e+1},cfg)
        for m in initial.memories:
            for c in m.cases:c.born-=m.clock;c.last-=m.clock
            m.clock=0;m.successes=m.failures=1
        def block(st,arm,mode):
            key=digest(st)
            if key not in cache:
                ref=f't{len(cache)}';before=digest(st);values=[]
                for e in range(40):
                    r=simulate(world(seed,'r017-ability',e,cfg),st,'G0',cfg,fixed=True,trace=True)
                    assert digest(st)==before;write(r,{'kind':'test','ref':ref},cfg);values.append(r['completion'])
                cache[key]={'ref':ref,'completion':statistics.mean(values)}
            row=dict(cache[key],arm=arm,mode=mode);rows.append(row);return row['completion']
        pre=block(initial,'common','pre')
        for arm in ARMS:
            local=config(arm);group='G1' if arm=='G1' else 'G2'
            state=deepcopy(initial);frozen=deepcopy(initial);before=digest(frozen)
            for e in range(60):
                w=world(seed,'r017-train',e,local)
                for learning,st in [('open',state),('frozen',frozen)]:
                    r=simulate(w,st,group,local,learn=learning=='open',trace=True)
                    write(r,{'kind':'train','arm':arm,'learning':learning,'episode':e+1},local)
                    if learning=='frozen':assert digest(st)==before
            states[arm]=deepcopy(state);block(state,arm,'full');assert block(frozen,arm,'frozen')==pre
        for arm,st in states.items():
            reset=deepcopy(st);reset.memories[0]=deepcopy(initial.memories[0]);block(reset,arm,'reset_venue')
        reset=deepcopy(states['S3']);reset.memories[3]=deepcopy(initial.memories[3]);block(reset,'S3','reset_command')
    tmp.replace(raw)
    snap=out/f'{seed}.pkl.gz'
    with gzip.open(snap,'wb') as f:pickle.dump({'initial':initial,'states':states},f)
    result={'seed':seed,'events':n,'rows':rows,'raw_sha256':sha(raw),'snapshot_sha256':sha(snap)}
    dest.write_text(json.dumps(result,indent=2),encoding='utf8');return seed

def compatibility():
    checked=[]
    for seed in (960000,960001,960002):
        with gzip.open(PREV/f'runs/step3/{seed}.pkl.gz','rb') as f:old=pickle.load(f)
        st=deepcopy(old['initial']);cfg=config('S3')
        for e in range(60):simulate(world(seed,'r017-train',e,cfg),st,'G2',cfg,learn=True,trace=True)
        assert asdict(st)==asdict(old['states']['S3']);checked.append(seed)
    return checked

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);a=p.parse_args()
    out=ROOT/'runs';out.mkdir(exist_ok=True)
    seeds=list(range(970000,970200))
    plan={'seeds':seeds,'arms':list(ARMS),'source_sha256':hashes(),'protocol_sha256':sha(ROOT/'protocol/方案.md'),
        'warmup':12,'training':60,'tasks':40,'bootstrap':10000,'bootstrap_seed':261026,
        'primary_pairs':[list(x) for x in combinations(ARMS,2)],'holm_family_size':10,
        'mechanism':'restore initial venue memory in all five final states; restore initial command in S3',
        'status':'new independent simulation sample after internal freeze; no human calibration',
        'policy_selection':'S3 remains selected; do not select new winner on this sample'}
    frozen=ROOT/'protocol/frozen.json'
    if frozen.exists():assert json.loads(frozen.read_text(encoding='utf8'))==plan,'Frozen plan mismatch'
    else:frozen.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    checked=compatibility()
    (ROOT/'protocol/兼容性.json').write_text(json.dumps({'passed':True,'teams':checked,'method':'asdict equality after full training'}),encoding='utf8')
    start=time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        jobs=[pool.submit(worker,s) for s in seeds]
        for i,f in enumerate(as_completed(jobs),1):
            s=f.result()
            if i%10==0 or i==200:print(f'{i}/200 teams, {time.time()-start:.1f}s, latest {s}',flush=True)
    (out/'complete.json').write_text(json.dumps({'teams':200,'seconds':time.time()-start,'source_sha256':hashes()},indent=2),encoding='utf8')

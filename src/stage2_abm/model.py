"""Explicit information, memory and public movement. No LLM or ability score.

Policies receive Observation records only. World is private to the simulator.
"""
from dataclasses import dataclass, field, asdict
from copy import deepcopy
from hashlib import blake2b
from functools import lru_cache
import random
import math

ROLES = ('venue', 'rescue', 'medical', 'command')
FIELDS = (('open0','open1'), ('warn0','warn1'),
          ('n0','v0','n1','v1','n2','v2'), ())
DISTANCES = ((3.,5.),(4.,3.),(5.,4.))

def rng(*key):
    return random.Random(int.from_bytes(blake2b(repr(key).encode(),digest_size=16).digest(),'big'))

@dataclass(frozen=True)
class Config:
    budget: int = 6
    deadline: int = 6
    digital_accuracy: float = .85
    digital_delay: int = 1
    field_available: float = .90
    field_accuracy: float = .90
    neighbors: int = 5
    capacity: int = 100
    decay: float = 1.0
    trust_adapts: bool = False
    venue_learning: bool = True
    command_learning: bool = True
    venue_threshold: float = .50
    exact_execution_match: bool = False
    initial_cases: int = 12
    integration_cost: int = 2
    supervise: bool = True
    feedback: float = 1.
    communication: bool = True
    network: str = 'full'
    ai_summary: bool = True
    revision: bool = False
    vulnerable_first: bool = False
    population: tuple = (12,20,28)
    capacities: tuple = (6,5)
    monitor_period: int = 3
    adaptive_practice: bool = False
    matched_venue_signal: bool = False
    command_min_support: int = 1
    practice_policy: str = 'legacy'

    def __post_init__(self):
        if self.practice_policy not in ('legacy','random','alternating'):raise ValueError('invalid practice_policy')
        if self.adaptive_practice and self.practice_policy!='legacy':raise ValueError('ambiguous practice policy')
        object.__setattr__(self,'population',tuple(self.population))
        object.__setattr__(self,'capacities',tuple(self.capacities))
        if not (1<=self.deadline<=14 and self.budget>=0 and 0<=self.venue_threshold<=1):
            raise ValueError('Invalid deadline, budget or venue threshold')

@dataclass(frozen=True)
class Observation:
    field: str
    value: float | None
    observed: int
    available: int
    source: str
    original: str

@dataclass
class Case:
    features: dict
    labels: dict
    born: int
    last: int
    source: str
    decision: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

@dataclass
class Memory:
    cases: list = field(default_factory=list)
    clock: int = 0
    successes: int = 1
    failures: int = 1
    touched: set = field(default_factory=set,repr=False)

    @property
    def trust(self):
        return self.successes/(self.successes+self.failures)

    def predict(self, features, target, prior, cfg):
        choices=[]
        for i,c in enumerate(self.cases):
            common=features.keys() & c.features.keys()
            if target not in c.labels or not common: continue
            distance=sum(abs(features[k]-c.features[k]) / (60 if k.startswith('n') else 12 if k.startswith('v') else 1) for k in sorted(common))/len(common)
            choices.append((distance,-c.born,i,c))
        selected=sorted(choices,key=lambda z:z[:3])[:cfg.neighbors]
        self.touched.update(i for _,_,i,_ in selected)
        if not selected: return prior
        weights=[1/(1+d)*cfg.decay**max(0,self.clock-c.born) for d,_,_,c in selected]
        return sum(w*c.labels[target] for w,(_,_,_,c) in zip(weights,selected))/sum(weights)

    def add(self, features, labels, source, cfg):
        if not features or not labels: return None
        if len(self.cases)>=cfg.capacity:
            i=min(range(len(self.cases)),key=lambda i:(self.cases[i].last,self.cases[i].born,i))
            self.cases.pop(i)
        case=Case(dict(features),dict(labels),self.clock,self.clock,source)
        self.cases.append(case)
        return case

@dataclass
class TeamSnapshot:
    memories: list
    episode: int = 0

@dataclass
class WorldState:
    seed: int
    family: str
    event: int
    regions: list
    vulnerable: list
    order: list
    failure: int
    failure_tick: int
    warning: tuple
    distances: tuple
    capacities: tuple
    mechanical: bool = False

    def closed(self,tick):
        if self.failure<0: return (False,False)
        on=self.failure_tick<=tick and (not self.mechanical or tick<9)
        return tuple(on and e==self.failure for e in range(2))

def world(seed,family,event,cfg,challenge='base'):
    r=rng(seed,family,event,'world')
    ns=list(cfg.population);r.shuffle(ns)
    regions=[z for z,n in enumerate(ns) for _ in range(n)]
    vulnerable=set(r.sample(range(60),12));order=list(range(60));r.shuffle(order)
    u=r.random();failure=-1 if u<.30 else 0 if u<.65 else 1
    ft=r.choice((8,10,12));mechanical=challenge=='mechanical'
    if mechanical: failure=r.randrange(2) if r.random()<.5 else -1;ft=3
    warnings=tuple(int(r.random()<(.8 if e==failure else .2)) for e in range(2))
    distances=((6.,5.),(4.,3.),(5.,2.)) if challenge=='spatial' else DISTANCES
    caps=(4,7) if challenge=='spatial' else cfg.capacities
    return WorldState(seed,family,event,regions,[i in vulnerable for i in range(60)],order,failure,ft,warnings,distances,caps,mechanical)

def channel(w,role,tick,cfg,onsite=False,target=None):
    if onsite and (role==3 or (target is not None and target not in FIELDS[role])):
        raise ValueError('Onsite query outside role whitelist')
    fields=FIELDS[role]
    if target:
        if target.startswith(('open','warn')):
            fields=(target, ('warn' if target.startswith('open') else 'open')+target[-1])
        else: fields=('n'+target[-1],'v'+target[-1])
    elif role==2 and onsite: fields=('n0','v0')
    result=[]
    packet_available=not onsite or rng(w.seed,w.family,w.event,'packet-availability',role,target,tick).random()<cfg.field_available
    for f in fields:
        r=rng(w.seed,w.family,w.event,'field' if onsite else 'digital',role,f,tick)
        observed=max(0,tick-(0 if onsite else cfg.digital_delay))
        if f.startswith('open'): value=float(not w.closed(observed)[int(f[-1])])
        elif f.startswith('warn'): value=float(w.warning[int(f[-1])])
        else:
            z=int(f[-1]);value=float(sum(a==z and (not f.startswith('v') or v) for a,v in zip(w.regions,w.vulnerable)))
        if not packet_available: value=None
        elif f.startswith(('n','v')):
            if not onsite and r.random()>cfg.digital_accuracy: value=None
            elif onsite and r.random()>cfg.field_accuracy: value=max(0.,min(60 if f.startswith('n') else 12,value+r.choice((-4,4))))
        elif r.random()>(cfg.field_accuracy if onsite else cfg.digital_accuracy): value=1-value
        source=f'{w.family}:{w.event}:{role}:{f}:{tick}:{int(onsite)}'
        result.append(Observation(f,value,observed,tick,source,source))
    return result

def initial_team(seed,cfg):
    # Initial memories are generated by the very same paid actions and feedback
    # interfaces used later, with a common no-AI warm-up history for all regimes.
    team=TeamSnapshot([Memory() for _ in ROLES])
    initial_cfg=Config(**{**asdict(cfg),'feedback':1.})
    for j in range(cfg.initial_cases):
        simulate(world(seed,'initial',j,initial_cfg),team,'G0',initial_cfg,learn=True)
    return team


def visible_values(observations):
    result={}
    for o in sorted(observations,key=lambda o:(o.observed,o.available)):
        if o.value is not None: result[o.field]=o.value
    return result

def scenario_key(distances,capacities):
    return repr((tuple(tuple(row) for row in distances),tuple(capacities)))


def decision_features(observations,judgments):
    # Only actually received facts/judgments; never use model-imputed features.
    result=visible_values(observations)
    result.update(judgments)
    return result


def merge_judgments(observations,judgments,forecast=None):
    result=dict(forecast) if forecast is not None else visible_values(observations)
    result.update(judgments)
    # A current direct field reading is evidence, not a historical estimate.
    for e in range(2):
        records=[o for o in observations if o.field=='open'+str(e) and o.value is not None]
        if records:
            latest=max(records,key=lambda o:(o.observed,o.source.endswith(':1'),o.available))
            if latest.source.endswith(':1'):result[latest.field]=latest.value
    return result


def venue_training_pairs(before,onsite,tick):
    pairs=[]
    values=visible_values(before)
    for o in onsite:
        if not o.field.startswith('open') or o.value is None:continue
        digitals=[p for p in before if p.field==o.field and p.value is not None and p.source.endswith(':0') and p.available<=tick]
        if not digitals:continue
        d=max(digitals,key=lambda p:(p.observed,p.available))
        age=o.observed-d.observed
        if age<0:continue
        e=o.field[-1]
        features={'digital_open'+e:d.value,'age'+e:float(age)}
        if 'warn'+e in values:features['warn'+e]=values['warn'+e]
        pairs.append({'features':features,'labels':{'onsite_open'+e:o.value},
            'provenance':{'role':0,'digital_id':d.original,'digital_observed':d.observed,
                'label_id':o.original,'label_observed':o.observed,'available':o.available,
                'feature_evidence':[p.original for p in before if p.value is not None]}})
    # One per target per event, earliest eligible observation; later monitoring
    # must not add repeated cases for the same target.
    return pairs


def venue_estimates(observations,memory,cfg,tick):
    result={};support={}
    for e in range(2):
        f='open'+str(e)
        records=[o for o in observations if o.field==f and o.value is not None]
        if not records:continue
        newest=max(records,key=lambda o:(o.observed,o.source.endswith(':1'),o.available))
        if newest.source.endswith(':1'):
            result[f]=newest.value;support[f]={'kind':'direct','cases':[]};continue
        age=tick-newest.observed
        features={'digital_'+f:newest.value,'age'+str(e):float(age)}
        vals=visible_values(observations)
        if 'warn'+str(e) in vals:features['warn'+str(e)]=vals['warn'+str(e)]
        target='onsite_'+f
        eligible=[(i,c) for i,c in enumerate(memory.cases) if target in c.labels and c.features.get('age'+str(e))==age
                  and (not cfg.matched_venue_signal or c.features.get('digital_'+f)==newest.value)]
        view=Memory([c for _,c in eligible],memory.clock)
        q=view.predict(features,target,newest.value,cfg)
        used=[eligible[i][0] for i in sorted(view.touched)]
        memory.touched.update(used)
        result[f]=float(q>=cfg.venue_threshold) if used else newest.value
        support[f]={'kind':'memory' if used else 'fallback','probability':q,'age':age,'cases':used}
    return result,support


def command_score(plan,info,features,memory,distances,capacities,publish,cfg):
    base=score_plan(plan,info,distances,capacities,publish,cfg)
    # Public scoring returns counts; empirical predictions use identical units.
    prior=(base[0]/(12 if cfg.vulnerable_first else 60),base[1]/(60 if cfg.vulnerable_first else 12),base[2])
    if not cfg.command_learning or plan<0 or not legal(plan,info,distances):return prior,[]
    scenario=scenario_key(distances,capacities)
    eligible=[]
    for i,c in enumerate(memory.cases):
        d=c.decision
        if d.get('published_plan')!=plan or d.get('publish')!=publish or d.get('scenario')!=scenario:continue
        if not all(k in c.labels for k in ('completed','v_completed')):continue
        if cfg.exact_execution_match and (tuple(d.get('routes',()))!=routes(plan,info,distances) or list(d.get('priority',()))!=resource_priority(plan,info)):continue
        if cfg.command_min_support>1 and not (features.keys() & c.features.keys()):continue
        eligible.append((i,c))
    if len(eligible)<cfg.command_min_support:return prior,[]
    view=Memory([c for _,c in eligible],memory.clock)
    total=view.predict(features,'completed',prior[1]*60 if cfg.vulnerable_first else prior[0]*60,cfg)/60
    vulnerable=view.predict(features,'v_completed',prior[0]*12 if cfg.vulnerable_first else prior[1]*12,cfg)/12
    used=[eligible[i][0] for i in sorted(view.touched)]
    memory.touched.update(used)
    return ((vulnerable,total,prior[2]) if cfg.vulnerable_first else (total,vulnerable,prior[2])),used


def prediction(observations,memory,cfg,*,role=None,tick=None):
    values=visible_values(observations);out=dict(values)
    for e in range(2): out['fail'+str(e)]=memory.predict(values,'fail'+str(e),.35,cfg)
    for z in range(3):
        for prefix,prior in [('n',20.),('v',4.)]:
            f=prefix+str(z)
            if f not in out:out[f]=memory.predict(values,f,prior,cfg)
    if role==0 and tick is not None and cfg.venue_learning:
        out.update(venue_estimates(observations,memory,cfg,tick)[0])
    return out

def routes(plan,info,distances):
    if plan<0:return (-1,-1,-1)
    p=plan//2
    if p<2: return (p,p,p)
    return tuple(min((e for e in range(2) if info.get('open'+str(e),1)>0),key=lambda e:(distances[z][e],e),default=-1) for z in range(3))

def legal(plan,info,distances):
    if plan<0:return True
    path=routes(plan,info,distances)
    return any(e>=0 for e in path) and all(e<0 or info.get('open'+str(e),1)>0 for e in path)

def execute_public(regions,vulnerable,order,distances,capacities,route,priority,publish,closed,trace=False,revision=None):
    """Physical movement with queue/service conservation; independent of regime."""
    remaining=[distances[z][route[z]] if route[z]>=0 else math.inf for z in regions]
    destinations=[route[z] for z in regions];arrived=[None]*60;done=[0]*60
    diverted=[False]*60;wait=[0]*60;assigned={};helpers=[(-1,publish+1)]*4;encountered=set();deployed=[False]*4
    ranks={p:i for i,p in enumerate(order)};logs=[]
    service_order=sorted(range(60),key=lambda i:(priority.index(regions[i]),ranks[i]))
    for t in range(publish+1,15):
        shut=closed(t)
        if revision is not None and t==revision[0]+1:
            for i in order:
                destination=revision[1][regions[i]]
                if not done[i] and destination>=0 and destinations[i]!=destination:
                    remaining[i]=distances[regions[i]][destination] if destinations[i]<0 else 3.
                    destinations[i]=destination;arrived[i]=None
        for h,(person,available) in enumerate(helpers):
            if person>=0 and done[person]:
                available=done[person]+2;assigned.pop(person,None);person=-1;helpers[h]=(person,available)
            if person<0 and t>=available:
                candidate=next((i for i in service_order if not done[i] and i not in assigned and remaining[i]>0),None)
                if candidate is not None:
                    helpers[h]=(candidate,t if deployed[h] else t+1);assigned[candidate]=h;deployed[h]=True
        for i in order:
            if done[i] or destinations[i]<0:continue
            if remaining[i]>0:
                helped=i in assigned and t>=helpers[assigned[i]][1]
                speed=(1 if vulnerable[i] else 1.25) if helped else (.5 if vulnerable[i] else 1.)
                remaining[i]=max(0.,remaining[i]-speed)
                if remaining[i]==0:arrived[i]=t
            elif shut[destinations[i]]:
                if not diverted[i]:
                    encountered.add(destinations[i])
                    # One tick detection, then start the alternative corridor next tick.
                    diverted[i]=True;destinations[i]=1-destinations[i];remaining[i]=3.;arrived[i]=None
        for e in range(2):
            q=sorted((i for i in order if not done[i] and destinations[i]==e and remaining[i]==0),key=lambda i:(arrived[i],ranks[i]))
            if not shut[e]:
                for i in q[:capacities[e]]:done[i]=t
                q=q[capacities[e]:]
            for i in q:wait[i]+=1
        assert len(assigned)<=4
        if trace:logs.append({'tick':t,'remaining':[x if math.isfinite(x) else None for x in remaining],'destination':destinations.copy(),'done':done.copy(),'helpers':helpers.copy()})
    return {'completed':sum(bool(t) for t in done),'v_completed':sum(bool(t) and v for t,v in zip(done,vulnerable)),
            'arrival_sum':sum(done),'queue_ticks':sum(wait),'rerouted':sum(diverted),'arrivals':done,'trajectory':logs,
            'encountered_closed':sorted(encountered)}

def resource_priority(plan,info):
    prefix='v' if plan%2==0 else 'n'
    return sorted(range(3),key=lambda z:(-info.get(prefix+str(z),4 if prefix=='v' else 20),z))

def score_plan(plan,info,distances,capacities,publish,cfg):
    return _score_plan(plan,tuple(sorted(info.items())),distances,capacities,publish,cfg)

@lru_cache(maxsize=20000)
def _score_plan(plan,items,distances,capacities,publish,cfg):
    info=dict(items)
    if not legal(plan,info,distances):return (-1.,-1.,-math.inf)
    # Synthetic populations use visible estimates only; no access to actual WorldState.
    counts=[max(0,round(info.get('n'+str(z),20))) for z in range(3)]
    # Preserve the task total without accessing true regional counts.
    counts=[round(n*60/max(1,sum(counts))) for n in counts];counts[-1]+=60-sum(counts)
    regions=[z for z,n in enumerate(counts) for _ in range(max(0,n))]
    vs=[i<min(counts[z],round(info.get('v'+str(z),4))) for z,n in enumerate(counts) for i in range(max(0,n))]
    p=[max(0,min(1,info.get('fail'+str(e),.35))) for e in range(2)];s=sum(p)
    if s>1:p=[x/s for x in p]
    weights=[max(0,1-s),*p];total=vc=arrival=0.
    for fail,weight in zip((-1,0,1),weights):
        if not weight:continue
        sim=execute_public(regions,vs,list(range(60)),distances,capacities,routes(plan,info,distances),resource_priority(plan,info),publish,
                           lambda t:tuple(info.get('open'+str(e),1)<=0 or (fail==e and t>=10) for e in range(2)))
        total+=weight*sim['completed'];vc+=weight*sim['v_completed'];arrival+=weight*sim['arrival_sum']
    return (vc,total,-arrival) if cfg.vulnerable_first else (total,vc,-arrival)

def choose_plan(info,distances,capacities,publish,cfg):
    valid=[p for p in range(6) if legal(p,info,distances)]
    return max(valid,key=lambda p:(*score_plan(p,info,distances,capacities,publish,cfg),-p),default=-1)

@dataclass(frozen=True)
class Message:
    sender: int
    recipient: int
    sent: int
    due: int
    observations: tuple = ()
    judgments: tuple = ()
    evidence_ids: tuple = ()
    request: str | None = None
    reply: bool = False
    request_token: str | None = None

@dataclass(frozen=True)
class AIReport:
    facts: tuple
    info: dict
    plan: int
    unmanipulated: int

def ai_report(observations,distances,capacities,publish,cfg,manipulate=False):
    info=visible_values(observations)
    for e in range(2):info['fail'+str(e)]=.60 if info.get('warn'+str(e),0) else .15
    plan=choose_plan(info,distances,capacities,publish,cfg)
    original=plan
    if manipulate and plan>=0:plan=(((plan//2)+1)%3)*2+plan%2
    return AIReport(tuple(observations),info,plan,original)

def conflict_ratio(received,report,distances):
    active={e for e in routes(report.plan,report.info,distances) if e>=0}
    if not active:active={0,1}
    relevant={prefix+str(e) for e in active for prefix in ('open','warn','fail')}
    relevant.update(prefix+str(z) for z in range(3) for prefix in ('n','v'))
    known={k:v for k,v in received.items() if k in relevant}
    return sum(k in report.info and v!=report.info[k] for k,v in known.items())/len(known) if known else 0.

def select_practice_target(observations,memory,cfg,tick):
    """One visible-evidence target; shrink memory towards channel reliability."""
    scratch=Memory(memory.cases,memory.clock,memory.successes,memory.failures)
    _,supports=venue_estimates(observations,scratch,cfg,tick)
    diagnostics=[]
    for e in range(2):
        f='open'+str(e);records=[o for o in observations if o.field==f and o.value is not None]
        last_field=max((o.observed for o in records if o.source.endswith(':1')),default=-1)
        if not records:q=.5;n=0;prior=.5
        else:
            newest=max(records,key=lambda o:(o.observed,o.source.endswith(':1'),o.available))
            reliability=cfg.field_accuracy if newest.source.endswith(':1') else cfg.digital_accuracy
            prior=reliability if newest.value else 1-reliability
            s=supports.get(f,{});n=len(s.get('cases',[]))
            q=(n*s.get('probability',prior)+2*prior)/(n+2)
        q=max(1e-12,min(1-1e-12,q));entropy=-q*math.log2(q)-(1-q)*math.log2(1-q)
        diagnostics.append(dict(target=f,probability=q,prior=prior,support=n,entropy=entropy,last_field=last_field))
    best=max(range(2),key=lambda e:(diagnostics[e]['entropy'],-diagnostics[e]['last_field'],-e))
    return 'open'+str(best),diagnostics

def choose_practice_exit(observations,memory,cfg,tick,public_key):
    if cfg.adaptive_practice:return select_practice_target(observations,memory,cfg,tick)
    if cfg.practice_policy=='random':return 'open'+str(rng(*public_key,'practice-target').randrange(2)),[]
    if cfg.practice_policy=='alternating':return 'open'+str(int(public_key[2])%2),[]
    return 'open0',[]

def simulate(w,team,group,cfg,*,learn=False,trust_only=False,manipulate=False,fixed=False,trace=False,matched=None,release_at=None):
    """One event. All policy decisions precede same-tick channel/message updates."""
    # Retrieval metadata lives in an event-local view; holdouts never mutate snapshots.
    memory_views=[Memory(m.cases,m.clock,m.successes,m.failures) for m in team.memories]
    observations=[channel(w,r,1,cfg) if r<3 else [] for r in range(4)]
    forecast_cache={}
    forecast_audit=[]
    def forecast(role):
        key=role,len(observations[role]),t
        if key not in forecast_cache:
            forecast_cache[key]=prediction(observations[role],memory_views[role],cfg,role=role,tick=t)
            if trace and role==0:
                scratch=Memory(memory_views[role].cases,memory_views[role].clock)
                _,support=venue_estimates(observations[role],scratch,cfg,t)
                forecast_audit.append(dict(tick=t,role=role,prediction=dict(forecast_cache[key]),support=support))
        return dict(forecast_cache[key])
    if release_at is not None and (not fixed or release_at<cfg.deadline):
        raise ValueError('release_at requires fixed and must be >= deadline')
    publication_tick=(release_at or cfg.deadline) if fixed else None
    venue_pairs=[]; learning_scores=[]; feedback_log=[]; candidate_log=[]; release_features=None
    target_choices=[]
    venue_decision_support=None
    observation_limits=[len(o) for o in observations]
    judgments=[{} for _ in ROLES];messages=[];requests=[[] for _ in ROLES]
    judgment_evidence=[{} for _ in ROLES]
    spent=[0]*4;sent=[set() for _ in ROLES];seen=[set() for _ in ROLES]
    pending_reply=[None]*4;observed_fields=[set() for _ in ROLES]
    onsite=[];actions=[];message_log=[];field_log=[];read=False;report=None
    phase='unread';verification=False;verified=False;candidate=None;published=None;publish=None
    verification_token=None;verification_reply_time=None
    integrated=0;practice=False;practice_received=False;practice_proposed=False
    observed_labels=[{} for _ in ROLES];nobs=0;correction=False;adopt=False;ai_inputs=[];release_info=None;assay=None;revision=None;case_features=None
    for t in range(1,15):
        if fixed and release_at is not None and t==cfg.deadline+1:
            cutoff_info=dict(command_info)
            cutoff_features=decision_features(observations[3],judgments[3])
        # Deliver at most two messages per actor, FIFO; retain excess.
        for r in range(4):
            inbox=sorted((m for m in messages if m.recipient==r and m.due<=t),key=lambda m:(m.due,m.sent,m.sender))[:2]
            for msg in inbox:
                messages.remove(msg)
                if msg.request:requests[r].append((msg.sender,msg.request,msg.request_token))
                for o in msg.observations:
                    if o.original not in seen[r]:observations[r].append(o);seen[r].add(o.original)
                    if r==3 and msg.sender==0 and ':1'==o.source[-2:]:practice_received=True
                judgments[r].update(dict(msg.judgments))
                for k,_ in msg.judgments:judgment_evidence[r][k]=list(msg.evidence_ids)
                if msg.reply and r==3 and verification_token is not None and msg.request_token==verification_token:
                    verification_reply_time=t
                    if published is None and t<=cfg.deadline:verified=True
                message_log.append({**asdict(msg),'processed':t})
        # Safety and conflict flags concern received evidence; unknown-field
        # priors must not be counted as received contradictory evidence.
        command_info=merge_judgments(observations[3],judgments[3])
        if fixed and release_at is not None and t>cfg.deadline:command_info=dict(cutoff_info)
        decisions=[]
        for r in range(4):
            action=('wait',None)
            if spent[r]>=cfg.budget or (published is not None and not cfg.supervise) or (fixed and release_at is not None and cfg.deadline<t<=release_at):decisions.append(action);continue
            own=visible_values(observations[r]);before=published is None and t<=cfg.deadline
            danger=next((o for o in observations[r] if o.field.startswith('open') and o.value==0 and o.original not in sent[r]),None) if r<3 else None
            if r==3 and published is not None and cfg.revision and revision is None and ((published<0 and any(command_info.get('open'+str(e),0)>0 for e in range(2))) or any(command_info.get('open'+str(e),1)<=0 for e in routes(published,release_info,w.distances) if e>=0)):
                action=('revise',None)
            elif danger is not None and cfg.communication:
                action=('send',(danger,))
            elif pending_reply[r] is not None:
                action=('reply',pending_reply[r])
            elif requests[r] and r<3:
                who,target,token=requests[r][0]
                if target in observed_fields[r]:action=('reply',(who,target,token))
                else:action=('requested_observe',(who,target,token))
            elif r==0 and group in ('G2','M') and not practice and before:
                if group!='M' or matched is None or t>=matched['tick']:
                    target,diagnostics=choose_practice_exit(observations[r],memory_views[r],cfg,t,(w.seed,w.family,w.event))
                    if cfg.adaptive_practice or cfg.practice_policy!='legacy':
                        target_choices.append(dict(tick=t,selected=target,candidates=diagnostics))
                    action=('practice_observe',target)
            elif r==0 and group in ('G2','M') and practice and not any(x.startswith('practice') for x in sent[r]) and before:
                action=('practice_send',None)
            elif r==3 and group in ('G2','M') and practice_received and not practice_proposed and before:
                action=('propose' if group=='G2' else 'structured_check',None)
            elif r<3 and before:
                fields=[o for o in observations[r] if o.original not in sent[r]]
                if fields:action=('send',tuple(fields[:2]))
                elif r==1 and cfg.network=='full' and 'peer' not in sent[r] and cfg.communication:action=('peer_request',(0,'open0'))
                elif r==2 and cfg.network=='full' and 'peer' not in sent[r] and cfg.communication:action=('peer_request',(1,'warn0'))
                else:action=('observe',next((f for f in FIELDS[r] if f not in observed_fields[r]),None))
            elif r==3 and before and phase!='prepared':
                if group!='G0' and not read:action=('read_ai',None)
                elif group!='G0' and phase=='choose':
                    probability=min(1,.20+.50*conflict_ratio(command_info,report,w.distances)+.30*(1-memory_views[3].trust))
                    if rng(w.seed,w.family,w.event,'verify',t).random()<probability or not legal(report.plan,command_info,w.distances):action=('verify_request',None)
                    elif group not in ('G2','M') or practice_proposed:action=('adopt',None)
                elif phase=='waiting' and verified:action=('propose',None)
                elif group=='G0' or (group in ('G2','M') and practice_proposed):
                    if integrated<cfg.integration_cost:action=('integrate',None)
                    else:action=('propose',None)
                elif phase=='waiting':action=('wait',None)
            else:
                # Do not exhaust spare time on redundant immediate re-observations.
                # A common three-tick monitoring cadence permits later evidence;
                # it uses elapsed time, never the hidden hazard realization.
                if published is not None and (t-publish)%cfg.monitor_period==0:
                    if r<3:
                        fields=FIELDS[r]
                        target=min(fields,key=lambda f:(max((o.observed for o in observations[r] if o.field==f),default=-1),f))
                        action=('observe',target)
                    elif cfg.communication:
                        action=('supervision_request',(0,'open'+str((t//cfg.monitor_period)%2)))
            decisions.append(action)
        for r,(action,arg) in enumerate(decisions):
            if action=='wait' or (action=='observe' and arg is None):continue
            spent[r]+=1;assert spent[r]<=cfg.budget
            actions.append({'tick':t,'role':r,'action':action,'argument':arg,'spent':spent[r]})
            def send(recipient,obs=(),js=(),request=None,reply=False,evidence_ids=(),request_token=None):
                if request is not None and request_token is None:
                    request_token=f'{w.seed}:{w.family}:{w.event}:{r}:{t}:{request}'
                if cfg.communication:
                    messages.append(Message(r,recipient,t,t+1,tuple(obs),tuple(js),tuple(evidence_ids),request,reply,request_token))
                return request_token
            if action in ('observe','practice_observe','requested_observe'):
                target=arg[1] if action=='requested_observe' else arg
                obs=channel(w,r,t,cfg,True,target)
                if action=='practice_observe' and group=='M' and matched is not None:obs=[Observation(**o) for o in matched['observations']]
                if r==0:
                    used_targets={next(iter(p['labels'])) for p in venue_pairs}
                    venue_pairs.extend(p for p in venue_training_pairs(observations[r],obs,t)
                                       if next(iter(p['labels'])) not in used_targets)
                observations[r].extend(obs);observed_fields[r].update(o.field for o in obs)
                field_log.extend({'role':r,**asdict(o)} for o in obs);nobs+=sum(o.value is not None for o in obs)
                for o in obs:
                    if o.value is not None:
                        observed_labels[r][o.field]=o.value
                        if o.field.startswith('open') and not w.mechanical:
                            if o.value==0 and t>=8:observed_labels[r]['fail'+o.field[-1]]=1.
                            # A single late open reading is not coverage of the
                            # entire risk interval; do not invent a negative label.
                if action=='practice_observe':practice=True;onsite.append({'tick':t,'observations':[asdict(o) for o in obs]})
                if action=='requested_observe':pending_reply[r]=arg
            elif action in ('send','practice_send','reply'):
                if action=='reply':
                    recipient,target,token=arg;obs=tuple(o for o in observations[r] if o.field in (target,('warn' if target.startswith('open') else 'open')+target[-1]))[-2:]
                    pending_reply[r]=None
                    if requests[r]:requests[r].pop(0)
                else:recipient=3;obs=arg if action=='send' else tuple(o for o in observations[r] if o.source.endswith(':1'))[-2:]
                p=forecast(r)
                # One domain judgment per message and its evidence; never transmit all fields for free.
                target=('fail'+obs[0].field[-1] if r==1 and obs else obs[0].field if obs else 'open0')
                evidence_ids=tuple(o.original for o in observations[r] if o.value is not None)
                send(recipient,obs[:1],((target,p.get(target,.35)),),reply=action=='reply',evidence_ids=evidence_ids,
                     request_token=token if action=='reply' else None)
                sent[r].update(o.original for o in obs[:1])
                if action=='practice_send':sent[r].add('practice_done')
            elif action in ('peer_request','supervision_request'):
                send(arg[0],request=arg[1])
                if action=='peer_request':sent[r].add('peer')
            elif action=='read_ai':
                ai_inputs=[o for rr in range(3) for o in channel(w,rr,t,cfg)] if cfg.ai_summary else list(observations[3])
                report=ai_report(ai_inputs,w.distances,w.capacities,publication_tick if fixed else min(t+1,cfg.deadline),cfg,manipulate)
                read=True;phase='choose';observations[3].extend(ai_inputs)
            elif action=='verify_request':
                target='open'+str(report.plan//2 if 0<=report.plan//2<2 else 0)
                verification_token=send(0,request=target);verification=True;phase='waiting'
            elif action=='integrate':integrated+=1
            elif action=='revise':
                newplan=choose_plan(command_info,w.distances,w.capacities,t,cfg)
                revision=(t,routes(newplan,command_info,w.distances))
            elif action in ('propose','structured_check'):
                info=merge_judgments(observations[r],judgments[r],forecast(r))
                features=decision_features(observations[r],judgments[r])
                planned_publish=publication_tick if fixed else t
                def rank(plan):
                    score,support=command_score(plan,info,features,memory_views[r],w.distances,w.capacities,planned_publish,cfg)
                    learning_scores.append(dict(tick=t,plan=plan,score=score,support=support))
                    return (*score,-plan)
                ownplan=(report.plan if report is not None and legal(report.plan,info,w.distances) else 4) if action=='structured_check' else max((p for p in range(6) if legal(p,info,w.distances)),key=rank,default=-1)
                candidate=ownplan
                if group in ('G2','M') and practice_received:practice_proposed=True
                if group!='G0' and report is not None and legal(report.plan,info,w.distances):
                    if rank(report.plan)>=rank(ownplan):candidate=report.plan
                if verification and verified and report is not None:correction=candidate!=report.plan
                if group not in ('G2','M') or practice_proposed:
                    release_info=dict(info)
                    release_features=dict(features)
                    candidate_log.append(dict(tick=t,plan=candidate,information=dict(info),features=dict(features)))
                    if not fixed:published=candidate;publish=t
                    else:phase='prepared'
            elif action=='adopt':
                candidate=report.plan;adopt=True;release_info=dict(command_info);phase='prepared'
                release_features=decision_features(observations[r],judgments[r])
                candidate_log.append(dict(tick=t,plan=candidate,information=dict(command_info),features=dict(release_features),direct_adopt=True))
            if action=='adopt' and not fixed:published=candidate;publish=t
        if t==(publication_tick if fixed else cfg.deadline) and published is None:
            cached_routes=routes(candidate,release_info,w.distances) if candidate is not None and release_info is not None else ()
            cached_valid=candidate is not None and legal(candidate,command_info,w.distances) and all(e<0 or command_info.get('open'+str(e),1)>0 for e in cached_routes)
            published=candidate if cached_valid else (4 if legal(4,command_info,w.distances) else -1)
            publish=t
            # Cached plan includes its information-based allocation. New evidence
            # checks legality; only an explicit fallback replaces that allocation.
            candidate_log.append(dict(tick=t,cached_valid=cached_valid,fallback=not cached_valid,plan=published))
            if not cached_valid or release_info is None:
                release_info=dict(command_info)
                release_features=decision_features(observations[3],judgments[3]) if release_at is None else cutoff_features
        if publish==t and assay is None:
            assay=[forecast(r) for r in range(4)]
            case_features=[visible_values(observations[r]) for r in range(4)]
            case_features[3]=dict(release_features or decision_features(observations[3],judgments[3]))
            observation_limits=[len(o) for o in observations]
            venue_decision_support=venue_estimates(observations[0],memory_views[0],cfg,t)[1]
    info=release_info
    # Physical outcome is generated after the control timeline from the immutable plan.
    outcome=execute_public(w.regions,w.vulnerable,w.order,w.distances,w.capacities,routes(published,info,w.distances),resource_priority(published,info),publish,w.closed,trace,revision)
    if learn or trust_only:
        for r,m in enumerate(team.memories):
            if learn:
                m.clock+=1
                for i in memory_views[r].touched:m.cases[i].last=m.clock
                labels=dict(observed_labels[r])
                if rng(w.seed,w.family,w.event,'feedback',r).random()<cfg.feedback:
                    labels.update(completed=outcome['completed'],v_completed=outcome['v_completed'])
                    for e in outcome['encountered_closed']:labels['fail'+str(e)]=1.
                case=m.add(case_features[r],labels,'mixed-visible',cfg)
                if case is not None:
                    case.decision={'own_prediction':assay[r],'published_plan':published if 'completed' in labels else None,
                        'publish':publish,'scenario':scenario_key(w.distances,w.capacities),
                        'routes':routes(published,info,w.distances),'priority':resource_priority(published,info),
                        'model_prediction':score_plan(published,info,w.distances,w.capacities,publish,cfg)}
                    case.provenance={'seed':w.seed,'family':w.family,'event':w.event,'role':r,
                        'feature_evidence':[o.original for o in observations[r][:observation_limits[r]] if o.value is not None],
                        'judgment_evidence':deepcopy(judgment_evidence[r]),'feedback_labels':list(labels)}
                if r==0:
                    for pair in venue_pairs:
                        c=m.add(pair['features'],pair['labels'],'venue-observation',cfg)
                        if c is not None:c.provenance=dict(pair['provenance'])
                feedback_log.append({'role':r,'labels':dict(labels),'selected_plan':published if 'completed' in labels else None})
            if cfg.trust_adapts and report is not None and r==3:
                checked=[o for o in observations[r] if o.source.endswith(':1') and o.field in report.info and o.value is not None]
                for o in checked:
                    if o.value==report.info[o.field]:m.successes+=1
                    else:m.failures+=1
        team.episode+=1
    accepted=None if report is None or not manipulate else float(published>=0 and published//2==report.plan//2)
    result={'completed':outcome['completed'],'completion':outcome['completed']/60,'v_completion':outcome['v_completed']/12,
            'target_choices':target_choices,
            'forecast_audit':forecast_audit,
            'ordinary_completion':(outcome['completed']-outcome['v_completed'])/48,'publish':publish,'plan':published,
            'acceptance':accepted,'direct_adopt':adopt,'verification':verification,'verified':verified,'correction':correction,
            'practice_complete':practice_received and practice_proposed,'observations':nobs,'operations':sum(spent),
            'practice_received':practice_received,'practice_proposed':practice_proposed,
            'revised':revision is not None,
            'queue_ticks':outcome['queue_ticks'],'rerouted':outcome['rerouted'],'messages':len(message_log),
            'brier':sum((assay[1]['fail'+str(e)]-float(w.failure==e))**2 for e in range(2))/2,
            'count_mae':sum(abs(assay[2].get('n'+str(z),20)-w.regions.count(z)) for z in range(3))/3,
            'predictions':assay,
            'new_cases':[[asdict(c) for c in m.cases if c.born==m.clock] if learn else [] for m in team.memories],
            'command_scores':learning_scores,'venue_support':venue_decision_support,
            'feedback':feedback_log,'candidate_log':candidate_log,
            'verification_token':verification_token,'verification_reply_time':verification_reply_time,
            'venue_pairs':venue_pairs if learn or trace else [],
            'waiting':published<0,'onsite':onsite,'seed':w.seed,'event':w.event,'family':w.family,
            'release_information':dict(release_info),'release_routes':routes(published,release_info,w.distances),'release_priority':resource_priority(published,release_info),
            'group':group,'trace':{'actions':actions,'messages':message_log,'fields':field_log,'public':outcome['trajectory']} if trace else None}
    return result

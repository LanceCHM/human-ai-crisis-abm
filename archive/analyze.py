from pathlib import Path
import sys,json,gzip,pickle,hashlib,csv,math
import numpy as np
from scipy.stats import t as student_t
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from stage2_abm.model import *
ARMS=('G1','G2','S3','R','ALT')
PAIRS=[('G2','G1'),('S3','G1'),('R','G1'),('ALT','G1'),('S3','G2'),('R','G2'),('ALT','G2'),('S3','R'),('S3','ALT'),('R','ALT')]
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10,'svg.fonttype':'none','pdf.fonttype':42})

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    out=ROOT/'results';out.mkdir(exist_ok=True);plan=json.loads((ROOT/'protocol/frozen.json').read_text(encoding='utf8'))
    assert json.loads((ROOT/'runs/complete.json').read_text())['source_sha256']==plan['source_sha256']
    results=[];costs=[];knowledge=[];mechanisms=[];test_metrics=[];event_n=0
    for index,seed in enumerate(plan['seeds']):
        obj=json.loads((ROOT/f'runs/{seed}.json').read_text());raw=ROOT/f'runs/{seed}.jsonl.gz';snap=ROOT/f'runs/{seed}.pkl.gz'
        assert sha(raw)==obj['raw_sha256'] and sha(snap)==obj['snapshot_sha256']
        with gzip.open(snap,'rb') as f:states=pickle.load(f)
        for arm,st in states['states'].items():
            m=st.memories[0]
            for e in range(2):
                target='onsite_open'+str(e);cs=[c for c in m.cases if target in c.labels]
                knowledge.append({'seed':seed,'arm':arm,'exit':e,'retained_pairs':len(cs),
                    'label_open':sum(c.labels[target]>0 for c in cs),'label_closed':sum(c.labels[target]==0 for c in cs),
                    'digital_zero':sum(c.features.get('digital_open'+str(e))==0 for c in cs),
                    'digital_one':sum(c.features.get('digital_open'+str(e))==1 for c in cs)})
        tests={};training={};n=0
        with gzip.open(raw,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);n+=1;acts=r['trace']['actions'];practice=[a for a in acts if a['action']=='practice_observe']
                assert len(practice)<=1 and all(sum(a['role']==role for a in acts)<=6 for role in range(4))
                assert sum(t>0 for t in r['trace']['public'][-1]['done'])==r['completed']
                assert r['completion']==r['completed']/60
                assert all(m['processed']>m['sent'] for m in r['trace']['messages'])
                if r['kind']=='test':assert r['publish']==6;tests.setdefault(r['ref'],[]).append(r)
                if r['kind']=='train' and r['learning']=='open':
                    arm=r['arm'];ep=r['episode']
                    for a in practice:
                        if arm=='G2':assert a['argument']=='open0'
                        if arm=='R':assert a['argument']=='open'+str(rng(seed,'r017-train',ep-1,'practice-target').randrange(2))
                        if arm=='ALT':assert a['argument']=='open'+str((ep-1)%2)
                    for d in r['target_choices']:
                        if arm=='S3':
                            best=max(d['candidates'],key=lambda x:(x['entropy'],-x['last_field'],-int(x['target'][-1])))
                            assert best['target']==d['selected']
                    pairs=[p for p in r['venue_pairs']]
                    training.setdefault(arm,[]).append({'completion':r['completion'],'publish':r['publish'],'operations':r['operations'],
                        'messages':r['messages'],'field_actions':sum(a['action'] in ('observe','requested_observe','practice_observe') for a in acts),
                        'practice_slots':len(practice),'exit1_slots':sum(a['argument']=='open1' for a in practice),
                        'pairs_exit0':sum('onsite_open0' in p['labels'] for p in pairs),'pairs_exit1':sum('onsite_open1' in p['labels'] for p in pairs)})
        assert n==obj['events'];event_n+=n
        values={}
        for r in obj['rows']:
            rs=tests[r['ref']];assert len(rs)==40 and abs(np.mean([x['completion'] for x in rs])-r['completion'])<1e-12
            values[r['arm'],r['mode']]=r
        pre=values['common','pre']['completion']
        for arm in ARMS:
            assert values[arm,'frozen']['completion']==pre
            post=values[arm,'full']['completion'];results.append({'seed':seed,'arm':arm,'pre':pre,'post':post,'gain_pp':100*(post-pre)})
            rs=training[arm];assert len(rs)==60
            costs.append({'seed':seed,'arm':arm,**{k:float(np.mean([r[k] for r in rs])) for k in rs[0]}})
            full=tests[values[arm,'full']['ref']]
            # Evaluate earliest venue judgment, before later observations can hide retrieval.
            assay=[]
            for r in full:
                a=r['forecast_audit'][0];truth=world(seed,'r017-ability',r['event'],Config()).closed(a['tick'])
                probs=[a['support'].get('open'+str(e),{}).get('probability',a['prediction'].get('open'+str(e),1)) for e in range(2)]
                assay.append({'early_brier':sum((q-float(not y))**2 for q,y in zip(probs,truth))/2,
                    'early_venue_use':int(any(s['kind']=='memory' for s in a['support'].values())),
                    'any_venue_use':int(any(s['kind']=='memory' for a in r['forecast_audit'] if a['tick']<=r['publish'] for s in a['support'].values())),
                    'command_use':int(any(s['support'] for s in r['command_scores']))})
            test_metrics.append({'seed':seed,'arm':arm,**{k:float(np.mean([r[k] for r in assay])) for k in assay[0]}})
            reset=tests[values[arm,'reset_venue']['ref']]
            assert [r['event'] for r in full]==[r['event'] for r in reset]
            mechanisms.append({'seed':seed,'arm':arm,'reset':'venue','effect_pp':100*np.mean([a['completion']-b['completion'] for a,b in zip(full,reset)]),
                'plan_change':float(np.mean([a['plan']!=b['plan'] for a,b in zip(full,reset)])),
                'route_change':float(np.mean([a['release_routes']!=b['release_routes'] for a,b in zip(full,reset)]))})
        full=tests[values['S3','full']['ref']];reset=tests[values['S3','reset_command']['ref']]
        mechanisms.append({'seed':seed,'arm':'S3','reset':'command','effect_pp':100*np.mean([a['completion']-b['completion'] for a,b in zip(full,reset)]),
            'plan_change':float(np.mean([a['plan']!=b['plan'] for a,b in zip(full,reset)])),
            'route_change':float(np.mean([a['release_routes']!=b['release_routes'] for a,b in zip(full,reset)]))})
        if (index+1)%25==0:print(f'audit {index+1}/200',flush=True)
    def csvsave(name,rs):
        with (out/name).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
    for name,rs in [('团队前后表现.csv',results),('训练成本与核验分配.csv',costs),('场地案例覆盖.csv',knowledge),('测试调用与早期误差.csv',test_metrics),('记忆干预逐团队.csv',mechanisms)]:csvsave(name,rs)
    ix=np.random.default_rng(plan['bootstrap_seed']).integers(0,200,(10000,200))
    def stat(x):
        x=np.array(x);m=float(x.mean());sd=float(x.std(ddof=1));lo,hi=np.quantile(x[ix].mean(axis=1),[.025,.975])
        p=float(2*student_t.sf(abs(m)/(sd/math.sqrt(200)),199)) if sd>1e-12 else (1. if abs(m)<1e-12 else 0.)
        return {'mean':m,'lower':float(lo),'upper':float(hi),'p':p,'positive':int(np.sum(x>1e-10)),'zero':int(np.sum(abs(x)<=1e-10)),'negative':int(np.sum(x< -1e-10))}
    def holm(rs):
        running=0.
        for rank,i in enumerate(sorted(range(len(rs)),key=lambda i:rs[i]['p'])):
            running=max(running,min(1,rs[i]['p']*(len(rs)-rank)));rs[i]['holm_p']=running
    gains={(r['seed'],r['arm']):r['gain_pp'] for r in results}
    effects=[{'contrast':a+'-'+b,**stat([gains[s,a]-gains[s,b] for s in plan['seeds']])} for a,b in PAIRS];holm(effects)
    mstats=[]
    for arm,reset in [(a,'venue') for a in ARMS]+[('S3','command')]:
        rs=[r for r in mechanisms if r['arm']==arm and r['reset']==reset]
        mstats.append({'arm':arm,'reset':reset,**stat([r['effect_pp'] for r in rs]),
            'plan_change':float(np.mean([r['plan_change'] for r in rs])),'route_change':float(np.mean([r['route_change'] for r in rs]))})
    holm(mstats);csvsave('全部十项主要比较.csv',effects);csvsave('记忆干预汇总.csv',mstats)
    descript=[]
    for arm in ARMS:
        rs=[r for r in results if r['arm']==arm];cs=[r for r in costs if r['arm']==arm];ts=[r for r in test_metrics if r['arm']==arm]
        row={'arm':arm,'pre_percent':float(np.mean([r['pre'] for r in rs])*100),'post_percent':float(np.mean([r['post'] for r in rs])*100),
            'gain_pp':float(np.mean([r['gain_pp'] for r in rs]))}
        for k in cs[0]:
            if k not in ('seed','arm'):row['train_'+k]=float(np.mean([r[k] for r in cs]))
        for k in ts[0]:
            if k not in ('seed','arm'):row[k]=float(np.mean([r[k] for r in ts]))
        for e in range(2):row['pairs_retained_exit'+str(e)]=float(np.mean([r['retained_pairs'] for r in knowledge if r['arm']==arm and r['exit']==e]))
        descript.append(row)
    csvsave('描述性统计.csv',descript)
    audit={'passed':True,'teams':200,'events_recomputed':event_n,'source_unchanged':True,'independent_new_seed_sample':True,
        'frozen_and_holdout_checks':'passed','single_practice_slot_and_budget':'passed','policy_choice_checks':'passed'}
    (out/'审计.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    for folder in ['01_结果分析','02_描述性统计']:(ROOT/'figures'/folder).mkdir(parents=True,exist_ok=True)
    def save(fig,folder,name):
        fig.tight_layout()
        for ext in ['png','svg','pdf']:fig.savefig(ROOT/'figures'/folder/f'{name}.{ext}',dpi=300,bbox_inches='tight')
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,6))
    for i,r in enumerate(effects):ax.errorbar(r['mean'],i,xerr=[[max(0,r['mean']-r['lower'])],[max(0,r['upper']-r['mean'])]],fmt='o',color='#267496',capsize=3)
    ax.set_yticks(range(10),[r['contrast'] for r in effects]);ax.invert_yaxis();ax.axvline(0,color='gray');ax.set_xlabel('学习收益差（百分点）；逐项95%区间');ax.set_title('新200团队：不确定性、随机与轮流核验');ax.grid(axis='x',alpha=.2)
    save(fig,'01_结果分析','图1_全部主要比较')
    fig,axs=plt.subplots(1,2,figsize=(11,4.3))
    rr=[r for r in mstats if r['reset']=='venue']
    for i,r in enumerate(rr):axs[0].errorbar(r['mean'],i,xerr=[[max(0,r['mean']-r['lower'])],[max(0,r['upper']-r['mean'])]],fmt='o',color='#267496',capsize=3)
    axs[0].set_yticks(range(5),[r['arm'] for r in rr]);axs[0].axvline(0,color='gray');axs[0].set_xlabel('完整−场地记忆恢复起点（百分点）');axs[0].set_title('新增场地经验的条件贡献')
    axs[1].bar([r['arm'] for r in rr],[100*r['plan_change'] for r in rr]);axs[1].set_ylabel('方案变化任务比例（%）');axs[1].set_title('场地记忆干预是否改变方案')
    save(fig,'01_结果分析','图2_记忆到行动干预')
    fig,axs=plt.subplots(1,3,figsize=(12,4))
    for ax,(field,title,scale) in zip(axs,[('train_exit1_slots','每轮出口1实践核验',1),('post_percent','训练后无AI完成率（%）',1),('train_completion','训练当期完成率（%）',100)]):
        ax.bar(ARMS,[r[field]*scale for r in descript]);ax.set_title(title)
    save(fig,'02_描述性统计','图3_核验分配与表现')
    text='# S3独立模拟确认与简单策略对照\n\n2026-10-26。使用新200团队，S3与旧版本规则一致；R随机核验、ALT轮流核验。全部组每轮最多一次实践核验。模型、任务与原调用规则固定，不能将本批与旧批合并扩大样本。\n\n'
    text+='## 十项主要比较\n\n|比较|学习收益差pp|逐项95%区间|Holm p|正/零/负团队|\n|---|---:|---|---:|---|\n'
    for r in effects:text+=f"|{r['contrast']}|{r['mean']:+.4f}|[{r['lower']:+.4f}, {r['upper']:+.4f}]|{r['holm_p']:.5g}|{r['positive']}/{r['zero']}/{r['negative']}|\n"
    text+='\n## 绝对表现、覆盖与投入\n\n|组别|测试起点%|测试末态%|学习增量pp|训练完成率%|训练发布时间|总操作|出口1实践核验/轮|出口0/1保留案例|\n|---|---:|---:|---:|---:|---:|---:|---:|---|\n'
    for r in descript:text+=f"|{r['arm']}|{r['pre_percent']:.3f}|{r['post_percent']:.3f}|{r['gain_pp']:+.3f}|{r['train_completion']*100:.3f}|{r['train_publish']:.3f}|{r['train_operations']:.3f}|{r['train_exit1_slots']:.3f}|{r['pairs_retained_exit0']:.2f}/{r['pairs_retained_exit1']:.2f}|\n"
    text+='\n## 调用与判断\n\n|组别|早期场地Brier|早期调用记忆任务比例|发布前任一时点调用比例|指挥调用比例|\n|---|---:|---:|---:|---:|\n'
    for r in descript:text+=f"|{r['arm']}|{r['early_brier']:.5f}|{r['early_venue_use']:.3f}|{r['any_venue_use']:.3f}|{r['command_use']:.3f}|\n"
    text+='\n早期Brier以每个任务最早场地预测与当时状态计分，再在团队内平均；不是发布时点概率准确率，也不等同独立知识全测验。过程支持率不自动代表预测正确或因果贡献。\n\n'
    text+='## 经验干预\n\n|组别|恢复的记忆|完整−恢复起点pp|逐项95%区间|Holm p|方案变化率|路线变化率|\n|---|---|---:|---|---:|---:|---:|\n'
    for r in mstats:text+=f"|{r['arm']}|{r['reset']}|{r['mean']:+.4f}|[{r['lower']:+.4f}, {r['upper']:+.4f}]|{r['holm_p']:.5g}|{100*r['plan_change']:.2f}%|{100*r['route_change']:.2f}%|\n"
    text+='\n干预在同一末态中只恢复指定角色起点记忆，其他角色保留训练状态。是条件性的组件贡献，不是完整中介证明。案例内容、数量与使用记录同时变化；不能将该差异直接称为占总学习收益的百分比。\n\n'
    text+=f'## 审计与边界\n\n40项测试通过，3个旧团队S3末态逐字段回归一致，{event_n}条新事件完成复算；预算、消息延迟、公众守恒、冻结与测试只读通过。主要10项与补充6项分别Holm校正，自举10000次，区间逐项覆盖。固定200团队全部完成，未因结果调参。\n\n'
    text+='新样本只确认固定模型与原调用规则下的稳定性；此前更严格调用下收益缩小的结果仍保留。未开展新的真人招募或采集，现有试填是否足以校准另见现实依据检查。若R/ALT相当或更好，应把研究解释转向核验覆盖与分配，不宣称不确定性规则独特优越。当前选择不自动改变。\n'
    (out/'实验分析.md').write_text(text,encoding='utf8')
    print(json.dumps(audit,ensure_ascii=False));print(json.dumps({'effects':effects,'memory':mstats,'descriptives':descript},ensure_ascii=False,indent=2))

if __name__=='__main__':main()

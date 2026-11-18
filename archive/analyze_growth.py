"""Post hoc descriptive analysis of existing frozen logs; no new simulations."""
from pathlib import Path
import sys,json,gzip,pickle,hashlib,csv
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'v5_S3独立确认'
sys.path.insert(0,str(SOURCE/'src'))
from stage2_abm.model import *
ARMS=('G1','G2','S3','R','ALT');POINTS=(5,10,15,30,45,60)

def worker(seed):
    obj=json.loads((SOURCE/f'runs/{seed}.json').read_text());raw=SOURCE/f'runs/{seed}.jsonl.gz'
    assert hashlib.sha256(raw.read_bytes()).hexdigest()==obj['raw_sha256']
    with gzip.open(SOURCE/f'runs/{seed}.pkl.gz','rb') as f:snap=pickle.load(f)
    initial=snap['initial'].memories[0]
    initial_age1=[sum('onsite_open'+str(e) in c.labels and c.features.get('age'+str(e))==1 for c in initial.cases) for e in range(2)]
    totals={a:[0]*60 for a in ARMS};age1={a:[[0,0] for _ in range(60)] for a in ARMS}
    with gzip.open(raw,'rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line)
            if r['kind']!='train' or r['learning']!='open':continue
            a=r['arm'];ep=r['episode']-1;pairs=r['venue_pairs']
            assert len(pairs)==sum(c['source']=='venue-observation' for c in r['new_cases'][0])
            totals[a][ep]=len(pairs)
            for pair in pairs:
                e=int(next(iter(pair['labels']))[-1])
                if pair['features']['age'+str(e)]==1:age1[a][ep][e]+=1
    rows=[];curves=[]
    for a in ARMS:
        cum_total=0;cum_age=[0,0];first_both=0 if all(initial_age1) else None
        for ep in range(60):
            cum_total+=totals[a][ep]
            cum_age=[x+y for x,y in zip(cum_age,age1[a][ep])]
            if first_both is None and all(c+i>0 for c,i in zip(cum_age,initial_age1)):first_both=ep+1
            curves.append({'seed':seed,'arm':a,'round':ep+1,'cumulative_pairs':cum_total,
                'cumulative_age1':sum(cum_age),'age1_exit0':cum_age[0],'age1_exit1':cum_age[1],
                'both_ever_formed':int(all(c+i>0 for c,i in zip(cum_age,initial_age1)))})
        retained=snap['states'][a].memories[0].cases
        row={'seed':seed,'arm':a,'pairs_per_round':cum_total/60,'age1_per_round':sum(cum_age)/60,
            'initial_age1_exit0':initial_age1[0],'initial_age1_exit1':initial_age1[1],
            'first_both_round':first_both if first_both is not None else '',
            'not_formed_by60':int(first_both is None),
            'retained_age1_exit0':sum('onsite_open0' in c.labels and c.features.get('age0')==1 for c in retained),
            'retained_age1_exit1':sum('onsite_open1' in c.labels and c.features.get('age1')==1 for c in retained)}
        for cp in POINTS:
            c=next(c for c in curves if c['arm']==a and c['round']==cp)
            row['total_at'+str(cp)]=c['cumulative_pairs'];row['age1_at'+str(cp)]=c['cumulative_age1'];row['both_by'+str(cp)]=c['both_ever_formed']
        rows.append(row)
    return rows,curves

def main():
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':10})
    rows=[];curves=[]
    with ProcessPoolExecutor(max_workers=6) as pool:
        jobs=[pool.submit(worker,s) for s in range(970000,970200)]
        for i,f in enumerate(as_completed(jobs),1):
            rr,cc=f.result();rows+=rr;curves+=cc
            if i%50==0:print(f'growth audit {i}/200',flush=True)
    rows.sort(key=lambda r:(r['seed'],r['arm']));curves.sort(key=lambda r:(r['seed'],r['arm'],r['round']))
    def save(name,rs):
        with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
    save('逐团队经验形成.csv',rows);save('逐轮累计经验.csv',curves)
    summaries=[]
    for a in ARMS:
        rs=[r for r in rows if r['arm']==a];formed=[r['first_both_round'] for r in rs if r['first_both_round']!='']
        summary={'arm':a,'pairs_per_round':float(np.mean([r['pairs_per_round'] for r in rs])),
            'age1_per_round':float(np.mean([r['age1_per_round'] for r in rs])),
            'median_round_among_formed':float(np.median(formed)) if formed else None,
            'not_formed_by60':float(np.mean([r['not_formed_by60'] for r in rs])),
            'retained_age1_exit0':float(np.mean([r['retained_age1_exit0'] for r in rs])),
            'retained_age1_exit1':float(np.mean([r['retained_age1_exit1'] for r in rs]))}
        for cp in POINTS:
            for prefix in ['total_at','age1_at','both_by']:summary[prefix+str(cp)]=float(np.mean([r[prefix+str(cp)] for r in rs]))
        summaries.append(summary)
    (ROOT/'汇总.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding='utf8');save('经验形成描述统计.csv',summaries)
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for a in ARMS:
        for ax,key in zip(axes,['cumulative_pairs','cumulative_age1']):
            data=np.array([[r[key] for r in curves if r['seed']==s and r['arm']==a] for s in range(970000,970200)])
            ax.plot(range(1,61),data.mean(axis=0),label=a)
    axes[0].set_title('累计形成的全部场地观察配对');axes[1].set_title('累计形成的年龄1配对（匹配最早测试查询）')
    for ax in axes:ax.set_xlabel('训练轮次');ax.set_ylabel('每团队累计配对数');ax.grid(alpha=.2);ax.legend()
    fig.tight_layout()
    for ext in ['png','svg','pdf']:fig.savefig(ROOT/f'经验形成轨迹.{ext}',dpi=300,bbox_inches='tight')
    plt.close(fig)
    text='# 经验形成速度的补充描述\n\n2026-10-26，针对既有v5原始日志的事后描述分析，未新增模拟或改变冻结结果。累计形成数不是当前库存；案例容量限制可能淘汰旧案例。年龄1指现场标签与其数字记录的时间差，与最早测试查询的精确年龄匹配要求相对应，不代表经验本身更真实或更全面。\n\n'
    text+='|组别|全部配对/轮|年龄1配对/轮|前10轮形成双出口年龄1经验比例|前30轮比例|60轮末比例|形成者的首次轮次中位数|末态保留年龄1案例 出口0/1|\n|---|---:|---:|---:|---:|---:|---:|---|\n'
    for r in summaries:text+=f"|{r['arm']}|{r['pairs_per_round']:.3f}|{r['age1_per_round']:.3f}|{r['both_by10']*100:.1f}%|{r['both_by30']*100:.1f}%|{r['both_by60']*100:.1f}%|{r['median_round_among_formed']}|{r['retained_age1_exit0']:.2f}/{r['retained_age1_exit1']:.2f}|\n"
    text+='\n不能据全部配对增长曲线就声称能力提升速度更快；中途没有按轮测量独立任务表现。当前可描述的是观察配对获得率、特定查询条件的经验覆盖形成时间，以及末态的适用案例库存。首次形成统计只要求曾形成至少一条每出口的年龄1案例，不保证一直保留，也不保证标签正确；中位数仅在完成者中计算，需与60轮未完成比例一起读。\n'
    (ROOT/'经验积累分析.md').write_text(text,encoding='utf8')
    print(json.dumps(summaries,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

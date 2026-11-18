"""Recompute manuscript tables and numerical figures from per-team data."""
from pathlib import Path
import argparse,csv,json,sys,shutil,runpy
import numpy as np
from scipy.stats import t as student_t
ROOT=Path(__file__).resolve().parents[1]
ARMS=['G1','G2','S3','R','ALT'];PAIRS=[('G2','G1'),('S3','G1'),('R','G1'),('ALT','G1'),('S3','G2'),('R','G2'),('ALT','G2'),('S3','R'),('S3','ALT'),('R','ALT')]
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
def validate_teams(rows,arms=ARMS):
 expected={(s,a) for s in range(970000,970200) for a in arms}
 actual=[(int(r['seed']),r['arm']) for r in rows]
 if len(actual)!=len(expected) or set(actual)!=expected:raise ValueError('Missing, duplicated, or unexpected team/arm records.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=ROOT/'data/published');p.add_argument('--output',type=Path,default=ROOT/'outputs/reproduced');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 rows=read(a.data/'results/团队前后表现.csv');seeds=sorted({int(r['seed']) for r in rows});assert seeds==list(range(970000,970200))
 validate_teams(rows)
 for r in rows:
  if not np.isclose(float(r['gain_pp']),100*(float(r['post'])-float(r['pre'])),atol=1e-10):raise ValueError('Gain inconsistent with pre/post values.')
 ix=np.random.default_rng(261026).integers(0,200,(10000,200))
 def stat(xs):
  x=np.array(xs);m=float(x.mean());sd=x.std(ddof=1);lo,hi=np.quantile(x[ix].mean(axis=1),[.025,.975]);p=float(2*student_t.sf(abs(m)/(sd/np.sqrt(200)),199)) if sd>1e-12 else (1. if abs(m)<1e-12 else 0.)
  return dict(mean=m,lower=float(lo),upper=float(hi),p=p)
 def holm(rs):
  last=0
  for rank,i in enumerate(sorted(range(len(rs)),key=lambda i:rs[i]['p'])):last=max(last,min(1,rs[i]['p']*(len(rs)-rank)));rs[i]['holm_p']=last
 gain={(int(r['seed']),r['arm']):float(r['gain_pp']) for r in rows}
 tab2=[]
 for arm in ARMS:
  rr=[r for r in rows if r['arm']==arm];assert len(rr)==200
  tab2.append(dict(arm=arm,pre_percent=np.mean([float(r['pre']) for r in rr])*100,post_percent=np.mean([float(r['post']) for r in rr])*100,gain_pp=np.mean([float(r['gain_pp']) for r in rr])))
 save(out/'Table_2.csv',tab2)
 contrasts=[dict(contrast=x+'-'+y,**stat([gain[s,x]-gain[s,y] for s in seeds])) for x,y in PAIRS];holm(contrasts);save(out/'Table_3.csv',contrasts)
 m=read(a.data/'results/记忆干预逐团队.csv');tab4=[]
 validate_teams([r for r in m if r['reset']=='venue'])
 for arm in ['G1','G2','S3']:
  rr=sorted([r for r in m if r['arm']==arm and r['reset']=='venue'],key=lambda r:int(r['seed']))
  z=stat([-float(r['effect_pp']) for r in rr]);tab4.append(dict(arm=arm,change_pp=z['mean'],lower=z['lower'],upper=z['upper'],plan_change_percent=100*np.mean([float(r['plan_change']) for r in rr])))
 save(out/'Table_4.csv',tab4)
 tables=json.loads((ROOT/'assets/manuscript_tables.json').read_text(encoding='utf-8'))
 with (out/'Table_1.csv').open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerows(tables[0])
 # Figure 3 retains team pairing and the original deterministic jitter seed in its plotting script.
 paired=[dict(contrast=x+'-'+y,seed=s,gain_difference_pp=gain[s,x]-gain[s,y]) for x,y in PAIRS for s in seeds]
 save(out/'作图用逐团队差异.csv',paired)
 growth=read(a.data/'growth/逐团队经验形成.csv');metric=read(a.data/'results/测试调用与早期误差.csv');fig4=[]
 validate_teams(growth);validate_teams(metric)
 for arm in ARMS:
  g=[r for r in growth if r['arm']==arm];mm=[r for r in metric if r['arm']==arm];assert len(g)==len(mm)==200
  mean=lambda rs,k:float(np.mean([float(r[k]) for r in rs]))
  fig4.append(dict(arm=arm,total_new_pairs=mean(g,'total_at60'),new_lag1_pairs=mean(g,'age1_at60'),retained_lag1_exit0=mean(g,'retained_age1_exit0'),retained_lag1_exit1=mean(g,'retained_age1_exit1'),early_memory_use_percent=100*mean(mm,'early_venue_use'),early_brier=mean(mm,'early_brier')))
 save(out/'经验覆盖与调用_作图数据.csv',fig4);save(out/'Figure_4_data.csv',fig4)
 for name in ['plot_figure3.py','plot_figure4.py']:
  target=out/name;shutil.copyfile(ROOT/'scripts'/name,target);old=sys.argv;sys.argv=[str(target),'--contrast'];runpy.run_path(str(target),run_name='__main__');sys.argv=old
 # Compare the newly computed statistics with archived published machine-readable results.
 archived=read(ROOT/'data/published/results/全部十项主要比较.csv')
 assert len(archived)==len(contrasts)==10
 for x,y in zip(contrasts,archived):
  assert x['contrast']==y['contrast']
  for k in ['mean','lower','upper','p','holm_p']:assert np.isclose(x[k],float(y[k]),rtol=1e-10,atol=1e-10),(x['contrast'],k)
 baseline={r['arm']:r for r in read(ROOT/'data/published/results/描述性统计.csv')}
 for r in tab2:
  for k in ['pre_percent','post_percent','gain_pp']:assert np.isclose(r[k],float(baseline[r['arm']][k]),atol=1e-10,rtol=1e-10),('Table 2',r['arm'],k)
 baseline={r['arm']:r for r in read(ROOT/'data/published/results/记忆干预汇总.csv') if r['reset']=='venue'}
 for r in tab4:
  b=baseline[r['arm']]
  for k,value in {'change_pp':-float(b['mean']),'lower':-float(b['upper']),'upper':-float(b['lower']),'plan_change_percent':100*float(b['plan_change'])}.items():assert np.isclose(r[k],value,atol=1e-10,rtol=1e-10),('Table 4',r['arm'],k)
 baseline={r['arm']:r for r in read(ROOT/'data/published/reference_figure4.csv')}
 for r in fig4:
  for k in r:
   if k!='arm':assert np.isclose(r[k],float(baseline[r['arm']][k]),atol=1e-10,rtol=1e-10),('Figure 4',r['arm'],k)
 (out/'validation.json').write_text(json.dumps({'teams':200,'paired_comparisons':10,'archived_comparison_match':True,'table4_sign':'reset minus full','conceptual_figures':'Figures 1 and 2 excluded by author instruction'},indent=2))
 print('Reproduction complete:',out)
if __name__=='__main__':main()

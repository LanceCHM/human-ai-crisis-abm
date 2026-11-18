"""Recompute original audit/statistics and growth summaries from trusted raw logs."""
from pathlib import Path
import argparse,sys,json,types,os,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,default=ROOT/'data/published');p.add_argument('--output',type=Path,default=ROOT/'outputs/raw_audit');a=p.parse_args();source=a.run.resolve();run=a.output.resolve()
 if source==run:raise ValueError('Choose a separate output directory.')
 if run.exists() and any(run.iterdir()):raise ValueError('Use a fresh audit output directory; cached logs from another run must not be reused.')
 if json.loads((source/'runs/complete.json').read_text())['teams']!=200:raise ValueError('Full statistical audit requires 200 teams.')
 (run/'runs').mkdir(parents=True,exist_ok=True);(run/'protocol').mkdir(exist_ok=True)
 for f in (source/'runs').iterdir():
  target=run/'runs'/f.name
  if not target.exists():
   try:os.link(f,target)
   except OSError:shutil.copyfile(f,target)
 plan=source/'protocol/frozen.json'
 shutil.copyfile(plan if plan.exists() else ROOT/'archive/frozen.json',run/'protocol/frozen.json')
 if json.loads((run/'runs/complete.json').read_text())['teams']!=200:raise ValueError('Full statistical audit requires 200 teams.')
 plan_data=json.loads((run/'protocol/frozen.json').read_text(encoding='utf-8'))
 if plan_data['seeds']!=list(range(970000,970200)):raise ValueError('Unexpected seed list; this audit reproduces the fixed manuscript sample.')
 # Execute original numeric analysis up to completion of its audit, omitting unrelated legacy plots/reports.
 s=(ROOT/'archive/analyze.py').read_text(encoding='utf-8').split("    for folder in ['01_结果分析'")[0]
 module=types.ModuleType('numeric_audit');module.__file__=str(ROOT/'archive/analyze.py');exec(compile(s,module.__file__,'exec'),module.__dict__);module.ROOT=run;module.main()
 # Growth worker remains unchanged; sequential iteration is portable and deterministic.
 s=(ROOT/'archive/analyze_growth.py').read_text(encoding='utf-8').split('def main():')[0]
 g=types.ModuleType('growth_audit');g.__file__=str(ROOT/'archive/analyze_growth.py');exec(compile(s,g.__file__,'exec'),g.__dict__);g.SOURCE=run
 import csv
 rows=[]
 for n,seed in enumerate(range(970000,970200),1):
  rr,_=g.worker(seed);rows.extend(rr)
  if n%25==0:print(f'growth {n}/200',flush=True)
 (run/'growth').mkdir(exist_ok=True)
 with (run/'growth/逐团队经验形成.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
 print('Raw audit completed. Use reproduce.py --data with this run directory.')
if __name__=='__main__':main()

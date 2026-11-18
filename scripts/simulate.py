"""Portable entry point; original worker and model are unchanged."""
from pathlib import Path
import argparse,sys,json,time,hashlib
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'archive')]
import run as engine
def init(output):engine.ROOT=Path(output)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'outputs/new_run');p.add_argument('--workers',type=int,default=4);p.add_argument('--teams',type=int,default=200);a=p.parse_args()
 if not 1<=a.teams<=200:p.error('teams must be 1..200; only 200 reproduces the paper')
 dest=a.output.resolve()
 if dest== (ROOT/'data/published').resolve():p.error('Published data are read-only inputs; choose a fresh output directory.')
 if (dest/'runs').exists() and any((dest/'runs').iterdir()):p.error('Use a fresh output directory to avoid mixing runs.')
 (dest/'runs').mkdir(parents=True,exist_ok=True);(dest/'protocol').mkdir(exist_ok=True)
 plan=json.loads((ROOT/'archive/frozen.json').read_text(encoding='utf-8'));plan['seeds']=list(range(970000,970000+a.teams))
 sources=list((ROOT/'src').rglob('*.py'))+[ROOT/'archive/run.py',Path(__file__).resolve()]
 plan['source_sha256']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
 plan['packaging_note']='Original simulation worker, unchanged model; portable entry point. Historical cross-version compatibility check is replaced by packaged regression tests.'
 (dest/'protocol/frozen.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
 start=time.time()
 with ProcessPoolExecutor(max_workers=a.workers,initializer=init,initargs=(str(dest),)) as pool:
  jobs=[pool.submit(engine.worker,s) for s in plan['seeds']]
  for i,f in enumerate(as_completed(jobs),1):print(f'{i}/{a.teams}: {f.result()}',flush=True)
 (dest/'runs/complete.json').write_text(json.dumps({'teams':a.teams,'seconds':time.time()-start,'source_sha256':plan['source_sha256']},indent=2))
if __name__=='__main__':main()

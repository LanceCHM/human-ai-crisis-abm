"""Verify archived inputs and source integrity before reproduction."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def main():
 failures=[];count=0
 for line in (ROOT/'MANIFEST.sha256').read_text(encoding='utf-8').splitlines():
  expected,name=line.split('  ',1);p=ROOT/name;count+=1
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:failures.append(name)
 if failures:raise SystemExit('Checksum mismatch or missing file: '+', '.join(failures))
 plan=json.loads((ROOT/'archive/frozen.json').read_text(encoding='utf-8'))
 for name,expected in plan['source_sha256'].items():
  name=name.replace('\\','/');p=ROOT/name
  if name in ['run.py','analyze.py']:p=ROOT/'archive'/name
  if name=='s3_model.py':p=ROOT/'archive/frozen_sources'/name
  if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise SystemExit('Original frozen source differs: '+name)
 print(f'All {count} packaged source/input checksums verified.')
if __name__=='__main__':main()

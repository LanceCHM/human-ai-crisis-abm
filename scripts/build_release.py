"""Build a clean review ZIP using the verified manifest, excluding caches/new-run outputs."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from verify_manifest import main as verify
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 verify()
 target=ROOT.parent/'Final_Code_Anonymous.zip'
 names=[line.split('  ',1)[1] for line in (ROOT/'MANIFEST.sha256').read_text(encoding='utf-8').splitlines()]+['MANIFEST.sha256']
 with ZipFile(target,'w',ZIP_DEFLATED,compresslevel=1) as z:
  for name in names:z.write(ROOT/name,'Final Code/'+name)
 print(target)

import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from reproduce import validate_teams
import audit_raw
def records():return [dict(seed=s,arm=a) for s in range(970000,970200) for a in ['G1','G2','S3','R','ALT']]
def test_complete_team_matrix():validate_teams(records())
def test_duplicate_cannot_replace_missing_team():
 rs=records();rs[-1]=dict(rs[-2])
 with pytest.raises(ValueError):validate_teams(rs)
def test_missing_team_rejected():
 with pytest.raises(ValueError):validate_teams(records()[:-1])
def test_audit_rejects_existing_output(tmp_path,monkeypatch):
 out=tmp_path/'existing';out.mkdir();(out/'marker.txt').write_text('old run')
 monkeypatch.setattr(sys,'argv',['audit_raw.py','--output',str(out)])
 with pytest.raises(ValueError,match='fresh audit'):audit_raw.main()

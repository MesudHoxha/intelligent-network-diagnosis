"""Source gate for future-only X6-R1.2 acceptance hardening."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
from src.expansion.x6_r1_gate import verify_x6_r1_source
ROOT=Path(__file__).resolve().parents[2]
PLAN=Path('plans/expansion/X6_R1_2_FUTURE_AUTHORITATIVE_ACCEPTANCE_HARDENING_V1.json')
def verify_x6_r1_2(root:Path=ROOT)->dict[str,object]:
    verify_x6_r1_source(root); plan=json.loads((Path(root)/PLAN).read_text()); auth=plan.get('runtime_scientific_authorization'); bindings=plan.get('source_bindings')
    if plan.get('release_id')!='X6_R1_2_FUTURE_AUTHORITATIVE_ACCEPTANCE_HARDENING' or not isinstance(auth,dict) or len(auth)!=10 or any(auth.values()): raise ValueError('X6-R1.2 boundary drifted')
    if not isinstance(bindings,list) or len(bindings)!=7: raise ValueError('X6-R1.2 requires seven source bindings')
    for row in bindings:
        if not isinstance(row,dict) or not isinstance(row.get('path'),str) or not isinstance(row.get('sha256'),str): raise ValueError('X6-R1.2 source binding malformed')
        path=Path(root)/row['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']: raise ValueError('X6-R1.2 source binding drifted: '+row['path'])
    return plan

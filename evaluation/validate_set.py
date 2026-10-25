import argparse
import json
from pathlib import Path

def load(path,require_reviewed=False):
    rows=[json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(rows)!=200 or len({r['id'] for r in rows})!=200:
        raise ValueError('Expected exactly 200 distinct question IDs')
    for r in rows:
        if not all(r.get(k) for k in ('question','reference','intent_id')):
            raise ValueError('Missing question, reference or intent')
        if require_reviewed and (r.get('reviewed') is not True or not r.get('expected_answer_ids')):
            raise ValueError('Every golden row needs human review and accepted answer IDs')
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('path')
    p.add_argument('--reviewed',action='store_true')
    a=p.parse_args()
    rows=load(a.path,a.reviewed)
    print(f"{len(rows)} rows; {len({r['intent_id'] for r in rows})} intent groups; reviewed={all(r.get('reviewed') for r in rows)}")

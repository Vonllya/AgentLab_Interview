"""Read-only protected asset audit and actual specialist-run summaries."""
import hashlib,json
from pathlib import Path
from backend import generation as g,storage as s
out=Path('data/roles-verification')
before=json.loads((out/'protected-before.json').read_text())
after={'jobs':{id:hashlib.sha256(json.dumps(s.get('generation',id),sort_keys=True).encode()).hexdigest() for id in before['jobs']},'published':{p:hashlib.sha256((s.DATA/p).read_bytes()).hexdigest() for p in before['published']}}
assert before==after,'Protected source records or published assets changed'
approved=g.get('81a3a18745ed4eaba0813d8b3f6d99b4')
digest=g.digest({'contract':approved['contract_hash'],'assets':{k:g.digest(g.asset(approved,k)) for k in ('build','evaluation','teaching')},'matrix':approved['matrix']})
assert digest=='1bc32e924954166a81386b76a7f66dceda9b61469d0da06baca1ca7ad8b4c3c1'
rows=[]
for j in s.all_objects('generation'):
 if j.get('parent_job') not in before['jobs'] or j.get('policy_version')!='roles-v1':continue
 matrices=[*j.get('validation_history',[]),j.get('matrix')]
 # Inherited matrix is evidence, not a newly executed verification.
 actual=[m for m in matrices if m and m['id']!=j.get('inherited_matrix_id')]
 parent=g.get(j['parent_job'])
 row={'id':j['id'],'parent':j['parent_job'],'status':j['status'],'requests':j['request_count'],'budget':j['budget'],'roles':[a['stage'] for a in j['attempts']],'models':sorted({a.get('metadata',{}).get('model','unknown') for a in j['attempts']}),'completed_matrices':sum(bool(m.get('finished')) for m in actual),'started_matrices':len(actual),'latest_gates':(j.get('matrix') or {}).get('gates'),'error':j.get('error'),'failures':[f['error'] for f in j.get('failure_history',[])],'unchanged_baselines':{k:g.asset(j,'build')[k]==g.asset(parent,'build')[k] for k in ('normal','faulty','reference')},'evaluation_unchanged':g.asset(j,'evaluation')==g.asset(parent,'evaluation'),'matrix_id':(j.get('matrix') or {}).get('id'),'review_digest':j.get('review_digest')}
 rows.append(row)
prior=json.loads(Path('data/v02-verification/approved-final-integrity.json').read_text())
r=s.get('report',prior['report']);run=s.get('run',prior['run'])
assert r['snapshot']==run['snapshot']==r['objective']['snapshot']==prior['snapshot']
assert s.get('session',prior['session'])['version']=='1.0.0'
result={'historical_report_snapshot_verified':r['id'],'protected_unchanged':True,'protected_jobs':len(after['jobs']),'protected_files':len(after['published']),'approved_digest':digest,'real_attempts':sorted(rows,key=lambda r:r['id'])}
usage_totals={k:0 for k in ('prompt_tokens','completion_tokens','total_tokens')};usage_missing=0
for row in rows:
 for attempt in g.get(row['id'])['attempts']:
  usage=attempt.get('metadata',{}).get('usage') or {}
  if any(type(usage.get(k)) is not int for k in usage_totals):usage_missing+=1
  for k in usage_totals:
   if type(usage.get(k)) is int:usage_totals[k]+=usage[k]
result.update(reported_usage_sum=usage_totals,missing_usage_attempts=usage_missing)
(out/'final-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({**{k:v for k,v in result.items() if k!='real_attempts'},'real_attempts':[{k:r[k] for k in ('id','status','requests','started_matrices','completed_matrices','latest_gates')} for r in rows]},ensure_ascii=False,indent=2))

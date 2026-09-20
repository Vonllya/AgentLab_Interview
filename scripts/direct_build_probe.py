"""Opt-in bounded merged-build live probe; no publication or production-data writes."""
import os
import json
import time
from pathlib import Path
assert os.getenv('AGENTLAB_REAL_SMOKE')=='1','Explicit real probe opt-in required'
root=Path(__file__).resolve().parents[1]
os.environ['AGENTLAB_DATA']=str(root/'data/direct-build-verification/real-isolated')
from backend import generation as g, generation_budget as b, storage as s, agent
from backend.generation_schema import Request
assert agent.mode()=='real','Real configuration unavailable; mock is not real validation'
s.init()
j=g.create(Request(requirement='Agent 启动时后端未就绪，导致空工具注册',minutes=45,difficulty='偏低'),direct_build=True)
j['budget']=b.initialize(b.BudgetPolicy(requests=12,output_tokens=64000,input_bytes=450000,seconds=600,validations=5));g.put(j)
print(json.dumps({'id':j['id'],'mode':j['mode'],'flow':j['project_flow'],'max_requests':12}),flush=True)
g.analyze(j['id'])
while j['id'] in g.ACTIVE:time.sleep(1)
j=g.get(j['id'])
result={k:j.get(k) for k in ('id','status','stage','project_flow','request_count','budget','error','contract_version','spec_reviews','confirmation')}
result['attempts']=[{k:a.get(k) for k in ('stage','role','status','attempt','metadata','error','failure_kind')} for a in j['attempts']]
result['matrices']=[{k:m.get(k) for k in ('id','passed','gates','contract_hash','environment')} for m in j.get('validation_history',[])+([j['matrix']] if j.get('matrix') else [])]
result['published']=False
(root/f'data/direct-build-verification/real-{j["id"]}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'id':j['id'],'status':j['status'],'requests':j['request_count'],'gates':(j.get('matrix') or {}).get('gates'),'error':j.get('error')},ensure_ascii=False),flush=True)

"""Opt-in bounded real generation from an already confirmed contract; never publishes."""
import json
import os
import sqlite3
import time
from pathlib import Path

assert os.getenv('AGENTLAB_REAL_SMOKE') == '1', 'Explicit real smoke opt-in required'
source='3c0efb715d084149912ed06ecc0f79e8'
root=Path(__file__).resolve().parents[1]
with sqlite3.connect(f'file:{root / "data/app.sqlite3"}?mode=ro',uri=True) as db:
    prior=json.loads(db.execute('SELECT body FROM objects WHERE id=?',(source,)).fetchone()[0])
os.environ['AGENTLAB_DATA']=str(root/'data/repair-protocol-verification/real-isolated')
from backend import storage as s, generation as g, generation_budget as b, agent
from backend.generation_schema import Request
assert agent.mode()=='real', 'Real provider not configured; mock is not real validation'
s.init()
job=g.create(Request.model_validate(prior['request']))
job.update(contract=prior['contract'],contract_version=1,confirmed_version=1,contract_hash=g.digest(prior['contract']),private_fault_requirements=prior['private_fault_requirements'],assessment=prior['assessment'],status='interrupted',checkpoint='build',source_contract_job=source,
           confirmation={'source':'system_function_verification_of_previously_confirmed_contract','not_learning_evidence':True},budget=b.initialize(b.BudgetPolicy(requests=12,output_tokens=64000,input_bytes=450000,seconds=600,validations=5)))
g.put(job)
print(json.dumps({'job':job['id'],'mode':job['mode'],'generation_protocol':job['generation_protocol'],'max_requests':12}),flush=True)
g.launch(job['id'],'build')
while job['id'] in g.ACTIVE:
    time.sleep(1)
result=g.get(job['id'])
summary={k:result.get(k) for k in ('id','status','stage','generation_protocol','request_count','budget','error','contract_version','source_contract_job')}
summary['attempts']=[{k:a.get(k) for k in ('stage','status','attempt','error','metadata','failure_kind')} for a in result['attempts']]
summary['matrix']={k:(result.get('matrix') or {}).get(k) for k in ('id','passed','gates','environment','build_hash','evaluation_hash','fingerprint_hash')}
summary['published']=False
(root/f'data/repair-protocol-verification/real-{result["id"]}.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps({'id':result['id'],'status':result['status'],'requests':result['request_count'],'gates':summary['matrix']['gates'],'error':result.get('error')},ensure_ascii=False),flush=True)

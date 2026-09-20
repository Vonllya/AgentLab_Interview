"""Bounded real evaluation retry of a saved failed job, in an isolated data directory."""
import os,json,sqlite3,shutil,time
from pathlib import Path
assert os.getenv('AGENTLAB_REAL_SMOKE')=='1'
root=Path(__file__).resolve().parents[1]
source_id='d7bf5d8786804d9ebf529a2e319bca90'
with sqlite3.connect(f'file:{root}/data/app.sqlite3?mode=ro',uri=True) as db:
    source=json.loads(db.execute('select body from objects where id=?',(source_id,)).fetchone()[0])
os.environ['AGENTLAB_DATA']=str(root/'data/preflight-verification/real-isolated')
from backend import generation as g, generation_budget as b, storage as s, agent
from backend.generation_schema import Request
assert agent.mode()=='real'
s.init();j=g.create(Request.model_validate(source['request']),direct_build=True)
for k in ('contract','contract_version','contract_hash','confirmed_version','confirmation','private_fault_requirements','assessment','rationale','spec_approval','spec_reviews','installed_bundle','applied_spec_review'):
    if k in source:j[k]=source[k]
j['assets']=source['assets'].copy()
for asset in set(j['assets'].values()):shutil.copytree(root/'data/generation'/source_id/asset,g.root(j)/asset)
last=source['attempts'][-1];folder=g.root(j)/last['asset'];folder.mkdir(exist_ok=True)
(folder/'rejected.json').write_text((root/'data/generation'/source_id/last['asset']/'response.txt').read_text())
j['evaluation_candidate']={'asset':folder.name,'contract_hash':j['contract_hash']}
j['budget']=b.initialize(b.BudgetPolicy(requests=8,output_tokens=40000,input_bytes=300000,seconds=600,validations=3))
j.update(status='interrupted',checkpoint='evaluation',source_probe=source_id);g.put(j)
print(json.dumps({'id':j['id'],'source':source_id,'max_requests':8}),flush=True)
g.launch(j['id'],'evaluation')
while j['id'] in g.ACTIVE:time.sleep(1)
j=g.get(j['id']);out={k:j.get(k) for k in ('id','status','request_count','error','budget','attempts','matrix','validation_history')}
(root/f'data/preflight-verification/real-{j["id"]}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'id':j['id'],'status':j['status'],'calls':j['request_count'],'error':j.get('error'),'gates':(j.get('matrix') or {}).get('gates')},ensure_ascii=False),flush=True)

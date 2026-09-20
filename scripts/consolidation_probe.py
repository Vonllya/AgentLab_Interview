"""One opt-in real generation batch for consolidated roles; isolated, never publishes."""
import os,json,time
from pathlib import Path
assert os.getenv('AGENTLAB_REAL_SMOKE')=='1'
root=Path(__file__).resolve().parents[1]
os.environ['AGENTLAB_DATA']=str(root/'data/consolidation-verification/real-isolated')
from backend import generation as g, storage as s, agent
from backend.generation_schema import Request
assert agent.mode()=='real','Real model configuration required'
s.init()
j=g.create(Request(requirement='Agent 启动时后端未就绪，导致空工具注册',minutes=15,difficulty='偏低'),direct_build=True)
print(json.dumps({'id':j['id'],'role_policy':j['role_policy'],'budget':j['budget']['policy']}),flush=True)
g.analyze(j['id'])
while j['id'] in g.ACTIVE:time.sleep(1)
j=g.get(j['id'])
result={k:j.get(k) for k in ('id','role_policy','status','request_count','budget','error','attempts','matrix','validation_history','contract','private_fault_requirements')}
(root/f'data/consolidation-verification/real-{j["id"]}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'id':j['id'],'status':j['status'],'calls':j['request_count'],'error':j.get('error'),'gates':(j.get('matrix') or {}).get('gates')},ensure_ascii=False),flush=True)

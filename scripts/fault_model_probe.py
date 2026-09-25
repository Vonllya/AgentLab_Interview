"""One opt-in isolated real batch, bounded; never approves or publishes."""
import json
import os
import time
from pathlib import Path

def main():
    if os.getenv('AGENTLAB_REAL_SMOKE')!='1':raise SystemExit('Requires AGENTLAB_REAL_SMOKE=1')
    root=Path(__file__).resolve().parents[1]
    out=root/'data/fault-model-verification';out.mkdir(parents=True,exist_ok=True)
    os.environ['AGENTLAB_DATA']=str(out/'real-isolated')
    from backend import generation as g, storage as s, agent
    from backend.generation_schema import Request
    from backend.generation_budget import initialize, BudgetPolicy
    if agent.mode()!='real':raise SystemExit('Real model configuration unavailable; unverified')
    s.init()
    j=g.create(Request(requirement='Agent 启动时后端未就绪，导致空工具注册',minutes=15,difficulty='偏低'),direct_build=True,handoff=True,fault_model=True)
    j['budget']=initialize(BudgetPolicy(requests=8,output_tokens=40000,seconds=600,validations=3));g.put(j)
    print(json.dumps({'id':j['id'],'protocol':j['fault_model_version'],'budget':j['budget']['policy']}),flush=True)
    g.analyze(j['id'])
    while j['id'] in g.ACTIVE:time.sleep(1)
    j=g.get(j['id'])
    summary={k:j.get(k) for k in ('id','status','error','request_count','budget')}
    summary['attempts']=[{k:a.get(k) for k in ('stage','status','error','metadata','charged_tokens')} for a in j['attempts']]
    summary['gates']=(j.get('matrix') or {}).get('gates')
    summary['matrix_id']=(j.get('matrix') or {}).get('id')
    (out/(j['id']+'.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
